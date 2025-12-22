import re
from typing import Tuple, List, Annotated, NotRequired, Any, TypedDict
from pydantic import Field
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langgraph.constants import START, END
from langgraph.graph import StateGraph, add_messages
from langgraph.store.postgres import  AsyncPostgresStore
from pydantic import BaseModel
from config import PRINT_SWITCH,DATABASE_DSN
from .state_utils import get_latest_HumanMessage, has_obvious_profile_info
from agent.my_llm import llm
from utils import extract_token_usage

key = "profile"  # 你可以改名，比如 "user_memory"
# 用户的画像 - 这个类就获得了数据验证、类型转换和序列化等强大功能。
class MemoryState(BaseModel):
    memory: str = Field(description="使用中文项目符号列表整理的用户画像信息，只包含用户明确表述的客观事实")
# 中文版提示词
CREATE_MEMORY_PROMPT = """你正在为单个用户整理一份长期用户画像，用来在后续对话中个性化回复。

当前已保存的用户信息：
{memory}

请严格按照下面的要求更新用户信息：
1. 仔细阅读下面给出的最新聊天记录（包括用户和助手的发言）
2. 只提取"由用户明确说出的"关于 TA 自己的各种客观事实信息，例如：
   - 基本情况（职业、角色、地区、行业、使用场景等）
   - 长期、稳定的偏好（例如：经常使用的语言、喜欢/不喜欢的风格）
   - 明确的长期目标（例如：准备考什么证、长期学习什么）
3. 将这些新信息与"当前已保存的用户信息"进行合并，去掉重复内容
4. 用中文的项目符号列表（每行以"- "开头）输出完整的用户信息
5. 如果新信息与旧信息冲突，以"最新聊天记录中的说法"为准进行覆盖
6. 不要生成主观评价或性格分析，只记录用户亲口说的事实
7. 不要编造、不要猜测，没说过的内容一律不要写入

如果本轮对话中没有任何新的用户信息可以补充或更新，
请原样返回当前已保存的用户信息，不要做任何改动。

最新聊天记录：
{messages}

请直接输出更新后的用户画像信息，使用项目符号列表格式："""

STORE_NAMESPACE_ROOT = "user_memory"

class MemoryAgentState(TypedDict):
    """
    记忆智能体的 State：
    - messages：对话消息（你会把这一轮对话或一段历史传进来）
    - context：可以把生成好的 user_memory 塞进去，方便外层使用
    """
    messages: Annotated[List[BaseMessage], add_messages]
    usages: dict[str, int]
    context: NotRequired[dict[str, Any]]
    update_profile: NotRequired[bool]
# 长期存储，并且智能体管理数据库这种操作用异步
async def init_store() -> AsyncPostgresStore:
    """初始化存储"""
    try:
        # 直接使用 from_conn_string 创建实例
        store = await AsyncPostgresStore.from_conn_string(DATABASE_DSN)
        await store.setup()
        return store
    except Exception as e:
        print(f"初始化存储失败: {e}")
        raise


def _namespace_for_user(user_id: str) -> Tuple[str, ...]:
    """
    AsyncPostgresStore 的 namespace 必须是 tuple[str, ...]。
    这里统一封装一下，后续如果想改层级结构更方便。
    """
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", user_id):
        raise ValueError(f"用户ID格式非法：{user_id}（仅允许字母/数字/下划线/短横线，长度1-64）")
    return STORE_NAMESPACE_ROOT, user_id


async def get_user_memory(store: AsyncPostgresStore,user_id: str,default_text: str = "空",) -> str:
    """
    从 AsyncPostgresStore 中读取单个用户的长期记忆。
    返回已经格式化好的文本（通常是中文 bullet list）。
    """
    namespace = _namespace_for_user(user_id)
    try:
        item = await store.aget(namespace, key)  # 读取用户记忆 aget专门异步获取用户数据
        if item is None:
            return default_text

        value = item.value or {}
        memory = value.get("memory", "") # 一般这种命名空间都是存到value里的
    except Exception as e:
        print(f"获取用户{user_id}数据失败: {e}")
        raise
    return memory or default_text


async def update_user_memory_with_messages(store: AsyncPostgresStore, user_id: str, query: List[BaseMessage]) -> tuple[str, dict[str, int]]:
    """
    使用当前对话消息列表 + 旧的记忆，生成新的用户画像，并写回 AsyncPostgresStore。
    返回最新 memory 文本。
    """
    try:
        existing_memory = await get_user_memory(store, user_id)  # 获取
        print(f"Debug - 现有记忆: {existing_memory}")  # 调试信息-后续要删除

        # 将消息列表转换为字符串
        messages_str = "\n".join([f"{msg.__class__.__name__}: {msg.content}" for msg in query])

        # 系统提问信息
        system_msg = SystemMessage(
            content=CREATE_MEMORY_PROMPT.format(
                memory=existing_memory,
                messages=messages_str
            )
        )
        # 使用普通调用而不是结构化输出
        response = await llm.ainvoke([system_msg])
        usage_delta = extract_token_usage(response)
        new_memory = response.content.strip()
        # 写回 Store
        namespace = _namespace_for_user(user_id)
        await store.aput(namespace, key, {"memory": new_memory})  # 放入空间对应的数据

        return new_memory,usage_delta  # 对应的记忆
    except Exception as e:
        print(f"更新{user_id}数据到数据库里失败: {e}")
        raise



