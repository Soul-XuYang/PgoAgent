import asyncio
import selectors
import json
import uuid
from typing import Annotated, List, TypedDict, NotRequired, Literal
from langchain_core.messages import ToolMessage, BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_core.tools import BaseTool
from langgraph.constants import END, START
from langgraph.graph import add_messages, StateGraph
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.types import interrupt
from langgraph_runtime_inmem.store import Store
from langmem.short_term import SummarizationNode
from agent.config import logger
from agent.subAgents.decisionAgent import decision_graph
from agent.config import PRINT_SWITCH, DATABASE_DSN
from agent.tools import *
from agent.mcp_server.mcp_external_server import get_mcp_tools  # 假设这里提供 get_mcp_tools
from agent.tools import BLACK_LIST
from agent.subAgents.planAgent import planner_graph,CAPABILITY_TO_TOOLS
from my_llm import llm
from agent.utils import extract_token_usage,accumulate_usage
# 内存形式
from agent.subAgents.memoryAgent import memory_graph, get_user_memory

# 参数设置-在配置文件已设置
input_limit = 8192
max_tool_output_chars = 500
MAX_TOOL_RESULT_CHARS = 500
latest_chat_size = 16

def sliding_window_add(window: list[BaseMessage], data: BaseMessage, window_length: int = latest_chat_size) -> list[BaseMessage]:
    if len(window) >= window_length:
        window.pop(0)  # 弹出第一个元素
    window.append(data)
    return window
# 主图中 State 定义
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    usages: Annotated[dict[str, int], accumulate_usage]
    context: NotRequired[dict[str]] # 上下文-chat功能
    requires_agent: NotRequired[bool] # 分支

    # 对话记录
    conversation_pairs: NotRequired[list[BaseMessage]] # 目前还是用list存，一是本身长度不长二是内存小一些
    # 计划步骤
    plan_steps: NotRequired[List[str]]
    plan_step_tools: NotRequired[List[str]]
    current_plan_step: NotRequired[int] # 当前步骤
    tool_attempts: NotRequired[int] # 工具尝试次数
    # 防止整体的无限循环
    agent_loop_count: NotRequired[int]
    # 状态机状态
    step_status: NotRequired[Literal["continue", "step_done", "plan_done", "fail"]]



# 不断总结以及裁剪信息
async def summarization_node(
        state: State,
        max_tokens: int = input_limit,
        max_summary_tokens: int = 1024,
        topK: int = 6,
) -> State:
    # 初始化
    state["plan_step_tools"] = []
    state["plan_steps"] = []
    state["current_plan_step"] = 0
    state["usages"] = {}
    state["agent_loop_count"] = 0  # 重置循环计数器
    state["step_status"] = "continue"# 初始化状态
    state["tool_attempts"] = 0  # 初始化RAG尝试次数
    # 确保对话记录存在
    if "conversation_pairs" not in state:
        state["conversation_pairs"] = []
    # 构建base_node节点
    base_node = SummarizationNode(
        token_counter=count_tokens_approximately,
        model=llm,
        max_tokens=max_tokens,
        max_summary_tokens=max_summary_tokens,
        output_messages_key="messages",
    )

    # ★ 确保 context 存在并保存用户最新提问
    ctx = state.setdefault("context", {})
    msgs = state.get("messages", [])
    # 从后向前查找最新的用户提问-必须走的一条路
    for msg in reversed(msgs):
        if isinstance(msg, HumanMessage):
            # 只添加非空的用户消息，避免空消息导致 API 调用失败-易错点
            msg_content = getattr(msg, "content", "") or ""
            if msg_content.strip():
                state["conversation_pairs"] = sliding_window_add(state["conversation_pairs"], msg)
                ctx["current_user_question"] = msg.content
                break
    total_tokens = count_tokens_approximately(state["messages"])

    if total_tokens <= max_tokens*0.6 and len(state["conversation_pairs"]) < latest_chat_size:
        return state

    new_state = await base_node.ainvoke(state)  # 注意这里还是对整体的msg进行总结
    summary_msg = new_state["messages"][0]

    state["context"]["summary"] = summary_msg.content

    tail = state["messages"][-topK:]
    state["messages"] = [summary_msg] + tail  # 总结+裁剪信息

    return state

