from typing import List, TypedDict, Annotated, Any, NotRequired, Dict, Literal
from langchain_core.messages import HumanMessage, SystemMessage, BaseMessage
from langgraph.constants import START, END
from langgraph.graph import add_messages, StateGraph
from pydantic import BaseModel, Field
from agent.my_llm import llm
from agent.state_utils import get_latest_HumanMessage
from utils import extract_token_usage
from config.basic_config import PRINT_SWITCH

class PlannerState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    usages: dict[str, int]
    context: NotRequired[dict[str, Any]]
    requires_rag :NotRequired[bool]
    # 工具补充
    plan_steps: NotRequired[List[str]]
    plan_step_tools: NotRequired[List[str]]
    origin_plan_steps: NotRequired[List[str]]


class PlanStep(BaseModel):
    """
    单个步骤：
    - description：自然语言描述这一步要做什么
    - capability：这一步需要的大致能力类型（后续由 Agent 选择具体工具）
    """
    description: str = Field(
        ...,
        description="该步骤要做的事情，用自然语言简述。",
    )
    capability: Literal[
        "none",
        "search",
        "rag",
        "file_read",
        "file_write",
        "list_dir",
        "get_time",
        "code_exec",
        "web_search",
        "external_mcp",
    ] = Field(
        "none",
        description="该步骤需要的大致能力类型，后续大模型根据能力类别映射具体工具。",
    )

# 这是一个双层套住的嵌套结构
class Planner(BaseModel):
    """
    LLM 规划输出：
    - plan_steps：步骤列表，每个步骤包含 description + capability
    - requires_rag：整体任务是否需要 RAG
    """
    plan_steps: List[PlanStep] = Field(
        description="为当前用户请求规划出的执行步骤，从上到下按顺序执行。"
    )
    requires_rag: bool = Field(
        default=False,
        description="当前任务是否需要从知识库 / 向量库中检索信息（RAG）。",
    )
PLANNER_PROMPT = """
你是任务规划助手，根据用户请求输出执行步骤计划。

输出结构（自动解析）：
- plan_steps：步骤列表，每个包含：
  - description：该步骤要做什么（自然语言）
  - capability：能力类型，选择其一：
    • none：纯思考/文本生成-无需工具
    • list_dir:列出文件及遍历文件目录
    • search：本地文件搜索
    • rag：知识库检索
    • file_read/file_write/create_file/delete_file：文件操作
    • get_time：时间查询
    • code_exec：代码执行
    • external_mcp：外部工具，如果现有工具无法完成则使用mcp工具，如网络搜索、路线规划、网络爬取等等

- requires_rag：任意步骤需要rag时设为true

要求：
1. 仅根据用户最后一次消息规划
2. 步骤清晰原子化（如：列目录→读文件→整理→回答）
3. 不提具体工具名，仅用capability表示能力
4. 仅输出结构化数据
"""
CAPABILITY_TO_TOOLS = {
    "list_dir": ["list_dir", "current_workdir"],
    "file_read": ["read_file", "read_json", "search_in_file"],
    "file_write": ["write_file", "write_json", "create_file", "append_file"],
    "get_time": ["get_time"],
    "search": ["search_in_file"],
    "rag": ["rag_search"],
    "code_exec": ["code_exec"],
    "external_mcp": [],  # MCP 工具动态加载
    "none": []
}