async def delete_user_memory(store: AsyncPostgresStore, user_id: str) -> bool:
    try:
        namespace = _namespace_for_user(user_id)
        # 删除指定用户的记忆数据
        await store.adelete(namespace, key)
        print(f"删除用户{user_id}的画像数据成功!")
        return True
    except Exception as e:
        print(f"删除用户记忆失败: {e}")
        return False
async def check_profile_node(state: MemoryAgentState) -> MemoryAgentState:
    """
    检测节点：判断是否有明显的用户画像信息，返回路由目标
    返回值："memory_node" 或 "end"
    """
    latest_msg = get_latest_HumanMessage(state["messages"])
    has_info = has_obvious_profile_info([latest_msg]) if latest_msg else False
    if has_info:
        state["update_profile"] = True
    else:
        state["update_profile"] = False
    # 关键修复：不要返回完整的 state，只返回必要的字段和空的 usages
    return {
        "messages": [],
        "usages": {}, # 空的 usages
        "update_profile": state["update_profile"] # 返回更新简历状态
    }
def get_recent_communications(messages: List[BaseMessage], limit: int = 6) -> List[BaseMessage]:
    """
    返回最近的若干条对话消息（HumanMessage 或 AIMessage），默认 6 条，按时间从旧到新。
    """
    if not messages or limit <= 0:
        return []
    selected = []
    for msg in reversed(messages):
        if isinstance(msg, (HumanMessage, AIMessage)):
            selected.append(msg) # 直接添加到列表
            if len(selected) >= limit:
                break
    return list(reversed(selected)) # 反转列表按照时间顺序来做

def memory_choice(state: MemoryAgentState):
    if state["update_profile"]:
        return "memory_node"
    else:
        return END
def memory_graph(store: AsyncPostgresStore | None = None):
    """
    构建一个“纯记忆智能体图”。
    使用方式（示例）：
    1. 外部先 init_store() 拿到 store
    2. 调用 create_memory_graph(store) 得到 graph
    3. 每次对话结束后，传入这轮 messages + user_id，调用 graph.ainvoke(...)
    4. graph 会：
    - 读取旧记忆
    - 基于 messages 更新记忆并写回
    - 在 state["context"]["user_memory"] 中放最新的画像文本
    """
    if store is None:
        # 如果你想让这个函数自动初始化 store，也可以改成 async，
        # 这里保持同步接口，方便你和主图合并时管理依赖。
        raise ValueError("需要初始化数据库并传入已初始化的 AsyncPostgresStore 实例")

    async def memory_node(state: MemoryAgentState, config: RunnableConfig) -> MemoryAgentState:
        """
        核心节点：更新并写入用户记忆。
        user_id 从 config.configurable.user_id 中获取。
        """
        configurable = getattr(config, "configurable", {}) or config.get("configurable", {}) # 考虑两种情况
        user_id = configurable.get("user_id", "anonymous")
        # 确保 context 存在
        ctx = state.setdefault("context", {}) # 获取上下问
        latest_msgs = get_recent_communications(state["messages"])
        if not latest_msgs:  # 修正：判断列表是否为空
            # 没有需要更新的消息，返回空的 usages
            return {
                "messages": [],
                "usages": {"input": 0, "output": 0, "total": 0},
                "context": state.get("context", {})
            }
        # 使用当前的 messages 更新用户画像
        latest_memory,usages_delta = await update_user_memory_with_messages(
            store=store,
            user_id=user_id,
            query=latest_msgs, # 获取当前的总消息
        )
        if PRINT_SWITCH:
            print(f"[memory-node]Token增量:{usages_delta}")
        ctx["user_profile"] = latest_memory # 保存对应的画像
        state["usages"] =usages_delta
        return {
            "messages": [],
            "usages": usages_delta,  # 只返回增量
            "context": ctx
        }

    # 构建图：非常简单，只有一个节点
    builder = StateGraph(MemoryAgentState)
    builder.add_node("check_profile_node", check_profile_node)
    builder.add_node("memory_node", memory_node)
    builder.add_edge(START, "check_profile_node")
    builder.add_conditional_edges(
        source="check_profile_node",
        path=memory_choice,
        path_map={"memory_node": "memory_node", END: END}
    )
    builder.add_edge("memory_node", END)

    graph = builder.compile()
    return graph
if __name__ == "__main__":
    import asyncio
    import selectors

    async def _test():
        # 1. 用 async with 打开 store
        async with AsyncPostgresStore.from_conn_string(DATABASE_DSN) as store:
            await store.setup()

            # 2. 构建记忆智能体图
            memory_graph_test = memory_graph(store)

            # 3. 构造一段"对话历史"
            msgs: List[BaseMessage] = [
                HumanMessage(content="你好，我是前端工程师，目前在上海工作，平时喜欢用中文交流。"),
            ]

            init_state: MemoryAgentState = {
                "messages": msgs,
                "usages": {},
            }

            config = {
                "configurable": {
                    "user_id": "test_001",
                }
            }

            # 4. 调用记忆图
            result = await memory_graph_test.ainvoke(init_state, config=config)
            print(result.get("usages")["total"])
            print("最新用户画像：")
            out = await get_user_memory(store, "test_001")
            print(out)


    async def _print():
        async with AsyncPostgresStore.from_conn_string(DATABASE_DSN) as store:
            await store.setup()
            await delete_user_memory(store, "teste_001")
            print("最新用户画像：")
            out = await get_user_memory(store, "user_001")
            print(out)


    # 使用 SelectorEventLoop 替代默认的 ProactorEventLoop
    # asyncio.run(_test(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))
    asyncio.run(_print(), loop_factory=lambda: asyncio.SelectorEventLoop(selectors.SelectSelector()))


