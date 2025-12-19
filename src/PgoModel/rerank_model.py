import asyncio

import aiohttp
import requests
from typing import List, Dict, TypedDict, NotRequired
from loguru import logger

class RerankRequest(TypedDict):
    model: str
    query: str
    documents: List[str]
    instruction: str
    top_n: int
    return_documents: bool
    max_chunks_per_doc: int
    overlap_tokens: int

class RerankResult(TypedDict):
    index: int
    relevance_score: float
    document: str  # 当 return_documents=True 时存在

class RerankResponse(TypedDict):
    results: List[RerankResult]
    usage: NotRequired[dict]  # token 使用信息
    model: str

class RerankModel: 
    """同步版 Rerank 模型类 
    - 仅支持Jina AI 重排序模型
    - 这里的token不是标准类型的，建议从rerank_documents获取token值
    """
    def __init__(self,model_name:str = "BAAI/bge-reranker-v2-m3", api_url: str = "https://api.openai.com/v1/rerank", api_key: str = None,timeout: int = 30, max_retries: int = 3):
        if not api_key:
            raise ValueError("请提供API密钥")
        self.api_url = api_url
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def rerank_documents(self, query: str, documents: List[str], instruction: str = "Please rerank the documents based on the query.", top_n: int = 4,
                    return_documents: bool = True, max_chunks_per_doc: int = 123, overlap_tokens: int = 79) -> Dict:
        """
        同步：根据查询和文档重新排序
        :param query: 查询文本
        :param documents: 文档列表
        :param instruction: 排序指令
        :param top_n: 返回排名前n的文档
        :param return_documents: 是否返回文档
        :param max_chunks_per_doc: 每个文档的最大块数
        :param overlap_tokens: 重叠的tokens数
        :return: 排序后的文档及其相关度分数
        """
        data: RerankRequest = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "instruction": instruction,
            "top_n": top_n,
            "return_documents": return_documents,
            "max_chunks_per_doc": max_chunks_per_doc,
            "overlap_tokens": overlap_tokens
        }
        # 因为这里获取的文本比较少-所以不用batch来分批次处理
        for attempt in range(self.max_retries):
            try:
                response = requests.post(self.api_url, headers=self.headers, json=data, timeout=self.timeout)
                response.raise_for_status()  # 如果返回的状态码是4xx或5xx，会抛出异常
                result: RerankResponse = response.json()
                return result  # 返回 API 返回的完整结果和token信息
            except requests.exceptions.Timeout:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    raise
            except requests.exceptions.RequestException as e:
                logger.error(f"请求失败: {e} (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    raise


class RerankModelAsync:
    """异步版 Rerank 模型类"""

    def __init__(self, model_name:str = "BAAI/bge-reranker-v2-m3",api_url: str = "https://api.siliconflow.cn/v1/rerank", api_key: str = None, timeout: int = 30,
                 max_retries: int = 3):
        if not api_key:
            raise ValueError("请提供API密钥")
        self.api_url = api_url
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.model_name = model_name
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def rerank_documents(self, query: str, documents: List[str], instruction: str= "Please rerank the documents based on the query.", top_k: int = 3,
                    return_documents: bool = True, max_chunks_per_doc: int = 123,
                    overlap_tokens: int = 40) -> Dict:
        """
        异步：根据查询和文档重新排序
        :param query: 查询文本
        :param documents: 文档列表
        :param instruction: 排序指令
        :param top_k: 返回排名前n的文档
        :param return_documents: 是否返回文档
        :param max_chunks_per_doc: 每个文档的最大块数
        :param overlap_tokens: 重叠的tokens数
        :return: 排序后的文档及其相关度分数和token信息
        """
        data: RerankRequest = {
            "model": self.model_name,
            "query": query,
            "documents": documents,
            "instruction": instruction,
            "top_n": top_k,
            "return_documents": return_documents,
            "max_chunks_per_doc": max_chunks_per_doc,
            "overlap_tokens": overlap_tokens
        }

        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(self.api_url, headers=self.headers, json=data,
                                            timeout=self.timeout) as response:
                        response.raise_for_status()  # 如果返回的状态码是4xx或5xx，会抛出异常
                        result: RerankResponse = await response.json()
                        return result  # 返回 API 返回的完整结果和token信息
            except asyncio.TimeoutError:
                logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    raise
            except aiohttp.ClientError as e:
                logger.error(f"请求失败: {e} (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    raise

async def test_rerank_model_async():
    from config import RERANK_API_KEY, RERANK_MODEL_URL
    reranker = RerankModelAsync(model_name="BAAI/bge-reranker-v2-m3",api_url=RERANK_MODEL_URL, api_key=RERANK_API_KEY)


    query = "Apple"
    documents = ["apple", "banana", "fruit", "vegetable","toys"]
    instruction = "Please rerank the documents based on the query."
    result = await reranker.rerank_documents(query, documents, instruction,top_k=3)
    print(result["results"])
    # 获取 token 使用情况

    logger.info(f"Reranked document indices: {[item['index'] for item in result['results']]}")
if __name__ == "__main__":
    # 创建Rerank模型实例
    # from config import RERANK_API_KEY, RERANK_MODEL_URL
    # rerank_model = RerankModel(model_name="BAAI/bge-reranker-v2-m3",api_url=RERANK_MODEL_URL, api_key=RERANK_API_KEY)
    # # 测试同步方法
    # query = "ChatGPT的定义是什么?"
    # documents = [
    #     "ChatGPT是一种基于人工智能的聊天机器人，它可以回答各种问题、提供建议和帮助。",
    #     "ChatGPT使用深度学习技术，它可以理解并生成自然语言，并给出合理的答案。",
    #     "ChatGPT可以用于各种场景，如客户服务、教育、娱乐等。"
    # ]
    # result1 = rerank_model.rerank_documents(query, documents, "Rerank the documents based on their relevance to the query.")
    # print(result1["results"])
    asyncio.run(test_rerank_model_async())

