from agent.rag.RAGEngine import RagEngine
from agent.rag.loader import DocumentLoader
from agent.rag.spliter import TextSplitter
from loader import get_files_in_folder
from config.logger_config import logger


if __name__ == "__main__":
    engine = RagEngine()
    loader = DocumentLoader() # 默认是配置文件路径
    splitter = TextSplitter()
    choose_all = True
    file_path = "xxx.docx"
    if choose_all:
        all_files, suffix = get_files_in_folder(loader.base_path)
        for file in all_files:
            # docs = loader.load_file(file)
            # chunks = splitter.split_documents(docs)
            # engine.embed_data(chunks)
            logger.info(f"本地向量数据库成功加载文件：{file}")
    else:
        docs = loader.load_file(file_path)
        chunks = splitter.split_documents(docs)
        engine.embed_data(chunks)  # 只在有新数据时跑一次
    logger.info(f"本地向量数据库初始化成功")

