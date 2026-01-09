import uuid
from typing import List, Optional, Sequence, Dict, Iterator, Any, Tuple
from langchain_core.documents import Document
from agent.config import *
from agent.rag.loader import DocumentLoader
from agent.rag.spliter import TextSplitter
from agent.rag.indexer import BM25Indexer

# 与测试脚本一致的分隔符设置（兼容递归切分）
SEPARATORS: list[str] = [
    "\n\n",
    "\n",
    "。",
    "！",
    "？",
    ". ",
    "! ",
    "? ",
    "；",
    "，",
    ", ",
    " ",
    "",
]
# === RAG参数 ===
query_distance_threshold = 0.5 # 距离阈值-越小要求越高
rerank_distance_threshold = 0.1 # 重排序距离阈值-越大要求越高
K= 60
#

class RagEngine:
    """
    结合 loader 与 splitter 的 RAG 引擎：
    - DocumentLoader 负责文件/网页加载
    - TextSplitter 根据 file_type 自动选择（md/html 标题分割，其他递归；可选语义）
    - Chroma 做向量存储
    - embedder 从全局配置获取
    """

    def __init__(
            self,
            base_path: Optional[str] = None,
            use_semantic_split: bool = True,
            collection_name: str = COLLECTION_NAME,
            chunk_size: int = 200,
            chunk_overlap: int = 20,
            hybrid_alpha: float = 0.5,
    ):
        self.base_path = base_path or FILE_PATH
        self.collection = get_chroma_collection(collection_name)
        self.embedding_model = embedder
        self.reranker = reranker

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_semantic_split = use_semantic_split
        self._closed = False
        # 混合检索相关
        self.hybrid_alpha = hybrid_alpha
        self.indexer = BM25Indexer()


    def __enter__(self): # 不用管
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()
        return False

    def cleanup(self):  # 保证其被清理
        if not self._closed:
            self.collection = None
            self.embedding_model = None
            self.reranker = None
            self.indexer = None
            self._closed = True

    def __del__(self): # 析构函数在被删除时调用
        self.cleanup()

    # ==================== 资源访问方法 ====================
    def embed_data(
        self,
        input_data: List[Document],
    ) -> int:
        """嵌入对应的文件。"""
        try:
            return self._add_to_vector_store(input_data)
        except Exception as e:
            logger.error(f"Failed to embed data: {e}")
            raise

    def query_embedded_store(
            self,
            question: str,
            top_k: Optional[int] = 10,
            include: Optional[List[str]] = None,
    ) -> list[Any] | list[tuple[Any, Any]]: # Chroma的query方法设计成可以同时查询多个问题
        """
        询问检索相似内容。
        :param question: 用户问题
        :param top_k: 返回条数
        :param include: chroma include 参数，默认 documents / metadatas / distances
        :return: List[Tuple[str, float,str]]返回一个列表，包含(文档内容, 相似度分数, 元数据)
        """
        k = top_k
        query_embedding = self.embedding_model.embed_query(question)
        query_result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            include=include or ["documents", "metadatas", "distances"],
        )
        docs = query_result["documents"][0]
        distances = query_result["distances"][0]
        metadatas = query_result["metadatas"][0]
        filtered = [(doc,metadata) for doc,dist,metadata in zip(docs,distances,metadatas) if dist >= query_distance_threshold]
        if not filtered:
            return []
        return filtered
    # 构建llm提示词
    def build_answer_prompt(self, question: str, top_k: Optional[int] = 10, use_rerank: bool = True,
                            rerank_top_n: int = 3, use_hybrid:bool = False, hybrid_alpha:float = 0.6) -> str:
        """直接返回拼好的 RAG Prompt，方便接入任意 LLM。
        用户问题 → 向量检索(召回) → Rerank(精排) → 构建提示词 → LLM 生成答案
        Args:
            question: 用户问题
            top_k: 向量检索返回的文档数量
            use_rerank: 是否使用rerank重排序，默认False
            rerank_top_n: rerank后保留的文档数量，默认为3
            use_hybrid : 使用混合检索
            hybrid_alpha: 混合检索的alpha参数
        Returns:
            str: 构建好的RAG提示词
        """
        if use_hybrid:
            search_results = self.query_hybrid_search(question, top_k=top_k, alpha = hybrid_alpha)
        else:
            search_results = self.query_embedded_store(question, top_k=top_k)
        #  实际的search_results是两个数值
        if not search_results:
            return self.build_rag_prompt(question, ["rag无相关检索内容"])

        # 构建文档内容和元数据的映射-构建两个哈希表来映射
        doc_to_metadata = {doc: metadata for doc, metadata in search_results}
        contents = list(doc_to_metadata.keys())

        if use_rerank:
            rerank_result = self.rerank(question, contents, top_n=rerank_top_n)
            reranked_docs = rerank_result.get("results", [])

            if not reranked_docs:
                return self.build_rag_prompt(question, ["rag无相关检索内容"])

            # 根据rerank结果构建contexts，同时保留metadata
            contexts = []
            for doc in reranked_docs:
                text = doc["document"]["text"]
                score = doc["relevance_score"]
                if score >= rerank_distance_threshold:
                    metadata = doc_to_metadata.get(text, {})  # 获取对应的metadata
                    contexts.append(f"内容: {text}| 来源: {os.path.basename(metadata["source"])}\n")
        else:
            # 不使用rerank时，直接使用原始结果
            contexts = [f"内容: {doc}| 来源: {os.path.basename( metadata["source"])}\n" for doc, metadata in search_results]

        if not contexts:
            return self.build_rag_prompt(question, ["rag无相关检索内容"])

        return self.build_rag_prompt(question, contexts)

    def _add_to_vector_store(self, docs: List[Document]) -> int:
        if not docs:
            return 0

        batch_size = 10
        total_added = 0
        # 双层保险分批次
        for i in range(0, len(docs), batch_size): # 外batch的处理
            batch_docs = docs[i:i + batch_size]
            texts = [doc.page_content for doc in batch_docs]

            embeddings = self.embedding_model.embed_documents(texts)

            ids = [str(uuid.uuid4()) for _ in batch_docs]
            metadatas = []
            for doc in batch_docs:
                meta = (doc.metadata or {}).copy()
                meta.setdefault("source", meta.get('source', ''))

                for key, value in meta.items():
                    if isinstance(value, list):
                        meta[key] = ",".join(str(v) for v in value)
                    elif not isinstance(value, (str, int, float, bool, type(None))):
                        meta[key] = str(value)

                metadatas.append(meta)

            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas,
            )
            total_added += len(batch_docs)
            logger.info(f"已嵌入 {total_added}/{len(docs)} 个文档块")

        return total_added

    def delete_vector_store(self,ids: Optional[List[str]] = None, source: Optional[str] = None, **metadata_filters) -> int:
        """删除文档的便捷方法
        :param ids: 删除的文档ID
        :param source: 删除的文档来源
        :param metadata_filters: 删除的文档元数据过滤条件
        """
        if ids:
            self.collection.delete(ids=ids)
            return len(ids)

        where_conditions = {}
        if source:
            where_conditions["source"] = source
        where_conditions.update(metadata_filters)

        if where_conditions:
            self.collection.delete(where=where_conditions)
            return 1  # 实际应用中可以返回删除的文档数量
        return 0

    # 内存管理
    def iterate_vector_store(
            self,
            batch_size: int = 100,
            include: List[str] = None,
            where: Optional[Dict] = None,
            **metadata_filters
    ) -> Iterator[Document]:
        """
        遍历向量数据库中的所有文档

        Args:
            batch_size: 每次获取的文档数量，默认100
            include: 要包含的字段列表，如 ['documents', 'metadatas', 'embeddings']
            where: 过滤条件字典
            **metadata_filters: 额外的元数据过滤条件
        Yields:
            Document: 每次迭代返回一个Document对象
        """
        if include is None:
            include = ['documents', 'metadatas']

        where_conditions = None  # 默认为None而不是空字典
        if where:
            where_conditions = where
        if metadata_filters:
            if where_conditions is None:
                where_conditions = metadata_filters
            else:
                where_conditions.update(metadata_filters) # 过滤并合并
        # 上述为过滤各个条件的过程
        offset = 0
        while True:
            # 获取一批数据
            get_params = {
                'include': include,
                'offset': offset,
                'limit': batch_size
            }
            if where_conditions:  # 只有在有过滤条件时才添加where参数
                get_params['where'] = where_conditions # 存在添加对应的过滤参数

            results = self.collection.get(**get_params) # 获取数据库的数据

            if not results['ids']: # 如果没有索引不考虑-说明没有可以查询到的数据
                break

            # 将结果转换为Document对象
            for i in range(len(results['ids'])):
                meta = results["metadatas"][i] if 'metadatas' in results else {} # 获取元数据
                meta["chroma_id"] = results["ids"][i]  # 关键：注入 Chroma 的 id
                doc = Document(
                    page_content=results['documents'][i] if 'documents' in results else "",
                    metadata=meta
                )
                yield doc

            offset += batch_size

    def get_all_documents(
            self,
            batch_size: int = 100,
            include: List[str] = None,
            where: Optional[Dict] = None,
            **metadata_filters
    ) -> List[Document]:
        """
        获取所有文档的便捷方法

        Args:
            batch_size: 每次获取的文档数量，默认100
            include: 要包含的字段列表
            where: 过滤条件字典
            **metadata_filters: 额外的元数据过滤条件

        Returns:
            List[Document]: 所有匹配的文档列表
        """
        return list(self.iterate_vector_store(
            batch_size=batch_size,
            include=include,
            where = where,
            **metadata_filters
        ))

    def rerank(self, question: str, data: List[str],top_n: Optional[int] = None,max_chunks_per_doc: int = 123,
                    overlap_tokens: int = 40) -> dict:
        """根据列举的列表数据和查询问题重排序，该函数只支持单问题循环
        Args:
        question (str): 用于重排序的查询问题
        data (List[str]): 需要重排序的文档列表
        top_n (Optional[int], optional): 返回前n个最相关的结果。默认为None，表示返回全部结果
        max_chunks_per_doc (int, optional): 每个文档的最大分块数量。默认为123
        overlap_tokens (int, optional): 文档分块时的重叠token数量。默认为40

    Returns:
        Dict[str, Any]: 包含重排序结果的字典，通常包含：
            - results(list): 重排序后的文档列表，每个文档包含相关性分数和索引
            - tokens: token使用情况
            - id: 请求ID（如果API返回）
        """

        return self.reranker.rerank_documents(query=question, documents=data, top_n=top_n, max_chunks_per_doc=max_chunks_per_doc,overlap_tokens=overlap_tokens)

    def build_bm25_index(self,force:bool = False):
        """构建 BM25 索引，需要先获取所有文档，它不支持增量更新
            Args:
            Force(bool): 参数用于强制重新构建索引，即使索引已经存在
        """
        if self.indexer.is_built() and not force:
            logger.info("BM25 索引已存在，无需重新构建")
            return
        logger.info("开始构建 BM25 索引...")
        all_docs = self.get_all_documents()

        if not all_docs:
            logger.warning("知识库里没有文档可用于构建 BM25 索引")
            return

        self.indexer.build_index(all_docs) # 将文档传进去
        logger.info("BM25 索引构建完成")

    def _query_bm25_search(self, question: str, top_k: int) -> list[Any] | list[tuple[str, float]]:
        """使用问题通过BM25库进行稀疏检索"""
        if self.indexer is None or not self.indexer.is_built():
            logger.warning("BM25 索引未构建，正在构建...")
            self.build_bm25_index()
            if self.indexer is None or not self.indexer.is_built():
                return []

        return self.indexer.search_index(question, top_k=top_k) # 直接返回对应的文档

    def query_hybrid_search(
            self,
            question: str,
            top_k: int,
            alpha: float = 0.6,
    ) -> List[Tuple[str, dict]]:
        """混合检索：返回结合Dense向量检索和BM25稀疏检索的结果
        Args:
            question: 查询问题
            top_k: 返回的文档数量
            alpha: 混合检索的权重
        Returns:
            List[Tuple[str, float, dict]]: (文档内容, 融合分数, 元数据)

        """


        query_embedding = self.embedding_model.embed_query(question) # 获取嵌入向量
        # 用的就是原始的数据，不要进行距离过滤-易错
        dense_results  = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents"]
        ) # 这里自带索引ids

        sparse_results = self._query_bm25_search(question, top_k)
        # 实际上每个2k融合4k，但是这里直接返回k
        result_ids = self.rrf_fusion(dense_results, sparse_results , top_k,hybrid_alpha=alpha)

        return self.search_by_id(result_ids)

    def search_by_id(self, id_score_list: List[Tuple[str, float]] ) -> List[
        Tuple[str, Dict[str, Any]]]:
        """通过文档ID并获取数据库的列表数据
        Args:
            List[Tuple[str, float]] : id列表或者id-分数列表

        Returns:
            Tuple[str, Dict[str, Any]]: 第一个为数据，第二个为metadata字典
        """
        ids = [doc_id for doc_id, _ in id_score_list]
        # 从集合中获取文档内容和元数据
        got = self.collection.get(ids=ids, include=["documents", "metadatas"])
        result = []
        for doc_data,doc_metadata in zip(got["documents"], got["metadatas"]):
            result.append((doc_data, doc_metadata))
        return result

    def get_all_file(self) -> tuple[list[Any], str | None ]:
        """
        返回Rag系统对应的路径下的文件夹列表

        Returns:
            tuple[list[Any], str | None]: 文件夹列表和基础路径
        :return:
        """
        files = []
        base_path = self.base_path
        folder = Path(base_path)
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在：{folder}")

        for file_path in folder.iterdir():
            if file_path.is_file():
                files.append(file_path.name)
        return files,base_path

    @staticmethod
    def build_rag_prompt(question: str, contexts: Sequence[str]) -> str:
        """根据检索到的上下文构建回答提示词。"""
        context_text = "\n\n".join([f"{i + 1}：{text}" for i, text in enumerate(contexts)])
        return (
            "请仅依据提供的内容回答问题，不要编造和幻想。\n\n"
            f"相关内容按重要度依次排序如下：\n{context_text}\n\n"
            f"用户问题：{question}\n请回答："
        )
    @staticmethod
    def rrf_fusion(
            dense_results: dict|list[Any]| list[str],
            sparse_results: dict|list[Any] | list[str],
            top_k: int,
            hybrid_alpha:float  =0.6
    ) -> list[tuple[Any, set[float] | float]]:
        """RRF (Reciprocal Rank Fusion) 融合算法
            rank为本身列表的顺序排名
        Args:
            dense_results: Chroma返回的dense检索结果(包含chunk的id)
            sparse_results: BM25返回的sparse检索结果(包含chunk的id)
            top_k: 最终返回的文档数量
            hybrid_alpha: RRF算法的混合系数，默认0.5

        Returns:
            List[Tuple[str, float, dict]]: 融合后的结果
        """
        doc_scores = {}
        dense_ids =dense_results["ids"][0] # 支持多轮对话
        for rank, doc_id in enumerate(dense_ids, 1):
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
            doc_scores[doc_id] += hybrid_alpha * (1.0 / (rank + K))

        for rank, doc_id in enumerate(sparse_results, 1):
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
            doc_scores[doc_id] += (1.0 - hybrid_alpha) * (1.0 / (rank + K))

        sorted_results = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return sorted_results # 返回的是id和分数


