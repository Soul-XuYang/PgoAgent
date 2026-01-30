# 初始化嵌入模型和重排序模型实例
from agent.model import EmbeddingModel, EmbeddingModelAsync, RerankModel, RerankModelAsync
from agent.config import EMBEDDING_MODEL_URL,EMBEDDING_API_KEY, RERANK_MODEL_URL,RERANK_API_KEY
# 同步模型实例
embedder = EmbeddingModel(
    model_name="BAAI/bge-large-zh-v1.5",
    api_url=EMBEDDING_MODEL_URL,
    api_key=EMBEDDING_API_KEY
) if EMBEDDING_API_KEY and EMBEDDING_MODEL_URL else None

reranker = RerankModel(
    model_name="BAAI/bge-reranker-v2-m3",
    api_url=RERANK_MODEL_URL,
    api_key=RERANK_API_KEY
) if RERANK_API_KEY and RERANK_MODEL_URL else None

# 异步模型实例
async_embedder = EmbeddingModelAsync(
    model_name="BAAI/bge-large-zh-v1.5",
    api_url=EMBEDDING_MODEL_URL,
    api_key=EMBEDDING_API_KEY
) if EMBEDDING_API_KEY and EMBEDDING_MODEL_URL else None

async_reranker = RerankModelAsync(
    model_name="BAAI/bge-reranker-v2-m3",
    api_url=RERANK_MODEL_URL,
    api_key=RERANK_API_KEY
) if RERANK_API_KEY and RERANK_MODEL_URL else None
