import chromadb
from agent.config import DB_PATH,COLLECTION_NAME,logger

# 全局变量-这里用于数据库的测试使用
_chroma_client = None
_chroma_collection = None

def get_chroma_client(db_path:str = DB_PATH) -> chromadb.PersistentClient:
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=db_path)
    return _chroma_client

def get_chroma_collection(collection_name:str = COLLECTION_NAME):
    global _chroma_collection
    if _chroma_collection is None:
        client = get_chroma_client()
        _chroma_collection = client.get_or_create_collection(collection_name)
    return _chroma_collection
def delete_chroma_collection(collection_name: str, db_path: str=DB_PATH) -> bool:
    """删除指定的集合"""
    try:
        client = get_chroma_client(db_path)
        # 检查集合是否存在
        if collection_name in [col.name for col in client.list_collections()]:
            client.delete_collection(collection_name)
            # 如果删除的是当前缓存的集合，清除缓存
            logger.info(f"成功删除chromadb的表: {collection_name}")
            return True
        else:
            logger.warning(f"chromadb表 {collection_name} 不存在.")
            return False
    except Exception as e:
        logger.error(f"删除chromadb的表错误: {collection_name}: {str(e)}")
        return False


def close_chroma():
    global _chroma_client, _chroma_collection
    if _chroma_client is not None:
        try:
            if hasattr(_chroma_client, 'close'):
                _chroma_client.close()
        except Exception as e:
            print(f"Error closing ChromaDB client: {e}")
        finally:
            _chroma_client = None
            _chroma_collection = None

def get_all_docs():
    collection = get_chroma_collection()
    results = collection.get(include=['documents', 'metadatas', 'embeddings'])
    for i in range(len(results['ids'])):
        print(f"文档ID: {results['ids'][i]}")
        print(f"内容: {results['documents'][i]}")
        print(f"元数据: {results['metadatas'][i]}")
        print(f"向量: {results['embeddings'][i]}")
        print("-" * 50)

# def get_all_docs():
#     results = _collection.get(include=['documents', 'metadatas', 'embeddings'])
#     for i in range(len(results['ids'])):
#         print(f"文档ID: {results['ids'][i]}")
#         print(f"内容: {results['documents'][i]}")
#         print(f"元数据: {results['metadatas'][i]}")
#         print(f"向量: {results['embeddings'][i]}")
#         print("-" * 50)