# 工具结果判断函数
def tool_result_judgement(tool_msg: ToolMessage) -> bool:
    tool_content = (tool_msg.content or "").strip()
    # 无内容失败或者工具执行失败
    if not tool_content :
        return True
    if "工具执行失败" in tool_content or "❌" in tool_content:
        return True
    # RAG 工具特殊判断
    if tool_msg.name == "rag_retrieve":
        try:
            data = json.loads(tool_content)
            # contexts 为空、空列表、空字符串或 count 为 0 都视为失败
            if isinstance(data, dict):
                contexts = data.get("contexts", "")
                count = data.get("count", 0)
                if not contexts or (isinstance(contexts, list) and len(contexts) == 0) or count == 0:
                    return True
                if "未找到" in str(contexts) or "未找到相关内容" in str(contexts) or "知识库中未找到" in str(contexts):
                    return True
        except (json.JSONDecodeError, Exception):
            pass  # 如果不是 JSON，继续下面的通用判断

    # 常见失败/空结果提示
    bad_markers = ["未找到", "无结果", "not found", "empty", "error:", "exception:", "知识库中未找到"]
    cl = tool_content.lower()
    if any(x in cl for x in bad_markers):
        return True

    # 尝试解析 JSON，空 dict/list 视作坏结果
    try:
        data = json.loads(tool_content)
        if isinstance(data, dict) and len(data) == 0:
            return True
        if isinstance(data, list) and len(data) == 0:
            return True
    except json.JSONDecodeError as e:
        logger.error(f"JSON解析错误: {str(e)}")
        return False
    except Exception as e:
        logger.info(f"处理数据时发生错误: {str(e)}")
        return False

    return False

