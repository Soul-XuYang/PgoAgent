import asyncio
import time
import sys
from pathlib import Path

from openai import AsyncOpenAI

# -------------------------- 配置项（来自 deployment_config.toml） --------------------------

# 确保可以导入同目录下的 deployment_config
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from config import ConfigLoader

config_loader = ConfigLoader()

# 嵌入模型部署配置
embedding_config = config_loader.get_embedding_config()

# 测试配置（[test] + [test.embedding]）
test_root_config = config_loader.get_test_config()
test_embedding_config = test_root_config.get("embedding", {})

# 模型名称：优先使用 served_model_name，其次 model_name
MODEL_NAME = embedding_config.get(
    "served_model_name",
    embedding_config.get("model_name", "BAAI-bge-m3"),
)

# base_url 与 api_key 从 [test] 或全局中读取
BASE_URL = test_root_config.get(
    "base_url",
    f"http://{embedding_config.get('host', '0.0.0.0')}:{embedding_config.get('port', 8000)}/v1",
)
API_KEY = test_root_config.get(
    "api_key",
    embedding_config.get("api_key", config_loader.get_global_config().get("api_key", "")),
)

# 文本列表与测试参数
TEST_TEXT_LIST = test_embedding_config.get(
    "test_texts",
    [
        "测试BAAI/bge-m3的文本嵌入功能",
        "今天天气很好，适合出门游玩",
        "大语言模型的文本嵌入技术在RAG中应用广泛",
    ],
)
MAX_LENGTH = int(test_embedding_config.get("max_length", 512))
NORMALIZE_EMBEDDINGS = bool(test_embedding_config.get("normalize_embeddings", True))

# 初始化异步客户端
client = AsyncOpenAI(
    base_url=BASE_URL,
    api_key=API_KEY,
)


async def embedding_loop():
    """
    对标 test_chat 的格式：
    - 使用 AsyncOpenAI 调用本地 vLLM /embeddings 接口
    - 从 deployment_config.toml 读取 base_url、api_key、模型名和测试文本
    """
    print(f"当前 Embedding 模型：{MODEL_NAME}")
    print(f"服务地址：{BASE_URL}")
    print("输入文本计算嵌入，直接回车则使用配置文件中的测试样例；输入 'exit' 或 'quit' 退出。\n")

    while True:
        user_input = input("文本（留空使用配置样例）：").strip()

        if user_input.lower() in ["exit", "quit"]:
            print("退出 Embedding 测试程序！")
            break

        # 根据输入决定使用单条文本还是配置样例列表
        if user_input:
            texts = [user_input]
        else:
            texts = TEST_TEXT_LIST

        try:
            start_time = time.time()
            # 调用 /embeddings 接口
            resp = await client.embeddings.create(
                model=MODEL_NAME,
                input=texts,
            )

            elapsed = time.time() - start_time
            print("-" * 50)
            print(f"共生成 {len(resp.data)} 条嵌入，耗时：{elapsed:.2f}s")

            for i, (text, item) in enumerate(zip(texts, resp.data), start=1):
                vec = item.embedding
                dim = len(vec)
                print(f"\n{i}. 输入文本：{text}")
                print(f"   嵌入维度：{dim}")
                print(f"   前 8 维示例：{vec[:8]}")

            print("\n" + "=" * 50 + "\n")

        except Exception as e:
            print(f"嵌入计算出错！错误信息：{e}\n")


if __name__ == "__main__":
    asyncio.run(embedding_loop())
