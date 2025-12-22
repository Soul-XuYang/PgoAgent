from typing import Type, Literal
from agent.rag.RAGEngine import RagEngine
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from agent.my_llm import llm

RAG_TOOL_NAMES = {"rag_rewrite_query", "rag_retrieve"}

## 第一个是检索前的参数设置
# === 检索查询 ===
# class RagDecideArgs(BaseModel):
#     question: str = Field(..., description="当前rag检索query")

# class rag_decide_strategy(BaseTool):
#     name: str = "rag_decide_strategy"
#     description: str = "根据问题确定RAG检索策略参数。返回strategy、top_k、alpha等参数供rag_retrieve使用。"
#     args_schema: Type[BaseModel] = RagDecideArgs
#
#     async def _arun(self, question: str) -> dict:
#         my_llm = llm.with_structured_output(RagDecideOut)
#         prompt = (
#             "你是检索策略选择器。输出适合该query的检索策略参数。\n"
#             "规则：\n"
#             "- 有明确术语/文件名/接口名/关键词 -> hybrid\n"
#             "- 概念性/描述性/语义理解 -> vector\n"
#             "- top_k默认10~20；alpha默认0.6；rerank_top_n默认3\n\n"
#             f"query: {question}"
#         )
#         out = await my_llm.ainvoke([SystemMessage(content=prompt)])
#         return out.model_dump()
#
#     def _run(self, question: str) -> dict:
#         import asyncio
#         return asyncio.run(self._arun(question))

# class RagDecideOut(BaseModel):
#     strategy: Literal["vector", "hybrid"] = Field(
#         ...,
#         description="vector=纯向量检索，hybrid=混合检索(向量+BM25)"
#     )
#     top_k: int = Field(default=10, ge=3, le=50, description="初始检索数量")
#     alpha: float = Field(default=0.6, ge=0.0, le=1.0, description="混合检索权重，越接近1越偏向向量")
#     use_rerank: bool = Field(default=True, description="是否使用重排序")
#     rerank_top_n: int = Field(default=3, ge=2, le=15, description="重排序后保留数量")
# 上述的工具有点多余----------------------------------------------------------------------
# 顶部
import threading
_engine = None
_engine_lock = threading.Lock()

def get_engine() -> RagEngine:
    global _engine
    if _engine is None:
        with _engine_lock: # 线程锁，确保只有一个线程初始化engine
            if _engine is None:
                _engine = RagEngine()  # 初始化 BM25/向量索引
    return _engine

def reset_engine():
    global _engine
    with _engine_lock:
        if _engine is not None:
            try:
                _engine.cleanup()
            finally:
                _engine = None


# === rewriting程序 ===
class RagRewriteArgs(BaseModel):
    question: str = Field(..., description="原始问题或当前query")
    failure_reason: str = Field(default="", description="失败原因（可选：例如召回为空/不相关/缺少关键词）")


class RagRewriteOut(BaseModel):
    refined_query: str = Field(..., description="更适合检索的改写query")

# 重写必要时的使用
class rag_rewrite_query(BaseTool):
    name: str = "rag_rewrite_query"
    description: str = "将问题改写为更适合检索的query（不执行检索）。返回refined_query供后续使用。"
    args_schema: Type[BaseModel] = RagRewriteArgs

    async def _arun(self, question: str, failure_reason: str = "") -> dict:
        model = llm.with_structured_output(RagRewriteOut)
        prompt = (
            "你是检索query改写器。请把用户问题改写为更适合在知识库中检索的短query。\n"
            "要求：\n"
            "- query尽量短（<=20字/英文<=12词）\n"
            "- 尽量包含实体名、模块名、接口名、关键术语\n"
            "- 保留核心语义，去除冗余表达\n\n"
            f"原始: {question}\n"
            f"失败原因: {failure_reason}\n"
        )
        out = await model.ainvoke([HumanMessage(content=prompt)])
        return out.model_dump()

    def _run(self, question: str, failure_reason: str = "") -> dict:
        import asyncio
        return asyncio.run(self._arun(question, failure_reason))

# 实际的rag使用和执行
class RagRetrieveArgs(BaseModel):
    query: str = Field(..., description="检索query")
    strategy: Literal["vector", "hybrid"] = Field(default="vector", description="检索策略vector/hybrid混合检索模式")
    top_k: int = Field(default=10, ge=10, le=40, description="初始检索数量")
    alpha: float = Field(default=0.6, ge=0.0, le=1.0, description="混合检索权重,如果检索策略设置为vector，则该参数无效")
    use_rerank: bool = Field(default=True, description="是否重排序")
    rerank_top_n: int = Field(default=3, ge=2, le=5, description="重排序后保留数量")

