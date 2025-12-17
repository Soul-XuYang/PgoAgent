from typing import TypedDict, Annotated, NotRequired, List
from langchain_core.messages import SystemMessage, HumanMessage, BaseMessage
from langgraph.constants import START, END
from langgraph.graph import add_messages, StateGraph
from pydantic import BaseModel, Field
from config.basic_config import PRINT_SWITCH
from agent.my_llm import llm
from utils import extract_token_usage

DECISION_SYSTEM_PROMPT = """你是一个只负责“是否需要调用工具”的路由器。
请严格按照下面规则设置 requires_agent：

- 在用户明确提出：查询时间/日期、搜索互联网/知识库、读取/操作文件、访问外部系统或数据库、需要最新数据、使用RAG获取知识库内容时，才把 requires_agent 设为 true。
- 如果用户提出需要使用MCP工具时,把 requires_agent 设为 true。
- 其它情况一律将 requires_agent 设为 false。
- 如果不确定，默认 requires_agent = false。
"""
class DecisionAgentState(TypedDict):
    """
    记忆智能体的 State：
    - messages：对话消息（你会把这一轮对话或一段历史传进来）
    - context：可以把生成好的 user_memory 塞进去，方便外层使用
    """
    messages: Annotated[List[BaseMessage], add_messages]
    usages: dict[str, int]
    requires_agent: NotRequired[bool]
# 长期存储，并且智能体管理数据库这种操作用异步

# 决策几点
class DecisionOutput(BaseModel):
    requires_agent: bool = Field(
        description="是否需要调用外部工具（如时间 / 搜索 / 文件 / 知识库等）。"
            "只有在用户明确提出需要查询外部信息、访问文件、数据库等时，才设为 true。"
            "不确定或者其它情况设置为 false。"
    )
TRIGGER_KEYWORDS = [
    "时间", "日期", "现在几点", "今天", "明天", "昨天",
    "搜索", "查询", "检索", "互联网", "网上",
    "文件", "读取", "写入", "保存", "打开",
    "知识库", "RAG", "向量库", "文档",
    "数据库", "MySQL", "PostgreSQL",
    "MCP工具", "MCP", "工具",
    "最新", "实时", "当前"
]


async def decision_node(state: DecisionAgentState) -> DecisionAgentState:
    msgs = state["messages"]
    latest = msgs[-1]
    user_input = latest.content if hasattr(latest, "content") else str(latest)

    keyword_matched = any(keyword in user_input for keyword in TRIGGER_KEYWORDS)

    if keyword_matched:
        if PRINT_SWITCH:
            print("决策器输出：True (关键词匹配)")
        return {
            "messages": [],
            "usages": {},
            "requires_agent": True
        }

    decision_llm = llm.with_structured_output(DecisionOutput, include_raw=True)
    inputs = [
        SystemMessage(content=DECISION_SYSTEM_PROMPT),
        HumanMessage(content=user_input),
    ]
    response = await decision_llm.ainvoke(inputs)
    parsed_data = response["parsed"]
    raw_message = response["raw"]
    usage_delta = extract_token_usage(raw_message)

    if PRINT_SWITCH:
        print("决策器输出：", parsed_data.requires_agent)
        print(f"[decision_node] Token增量: {usage_delta}")
    return {
        "messages": [],
        "usages": usage_delta,
        "requires_agent": parsed_data.requires_agent
    }
def decision_graph():
    builder = StateGraph(DecisionAgentState)
    builder.add_node("decision_node", decision_node)
    builder.add_edge(START, "decision_node")
    builder.add_edge("decision_node", END)
    graph = builder.compile()
    return graph