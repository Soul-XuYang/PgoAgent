from typing import List, Optional, Any
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi
import jieba
from agent.config.logger_config import logger
class BM25Indexer:
    """
    负责：
    - 从 Document 列表构建 BM25 索引
    - 默认用jieba分词
    - 对查询做 BM25 检索
    """

    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer or (lambda text: list(jieba.cut_for_search(text)))
        self._bm25: Optional[BM25Okapi] = None
        self._doc_ids: List[str] = []  # 只存 id，不存 metadata/全文-减少内存压力

    def build_index(self, docs: List[Document]) -> None:  # 这里返回的List[Document]以及够了
        if not docs:
            logger.warning("BM25Indexer: 没有文档可用于构建索引")
            self._bm25 = None
            self._doc_ids = []
            return

        self._doc_ids = []
        tokenized_corpus: List[List[str]] = []

        for doc in docs:
            content = doc.page_content
            metadata = (doc.metadata or {}).copy()

            doc_id = metadata.get("chroma_id")
            if not doc_id:
                raise ValueError("BM25Indexer: 缺少 chroma_id（请在 iterate_vector_store函数内注入）")

            self._doc_ids.append(doc_id)  # 只存 id + metadata
            tokenized_corpus.append(self.tokenizer(content))  # 仍需要用全文的内容分词来建索引

        self._bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25Indexer: 索引构建完成，共索引 {len(self._doc_ids)} 个文档")

    def is_built(self) -> bool:
        return self._bm25 is not None and len(self._doc_ids) > 0

    def search_index(self, query: str, top_k: int = 10) -> list[Any] | list[str]:
        """返回的是对应的数据库的chunk索引和BM25分数"""
        if not self.is_built():
            logger.warning("BM25Indexer: 索引尚未构建，无法搜索")
            return []

        tokenized_query = self.tokenizer(query)
        score_lists = self._bm25.get_scores(tokenized_query)  # 获取对应的分数

        # 这里是依据分数进行排序，返回的结果是range(len(score_lists))对应的索引
        top_indices = sorted(range(len(score_lists)), key=lambda i: score_lists[i], reverse=True)[:top_k]

        return [self._doc_ids[i] for i in top_indices]  # 返回对应的数据库索引和对应的分数

