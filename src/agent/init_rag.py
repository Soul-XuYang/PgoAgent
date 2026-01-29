from agent.rag.RAGEngine import RagEngine
from agent.rag.loader import DocumentLoader,get_files_in_folder
from agent.rag.spliter import TextSplitter
from agent.config import FILE_PATH
from typing import Literal

def init_rag_engine(collection_name:str = "my_vector",path:str = FILE_PATH,file_name:str|list[str]=None,mode:str= Literal["semantic", "recursive"] | None ):
    """
    加载知识库文件并构建向量索引
    mode:分割模式，recursive递归分割，semantic语义分割,None则是针对markdown/html的标题分割
    path:文档路径
    file_name:文档名称或列表
    collection_name:向量库名称
    """
    engine = RagEngine(collection_name=collection_name,base_path=path) # 默认就是file_path路径
    documents = DocumentLoader().load_file(file_name) # 专门的内容加载器
    splitter_md = TextSplitter(mode =mode ) # 专门的分块器
    documents1 = splitter_md.split_documents(documents) # 分割后的文档
    engine.embed_data(documents1) # 构建向量索引
    return engine
# 初始化向量数据库的数据
if __name__ == "__main__":
   file,file_extension = get_files_in_folder(FILE_PATH)
   print(file)
   print(file_extension)
   init_rag_engine(file_name="矩阵.md",mode = "semantic")
