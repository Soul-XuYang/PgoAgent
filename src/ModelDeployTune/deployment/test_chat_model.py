import asyncio
import time
import sys
from pathlib import Path

from openai import AsyncOpenAI  # 导入异步客户端

# 确保可以导入同目录下的 deployment_config
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from config import ConfigLoader

# 加载配置
config_loader = ConfigLoader()

# Chat 模型部署配置
chat_config = config_loader.get_chat_config()

# 测试配置（[test] + [test.chat]）
test_root_config = config_loader.get_test_config()
test_chat_config = test_root_config.get("chat", {})

# 模型名称：优先使用 served_model_name，其次 model_name
MODEL_NAME = chat_config.get(
    "served_model_name",
    chat_config.get("model_name", "Qwen3-8B"),
)

# base_url 与 api_key 从 [test] 或全局中读取
BASE_URL = test_root_config.get(
    "base_url",
    f"http://{chat_config.get('host', '0.0.0.0')}:{chat_config.get('port', 8000)}/v1",
)
API_KEY = test_root_config.get(
    "api_key",
    chat_config.get("api_key", config_loader.get_global_config().get("api_key", "")),
)

# 聊天测试参数
TEMPERATURE = float(test_chat_config.get("temperature", 0.5))
MAX_TOKENS = int(test_chat_config.get("max_tokens", 4096))
STREAM = bool(test_chat_config.get("stream", True))

# 初始化异步客户端-执行本地的电脑服务
client = AsyncOpenAI(
    base_url=BASE_URL,  # vLLM的本地API地址
    api_key=API_KEY,
)


async def chat_loop():
    """异步循环聊天函数，支持流式输出"""
    print(f"欢迎使用{MODEL_NAME}模型，输入 'exit' 或 'quit' 退出对话！\n")

    while True:
        user_input = input("用户：").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("退出本程序!")
            break

        # 3. 空输入处理
        if not user_input:
            print("模型：请输入有效内容！")
            continue

        try:
            # 根据配置决定是否流式
            if STREAM:
                stream = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "user", "content": user_input}
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=True,  # 开启流式输出
                )

                # 逐段接收并打印流式响应
                print("模型：", end="", flush=True)
                response_content = ""
                start_time = time.time()
                async for chunk in stream:
                    # 提取当前chunk的内容（排除空内容）
                    chunk_content = chunk.choices[0].delta.content or ""
                    response_content += chunk_content
                    # 实时打印（flush=True 强制刷新缓冲区）
                    print(chunk_content, end="", flush=True)
                print(f"\n该对话耗时：{time.time() - start_time:.2f}s")
                print("\n" + "-" * 50 + "\n")  # 分隔线
            else:
                # 非流式一次性返回
                print("模型：", end="", flush=True)
                start_time = time.time()
                resp = await client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "user", "content": user_input}
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=MAX_TOKENS,
                    stream=False,
                )
                content = resp.choices[0].message.content
                print(content)
                print(f"\n该对话耗时：{time.time() - start_time:.2f}s")
                print("\n" + "-" * 50 + "\n")  # 分隔线

        except Exception as e:
            print(f"模型出错！错误信息：{e}\n")

if __name__ == "__main__":
    # 运行异步函数
    asyncio.run(chat_loop())
