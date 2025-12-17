import asyncio

from loguru import logger
import sys
import time
logger.remove()  # 移除默认的日志处理器
logger.add(sys.stdout, level="INFO", format="{time:YYYY-MM-DD|HH:mm:ss} - {level} - {message}") # 只有ERROR级别以上的日志才会被输出到控制台
logger.add("app.logs", rotation="100 MB", mode="a") # 续写日志

def time_logger(fn):
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        try:
            return fn(*args, **kwargs)
        finally:
            logger.info(f"{fn.__name__} took {(time.time() - start) * 1000:.1f} ms")

    async def async_wrapper(*args, **kwargs):
        start = time.time()
        try:
            return await fn(*args, **kwargs)
        finally:
            logger.info(f"{fn.__name__} took {(time.time() - start) * 1000:.1f} ms")

    # 根据函数类型返回对应的包装器
    return async_wrapper if asyncio.iscoroutinefunction(fn) else sync_wrapper