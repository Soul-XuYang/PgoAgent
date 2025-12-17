import asyncio
import selectors
import json
import uuid
from typing import Annotated, List, TypedDict, NotRequired
from langchain_core.messages import ToolMessage, BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.messages.utils import count_tokens_approximately, trim_messages
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.constants import END, START
from langgraph.graph import add_messages, StateGraph
from langgraph.store.postgres import AsyncPostgresStore
from langgraph.types import interrupt
from langgraph_runtime_inmem.store import Store
from langmem.short_term import SummarizationNode
from pydantic import BaseModel, Field

from agent.subAgents.decisionAgent import decision_graph
from config import PRINT_SWITCH,MODEL_MAX_INPUT, DATABASE_URL
from agent.tools import *
from agent.mcp_server.mcp_external_server import get_mcp_tools  # 假设这里提供 get_mcp_tools
from agent.tools import BLACK_LIST
from agent.subAgents.planAgent import planner_graph,CAPABILITY_TO_TOOLS
from my_llm import llm
from utils import extract_token_usage,accumulate_usage
# 内存形式
from langgraph.checkpoint.memory import MemorySaver
from agent.subAgents.memoryAgent import memory_graph, get_user_memory

# 参数设置
model_name = getattr(llm, "model_name", None) or getattr(llm, "model", None)
input_limit = MODEL_MAX_INPUT.get(model_name, 8192)
# 主图中 State 定义处
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    usages: Annotated[dict[str, int], accumulate_usage]
    context: NotRequired[dict[str]] # 上下文，这里更多和对话相连-注重于chat功能
    requires_agent: NotRequired[bool]
    requires_rag: NotRequired[bool]
    # 工具-设置
    plan_steps: NotRequired[List[str]]
    plan_step_tools: NotRequired[List[str]]
    origin_plan_steps:NotRequired[List[str]]
    # 防止无限循环
    agent_loop_count: NotRequired[int]


# 不断总结以及裁剪信息
async def summarization_node(
        state: State,
        max_tokens: int = 4096,
        max_summary_tokens: int = 1024,
        topK: int = 6,
) -> State:
    # 初始化
    state["requires_agent"] = False
    state["requires_rag"] = False
    state["plan_step_tools"] = []
    state["plan_steps"] = []
    state["usages"] = {}
    state["agent_loop_count"] = 0  # 重置循环计数器
    # --------------------------------------------
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
    # 从后向前查找最新的用户提问
    for msg in reversed(msgs):
        if isinstance(msg, HumanMessage):
            ctx["current_user_question"] = msg.content
            break
    total_tokens = count_tokens_approximately(state["messages"])
    if total_tokens <= max_tokens or len(state["messages"]) < 10:
        return state

    new_state = await base_node.ainvoke(state)  # 注意这里还是
    summary_msg = new_state["messages"][0]

    state["context"]["summary"] = summary_msg.content

    tail = state["messages"][-topK:]
    state["messages"] = [summary_msg] + tail  # 总结+裁剪信息
    return state

