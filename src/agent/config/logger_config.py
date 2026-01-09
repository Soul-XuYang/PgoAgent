import asyncio
from pathlib import Path
from loguru import logger
import sys
import time
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True) # 确保存在
LOG_FILE = LOG_DIR / "py.log"  # 推荐用.log后缀，也可以改为app.logs
logger.remove()  # 移除默认的日志处理器
logger.add(sys.stdout, level="DEBUG", format="{time:YYYY-MM-DD|HH:mm:ss} - {level} - {message}",colorize=True) # 只有ERROR级别以上的日志才会被输出到控制台
logger.add(LOG_FILE, rotation="100 MB", mode="a",retention="7 days",encoding="utf-8") # 续写日志

def time_logger(fn):
    def sync_wrapper(*args, **kwargs):
        start = time.time()
        try:
            return fn(*args, **kwargs) # 包装器
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
