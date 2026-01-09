import asyncio


import aiohttp
import requests
import time
import numpy as np
from typing import List, Union, TypedDict
from langchain.embeddings.base import Embeddings
from agent.config.logger_config import logger

class EmbeddingRequest(TypedDict):
    model: str
    input: List[str]
    encoding_format: str
    dimensions: int

class EmbeddingModel(Embeddings):
    """一个兼容LangChain Embeddings接口等硅基流动同步封装类
    该类封装了OpenAI Embeddings API的官方标准格式，提供了向量嵌入的功能。
    支持批量处理、重试机制、超时控制等特性。
    Args:
        model_name (str): 模型名称，默认为"OpenAI"
        api_url (str): API接口地址，默认为OpenAI官方地址
        api_key (str): API密钥，必须提供
        timeout (int): 请求超时时间（秒），默认30秒
        max_retries (int): 最大重试次数，默认3次
        encoding_format (str): 编码格式，默认为"float"
        dimensions (int): 向量维度，默认1024
        batch_size (int): 批处理大小，默认128
        request_interval (float): 请求间隔时间（秒），默认1.0秒

    Note:
        - 仅支持OpenAI Embeddings API的官方标准格式
        - 需要提供有效的API密钥
        - 建议根据实际需求调整batch_size和request_interval参数
    """
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5", api_url: str = "https://api.openai.com/v1/embeddings", api_key: str = None, timeout: int = 30, max_retries: int = 3, encoding_format: str = "float",
                dimensions: int = 1024, batch_size: int = 128,request_interval: int = 1.0):
        self.model_name = model_name
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("请提供API密钥或设置对应的密钥的环境变量")
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = timeout
        self.max_retries = max_retries
        self.encoding_format = encoding_format
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.request_interval = request_interval

    def _embed(self, texts: List[str]) -> List[List[float]]:
        """
        内部方法：批量编码文本为向量（同步）
        :param texts: 文本列表
        :return: 向量列表的列表
        """
        if not texts:
            return []

        all_embeddings = []
        batch_size = min(self.batch_size, len(texts))

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size] # 每次请求的文本长度
            # 自动根据用用户的输入请求来构建
            data: EmbeddingRequest = {
                "model": self.model_name,
                "input": batch_texts,
                "encoding_format": self.encoding_format,
                "dimensions": self.dimensions
            }
            for attempt in range(self.max_retries):
                try:
                    response = requests.post(self.api_url, json=data, headers=self.headers, timeout=self.timeout)

                    if response.status_code == 429 or response.status_code == 403:
                        wait_time = (attempt + 1) * 2
                        logger.warning(f"遇到速率限制 (状态码: {response.status_code})，等待 {wait_time}s 后重试...")
                        time.sleep(wait_time)
                        if attempt == self.max_retries - 1:
                            logger.error(f"API响应: {response.text}")
                            raise
                        continue

                    response.raise_for_status()
                    result = response.json()

                    if "data" not in result:
                        raise ValueError(f"API响应格式错误: {result}")

                    embedding_vectors = [item["embedding"] for item in result["data"]]
                    all_embeddings.extend(embedding_vectors)

                    if "usage" in result:
                        if not hasattr(self, 'token_usage'):
                            self.token_usage = {"prompt_tokens": 0, "total_tokens": 0}
                        self.token_usage["prompt_tokens"] += result["usage"].get("prompt_tokens", 0)
                        self.token_usage["total_tokens"] += result["usage"].get("total_tokens", 0)

                    if i + batch_size < len(texts):
                        time.sleep(self.request_interval)

                    break

                except requests.exceptions.Timeout:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                    time.sleep(1)

                except requests.exceptions.RequestException as e:
                    if attempt == self.max_retries - 1:
                        raise
                    logger.error(f"请求失败: {e} (尝试 {attempt + 1}/{self.max_retries})")
                    time.sleep((attempt + 1) * 2)

                except (KeyError, ValueError) as e:
                    logger.error(f"响应解析失败: {e}")
                    raise
            else:
                raise RuntimeError("达到最大重试次数")

        return all_embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        :param texts: 文档文本列表
        :return: 向量列表的列表
        """
        return self._embed(texts)

    def embed_query(self, text: str) -> List[float]:
        """
        :param text: 查询文本
        :return: 向量列表
        """
        embedding_vector = self._embed([text])
        return embedding_vector[0]  # 获得第一个即可

    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        兼容SentenceTransformer的encode方法（可选，用于向后兼容）
        :param texts: 单个文本字符串或文本列表
        :return: 向量列表（单个文本）或向量列表的列表（多个文本）
        """
        if isinstance(texts, str):
            return self.embed_query(texts)
        else:
            return self.embed_documents(texts)

    def get_usage(self) -> dict:
        """
        返回嵌入模型总体的token的使用量
        :return: token使用情况
        """
        return getattr(self, 'token_usage', {})
