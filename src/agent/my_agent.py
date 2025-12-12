import asyncio
from langchain_core.messages import HumanMessage, ToolMessage, AIMessage
from langgraph.types import Command

from graph import create_graph
from utils import run_time


async def _execute_graph(user_input: str, config: dict, graph):
    human_input = {"messages": [HumanMessage(content=user_input)]}

    async for chunk in graph.astream(human_input, config=config, stream_mode="updates"):
        if "__interrupt__" in chunk:
            interrupt_obj = chunk["__interrupt__"]
            # 优先使用ToolNode抛出的专属中断提示语，而非默认值
            question = interrupt_obj[0]["value"]["question"] if (interrupt_obj and interrupt_obj[0]["value"].get("question")) else "当前会话涉及敏感工具，请审核并选择:批准(y)或者拒绝(n)，可以给出对应理由"

            print(f"AI: {question}")
            user_answer = input("你的回答: ").strip()

            cmd = Command(resume={"answer": user_answer})
            try:
                result = await graph.ainvoke(cmd, config)
                print("\n=== 中断恢复后结果 ===")
                # 区分ToolMessage的类型（拒绝/工具执行结果）
                last_msg = result["messages"][-1]
                if isinstance(last_msg, ToolMessage):
                    if "用户拒绝执行工具" in last_msg.content:
                        print(f"【拒绝工具】{last_msg.content}")
                    else:
                        print(f"【工具执行结果】工具名: {last_msg.name}, 结果: {last_msg.content}")
                else:
                    print(last_msg.content)
                return result
            except RuntimeError as e:
                # 捕获ToolNode抛出的工具执行异常
                print(f"\n=== 工具执行失败 ===")
                print(f"错误信息: {e}")
                raise
        if "messages" in chunk:
            print("\n=== AI 回复 ===")
            last_msg = chunk["messages"][-1]
            # 打印ToolMessage的完整信息
            if isinstance(last_msg, ToolMessage):
                print(f"工具名: {last_msg.name}, 内容: {last_msg.content}")
            else:
                print(last_msg.content)


async def run_graph():
    graph = await create_graph()

    config = {
        "configurable": {
            "thread_id": "cli-thread-01"
        }
    }

    print("Graph 启动成功，开始对话...")
    while True:
        user_input = input("用户> \n").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("退出对话")
            break

        await _execute_graph(user_input, config, graph)
    print()
    # 使用本地工具看看当前时间是什么?


@run_time
async def main():
    # 1. 构建Graph
    agent = await create_graph()
    print("Graph 启动成功，开始对话...")
    final_token = 0
    user_config = {"configurable": {"thread_id": "user_001"}}
    while True:
        user_input = input("用户> \n").strip()
        if user_input.lower() in {"exit", "quit"}:
            print("退出对话")
            break
        chat_state = {
            "messages": [HumanMessage(content=user_input)],
        }
        chat_before_token = final_token
        result = await agent.ainvoke(chat_state, config=user_config)
        # 检查是否有中断
        if "__interrupt__" in result:  # 返回的对象是否有中断属性
            interrupt_info = result["__interrupt__"][0]  # 这里取列表的第一个信息即可
            print(interrupt_info.value)
            user_interrupt = input("用户> \n").strip()
            result = await agent.ainvoke(
                Command(resume={"answer": user_interrupt}),
                config=user_config
            )
        final_msg = result["messages"][-1]
        final_token = result.get("usages")["total"]
        print("模型回答：", final_msg.content)
        print("本次LLM token用量：", final_token-chat_before_token)
    print(f"总的token用量:{final_token}")

if __name__ == "__main__":
    asyncio.run(main())