class ToolNode:
    """
    处理大模型返回的 tool_calls-优先调用本地工具。
    - 支持黑名单拦截（仅拦截被禁用工具，其余正常执行）
    - 工具输出自动截断（防止token爆炸）
    - 不再修改计划状态（由agent_node统一管理）
    """
    def __init__(self, tools: list[BaseTool]):         # 将工具列表转换为 {name: tool} 的映射-注册
        self._tool_map = {tool.name: tool for tool in tools}
        self._max_output_chars = input_limit /2 * 4 # 保证单个工具的最大token数

    async def __call__(self, state: State) -> State:
        approved = {}
        if not (msgs := state.get("messages")):
            raise ValueError("状态中没有上下文的消息内容")
        latest = msgs[-1] # 注意这里取的是最新的消息
        tool_infos = latest.tool_calls
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

                    return {
                        "messages": tool_messages,
                        "usages": {},
                    }
                else:
                    # 批准：黑名单工具加入允许列表
                    allowed_tools.extend(banned_tools)

        # 执行所有允许的工具（包括批准后的黑名单工具）
        tool_messages = await self._execute_tool_calls(allowed_tools)
        return {
            "messages": tool_messages,
            "usages": {},
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


async def answer_thinking_node(state: State) -> State:
    msgs = state.get("messages", [])
    origin_plan_steps = state.get("origin_plan_steps", [])
    ctx = state.get("context", {})
    fallback_question = ctx.get("current_user_question", "用户问题缺失")

    # 收集所有 ToolMessage（工具执行结果）
    tool_results = []
    ai_messages = []

    # 从后往前查找，收集本次任务周期内的所有消息
    for msg in reversed(msgs):
        if isinstance(msg, HumanMessage):
            # 遇到用户问题就停止（说明到达本次任务的起点）
            if msg.content == fallback_question:
                break
        elif isinstance(msg, ToolMessage):
            tool_results.insert(0, msg)  # 保持顺序
        elif isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
            ai_messages.insert(0, msg)

    # 构建执行记录描述
    execution_log = "执行步骤的详细记录：\n"
    if tool_results:
        for i, tool_msg in enumerate(tool_results, 1):
            execution_log += f"\n步骤 {i}：工具 {tool_msg.name}\n"
            execution_log += f"返回结果：{tool_msg.content}\n"
    else:
        execution_log += "\n⚠️ 警告：未找到工具执行结果！\n"

    question = (
        f"用户提问: {fallback_question}\n"
        f"解决用户问题的计划步骤: {origin_plan_steps}\n\n"
        f"{execution_log}\n"
        "请根据上述工具返回的实际数据，详细、准确地回答用户的问题。\n"
        "要求:\n"
        "- 提取工具返回的真实数据（JSON 格式的文件列表、路径信息等）\n"
        "- 不要编造任何数据\n"
        "- 如果工具返回了具体的文件名和目录，请完整列出"
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
    msgs_for_summary = trimmed
    response = await llm.ainvoke(msgs_for_summary)
    usage_delta = extract_token_usage(response)  # 获取此次对话的token使用清空
    if PRINT_SWITCH:
        print(f"[agent_node-总结]的Token增量: {usage_delta}")
    return {
        "messages": msgs + [response],
        "usages": usage_delta
    }

async def create_graph(store:Store,config: RunnableConfig):
    mcp_tools= await get_mcp_tools()
    all_tools=mcp_tools + LOCAL_TOOLS
    # 对话节点
    async def agent_node(state: State) -> State:
        msgs = state.get("messages", [])
        # 获取规划结果
        plan_steps = state.get("plan_steps", [])
        plan_step_tools = state.get("plan_step_tools", [])
        # 获取当前步骤的 capability - 获取当前的工具能力
        current_capability = plan_step_tools[0] if plan_step_tools else "none"
        current_step = plan_steps[0] if plan_steps else "直接处理用户请求"
        # 根据 capability 筛选相关工具
        relevant_tool_names = CAPABILITY_TO_TOOLS.get(current_capability, [])

        if relevant_tool_names:
            # 根据工具名称从 all_tools 中筛选出实际的工具对象
            relevant_tools = [t for t in LOCAL_TOOLS if t.name in relevant_tool_names]
        else:
            relevant_tools = []  # none 或者未知 capability，不绑定工具
        if "external_mcp" in current_capability and mcp_tools:
            relevant_tools.extend(mcp_tools)

        # 创建系统提示
        ctx = state.get("context", {})
        user_question = ctx.get("current_user_question", "")

        system_content = f"用户问题: {user_question}\n"
        system_content += f"当前任务步骤: {current_step}\n"
        if relevant_tools:
            system_content += f"可用工具: {', '.join([t.name for t in relevant_tools])}\n"
            system_content += "\n请使用上述工具完成当前步骤。"
        else:
            system_content += "\n无需使用工具，请直接回答。"

        # 构建消息历史 - 保持消息对象的结构-langgraph的格式需求-上下文使用
        msgs_for_llm = [SystemMessage(content=system_content)]
        if len(msgs) >= 2:
            # 从后往前查找最近的 AIMessage 和 ToolMessage 配对
            temp_history = []
            i = len(msgs) - 1
            collected_pairs = 0
            max_pairs = 3  # 最多保留 3 对历史
            while i >= 0 and collected_pairs < max_pairs:
                msg = msgs[i]
                # 找到 AIMessage with tool_calls
                if isinstance(msg, AIMessage) and hasattr(msg, 'tool_calls') and msg.tool_calls:
                    # 收集这个 AIMessage 的所有 tool_call_ids
                    tool_call_ids = {tc['id'] for tc in msg.tool_calls}
                    tool_messages = []

                    # 向后查找对应的 ToolMessage
                    for j in range(i + 1, len(msgs)):
                        if isinstance(msgs[j], ToolMessage):
                            if msgs[j].tool_call_id in tool_call_ids:
                                tool_messages.append(msgs[j])
                                tool_call_ids.discard(msgs[j].tool_call_id)
                        elif isinstance(msgs[j], AIMessage):
                            # 遇到下一个 AIMessage 停止
                            break

                    # 只有当所有 tool_calls 都有响应时才添加
                    if len(tool_call_ids) == 0:
                        temp_history.insert(0, msg)
                        temp_history[1:1] = tool_messages  # 在 AIMessage 后插入 ToolMessages
                        collected_pairs += 1
                i -= 1
            # 添加到消息列表
            msgs_for_llm.extend(temp_history)
        total_tokens = count_tokens_approximately(msgs_for_llm)
        # 对每次工具的执行进行裁剪
        if total_tokens > input_limit:
            trimmed = trim_messages(
                msgs_for_llm,
                strategy="last",
                token_counter=count_tokens_approximately,
                max_tokens=input_limit,
                start_on=("human", "system"),
                end_on=("human", "system"),
            )
            msgs_for_llm = trimmed
        if relevant_tools:
            llm_run = llm.bind_tools(relevant_tools)  #  只绑定相关工具-减轻工具调用负担
        else:
            llm_run = llm
        # 选用工具
        response: BaseMessage = await llm_run.ainvoke(msgs_for_llm)
        usage_delta = extract_token_usage(response)
        if PRINT_SWITCH:
            print(system_content)
            print(f"当前工具的执行结果{response.content}")
            print(f"[agent_node-执行] 步骤: {current_step}, 工具: {current_capability}, Token: {usage_delta}")

        # 不管什么情况都要消耗步骤
        next_steps = plan_steps[1:]  # 该 step 已经“落地成文本结果”，消耗它
        next_tools = plan_step_tools[1:]
        return {
            "messages":[response],
            "usages": usage_delta,
            "plan_steps": next_steps,
            "plan_step_tools": next_tools,
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
        # 注入用户画像，让回答更贴合用户，但不要直接给用户看
        if user_profile:
            injected_msgs.append(
                SystemMessage(
                    content=(
                        "以下是当前用户的长期画像信息，用于帮助你更个性化地回答。"
                        "不要直接把这些条目原样复述给用户：\n"
                        f"{user_profile}"
                    )
                )
            )
        if summary: # 只有对话节点才会使用summary
            injected_msgs.append(
                SystemMessage(
                    content=f"以下内容是之前对话的压缩摘要，仅供模型理解：\n{summary}"
                )
            )
        # 再接上真实对话消息
        msgs_for_llm = injected_msgs + msgs
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

        return {
            "messages": [response],  # 把模型回答追加到原始消息后
            "usages": usage_delta,
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

    memory = MemorySaver()
    graph = builder.compile(checkpointer=memory)
    return graph
# ===== 路由即条件函数-langgraph里推荐路由函数只做判断别的都不做 =====
def agent_choice(state: State):
    plan_steps = state.get("plan_steps", [])
    plan_step_tools = state.get("plan_step_tools", [])
    # 获取循环计数器
    loop_count = state.get("agent_loop_count", 0)

    # 安全保护：如果循环超过10次，强制结束
    if loop_count >= 10:
        if PRINT_SWITCH:
            print(f"[错误] agent_node 循环超过10次，强制结束！")
            print(f"[错误] 剩余步骤: {plan_steps}")
            print(f"[错误] 剩余工具: {plan_step_tools}")
        return "think-answer"

    # 先检查是否有工具调用，再检查计划完成
    msgs = state["messages"]
    latest_msg = msgs[-1] # 最新的消息有没有工具调用
    tool_calls = getattr(latest_msg, "tool_calls", []) or []

    # 有工具调用 → 必须先执行工具
    if tool_calls:
        return "use_tools"

    # 一定是先判断工具调用，再判断计划完成
    if not plan_steps or not plan_step_tools:
        return "think-answer"

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
        async with AsyncPostgresStore.from_conn_string(DATABASE_URL) as store:
            await store.setup()
            print("PostgreSQL Store 数据初始化成功!")
            config = {"configurable": {"thread_id": "002", "user_id": "user_003"}}
            # 2. 构建Graph
            agent = await create_graph(store,config)
            print("Graph 构建完成")
            await draw(agent)

            # 3. 测试数据
            init_state = {
                "messages": [HumanMessage(content="你好，请列出当前的目录有哪些文件呢注意目录和文件名都要列出来?")],
                "context": {},
            }
            # 4. 执行Graph
            result = await agent.ainvoke(init_state, config=config)
            final_msg = result["messages"][-1]
            print(result)
            print("模型回答：", final_msg.content)
            print(120*'=')
            test_state = {
            "messages": [
                HumanMessage(content="作为大模型，请问你手头有没有mcp协议的外部工具呢?帮我规划下从电子科大清水河校区到"
                                     "四川大学望江校区的路线(坐地铁和步行)？并且预计我的方式到达川大的时间是本地时间的几点几分呢？")
                ]
            }
            result = await agent.ainvoke(test_state, config=config)
            final_msg2 = result["messages"][-1]
            print("模型回答：", final_msg2.content)
            print(result)
            final_token = result.get("usages")["total"]
            print("总的token用量:", final_token)
    asyncio.run(test(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))








