from typing import List, Optional, Tuple
from pathlib import Path
from bs4 import SoupStrainer
import os
os.environ.setdefault("USER_AGENT", "PgoAgent/1.0") # 设置网络请求来源
from config.basic_config import FILE_PATH
from langchain_community.document_loaders import (
    WebBaseLoader,
    JSONLoader,
    UnstructuredMarkdownLoader,
    PyPDFLoader,
    UnstructuredWordDocumentLoader,
    TextLoader
)
from langchain_core.documents import Document

# 不用本地的html直接网络搜索即可
SUPPORTED_EXTENSIONS = {
    'md': 'markdown',
    'txt': 'text',
    'pdf': 'pdf',
    'docx':'word',
    'csv': 'csv',
    'json': 'json',
}
# ====================== 文件类 ======================
def _get_loader(file_path: Path, file_type: str, encoding: str, **kwargs):
    """
    私有方法：根据文件类型创建对应的加载器（内部资源管理）
    :param file_path: 文件路径对象
    :param file_type: 文件类型
    :param encoding: 文件编码
    :param kwargs: 其他参数
    :return: 对应的加载器实例
    """
    file_path_str = str(file_path)
    if file_type == 'json':
        jq_schema = kwargs.get('jq_schema', '.')
        text_content = kwargs.get('text_content', True)  # 默认为True
        loader_json = JSONLoader(
            file_path=file_path_str,
            jq_schema=jq_schema,
            text_content=text_content  # 文本参数
        )
        # 如果提供了自定义metadata函数，则设置它
        if 'create_json_metadata' in kwargs:
            loader_json.create_json_metadata = kwargs['create_json_metadata'] # 设置对应的函数
        return loader_json
    elif file_type == 'markdown':
        markdown_mode = kwargs.get('markdown_mode', 'elements')
        return UnstructuredMarkdownLoader(
            file_path=file_path_str,
            encoding=encoding,
            mode=markdown_mode
        )
    elif file_type == 'word':
        mode_word = kwargs.get('word_mode', 'elements')
        strategy = kwargs.get('word_strategy', 'fast')
        return UnstructuredWordDocumentLoader(
            file_path=file_path_str,
            mode=mode_word ,  # 将文档拆分为元素
            strategy=strategy,  # 使用快速策略
    )
    elif file_type == 'pdf':
        extract_images = kwargs.get('extract_images', False)
        return PyPDFLoader(file_path=file_path_str, extract_images=extract_images)

    elif file_type == 'text':
        return TextLoader(file_path=file_path_str, encoding=encoding)
    else:
        raise ValueError(f"不支持的文件类型：{file_type}")


def load_web_page(
        url: str,
    encoding: str = 'utf-8',
    css_selector: Optional[str] = None,
    **kwargs
) -> List[Document]:
    """
    资源访问方法：加载网页内容
    :param url: 网页URL
    :param encoding: 编码，默认为'utf-8'
    :param css_selector: CSS选择器，用于只解析特定内容（如class_="md-content"）
    :param kwargs: 其他参数
    :return: Document列表
    """
    bs_kwargs = {}
    if css_selector:
        bs_kwargs['parse_only'] = SoupStrainer(class_=css_selector)

    loader = WebBaseLoader(
        web_paths=url,
        encoding=encoding,
        bs_kwargs=bs_kwargs
    )

    return loader.load()


class DocumentLoader:
    def __init__(self, base_path: str = None):
        """
        初始化文档加载器
        :param base_path: 基础文件路径，默认使用配置文件中的路径
        """
        self.base_path = Path(base_path) if base_path else Path(FILE_PATH)
        if not self.base_path.exists():
            raise FileNotFoundError(f"基础的知识库路径不存在：{self.base_path}")

    # 加载单个文件
    def load_file( self,file_path: str,file_type: Optional[str] = None,encoding: str = 'utf-8',**kwargs) -> list[
        Document]:
        """
        资源访问方法：加载单个文件
        :param file_path: 文件路径（可以是相对路径或绝对路径）
        :param file_type: 文件类型（'csv', 'json', 'markdown', 'pdf', 'text', 'web'），如果为None则自动推断
        :param encoding: 文件编码，默认为'utf-8'
        :param kwargs: 其他加载器特定参数
        :return: Document列表
        """
        file_path_obj = Path(file_path) # 当成路径来操作
        
        # 如果是相对路径，则基于base_path解析
        if not file_path_obj.is_absolute(): # 相对路径就在默认路径下拼接
            file_path_obj = self.base_path / file_path_obj # Path对象
        
        if not file_path_obj.exists(): # 路径不存在
            raise FileNotFoundError(f"文件路径不存在：{file_path_obj}")
        
        # 自动推断文件类型
        if file_type is None:
            extension = file_path_obj.suffix.lower().lstrip('.') # 获取扩展名
            file_type = SUPPORTED_EXTENSIONS.get(extension, 'text') # 默认按txt文件读
        
        # 根据文件类型选择对应的加载器
        data_loader = _get_loader(file_path_obj, file_type, encoding, **kwargs)
        documents = data_loader.load()
        
        return documents

    def load_folder(
            self,
            folder_path: str = None,
            file_extensions: List[str] = None,
            encoding: str = 'utf-8',
            **kwargs
    ) -> List[Document]:
        if folder_path is None:
            folder_path = self.base_path
        else:
            folder_path = Path(folder_path)
            if not folder_path.is_absolute():
                folder_path = self.base_path / folder_path

        if not folder_path.exists():
            raise FileNotFoundError(f"文件夹路径不存在：{folder_path}")

        # 这里是“允许加载的扩展名集合”
        allowed_exts = set(file_extensions or SUPPORTED_EXTENSIONS.keys())

        all_documents = []
        files, suffixes = get_files_in_folder(str(folder_path))

        for file_name, ext in zip(files, suffixes):
            if ext not in allowed_exts: # 不在所需的拓展名里就跳过
                continue
            try:
                file_path = folder_path / file_name
                docs = self.load_file(str(file_path), encoding=encoding, **kwargs)
                all_documents.extend(docs)
                print(f"成功加载文件：{file_name}，共{len(docs)}个文档")
            except Exception as e:
                print(f"加载文件失败：{file_name}，错误：{str(e)}")
                continue

        return all_documents