class ToolNode:
    """
    处理大模型返回的 tool_calls-优先调用本地工具。
    - 支持黑名单拦截（仅拦截被禁用工具，其余正常执行）
    - 工具输出自动截断（防止token爆炸）
    - 不再修改计划状态（由agent_node统一管理）
    """
    def __init__(self, tools: list[BaseTool]):         # 将工具列表转换为 {name: tool} 的映射-注册
        self._tool_map = {tool.name: tool for tool in tools}
        self._max_output_chars = int(input_limit / 2 * 4) # 保证单个工具的最大token数

    async def __call__(self, state: State) -> State:
        if not (msgs := state.get("messages")):
            raise ValueError("状态中没有上下文的消息内容")
        latest = msgs[-1] # 注意这里取的是最新的消息
        tool_infos = getattr(latest, "tool_calls", None) or [] # 保险措施
        if not tool_infos:
            # 没有工具调用就不要执行，也不要涨 attempts
            return {
                "messages": [],
                "usages": {},
                "tool_attempts": state.get("tool_attempts", 0),
            }
        # 分离合法和黑名单工具
        banned_tools = []
        allowed_tools = []
        for tool_info in tool_infos:
            if tool_info["name"] in BLACK_LIST:
                banned_tools.append(tool_info)
            else:
                allowed_tools.append(tool_info)
        # 如果有黑名单工具，请求人工审核
        if banned_tools:
            approved = interrupt(
                "当前会话涉及敏感工具："
                f"{', '.join(t['name'] for t in banned_tools)}。\n"
                "请你审核并选择:批准(y)或者拒绝(n)，可以给出对应理由"
            )
            # 处理审核结果
            if isinstance(approved, dict) and "answer" in approved:
                # 这两个遍历都是放在answer里的
                answer = approved["answer"].lower()
                reason = approved.get("answer", "")
                if reason.startswith('no'):
                    reason = reason[2:].strip()
                elif reason.startswith('n'):
                    reason = reason[1:].strip()
                # 拒绝：为黑名单工具生成拒绝消息
                if answer.startswith('n'):
                    tool_messages = []
                    for t in banned_tools:
                        tool_messages.append(ToolMessage(
                            content=f"⚠️ 工具 {t['name']} 被拒绝执行，理由：{reason if reason else '涉及敏感操作'}",
                            tool_call_id=t["id"],
                            name=t["name"]
                        ))

                    # 执行合法工具
                    if allowed_tools:
                        executed_messages = await self._execute_tool_calls(allowed_tools)
                        tool_messages.extend(executed_messages)
                    inc = 1 if allowed_tools else 0 # 如果有合法工具执行，则attempts+1
                    return {
                        "messages": tool_messages,
                        "usages": {},
                        "tool_attempts": state.get("tool_attempts", 0) + inc,
                    }
                else:
                    # 批准：黑名单工具加入允许列表
                    allowed_tools.extend(banned_tools)

        # 执行所有允许的工具
        tool_messages = await self._execute_tool_calls(allowed_tools) if allowed_tools else []
        inc = 1 if allowed_tools else 0 # 保险操作
        return {
            "messages": tool_messages,
            "usages": {},
            "tool_attempts": state.get("tool_attempts", 0) + inc,
        }
    async def _execute_tool_calls(self,tool_calls: list[dict]) -> List[ToolMessage]:

        async def _invoke_tool( tool_call: dict) -> ToolMessage:
            try:
                tool = self._tool_map.get(tool_call["name"])
                if not tool:
                    raise KeyError(f"未找到注册名为 {tool_call['name']} 的工具")
                if hasattr(tool, 'ainvoke'):
                    tool_result = await tool.ainvoke(tool_call["args"])
                else:
                    loop = asyncio.get_running_loop()  # 获取当前事件循环
                    tool_result = await loop.run_in_executor(
                        None,
                        tool.invoke,
                        tool_call["args"],
                    )
                result_str = json.dumps(tool_result, ensure_ascii=False) # 对输出结果进行预处理
                if len(result_str) > self._max_output_chars:
                    truncated = result_str[:self._max_output_chars]
                    result_str = (
                        f"{truncated}\n\n"
                        f"⚠️ [输出已截断，原始长度 {len(result_str)} 字符，"
                        f"已保留前 {self._max_output_chars} 字符]"
                    )
                return ToolMessage(
                    content=result_str,  # 将工具返回的结果转换为字符串
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"])
            except Exception as error:
                return ToolMessage(
                    content=f"❌ 工具执行失败: {str(error)}",
                    name=tool_call.get("name", "unknown"),
                    tool_call_id=tool_call["id"]
                )
        try:
            return await asyncio.gather(*[_invoke_tool(tool_call) for tool_call in tool_calls])
        except Exception as e:
            raise RuntimeError(f"并发执行调用工具失败: {e}") from e

# 依据结果生成计划摘要从而尽量减少token    
def build_smart_plan_summary(
    plan_steps: List[str], 
    tool_results: List[ToolMessage],
) -> str:
    """根据工具结果智能构建计划摘要"""
    if not plan_steps:
        return "无明确计划"
    
    total_steps = len(plan_steps)
    
    # 分析工具结果，判断任务复杂度
    tool_names = {msg.name for msg in tool_results}
    has_multiple_tools = len(tool_names) > 1
    has_rag = "rag_retrieve" in tool_names
    
    if total_steps <= 3:
        # 简单任务：全部传递
        return " → ".join(plan_steps)
    
    # 复杂任务：智能摘要
    first_step = plan_steps[0]  # 保留目标
    last_steps = plan_steps[-2:]  # 保留当前状态
    
    if has_rag and has_multiple_tools:
        # RAG + 多工具：可能是复杂查询任务，需要更多上下文
        if total_steps <= 5:
            return " → ".join(plan_steps)
        else:
            # 保留首步、中间关键步、最后2步
            mid_idx = total_steps // 2
            return f"{first_step} → ... → {plan_steps[mid_idx]} → ... → {' → '.join(last_steps)}"
    else:
        # 简单任务：只保留首尾
        if total_steps <= 6:
            return f"{first_step} → ... → {' → '.join(last_steps)}"
        else:
            return f"{first_step} → [共{total_steps}步] → {' → '.join(last_steps)}"



async def answer_thinking_node(state: State) -> State:
    msgs = state.get("messages", [])
    origin_plan_steps = state.get("plan_steps", [])
    ctx = state.get("context", {})
    fallback_question = ctx.get("current_user_question", "用户问题缺失")
    current_step_index = state.get("current_plan_step",0)
    # 收集所有 ToolMessage（工具执行结果）
    K=3
    tool_results = []
    has_rag_result = False
    # 从后往前查找，收集本次任务周期内的所有消息
    for msg in reversed(msgs):
        if isinstance(msg, ToolMessage):
            c = msg.content or ""
            if msg.name == "rag_retrieve":
                has_rag_result = True # 提示词标记rag工具的使用
            if len(c) > MAX_TOOL_RESULT_CHARS:
                c = c[:MAX_TOOL_RESULT_CHARS] + f"\n...[已截断，原{len(msg.content)}字符]"

            tool_results.insert(0, ToolMessage(content=c, name=msg.name, tool_call_id=msg.tool_call_id))
            if len(tool_results) >= K:
                break
        if isinstance(msg, HumanMessage) and msg.content == fallback_question:
            break
    # 这里对步骤进行裁减
    if origin_plan_steps:
        plan_summary = build_smart_plan_summary(
            origin_plan_steps, 
            tool_results,
    )
    else:
        plan_summary = "无明确计划"
    # 生成最后的只要
    execution_log = f"工具调用结果摘要（已自动精简）：\n"
    if tool_results:
        for i, tool_msg in enumerate(tool_results, 1):
            execution_log += f"[{tool_msg.name}] {tool_msg.content}\n"
    else:
        execution_log += "\n⚠️ 警告：未找到工具执行结果！\n"

    base_requirements = (
        "- 基于真实数据回答，不编造\n"
        "- 如有具体数据（文件名、时间等），请完整列出\n"
        "- 语言简洁清晰"
    )

    if has_rag_result:
        base_requirements = (
            "- 请仅用rag查询知识库的内容,禁止编造、推测、补充任何未在知识库中出现的信息\n"
            "- 如果知识库中未找到相关信息，明确告知用户\n"
        )
    # 依据rag的使用进行替换
    question = (
        f"问题: {fallback_question}\n"
        f"计划: {plan_summary}\n"  # 只传递关键步骤
        f"工具结果:\n{execution_log}\n"
        f"要求: {base_requirements}"
    )
    msgs_for_summary = [SystemMessage(content=question)]
    # 强制裁剪到安全范围
    trimmed = trim_messages(
        msgs_for_summary,
        strategy="last",
        token_counter=count_tokens_approximately,
        max_tokens=input_limit,  # 最大的输入限制
        start_on="system",
        end_on="system",
    )
    if not trimmed:
        trimmed = [SystemMessage(content=question[-6000:])]
    response = await llm.ainvoke(trimmed)
    usage_delta = extract_token_usage(response)  # 获取此次对话的token使用清空
    if PRINT_SWITCH:
        print(f"[agent_node-总结]的Token增量: {usage_delta}")
    conversation_pairs = state.get("conversation_pairs", [])
    response_pairs = sliding_window_add(conversation_pairs, response)
    return {
        "messages": [response],
        "usages": usage_delta,
        "conversation_pairs": response_pairs,
    }


def collect_recent_tool_pairs(messages: List[BaseMessage],
                user_question: str,
                max_pairs: int = 1) -> List[BaseMessage]:
    """
    一次性遍历收集最近的 AIMessage-ToolMessage 配对(截止在本次对话前)
    返回格式：[AIMessage, ToolMessage1, ToolMessage2, ...]
    """
    result = []
    collected_pairs = 0
    i = len(messages) - 1

    # 首先找找到用户最新问题的位置
    question_boundary = -1
    for idx in range(len(messages) - 1, -1, -1):
        if isinstance(messages[idx], HumanMessage) and messages[idx].content == user_question:
            question_boundary = idx
            break

    # 从后往前，一次性收集配对
    while i >= question_boundary and collected_pairs < max_pairs:
        msg = messages[i]

        # 找到 AIMessage with tool_calls
        if isinstance(msg, AIMessage) and getattr(msg, 'tool_calls', None):
            tool_call_ids = {tc['id'] for tc in msg.tool_calls}
            tool_messages = []

            # 向后查找对应的 ToolMessage（只查一次）
            j = i + 1
            while j < len(messages) and len(tool_call_ids) > 0:
                if isinstance(messages[j], ToolMessage):
                    if messages[j].tool_call_id in tool_call_ids:
                        # 按 token 截断，而非字符
                        tool_msg = truncate_tool_message_by_tokens(
                            messages[j],
                            max_tokens=500
                        )
                        tool_messages.append(tool_msg)
                        tool_call_ids.discard(messages[j].tool_call_id)
                elif isinstance(messages[j], AIMessage):
                    break  # 遇到下一个 AI 响应，停止
                j += 1

            # 只有当所有 tool_calls 都有响应时才添加
            if len(tool_call_ids) == 0:
                result.insert(0, msg)  # AIMessage
                result[1:1] = tool_messages  # ToolMessages
                collected_pairs += 1

        i -= 1

    return result


def truncate_tool_message_by_tokens(tool_msg: ToolMessage, max_tokens: int = 500,scale:float = 0.95) -> ToolMessage:
    """根据 token 数量截断，而非字符数"""
    content = tool_msg.content or "" # 获取其内容
    current_tokens = count_tokens_approximately([SystemMessage(content=content)]) # 计算当前的token数量

    if current_tokens <= max_tokens:
        return tool_msg

    # 二分查找合适的截断点（简化版：按比例截断）
    ratio = max_tokens / current_tokens # 获得比例
    truncated_length = int(len(content) * ratio * scale)  # 留5%余量，剩余95%作为喂给模型的长度

    truncated_content = content[:truncated_length] + f"\n\n⚠️ [输出已截断，保留约{max_tokens} tokens]" # 截断末尾的长度

    return ToolMessage(
        content=truncated_content,
        name=tool_msg.name,
        tool_call_id=tool_msg.tool_call_id
    )
async def create_graph(store:Store,config: dict,max_tool_attempts:int=2,checkpointer=None):
    mcp_tools= await get_mcp_tools()
    all_tools=mcp_tools + LOCAL_TOOLS
    # 对话节点
    async def agent_node(state: State) -> State:
        msgs = state.get("messages", [])
        # 获取规划结果
        plan_steps = state.get("plan_steps", [])
        plan_step_tools = state.get("plan_step_tools", [])
        current_plan_step = state.get("current_plan_step", 0) # 获取当前的step
        if not plan_steps or current_plan_step >= len(plan_steps): # 跳出当前循环-计划结束保护
            return {
                "messages": [],
                "usages": {},
                "step_status": "plan_done",
                "agent_loop_count": state.get("agent_loop_count", 0) + 1, # 默认+1
            }

        # 获取当前步骤的 capability 和 规划步骤信息
        current_capability = plan_step_tools[current_plan_step] if plan_step_tools else "none" # 没有设置为none
        # 根据 capability 筛选相关工具
        current_step = plan_steps[current_plan_step] if plan_steps else "直接处理用户请求"
        relevant_tool_names = CAPABILITY_TO_TOOLS.get(current_capability, [])

        if relevant_tool_names:
            # 根据工具名称从 all_tools 中筛选出实际的工具对象-里面包含基本的工具和RAG工具
            relevant_tools = [t for t in LOCAL_TOOLS if t.name in relevant_tool_names]
        else:
            relevant_tools = []  # none 或者未知 capability，不绑定工具
        if "external_mcp" in current_capability and mcp_tools: # 绑定MCP
            relevant_tools.extend(mcp_tools)
        # 创建系统提示
        ctx = state.get("context", {})
        user_question = ctx.get("current_user_question", "")
        system_content = f"问题: {user_question}\n当前步骤: {current_step}\n"
        if current_capability == "rag_retrieve":
            system_content += (
                "1,必须调用 rag_retrieve 完成本步骤，不得跳过。\n"
                "2.若返回为空/不相关：先 rag_rewrite_query，再 rag_retrieve，最多重试 2 次。\n"
                "3.得到检索结果后直接回答，禁止臆测。"
            )
        elif current_capability in {"get_time", "calculate"}:
            system_content += "直接调用工具获取结果，无需额外说明。"
        elif relevant_tools:
            system_content += "需要使用工具完成当前步骤。"
            system_content += "⚠️ 重要提示：每个工具只需调用一次，获得结果后立即停止，不要重复调用。"
        else:
            system_content += "\n无需工具，请直接回答。"
        msgs_for_llm = [SystemMessage(content=system_content)]
        if len(msgs) >= 2:
            temp_history = collect_recent_tool_pairs(msgs, user_question, max_pairs=1) # 收集当前的临时信息
            msgs_for_llm.extend(temp_history)
        # 这个是对整体消息的裁剪
        total_tokens = count_tokens_approximately(msgs_for_llm)
        # 对每次工具的执行进行裁剪
        if total_tokens > input_limit:
            trimmed = trim_messages(
                msgs_for_llm,
                strategy="last",
                token_counter=count_tokens_approximately,
                max_tokens=input_limit,
                start_on="human",
                end_on=("human", "ai"),
            )
            msgs_for_llm = trimmed
        tool_attempts = state.get("tool_attempts", 0)
        allow_use_tool = bool(relevant_tools) and (tool_attempts < max_tool_attempts)
        override = None
        if msgs and isinstance(msgs[-1], ToolMessage):
            judge_bad = tool_result_judgement(msgs[-1])
            if judge_bad and allow_use_tool:
                # RAG 工具的特殊重试提示
                if msgs[-1].name == "rag_retrieve":
                    override = (
                        f"\n⚠️ 检测到RAG检索结果为空或不相关，将进行重试。"
                        f"当前工具尝试次数: {tool_attempts}/{max_tool_attempts}。\n"
                        "1. 请先调用rag_rewrite_query重写query（提供失败原因：检索结果为空或不相关）\n"
                        "2. 使用重写后的refined_query再次调用rag_retrieve（可调整参数）\n"
                        "如果仍失败，请说明知识库中未找到相关信息。"
                    )
                else:
                    override = (
                        f"\n⚠️ 检测到上一轮工具结果可能无效，将进行重试。"
                        f"当前工具尝试次数: {tool_attempts}/{max_tool_attempts}。"
                        "要求：本轮最多再调用一次工具，并尽量调整参数以获得不同结果。"
                    )
                allow_use_tool = True
        if tool_attempts >= max_tool_attempts and relevant_tools:
            override = (
                f"\n⚠️ 本步骤工具调用已达上限({tool_attempts}/{max_tool_attempts})，禁止再调用工具。"
                "请基于已有信息完成当前步骤，必要时说明无法补齐的数据。"
            )
            allow_use_tool = False
        if override:
            msgs_for_llm.insert(0, SystemMessage(content=override))
        if allow_use_tool:
            llm_run = llm.bind_tools(relevant_tools)  #  只绑定相关工具-减轻工具调用负担
        else:
            llm_run = llm
        # 选用工具
        response: BaseMessage = await llm_run.ainvoke(msgs_for_llm) # 存有的是工具调用信息
        usage_delta = extract_token_usage(response)
        if PRINT_SWITCH:
            logger.info(system_content)
            logger.info(f"当前工具的执行结果{response.content}")
            logger.info(f"[agent_node-执行] 步骤: {current_step}, 工具: {current_capability}, Token: {usage_delta}")
        tool_calls = getattr(response, "tool_calls", None) or []
        if (not allow_use_tool) and tool_calls:
            # 关键：清空 response 本身的 tool_calls，避免 agent_choice 再次 use_tools
            response.tool_calls = []
            tool_calls = []
        # 依据是否执行工具更新状态机
        if tool_calls:
            next_step = current_plan_step
            next_status = "continue"
            next_tool_attempts = state.get("tool_attempts", 0)  # 不重置
        else:
            next_step = current_plan_step + 1
            next_status = "plan_done" if next_step >= len(plan_steps) else "step_done"
            next_tool_attempts = 0  # ✅ 推进 step 必须重置 这个易错

        return {
            "messages": [response],
            "usages": usage_delta,
            "current_plan_step": next_step,
            "step_status": next_status,
            "tool_attempts": next_tool_attempts,
            "agent_loop_count": state.get("agent_loop_count", 0) + 1,
        }

    # 对话聊天节点
    async def chat_node(state: State) -> State:
        msgs = state.get("messages", [])
        ctx = state.setdefault("context", {})
        summary = ctx.get("summary")
        user_profile = ctx.get("user_profile", {})
        if not user_profile:
            configurable = getattr(config, "configurable", {}) or config.get("configurable", {})
            user_id = configurable.get("user_id", "anonymous")
            user_profile = await get_user_memory(store, user_id)
        injected_msgs = []
        injected_msgs.append(SystemMessage(content="你现在是一个名为 PgoAgent 的智能助手，由 PgoAgent 项目开发。你目前正在和用户进行对话，请根据用户的问题和上下文，给出合适的回答。"))
        # 注入用户画像，让回答更贴合用户，但不要直接给用户看
        if user_profile and user_profile != "空":
            profile_summary = str(user_profile)[:300] + "..." if len(str(user_profile)) > 300 else str(user_profile)
            injected_msgs.append(
                SystemMessage(
                    content=(

                        f"用户画像（参考）：{profile_summary}\n"
                        "提示：个性化回答，不要复述画像。"
                    )
                )
            )
        if summary: # 只有对话节点才会使用summary
            injected_msgs.append(
                SystemMessage(
                    content=f"以下内容是之前对话的压缩摘要，仅供模型理解：\n{summary}"
                )
            )
        injected_msgs.append(SystemMessage(content=f"以下为用户最近的{latest_chat_size}次对话:\n"))
        conversation_pairs = state.get("conversation_pairs", [])
        # 过滤掉空的 user 消息，避免 API 调用失败
        filtered_pairs = []
        for msg in conversation_pairs:
            if isinstance(msg, HumanMessage):
                msg_content = getattr(msg, "content", "") or ""
                if msg_content.strip():
                    filtered_pairs.append(msg)
            else:
                filtered_pairs.append(msg)
        # 再接上真实对话消息
        msgs_for_llm = injected_msgs + filtered_pairs
        # 对话裁剪
        total_tokens = count_tokens_approximately(msgs_for_llm)
        if total_tokens > input_limit:
            trimmed = trim_messages(
                msgs_for_llm,
                strategy="last",
                token_counter=count_tokens_approximately,
                max_tokens=input_limit,
                start_on=("human", "system"),
                end_on=("human", "system"),
            )

            # trim 后可能为空，必须兜底！
            if not trimmed:
                # 至少保留用户最近一句话
                if msgs:
                    trimmed = [msgs[-1]]
                else:
                    trimmed = [SystemMessage(content="历史已裁剪，请继续对话。")]

            msgs_for_llm = trimmed
        response: BaseMessage = await llm.ainvoke(msgs_for_llm)
        usage_delta = extract_token_usage(response)
        if PRINT_SWITCH:
            print(f"[chat_node]Token增量{usage_delta}")
        if getattr(response, "id", None) is None:
            response.id = str(uuid.uuid4())
        response_pairs = sliding_window_add(conversation_pairs, response)
        return {
            "messages": [response],  # 把模型回答追加到原始消息后
            "usages": usage_delta,
            "conversation_pairs": response_pairs,
        }
    #========正式开始构建图========
    # 构建图-一定要按顺序添加
    memory_node = memory_graph(store)
    builder = StateGraph(State)
    planner_node = planner_graph()
    decision_node = decision_graph()
    builder.add_node("summarization_node", summarization_node)
    builder.add_node("decision_node", decision_node)
    builder.add_node("planner_node", planner_node)
    builder.add_node("chat_node", chat_node)
    builder.add_node("agent_node", agent_node)
    builder.add_node("answer-thinking",answer_thinking_node)
    builder.add_node("long_memory_node", memory_node)
    # 自定义工具节点，支持敏感工具中断确认
    tools_node = ToolNode(all_tools)
    builder.add_node("tools_node", tools_node)

    # 构建边
    builder.add_edge(START, "summarization_node")
    builder.add_edge("summarization_node", "decision_node")
    builder.add_conditional_edges(
        "decision_node",
        decision_choice,
        {"plan": "planner_node","chat": "chat_node"},
    )
    builder.add_edge("planner_node", "agent_node")
    builder.add_edge("chat_node", "long_memory_node")
    builder.add_conditional_edges(
        "agent_node",
        agent_choice,
        {"use_tools": "tools_node", "self-think":"agent_node","think-answer": "answer-thinking"},
    )
    builder.add_edge("tools_node", "agent_node")
    builder.add_edge("answer-thinking", "long_memory_node")
    builder.add_edge("long_memory_node", END)
    # ===== 编译 =====
    if checkpointer is None: # 如果不传入默认使用内存保存
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()

    graph = builder.compile(checkpointer=checkpointer)
    return graph
# ===== 路由即条件函数-langgraph里推荐路由函数只做判断别的都不做 =====
def agent_choice(state: State):
    plan_steps = state.get("plan_steps", [])
    current_step_index = state.get("current_plan_step", 0)
    # 获取循环计数器
    loop_count = state.get("agent_loop_count", 0)
    # 获取显式状态
    step_status = state.get("step_status", "continue")

    # ——优先检查显式状态机——
    if step_status == "plan_done":
        # 所有计划步骤完成，进入总结
        if PRINT_SWITCH:
            logger.info(f"[agent_choice] 状态机：plan_done → 进入总结阶段")
        return "think-answer"

    if step_status == "fail":
        # 执行失败，强制结束
        if PRINT_SWITCH:
            logger.info(f"[agent_choice] 状态机：fail → 强制结束")
        return "think-answer"

    # 安全保护：如果循环超过10次，强制结束
    if loop_count >= 10:
        if PRINT_SWITCH:
            print(f"[错误] agent_node 循环超过10次，强制结束！")
            print(f"[错误] 当前步骤索引: {current_step_index}/{len(plan_steps)}")
            print(f"[错误] 剩余步骤: {plan_steps[current_step_index:] if current_step_index < len(plan_steps) else []}")
        return "think-answer"

    # ——检查索引边界——
    if not plan_steps or current_step_index >= len(plan_steps):
        if PRINT_SWITCH:
            logger.warning(f"[agent_choice] 步骤索引超出范围 → 进入总结")
        return "think-answer"

    # ——检查是否有工具调用（最高优先级）——
    msgs = state["messages"]
    latest_msg = msgs[-1]
    tool_calls = getattr(latest_msg, "tool_calls", []) or []
    if tool_calls:
        # 有工具调用 → 必须先执行工具
        if PRINT_SWITCH:
            print(f"[agent_choice] 状态机：{step_status} + 有工具调用 → 执行工具")
        return "use_tools"

    # ——没有工具调用，根据状态决定——
    if step_status == "step_done":
        # 当前步骤完成，继续执行下一步
        if PRINT_SWITCH:
            print(f"[agent_choice] 状态机：step_done → 继续执行步骤 [{current_step_index + 1}/{len(plan_steps)}]")
        return "self-think"

    if step_status == "continue":
        # 当前步骤未完成，继续思考当前步骤
        if PRINT_SWITCH:
            print(f"[agent_choice] 状态机：continue → 继续当前步骤 [{current_step_index + 1}/{len(plan_steps)}]")
        return "self-think"

    # 默认继续执行
    return "self-think"

def decision_choice(state: State):
    """决策后的路由：如果已经有答案则跳过agent，否则进入agent"""
    requires_agent = state.get("requires_agent", False)
    if requires_agent:
        return "plan"
    else:
        return "chat"
# ==========================

# 实际上是调用api画图的
async def draw(graph):
    try:
        png_bytes = graph.get_graph().draw_mermaid_png(
            max_retries=5,  # 增加重试次数
            retry_delay=2.0  # 增加重试延迟
        )
        with open("workflow.png", "wb") as f:
            f.write(png_bytes)
    except Exception as e:
        print(f"生成流程图失败: {e}")
        print("继续执行其他任务...")
# 输入限制-实际上也是裁剪的强制修剪范围

if __name__ == "__main__":
    async def test():
        # 1. 使用async with管理数据库连接
        async with AsyncPostgresStore.from_conn_string(DATABASE_DSN) as store:
            await store.setup()
            print("Postgresql Store 数据初始化成功!")

            config = {"configurable": {"thread_id": "002", "user_id": "user_003"}}
            # 2. 构建Graph
            agent = await create_graph(store,config)
            print("Graph 构建完成")
            await draw(agent)

            # 3. 测试数据
            init_state = {
                "messages": [HumanMessage(content="你好，请列出当前的目录有哪些文件呢?")],
                "context": {},
            }
            # 4. 执行Graph
            result = await agent.ainvoke(init_state, config=config)
            final_msg = result["messages"][-1]
            print("模型回答：", final_msg.content)
            print(100*'=')
            test_state1 = {
            "messages": [
                # HumanMessage(content="作为大模型，请问你手头有没有mcp协议的外部工具呢?帮我规划下从电子科大清水河校区到"
                #                      "四川大学望江校区的路线(坐地铁和步行)？如果我现在出发，那我后续到达川大的时间预计是多少呢?")
                HumanMessage(content="请问你可以帮我查询下知识库里:慢羊羊给懒羊羊四个的重要道具是什么呢?")
                ]
            }
            result = await agent.ainvoke(test_state1, config=config)
            final_msg2 = result["messages"][-1]
            print("模型回答：", final_msg2.content)
            test_state2 = {
                "messages": [

                    HumanMessage(content="请问你可以帮我查询下知识库里:暗太狼是什么？")
                ]

            }
            print(100 * '=')
            result = await agent.ainvoke(test_state2, config=config)
            final_msg3 = result["messages"][-1]
            print("模型回答：", final_msg3.content)
            final_token = result.get("usages")["total"]
            print("总的token用量:", final_token)
    asyncio.run(test(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))