class AsyncRagEngine:
    """
    异步版 RAG 引擎，支持高并发场景：
    - 使用 EmbeddingModelAsync 和 RerankModelAsync
    - 所有模型调用都是异步的
    - 支持批量并发操作
    - Chroma 向量库操作在线程池中执行以避免阻塞
    """

    def __init__(
            self,
            base_path: Optional[str] = None,
            use_semantic_split: bool = True,
            collection_name: str = COLLECTION_NAME,
            chunk_size: int = 200,
            chunk_overlap: int = 20,
            hybrid_alpha: float = 0.5,
    ):
        self.base_path = base_path or FILE_PATH
        self.collection = get_chroma_collection(collection_name)

        self.embedding_model = async_embedder
        self.reranker = async_reranker
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.use_semantic_split = use_semantic_split
        self._closed = False

        self.hybrid_alpha = hybrid_alpha
        self.indexer = BM25Indexer()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
        return False

    async def cleanup(self):
        if not self._closed:
            self.collection = None
            self.embedding_model = None
            self.reranker = None
            self.indexer = None
            self._closed = True

    async def embed_data(
            self,
            input_data: List[Document],
    ) -> int:
        """异步嵌入文档"""
        try:
            return await self._add_to_vector_store(input_data)
        except Exception as e:
            logger.error(f"Failed to embed data: {e}")
            raise

    async def query_embedded_store(
            self,
            question: str,
            top_k: Optional[int] = 10,
            include: Optional[List[str]] = None,
    ) -> list[Any] | list[tuple[Any, Any]]:
        """
        异步询问检索相似内容
        """
        k = top_k
        query_embedding = await self.embedding_model.embed_query(question)

        loop = asyncio.get_running_loop()
        query_result = await loop.run_in_executor(
            None,
            lambda: self.collection.query(
                query_embeddings=[query_embedding],
                n_results=k,
                include=include or ["documents", "metadatas", "distances"],
            )
        )

        docs = query_result["documents"][0]
        distances = query_result["distances"][0]
        metadatas = query_result["metadatas"][0]
        filtered = [(doc, metadata) for doc, dist, metadata in zip(docs, distances, metadatas)
                    if dist >= query_distance_threshold]
        if not filtered:
            return []
        return filtered

    async def build_answer_prompt(
            self,
            question: str,
            top_k: Optional[int] = 10,
            use_rerank: bool = True,
            rerank_top_n: Optional[int] = 3,
            use_hybrid: bool = False,
            hybrid_alpha: float = 0.6
    ) -> str:
        """异步构建 RAG Prompt"""
        if use_hybrid:
            search_results = await self.query_hybrid_search(question, top_k=top_k, alpha=hybrid_alpha)
        else:
            search_results = await self.query_embedded_store(question, top_k=top_k)

        if not search_results:
            return self.build_rag_prompt(question, ["rag无相关检索内容"])

        doc_to_metadata = {doc: metadata for doc, metadata in search_results}
        contents = list(doc_to_metadata.keys())

        if use_rerank:
            rerank_result = await self.rerank(question, contents, top_n=rerank_top_n)
            reranked_docs = rerank_result.get("results", [])

            if not reranked_docs:
                return self.build_rag_prompt(question, ["rag无相关检索内容"])

            contexts = []
            for doc in reranked_docs:
                text = doc["document"]["text"]
                score = doc["relevance_score"]
                if score >= rerank_distance_threshold:
                    metadata = doc_to_metadata.get(text, {})
                    contexts.append(f"内容: {text}| 来源: {os.path.basename(metadata['source'])}\n")
        else:
            contexts = [f"内容: {doc}| 来源: {os.path.basename(metadata['source'])}\n"
                        for doc, metadata in search_results]

        if not contexts:
            return self.build_rag_prompt(question, ["rag无相关检索内容"])

        return self.build_rag_prompt(question, contexts)

    async def _add_to_vector_store(self, docs: List[Document]) -> int:
        """异步批量嵌入文档"""
        if not docs:
            return 0

        batch_size = 10
        total_added = 0

        for i in range(0, len(docs), batch_size):
            batch_docs = docs[i:i + batch_size]
            texts = [doc.page_content for doc in batch_docs]

            embeddings = await self.embedding_model.embed_documents(texts)

            ids = [str(uuid.uuid4()) for _ in batch_docs]
            metadatas = []
            for doc in batch_docs:
                meta = (doc.metadata or {}).copy()
                meta.setdefault("source", meta.get('source', ''))

                for key, value in meta.items():
                    if isinstance(value, list):
                        meta[key] = ",".join(str(v) for v in value)
                    elif not isinstance(value, (str, int, float, bool, type(None))):
                        meta[key] = str(value)

                metadatas.append(meta)

            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,
                lambda: self.collection.add(
                    ids=ids,
                    embeddings=embeddings,
                    documents=texts,
                    metadatas=metadatas,
                )
            )
            total_added += len(batch_docs)
            logger.info(f"已嵌入 {total_added}/{len(docs)} 个文档块")

        return total_added

    async def delete_vector_store(
            self,
            ids: Optional[List[str]] = None,
            source: Optional[str] = None,
            **metadata_filters
    ) -> int:
        """异步删除文档"""
        loop = asyncio.get_running_loop()

        if ids:
            await loop.run_in_executor(None, lambda: self.collection.delete(ids=ids))
            return len(ids)

        where_conditions = {}
        if source:
            where_conditions["source"] = source
        where_conditions.update(metadata_filters)

        if where_conditions:
            await loop.run_in_executor(None, lambda: self.collection.delete(where=where_conditions))
            return 1
        return 0

    def iterate_vector_store(
            self,
            batch_size: int = 100,
            include: List[str] = None,
            where: Optional[Dict] = None,
            **metadata_filters
    ) -> Iterator[Document]:
        """
        遍历向量数据库（保持同步，因为是生成器）
        如需异步遍历，请使用 get_all_documents_async
        """
        if include is None:
            include = ['documents', 'metadatas']

        where_conditions = None
        if where:
            where_conditions = where
        if metadata_filters:
            if where_conditions is None:
                where_conditions = metadata_filters
            else:
                where_conditions.update(metadata_filters)

        offset = 0
        while True:
            get_params = {
                'include': include,
                'offset': offset,
                'limit': batch_size
            }
            if where_conditions:
                get_params['where'] = where_conditions

            results = self.collection.get(**get_params)

            if not results['ids']:
                break

            for i in range(len(results['ids'])):
                meta = results["metadatas"][i] if 'metadatas' in results else {}
                meta["chroma_id"] = results["ids"][i]
                doc = Document(
                    page_content=results['documents'][i] if 'documents' in results else "",
                    metadata=meta
                )
                yield doc

            offset += batch_size

    async def get_all_documents_async(
            self,
            batch_size: int = 100,
            include: List[str] = None,
            where: Optional[Dict] = None,
            **metadata_filters
    ) -> List[Document]:
        """异步获取所有文档"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: list(self.iterate_vector_store(
                batch_size=batch_size,
                include=include,
                where=where,
                **metadata_filters
            ))
        )

    async def rerank(
            self,
            question: str,
            data: List[str],
            top_n: Optional[int] = None,
            max_chunks_per_doc: int = 123,
            overlap_tokens: int = 40
    ) -> dict:
        """异步重排序"""
        return await self.reranker.rerank_documents(
            query=question,
            documents=data,
            top_k=top_n,
            max_chunks_per_doc=max_chunks_per_doc,
            overlap_tokens=overlap_tokens
        )

    async def build_bm25_index_async(self, force: bool = False):
        """异步构建 BM25 索引"""
        if self.indexer.is_built() and not force:
            logger.info("BM25 索引已存在，无需重新构建")
            return

        logger.info("开始构建 BM25 索引...")
        all_docs = await self.get_all_documents_async()

        if not all_docs:
            logger.warning("知识库里没有文档可用于构建 BM25 索引")
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.indexer.build_index(all_docs))
        logger.info("BM25 索引构建完成")

    async def _query_bm25_search(self, question: str, top_k: int) -> list[Any] | list[tuple[str, float]]:
        """异步 BM25 稀疏检索"""
        if self.indexer is None or not self.indexer.is_built():
            logger.warning("BM25 索引未构建，正在构建...")
            await self.build_bm25_index_async()
            if self.indexer is None or not self.indexer.is_built():
                return []

        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.indexer.search_index(question, top_k=top_k)
        )

    async def query_hybrid_search(
            self,
            question: str,
            top_k: int,
            alpha: float = 0.6,
    ) -> List[Tuple[str, dict]]:
        """异步混合检索：并发执行 Dense 和 BM25 检索"""
        query_embedding_task = self.embedding_model.embed_query(question)
        bm25_search_task = self._query_bm25_search(question, top_k)

        query_embedding, sparse_results = await asyncio.gather(
            query_embedding_task,
            bm25_search_task
        )

        loop = asyncio.get_running_loop()
        dense_results = await loop.run_in_executor(
            None,
            lambda: self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents"]
            )
        )

        result_ids = self.rrf_fusion(dense_results, sparse_results, top_k, hybrid_alpha=alpha)

        return await self.search_by_id_async(result_ids)

    async def search_by_id_async(
            self,
            id_score_list: List[Tuple[str, float]]
    ) -> List[Tuple[str, Dict[str, Any]]]:
        """异步通过 ID 获取文档"""
        ids = [doc_id for doc_id, _ in id_score_list]

        loop = asyncio.get_running_loop()
        got = await loop.run_in_executor(
            None,
            lambda: self.collection.get(ids=ids, include=["documents", "metadatas"])
        )

        result = []
        for doc_data, doc_metadata in zip(got["documents"], got["metadatas"]):
            result.append((doc_data, doc_metadata))
        return result

    async def get_all_file_async(self) -> tuple[list[Any], str | None]:
        """异步获取文件列表"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._get_all_file_sync)

    def _get_all_file_sync(self) -> tuple[list[Any], str | None]:
        """同步获取文件列表（内部方法）"""
        files = []
        base_path = self.base_path
        folder = Path(base_path)
        if not folder.exists():
            raise FileNotFoundError(f"文件夹不存在：{folder}")

        for file_path in folder.iterdir():
            if file_path.is_file():
                files.append(file_path.name)
        return files, base_path

    @staticmethod
    def build_rag_prompt(question: str, contexts: Sequence[str]) -> str:
        """根据检索到的上下文构建回答提示词"""
        context_text = "\n\n".join([f"{i + 1}：{text}" for i, text in enumerate(contexts)])
        return (
            "请仅依据提供的内容回答问题，不要编造和幻想。\n\n"
            f"相关内容按重要度依次排序如下：\n{context_text}\n\n"
            f"用户问题：{question}\n请回答："
        )

    @staticmethod
    def rrf_fusion(
            dense_results: dict | list[Any] | list[str],
            sparse_results: dict | list[Any] | list[str],
            top_k: int,
            hybrid_alpha: float = 0.6
    ) -> list[tuple[Any, set[float] | float]]:
        """RRF (Reciprocal Rank Fusion) 融合算法"""
        doc_scores = {}
        dense_ids = dense_results["ids"][0]
        for rank, doc_id in enumerate(dense_ids, 1):
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
            doc_scores[doc_id] += hybrid_alpha * (1.0 / (rank + K))

        for rank, doc_id in enumerate(sparse_results, 1):
            if doc_id not in doc_scores:
                doc_scores[doc_id] = 0.0
            doc_scores[doc_id] += (1.0 - hybrid_alpha) * (1.0 / (rank + K))

        sorted_results = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        return sorted_results


# ====================== 简单运行示例 ======================
if __name__ == "__main__":
    engine = RagEngine()
    documents = DocumentLoader().load_file("test.md") # 专门的内容加载器
    print(documents)
    splitter_md = TextSplitter() # 专门的文本分块器
    splitter_txt = TextSplitter(mode = "semantic")
    documents1 = splitter_md.split_documents(documents)
    # engine.embed_data(documents1)
    # result = engine.query_embedded_store("哆啦A梦使用的3个秘密道具是什么?",5) # 询问查询
    # documents = result["documents"][0]
    # print(documents)
    # answer= engine.rerank("哆啦A梦使用的3个秘密道具是什么?",documents,top_n=5)["results"]
    # print(answer)
    # for doc in  answer:
    #     print(doc["document"]["text"])
    #     print(doc["relevance_score"])
    print(50*'-')
    # print(engine.get_all_documents()) # 打印数据库的所有文档
    print(50 * '-')
    print("rag构建的prompt")
    answer=engine.build_answer_prompt(" 慢羊羊给懒羊羊的道具是什么呢?",use_rerank=True,use_hybrid=True,top_k=20,rerank_top_n=5,hybrid_alpha=0.6)
    print(answer)
    close_chroma()


