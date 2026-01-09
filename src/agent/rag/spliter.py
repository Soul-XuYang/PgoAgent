from __future__ import annotations

import re
from typing import Literal, Sequence, Any
import json

from langchain_experimental.text_splitter import SemanticChunker
from langchain_text_splitters import (
    HTMLHeaderTextSplitter,
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

try:
    # 与 RAGEngine 对齐，默认复用全局嵌入模型
    from agent.config.basic_config import embedder as default_embedder, FILE_PATH
except Exception:
    default_embedder = None  # 允许外部注入
    FILE_PATH = "../../file"

# 统一的分隔符配置
DEFAULT_SEPARATORS: list[str] = [
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

# Markdown / HTML 标题切分规则
DEFAULT_MARKDOWN_HEADERS = [
    ("#", "标题"),
    ("##", "大章节"),
    ("###", "小节"),
    ("####", "小点"),
]
DEFAULT_HTML_HEADERS = [
    ("h1", "章节 1"),
    ("h2", "小节 2"),
    ("h3", "小点 3"),
    ("h4", "子点 4"),
]
class TextSplitter:
    """
    多策略分割器封装，统一暴露 split_text / split_documents。
    - strategy（mode）描述“怎么切”：semantic / recursive
    - file_type 仅做文件类型提示：
        * markdown/html 自动走标题切分
        * 其它（txt/json/csv/word/pdf等）默认递归字符切分
    """

    def __init__(
        self,
        mode: Literal["semantic", "recursive"] | None = "recursive",
        *,
        file_type: Optional[str] = None,
        embedder=None,
        chunk_size: int = 200,
        chunk_overlap: int = 20,
        separators: Optional[Sequence[str]] = None,
        markdown_headers: Optional[Sequence[tuple[str, str]]] = None,
        html_headers: Optional[Sequence[tuple[str, str]]] = None,
    ):
        """
        初始化分割器，根据mode选择对应的分割器
        :param mode: 分割策略["semantic", "recursive"]；None 则依据 file_type 推断,markdown/html 自动走标题切分
        :param file_type: 文件类型提示（如 "txt" / "json" / "md" / "html" / "pdf" 等），md/html 自动走标题切分
        :param embedder: 语义模型
        :param chunk_size: 块大小
        :param chunk_overlap: 块重叠
        :param separators: 分隔符
        :param markdown_headers: Markdown 标题
        :param html_headers: HTML 标题
    """    
        self.file_type = (file_type or "").lower() or None
        # 默认对 md/html 进行专门的标题分割，其余走递归
        if mode is None:
            if self.file_type in {"md", "markdown"}:
                self.mode = "markdown"
            elif self.file_type in {"html", "htm"}:
                self.mode = "html"
            else:
                self.mode = "recursive"
        else:
            self.mode = mode
        self.embedder = embedder or default_embedder
        self.separators = list(separators or DEFAULT_SEPARATORS)
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.markdown_headers = markdown_headers or DEFAULT_MARKDOWN_HEADERS
        self.html_headers = html_headers or DEFAULT_HTML_HEADERS

        self.splitter = self._create_splitter() # 创建对应的分割器

    # ============ 公共方法 ============
    def split_text(self, text: str) -> List[Document]: # 输入纯文本，输出 Document 列表。
        """输入纯文本，自动对文本进行了清洗再进行分割，输出 Document 列表。"""
        text = self._ensure_text(text)
        text = self.clean_text(text)
        if self.mode in {"semantic"}:
            return self.splitter.create_documents([text]) # 直接返回 SemanticChunker 的结果
        if self.mode in {"markdown", "html"}:
            return self.splitter.split_text(text) # 按照标题和段落分割
        # 默认recursive模式分割
        chunks = self.splitter.split_text(text) # 这里是其它情况都不满足默认使用递归分割
        return [Document(page_content=chunk) for chunk in chunks] # 强制转换为document

    def split_documents(self, docs: List[Document]) -> List[Document]:  # 输入 Document 列表，输出 Document 列表。
        """
        输入 Document 列表，输出 Document 列表。
        semantic/recursive 直接保持原 metadata；markdown/html 默认取首个文档作为文档来源。
        """
        if not docs:
            return []

        if self.mode == "semantic":
            # SemanticChunker 不接受 Document，需要取出文本
            texts = [self._ensure_text(d.page_content) for d in docs]
            semantic_docs = self.splitter.create_documents(texts)
            # 透传简单 metadata（只透首个 source，避免过度覆盖）
            source = docs[0].metadata.get("source") if docs[0].metadata else None
            if source:
                for d in semantic_docs:
                    d.metadata.setdefault("source", source)
            return semantic_docs

        if self.mode == "recursive":
            return self.splitter.split_documents(docs) # 按照递归分块

        if self.mode in {"markdown", "html"}:
            # 合并所有文档内容，用双换行符保持文档间的分隔
            combined_text = "\n\n".join(self._ensure_text(doc.page_content) for doc in docs)
            # 对合并后的文本进行分割
            split_docs = self.splitter.split_text(combined_text)
            # 保留原始文档的 metadata
            source = docs[0].metadata.get("source") if docs[0].metadata else None
            if source:
                for d in split_docs:
                    d.metadata.setdefault("source", source)
            return split_docs

        return []
    # 分割器
    def _create_splitter(self):
        if self.mode == "semantic":
            if self.embedder is None:
                raise ValueError("语义分块需要提供嵌入模型embedder")
            return SemanticChunker(self.embedder, breakpoint_threshold_type="percentile")

        if self.mode == "recursive":
            return RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                length_function=len,
                separators=self.separators,
                is_separator_regex=False,
            )

        if self.mode == "markdown":
            return MarkdownHeaderTextSplitter(self.markdown_headers)

        if self.mode == "html":
            return HTMLHeaderTextSplitter(self.html_headers)

        raise ValueError(f"不支持的该分割模式:{self.mode}")
    @staticmethod
    def _ensure_text(content: Any) -> str:
        """确保内容为字符串，处理 JSONLoader 返回的 dict/list 场景。"""
        if isinstance(content, str):
            return content
        try:
            return json.dumps(content, ensure_ascii=False)
        except Exception:
            return str(content)
    @staticmethod
    def split_origin_text( doc_file, batch_size=10000) -> List[str]: # 工具函数
        with open(doc_file, 'r', encoding='utf-8') as f:
            context = f.read()
            chunk_list = []
            for i in range(0, len(context), batch_size):
                batch_texts = context[i:i + batch_size]
                chunk_list.extend([chunk for chunk in batch_texts.split('\n\n') if chunk.strip()])
        return chunk_list
    @staticmethod
    def clean_text(text: str) -> str:  # 清洗不必要的文本换行符
        """清理文本，去除多余的空白字符"""
        # 去除多余的换行符
        text = re.sub(r'\n+', '\n', text)
        # 去除行首行尾的空白
        text = '\n'.join(line.strip() for line in text.split('\n'))
        # 去除段落间的多余空格
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text



# ============ 简单演示 ============
if __name__ == "__main__":
    markdown_splitter = TextSplitter(mode="markdown")
    from loader import *
    from pprint import pprint
    loader = DocumentLoader()
    print(loader.base_path)
    # 2. 获取文件夹中的文件列表（纯逻辑）
    print("当前工作目录:", os.getcwd())
    file_lists, extensions = get_files_in_folder(str(loader.base_path))
    print(f"文件列表: {file_lists}")
    print(f"扩展名列表: {extensions}")
    if len(file_lists) > 0 and 'md' in extensions:
        md_file = file_lists[extensions.index('md')]  # 获取对应md格式的索引
        print(md_file)
        md_documents = loader.load_file(md_file, file_type='markdown', mode='elements')
        print(md_documents) # 文档数据
        print(TextSplitter.split_origin_text(os.path.join(FILE_PATH, md_file))) # 分割后的文本
        pprint(markdown_splitter.split_documents(md_documents))


