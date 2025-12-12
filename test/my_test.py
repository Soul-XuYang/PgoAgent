from langgraph_sdk import get_client
import asyncio
import sys


async def main():
    try:
        client = get_client(url="http://localhost:2024")

        # 直接尝试流式连接，如果服务器未运行会抛出异常
        async for chunk in client.runs.stream(
                None,
                "agent",
                input={
                    "messages": [{
                        "role": "user",
                        "content": "what is Langgraph?",
                    }],
                },
        ):
            print(f"Receiving new event of type {chunk.event_type} with data {chunk.data}")

    except Exception as e:
        print(f"Error: {str(e)}", file=sys.stderr)
if __name__ == "__main__":
    asyncio.run(main())
