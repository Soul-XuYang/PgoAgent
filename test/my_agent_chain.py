from pprint import pprint
from langchain_core.messages import HumanMessage
from langchain.agents import create_agent
from agent.my_llm import llm
from agent.tools import LOCAL_TOOLS
from utils.base_utils import *
from agent.tools.file_tool import *

agent = create_agent(
    llm,
    tools= LOCAL_TOOLS,
)
# 异步执行的agent对应的工具也是异步-Langchain的测试
print("请输入问题，回车发送;输入 exit 或者 quit 退出。")
total_token = 0
while True:
    q = input("User> ").strip()
    if not q:
        continue
    if q.lower() in {"exit", "quit","q","e"}: # 集合类型
        break

    inputs = {"messages": [HumanMessage(content=q)]}

    # stream_mode="values"：逐步打印 state（含 tool_calls）
    for event in agent.stream(inputs, stream_mode="values"):
        start=time.time()
        msgs = event["messages"]
        last = msgs[-1]
        print("\n--- step ---")
        pprint(last)
        total_token += extract_token_usage(last)
        print(f"耗时: {format_time(time.time() - start)}")

    print("=== done ===")

print("-----程序结束-----")
print(f"总token数: {total_token}")
