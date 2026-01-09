import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
load_dotenv()  # 加载环境变量
db_url = os.getenv("DATABASE_URL")

def check_checkpoint_exist(db_url):
    try:
        with ConnectionPool(db_url, min_size=1, max_size=5,timeout= 10) as pool:
            with pool.connection() as conn: # 获取连接
                with conn.cursor() as cur:
                    # 一次性检查两个表，COUNT(*) 会统计查询结果中的总行数
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        AND table_name IN ('checkpoints', 'checkpoint_writes','checkpoint_blobs'')
                    """)
                    table_count = cur.fetchone()[0]
                    return table_count == 2
    except Exception as e:
        print(f"检查数据表是否存在时发送错误: {e}")
        return False
def delete_checkpoint_by_thread_id(db_url: str, thread_id: str):
    """删除特定 thread_id 的所有 checkpoint（短期记忆）"""
    try:
        with ConnectionPool(db_url, min_size=1, max_size=5, timeout=10) as pool:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # 按依赖顺序删除
                    cur.execute("DELETE FROM checkpoint_writes WHERE thread_id = %s", (thread_id,))
                    cur.execute("DELETE FROM checkpoint_blobs  WHERE thread_id = %s", (thread_id,))
                    cur.execute("DELETE FROM checkpoints       WHERE thread_id = %s", (thread_id,))
                conn.commit()
        print(f"已删除 thread_id={thread_id} 的所有 checkpoint 记录")
        return True
    except Exception as e:
        print(f"删除 thread_id={thread_id} 的 checkpoint 失败: {e}")
        return False

def drop_all_checkpoint_tables(db_url: str, drop_migrations: bool = False):
    """
    删除所有 checkpoint 相关表（表结构也删掉）。

    参数:
      - drop_migrations: 是否连 checkpoint_migrations 一起删。
        True = 彻底重置（下次必须 setup）
        False = 保留迁移记录（但主表没了，下次仍需 setup）
    """
    try:
        with ConnectionPool(db_url, min_size=1, max_size=5, timeout=10) as pool:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # 依赖顺序：先删 writes / blobs，再删 checkpoints
                    cur.execute("DROP TABLE IF EXISTS checkpoint_writes CASCADE;")
                    cur.execute("DROP TABLE IF EXISTS checkpoint_blobs CASCADE;")
                    cur.execute("DROP TABLE IF EXISTS checkpoints CASCADE;")
                    cur.execute("DROP TABLE IF EXISTS checkpoint_migrations CASCADE;")
                conn.commit()
        print("✅ 已删除所有 checkpoint 相关表")
        if drop_migrations:
            print("（checkpoint_migrations 也已删除）")
        else:
            print("（checkpoint_migrations 已保留）")
        return True
    except Exception as e:
        print(f"❌ 删除 checkpoint 表失败: {e}")
        return False

def check_store_exist(db_url):
    """检查store相关表是否存在"""
    try:
        with ConnectionPool(db_url, min_size=1, max_size=5, timeout=10) as pool:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    # 检查items表是否存在
                    cur.execute("""
                        SELECT COUNT(*) 
                        FROM information_schema.tables 
                        WHERE table_schema = 'public'
                        AND table_name = 'items'
                    """)
                    table_count = cur.fetchone()[0]
                    return table_count == 1
    except Exception as e:
        print(f"检查store表是否存在时发生错误: {e}")
        return False
def delete_store_item_by_key(db_url, key):
    """删除store表中特定key的记录"""
    try:
        with ConnectionPool(db_url, min_size=1, max_size=5, timeout=10) as pool:
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        DELETE FROM items 
                        WHERE key = %s
                    """, (key,))
                    conn.commit()
                    print(f"已删除store表中key为 {key} 的记录")
                    return True

    except Exception as e:
        print(f"删除store表中key为 {key} 的记录时发生错误: {e}")
        return False
if __name__ == "__main__":
    print(check_checkpoint_exist(db_url))
    delete_checkpoint_by_thread_id(db_url,"1")







