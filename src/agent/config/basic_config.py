import os
from pathlib import Path
from dotenv import load_dotenv
from PgoModel import  EmbeddingModel,EmbeddingModelAsync
import chromadb
from agent.config.logger_config import logger
from PgoModel import RerankModel, RerankModelAsync

load_dotenv(override=True)  # 加载环境变量
API_KEY= os.getenv("OPENAI_API_KEY")  # 从环境变量中获取OPENAI_API_KEY的值
BASE_URL = os.getenv("OPENAI_BASE_URL")  # 从环境变量中获取OPENAI_BASE_URL的值
# 嵌入模型
EMBEDDING_MODEL_URL= os.getenv("EMBEDDING_MODEL_URL")
EMBEDDING_API_KEY = os.getenv("EMBEDDING_API_KEY")
# Rerank模型
RERANK_MODEL_URL= os.getenv("RERANK_MODEL_URL")
RERANK_API_KEY = os.getenv("RERANK_API_KEY")
PRINT_SWITCH = False# DEBUG各个节点的token数
# 路径设置
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent # 用相对路径导出绝对路径
FILE_PATH = str(PROJECT_ROOT / "file")
embedder = EmbeddingModel(
    model_name="BAAI/bge-large-zh-v1.5",
    api_url=EMBEDDING_MODEL_URL,
    api_key=EMBEDDING_API_KEY
)
reranker = RerankModel(
    model_name="BAAI/bge-reranker-v2-m3",
    api_url=RERANK_MODEL_URL,
    api_key=RERANK_API_KEY
)
async_embedder = EmbeddingModelAsync(
            model_name="BAAI/bge-large-zh-v1.5",
            api_url=EMBEDDING_MODEL_URL,
            api_key=EMBEDDING_API_KEY
)
async_reranker = RerankModelAsync(
    model_name="BAAI/bge-reranker-v2-m3",
    api_url=RERANK_MODEL_URL,
    api_key=RERANK_API_KEY
)
# 基本模型的输入token设置
MODEL_MAX_INPUT = {
    # 1M/2M 级：90% 规则
    "gpt-4.1": 900_000,
    "gpt-4.1-mini": 900_000,
    "gpt-4.1-nano": 900_000,
    "gemini-1.5-pro": 1_800_000,
    "gemini-1.5-flash": 900_000,
    "qwen2.5-turbo": 900_000,
    "qwen2.5-1m": 900_000,
    # 200K 级
    "claude-3.5-sonnet": 180_000,
    "claude-3.5-haiku": 180_000,
    "claude-3-opus": 180_000,
    "glm-4.6": 180_000,  # 或 160_000 更保守

    # 128K 级（预留≥8K）
    "gpt-4o": 120_000,
    "gpt-4o-mini": 120_000,
    "mistral-large-2": 120_000,
    "llama-3.1-8b-instruct": 120_000,
    "llama-3.1-70b-instruct": 120_000,
    "llama-3.1-405b-instruct": 120_000,
    "qwen2.5-7b-instruct": 120_000,
    "qwen2.5-72b-instruct": 120_000,
    "deepseek-v3.2": 120_000,
    "kimi-k2-instruct": 120_000,
    "command-r": 120_000,
    "command-r-plus": 120_000,
    "moonshot-v1-8k": 8192,
    "kimi-k2-thinking": 230_000,
}

# 向量数据库的配置参数
DB_PATH =  str(PROJECT_ROOT / "chroma_db")
COLLECTION_NAME = "my_vector"


_chroma_client = None
_chroma_collection = None

def get_chroma_client(db_path:str = DB_PATH) -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=db_path)
    return _chroma_client

def get_chroma_collection(collection_name:str = COLLECTION_NAME):
    global _chroma_collection
    if _chroma_collection is None:
        client = get_chroma_client()
        _chroma_collection = client.get_or_create_collection(collection_name)
    return _chroma_collection
def delete_chroma_collection(collection_name: str, db_path: str=DB_PATH) -> bool:
    """删除指定的集合"""
    try:
        client = get_chroma_client(db_path)
        # 检查集合是否存在
        if collection_name in [col.name for col in client.list_collections()]:
            client.delete_collection(collection_name)
            # 如果删除的是当前缓存的集合，清除缓存
            logger.info(f"成功删除chromadb的表: {collection_name}")
            return True
        else:
            logger.warning(f"chromadb表 {collection_name} 不存在.")
            return False
    except Exception as e:
        logger.error(f"删除chromadb的表错误: {collection_name}: {str(e)}")
        return False


def close_chroma():
    global _chroma_client, _chroma_collection
    if _chroma_client is not None:
        try:
            if hasattr(_chroma_client, 'close'):
                _chroma_client.close()
        except Exception as e:
            print(f"Error closing ChromaDB client: {e}")
        finally:
            _chroma_client = None
            _chroma_collection = None

def get_all_docs():
    collection = get_chroma_collection()
    results = collection.get(include=['documents', 'metadatas', 'embeddings'])
    for i in range(len(results['ids'])):
        print(f"文档ID: {results['ids'][i]}")
        print(f"内容: {results['documents'][i]}")
        print(f"元数据: {results['metadatas'][i]}")
        print(f"向量: {results['embeddings'][i]}")
        print("-" * 50)

# def get_all_docs():
#     results = _collection.get(include=['documents', 'metadatas', 'embeddings'])
#     for i in range(len(results['ids'])):
#         print(f"文档ID: {results['ids'][i]}")
#         print(f"内容: {results['documents'][i]}")
#         print(f"元数据: {results['metadatas'][i]}")
#         print(f"向量: {results['embeddings'][i]}")
#         print("-" * 50)