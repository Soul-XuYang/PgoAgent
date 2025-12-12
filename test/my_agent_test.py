from typing import TypedDict, Annotated, Any, List, Union
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage, trim_messages
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages.utils import count_tokens_approximately
from langmem.short_term import SummarizationNode
from langgraph.graph.message import add_messages
from agent.my_llm import llm,MODEL_MAX_INPUT
from agent.tools import LOCAL_TOOLS
from agent.database import db_url, check_checkpoint_exist
from langchain.agents import create_agent
import uuid
# -------- State --------
class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages] # 消息列表
    context: Annotated[dict[str, Any], "上下文的总结信息"] # 每次更新的上下文总结信息

def create_message(content: str, message_type: str = "human",message_id: int =None) -> Union[HumanMessage, AIMessage]:
    message_id = str(uuid.uuid4())
    if message_type == "human":
        return HumanMessage(id=message_id, content=content)
    elif message_type == "ai":
        return AIMessage(id=message_id, content=content)
    else:
        raise ValueError(f"Unknown message type: {message_type}")

# -------- Summarize Node --------
def summarization_node(state: State, max_tokens=2048, max_summary_tokens=1024, topK: int = 6) -> State:
    base_node = SummarizationNode(
        token_counter=count_tokens_approximately,
        model=llm,
        max_tokens=max_tokens,
        max_summary_tokens=max_summary_tokens,
        output_messages_key="messages"
    )

    total_tokens = count_tokens_approximately(state["messages"])
    if total_tokens <= max_tokens:
        return state

    new_state = base_node.invoke(state)
    summary_msg = new_state["messages"][0]

    state["context"]["summary"] = summary_msg.content

    tail = new_state["messages"][-topK:]
    state["messages"] = [summary_msg] + tail   # 保留摘要 + 最近topK条
    return state

# -------- Agent Node --------
def agent_node(state: State) -> State:
    max_input_tokens = input_limit
    msgs = state["messages"]
    summary = state["context"].get("summary")
    if summary:
        injected = SystemMessage(content=f"对话摘要：{summary}")
        msgs = [injected] + msgs
    if count_tokens_approximately(msgs) > max_input_tokens:
        msgs = trim_messages(
            msgs,
            startegy="last",
            token_countet=count_tokens_approximately,
            max_input_tokens=max_input_tokens,
            start_on = "human",
            end_on = ("human","tool")
        )
    response = agent.invoke({"messages": msgs})# 补充id
    last_msg: BaseMessage = response["messages"][-1]

    if getattr(last_msg, "id", None) is None:
        last_msg.id = str(uuid.uuid4())

    state["messages"] = state["messages"] + [last_msg]
    return state

# -------- Graph整体的流程图--------
def create_graph(checkpointer=None):
    workflow = StateGraph(State) # 初始化
    workflow.add_node("summarize", summarization_node)
    workflow.add_node("agent", agent_node)
    workflow.set_entry_point("summarize") # 设置入口点

    workflow.add_edge("summarize", "agent")
    workflow.add_edge("agent", END)
    return workflow.compile(checkpointer=checkpointer) if checkpointer else workflow.compile()


agent = create_agent(llm, tools=LOCAL_TOOLS)  # 只创建一次
config = {"configurable": {"thread_id": "1"}}
flag = False
display = True
model_name = getattr(llm, "model_name", None) or getattr(llm, "model", None)
input_limit = MODEL_MAX_INPUT.get(model_name, 2048)



with PostgresSaver.from_conn_string(db_url) as checkpointer:
    if not check_checkpoint_exist(db_url):
        checkpointer.setup()
    checkpointer.setup()
    graph = create_graph(checkpointer=checkpointer) # 构建图
    if display:
        png_bytes = graph.get_graph().draw_mermaid_png()
        with open("workflow.png", "wb") as f:
            f.write(png_bytes)

        print("saved to workflow.png")
    if flag:
        r3 = graph.invoke({"messages": [create_message("请问我的名字是什么?")], "context": {}}, config=config)
        print(r3["messages"][-1].content)

    r1 = graph.invoke({"messages": [create_message("你是一名机器人，你会利用各种工具回答问题，你的名字是小A")], "context": {}}, config=config)
    print(r1["messages"][-1].content)

    r2 = graph.invoke({"messages": [create_message("我是用户，我的名字叫做大A,请告诉我现在几点了?")], "context": {}}, config=config)
    print(r2["messages"][-1].content)