class EmbeddingModelAsync(Embeddings):
    """异步版嵌入模型类
    Args:
        model_name (str): 模型名称，默认为"OpenAI"
        api_url (str): API接口地址，默认为OpenAI官方地址
        api_key (str): API密钥，必须提供
        timeout (int): 请求超时时间（秒），默认30秒
        max_retries (int): 最大重试次数，默认3次
        encoding_format (str): 编码格式，默认为"float"
        dimensions (int): 向量维度，默认1024
        batch_size (int): 批处理大小，默认128
        request_interval (float): 请求间隔时间（秒），默认1.0秒

    Note:
        - 仅支持OpenAI Embeddings API的官方标准格式
        - 需要提供有效的API密钥
        - 建议根据实际需求调整batch_size和request_interval参数
    """
    def __init__(self, model_name: str = "BAAI/bge-large-zh-v1.5", api_url: str = "https://api.openai.com/v1/embeddings", api_key: str = None, timeout: int = 30, max_retries: int = 3, encoding_format: str = "float",
                 dimensions: int = 1024, batch_size: int = 128,request_interval: int = 1.0):
        self.model_name = model_name
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("请提供API密钥或设置对应的密钥的环境变量")
        self.api_url = api_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        self.timeout = timeout
        self.max_retries = max_retries
        self.encoding_format = encoding_format
        self.dimensions = dimensions
        self.batch_size = batch_size
        self.request_interval = request_interval

    async def _async_request(self, session, data, attempt):
        """发送异步请求并处理响应"""
        try:
            async with session.post(self.api_url, json=data, headers=self.headers, timeout=self.timeout) as response:
                if response.status == 429 or response.status == 403: # 如果遇到速率限制
                    wait_time = (attempt + 1) * 2
                    logger.warning(f"目前遇到速率限制 (状态码: {response.status})，等待 {wait_time}s 后重试...")
                    await asyncio.sleep(wait_time)
                    if attempt == self.max_retries - 1:
                        response_text = await response.text()
                        logger.error(f"API响应: {response_text}")
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                    return []

                response.raise_for_status()
                result = await response.json()

                if "data" not in result:
                    raise ValueError(f"API响应格式错误: {result}")

                embedding_vectors = [item["embedding"] for item in result["data"]]

                if "usage" in result:
                    if not hasattr(self, 'token_usage'):
                        self.token_usage = {"prompt_tokens": 0, "total_tokens": 0}
                    self.token_usage["prompt_tokens"] += result["usage"].get("prompt_tokens", 0)
                    self.token_usage["total_tokens"] += result["usage"].get("total_tokens", 0)

                return embedding_vectors
        except asyncio.TimeoutError:
            if attempt == self.max_retries - 1:
                raise
            logger.warning(f"请求超时 (尝试 {attempt + 1}/{self.max_retries})")
            await asyncio.sleep(1)
        except Exception as e:
            if attempt == self.max_retries - 1:
                raise
            logger.error(f"请求失败: {e} (尝试 {attempt + 1}/{self.max_retries})")
            await asyncio.sleep((attempt + 1) * 2)
        return []

    async def _embed(self, texts: List[str]) -> List[List[float]]:
        """批量编码文本为向量（异步）"""
        if not texts:
            return []

        all_embeddings = []
        batch_size = min(self.batch_size, len(texts))
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i + batch_size]
                data: EmbeddingRequest = {
                    "model": self.model_name,
                    "input": batch_texts,
                    "encoding_format": self.encoding_format,
                    "dimensions": self.dimensions
                }
                for attempt in range(self.max_retries):
                    result = await self._async_request(session, data, attempt)
                    if result:
                        all_embeddings.extend(result)
                        break
                else:
                    raise RuntimeError("达到最大重试次数")

                if i + batch_size < len(texts):
                    await asyncio.sleep(self.request_interval)

        return all_embeddings

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """
        :param texts: 文档文本列表
        :return: 向量列表的列表
        """
        return await self._embed(texts)

    async def embed_query(self, text: str) -> List[float]:
        """
        :param text: 查询文本
        :return: 向量列表
        """
        embedding_vector = await self._embed([text])
        return embedding_vector[0]  # 获得第一个即可

    def encode(self, texts: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
        """
        兼容SentenceTransformer的encode方法（可选，用于向后兼容）
        :param texts: 单个文本字符串或文本列表
        :return: 向量列表（单个文本）或向量列表的列表（多个文本）
        """
        if isinstance(texts, str):
            return asyncio.run(self.embed_query(texts))
        else:
            return asyncio.run(self.embed_documents(texts))

    def get_usage(self) -> dict:
        """
        返回异步嵌入模型总体的token的使用量
        :return: token使用情况
        """
        return getattr(self, 'token_usage', {})
# 需要在嵌入模型中添加归一化处理
def check_normalization(embedding: List[float]) -> bool:
    """检查向量是否已L2归一化"""
    vec = np.array(embedding)
    norm = np.linalg.norm(vec) # 范数L2
    return abs(norm - 1.0) < 1e-6  # 允许小的浮点误差
# 使用示例
if __name__ == "__main__":
    # 1. 初始化
    from agent.config.basic_config import EMBEDDING_API_KEY,EMBEDDING_MODEL_URL
    embedder = EmbeddingModel(
        model_name="BAAI/bge-large-zh-v1.5",
        api_url=EMBEDDING_MODEL_URL,
        api_key=EMBEDDING_API_KEY
    )

    # 2. 测试LangChain接口
    documents = ["这是第一个文档", "这是第二个文档"]
    embeddings = embedder.embed_documents(documents)
    print(f"文档向量数量: {len(embeddings)}")
    print(f"第一个文档向量维度: {len(embeddings[0])}")
    print(check_normalization(embeddings[0]))
    print(embedder.get_usage())
    print(50*'-')
    query_embedding = embedder.embed_query("查询第二个文档")
    print(f"查询向量维度: {len(query_embedding)}")
    print(check_normalization(query_embedding))
    print(embedder.get_usage())