# === 检索程序 ===
class rag_retrieve(BaseTool):
    name: str = "rag_retrieve"
    description: str = (
        "执行知识库检索，返回参考相关文档片段及来源。\n"
        "参数选择指南：\n"
        "- strategy: 'hybrid'（有明确术语/文件名/关键词）或 'vector'（概念性/语义理解问题）\n"
        "- top_k: 10-20（hybrid用15-20，vector用10）\n"
        "- alpha: 0.6（仅hybrid有效，越接近1越偏向向量）\n"
        "- use_rerank: 是否使用重排序\n"
        "- rerank_top_n: 3（重排序后保留数量）\n"
        "返回格式: {contexts: [文档内容...], count: 数量}，contexts为空表示无相关内容。\n"
        "如果检索失败，可先调用rag_rewrite_query重写query后再次检索。"
    )
    args_schema: Type[BaseModel] = RagRetrieveArgs

    async def _arun(
            self,
            query: str,
            strategy: str = "vector",
            top_k: int = 10,
            alpha: float = 0.6,
            use_rerank: bool = True,
            rerank_top_n: int = 3
    ) -> dict:
        engine =None
        try:
            # 每次调用都用全局变量
            engine = get_engine()

            use_hybrid = (strategy == "hybrid")

            if use_hybrid:
                search_results = engine.query_hybrid_search(
                    question=query,
                    top_k=top_k,
                    alpha=alpha
                )
            else:
                search_results = engine.query_embedded_store(query, top_k=top_k)  # 这里返回的是list，两个参数documents和 metadata

            if not search_results:  # 如果为空，则返回无内容
                return {
                    "contexts": "", 
                    "count": 0,  
                    "message": "知识库中未找到相关内容"
                }

            doc_to_metadata = {doc: metadata for doc, metadata in search_results}
            contents = list(doc_to_metadata.keys())  # 返回内容

            contexts = []

            # 使用重排序功能
            if use_rerank and contents:  # 上述不为空进行执行
                rerank_result = engine.rerank(query, contents, top_n=rerank_top_n)
                reranked_docs = rerank_result.get("results", [])  # 获得重排序结果

                for doc in reranked_docs:
                    text = doc["document"]["text"]
                    metadata = doc_to_metadata.get(text, {})  # 哈希表获取文档知识库来源
                    source = metadata.get("source", "unknown")

                    import os
                    source_name = os.path.basename(source) if source != "unknown" else "unknown"  # 直接赋值未知来源
                    contexts.append(f"[{text} | 摘自:{source_name}] ")

            else:
                for doc, metadata in search_results:  # 返回文本本身检索的长度
                    source = metadata.get("source", "unknown")
                    import os
                    source_name = os.path.basename(source) if source != "unknown" else "unknown"
                    contexts.append(f"[{doc} | 摘自: {source_name}] ")
            # 统一拼接成提示词文本
            joined_ctx = "\n\n".join(f"{i + 1}.{ctx}" for i, ctx in enumerate(contexts))
            contexts_text = f"Rag检索结果按重要性依次排序如下:\n{joined_ctx}"
            # print("-----检索结果-----："+contexts_text)
            return {
                "contexts": contexts_text,
                "count": len(contexts)
            }
        except Exception as e:
            return {
                "contexts": "",  # 返回空内容
                "error": f"本次系统检索失败: {str(e)}"
            }

    def _run(self,
            query: str,
            strategy: str = "vector",
            top_k: int = 10,
            alpha: float = 0.6,
            use_rerank: bool = True,
            rerank_top_n: int = 3) -> dict:
        import asyncio
        return asyncio.run(self._arun(query, strategy, top_k, alpha, use_rerank, rerank_top_n))

async def _test_rag_tools():
    # 测试 rag_decide_strategy
    # decide_tool = rag_decide_strategy()
    # result = await decide_tool._arun("慢羊羊给懒羊羊的道具是什么呢?")
    # print("检索策略决策结果:", result)

    # 测试 rag_retrieve
    retrieve_tool = rag_retrieve()
    result = await retrieve_tool._arun(
        query="暗太狼是什么呢??",
        strategy="vector",
        top_k=5,
        use_rerank=True,
        rerank_top_n=3
    )
    print(result)

    # 测试 rag_rewrite_query
    rewrite_tool = rag_rewrite_query()
    result = await rewrite_tool._arun(
        question="慢羊羊给懒羊羊的道具是什么呢?",
        failure_reason="检索结果不相关"
    )
    print("重写后的查询:", result)
if __name__ == "__main__":
    import asyncio
    asyncio.run(_test_rag_tools())