def get_files_in_folder(folder_path: str) -> Tuple[List[str], List[str]]:
    """
    获取文件夹中的文件列表
    :param folder_path: 文件夹路径
    :return: 文件列表，文件扩展名列表
    """
    files = []
    suffix = []
    folder = Path(folder_path) # 对应路径的文件夹
    if not folder.exists():
        raise FileNotFoundError(f"文件夹不存在：{folder_path}")

    for file_path in folder.iterdir(): # 遍历文件夹中的文件
        if file_path.is_file():
            files.append(file_path.name)
            suffix.append(file_path.suffix.lower().lstrip('.'))

    return files, suffix

# ====================== 测试代码 ======================

if __name__ == "__main__":
    # 1. 初始化文档加载器（资源初始化）
    loader = DocumentLoader()
    print(loader.base_path)
    # 2. 获取文件夹中的文件列表（纯逻辑）
    print("当前工作目录:", os.getcwd())
    file_lists, extensions = get_files_in_folder(str(loader.base_path))
    print(f"文件列表: {file_lists}")
    print(f"扩展名列表: {extensions}")
    # 1. 加载Markdown文件（资源访问方法）
    if len(file_lists) > 0 and 'md' in extensions:
        md_file = file_lists[extensions.index('md')] # 获取对应md格式的索引
        md_documents = loader.load_file(md_file, file_type='markdown', mode='elements')
        print(md_documents)
        for doc in md_documents:
            print(doc.page_content)
        print(f"\nMarkdown文件加载结果（共{len(md_documents)}个文档）")
    # 2. 加载PDF文件（资源访问方法）
    if len(file_lists) > 0 and 'pdf' in extensions:
        pdf_file = file_lists[extensions.index('pdf')]
        pdf_documents = loader.load_file(pdf_file, file_type='pdf', extract_images=True)
        for doc in pdf_documents:
            print(doc.page_content)
        print(f"\nPDF文件加载结果（共{len(pdf_documents)}个文档）")
    # 3. 加载JSON文件（资源访问方法）
    if len(file_lists) > 2 and 'json' in extensions:
        json_file = file_lists[extensions.index('json')]
        print(json_file)
        def create_json_metadata(record: dict, metadata: dict) -> dict:
            """自定义JSON metadata函数，提取产品相关信息"""
            # 添加产品ID到元数据
            metadata["product_id"] = record.get("id", "")
            # 添加产品类别到元数据
            metadata["category"] = record.get("category", "")
            return metadata

        json_documents = loader.load_file(
            json_file,
            file_type='json',
            jq_schema=".store.products[]",  # 这里是stor下的products
            text_content=False,  # 添加这个参数，允许返回字典内容
            create_json_metadata=create_json_metadata
        )
        print(f"\nJSON文件加载结果：{json_documents}")
    # 4. 加载Word文件（资源访问方法）
    if len(file_lists) > 0 and 'docx' in extensions:
        docx_file = file_lists[extensions.index('docx')]
        word_documents = loader.load_file(
            docx_file,
            file_type='word',
            word_mode='elements',  # 使用elements模式，将文档拆分为元素
            word_strategy='fast'   # 使用快速策略
        )
        print(f"\nWord文件加载结果（共{len(word_documents)}个文档）：")
        for i, doc in enumerate(word_documents):
            print(f"\n--- 文档 {i+1} ---")
            print(f"内容预览: {doc.page_content[:400]}...")  # 只显示前200个字符
            if doc.metadata:
                print(f"元数据: {doc.metadata}")