async def planner_node(state: PlannerState) -> PlannerState:
    msgs = state.get("messages", [])
    if not msgs:
        return state

    latest_msg = get_latest_HumanMessage(state["messages"])
    if not latest_msg:
        return state

    user_input = getattr(latest_msg, "content", str(latest_msg))
    planner_llm = llm.with_structured_output(Planner, include_raw=True)
    response: Dict[str, Any] = {}
    parsed: Planner | None = None
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = await planner_llm.ainvoke(
                [
                    SystemMessage(content=PLANNER_PROMPT),
                    HumanMessage(content=user_input),
                ]
            )
            parsed = response["parsed"]

            # 验证通过则跳出
            if validate_plan(parsed.plan_steps):
                break
        except Exception as e:
            print(f"错误，本地大模型LLM调用失败: {e}")
            if attempt == max_retries - 1:
                # 最后一次失败，返回默认plan
                return {
                    "messages": [],
                    "usages": {"input": 0, "output": 0, "total": 0},
                    "plan_steps": ["直接回答用户问题"],
                    "plan_step_tools": ["none"],
                    "requires_rag": False
                }
    # 如果所有重试都失败，使用最后一次的结果-作者失败
    if parsed is None or not validate_plan(parsed.plan_steps):
        return {
            "messages": [],
            "usages": {"input": 0, "output": 0, "total": 0},
            "plan_steps": ["分析用户问题并回答"],
            "plan_step_tools": ["none"],
            "requires_rag": False
        }

    raw = response["raw"]
    usage_delta = extract_token_usage(raw)
    # 类型转换
    plan_steps_text = [s.description for s in parsed.plan_steps]
    plan_step_tools = [s.capability for s in parsed.plan_steps]
    if PRINT_SWITCH:
        print(f"[planner_node]Token增量:{usage_delta}")

    return {
        "messages": [],
        "usages": usage_delta,
        "plan_steps":plan_steps_text ,
        "plan_step_tools": plan_step_tools,
        "origin_plan_steps":plan_step_tools,
        "requires_rag": parsed.requires_rag
    }
def validate_plan(steps: List[PlanStep]) -> bool:
    if not steps:
        return False
    if len(steps) > 20:
        return False
    if any(len(s.description.strip()) < 3 for s in steps):  # 使用 description 属性
        return False
    return True

def planner_graph():
    builder = StateGraph(PlannerState)
    builder.add_node("planner_node", planner_node)
    builder.add_edge(START, "planner_node")
    builder.add_edge("planner_node", END)
    graph = builder.compile()
    return graph


if __name__ == "__main__":
    import asyncio


    async def test_planner():
        # 测试用例1: 简单问答任务
        print("\n【测试1】简单问答任务（无需工具）")
        test_state_1 = {
            "messages": [HumanMessage(content="什么是机器学习？")],
            "usages": {"input": 0, "output": 0, "total": 0}
        }
        result_1 = await planner_node(test_state_1)
        print(f"✅ 步骤数: {len(result_1['plan_steps'])}")
        print(f"   步骤: {result_1['plan_steps']}")
        print(f"   工具: {result_1['plan_step_tools']}")
        print(f"   需要RAG: {result_1['requires_rag']}")
        print(f"   Token消耗: {result_1['usages']}")
        # 测试用例2: 文件操作任务
        print("\n【测试2】文件操作任务")
        test_state_2 = {
            "messages": [
                HumanMessage(content="帮我读取项目根目录下的README.md文件，总结主要内容")
            ],
            "usages": {"input": 0, "output": 0, "total": 0}
        }
        result_2 = await planner_node(test_state_2)
        print(f"✅ 步骤数: {len(result_2['plan_steps'])}")
        print(f"   步骤: {result_2['plan_steps']}")
        print(f"   工具: {result_2['plan_step_tools']}")
        print(f"   需要RAG: {result_2['requires_rag']}")
        print(f"   Token消耗: {result_2['usages']}")

        total_tokens = sum([
            result_1['usages']['total'],
            result_2['usages']['total'],
        ])
        print(f"总测试用例: 2个")
        print(f"总Token消耗: {total_tokens}")
        print(f"平均每次消耗: {total_tokens // 2} tokens") # 舍弃余数


    async def test_plan_graph():
        """测试完整的graph执行"""
        print("\n" + "=" * 60)
        print("🧪 测试 PlanGraph 完整流程")
        print("=" * 60)

        graph = planner_graph()

        test_input = {
            "messages": [
                HumanMessage(content="帮我分析src/agent目录下有哪些Python文件，并统计对应文件的总行数")
            ]
        }

        print("🚀 执行Graph...")
        result = await graph.ainvoke(test_input)

        print(f"\n✅ Graph执行完成！")
        print(f"   规划步骤: {result.get('plan_steps')}")
        print(f"   需要工具: {result.get('plan_step_tools')}")
        print(f"   需要RAG: {result.get('requires_rag')}")
        print(f"   Token消耗: {result.get('usages')}")
    # 运行所有测试
    async def run_all_tests():
        await test_planner()
        await test_plan_graph()
    # -------------------------------------------------------
    print("\n" + "=" * 30)
    print("🧪 开始测试 PlanAgent")
    print("=" * 30)
    # 执行测试
    asyncio.run(run_all_tests())
