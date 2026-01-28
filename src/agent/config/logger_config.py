import asyncio
from pathlib import Path
from loguru import logger
import sys
import time
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True) # 确保存在
LOG_PATH = LOG_DIR / "py.log"  # 推荐用.log后缀，也可以改为app.logs
# 日志-大于等于打印: TRACE DEBUG INFO WARNING ERROR CRITICAL
level_map = {
    "trace": "TRACE",
    "debug": "DEBUG",
    "info": "INFO",
    "warning": "WARNING",
    "error": "ERROR",
    "critical": "CRITICAL"
}
def setup_logger(
        log_level: str = "DEBUG",
        rotation: str = "100 MB",
        retention: str = "7 days",
        encoding: str = "utf-8",
        mode: str = "a",
        colorize: bool = True,
        log_format: str = "{time:YYYY-MM-DD|HH:mm:ss} - {level} - {message}",
        enable_console:bool = True,
        enable_warn_error: bool = False,
        enable_all_log = True,
        log_file: str = "all.log",
        warn_error_file: str = "warn_error.log",
) -> None:
    """
    设置日志记录参数
    Args:
        log_level (str): 默认日志级别
        log_file (str): 所有日志的文件名
        warn_error_file (str): 警告和错误日志的文件名
        rotation (str): 日志轮转大小
        retention (str): 日志保留时间
        encoding (str): 日志文件编码
        mode (str): 日志写入模式
        colorize (bool): 是否在控制台输出彩色日志
        log_format (str): 日志格式
        enable_all_log(bool): 是否启用所有日志
        enable_console(bool): 是否控制台进行日志输出,
        enable_warn_error(bool): 是否启用警告和错误日志

    """
    # 移除默认的日志处理器
    logger.remove()
    level = log_level.lower()
    if level not in level_map:
        raise ValueError(f"无效的日志级别: {level}")
    # 控制台输出
    if enable_console:
        logger.add(
            sys.stdout,
            level=level_map[level],
            format=log_format,
            colorize=colorize
        )
    # 警告和错误日志文件
    if enable_warn_error:
        warn_error_file = LOG_PATH / warn_error_file
        logger.add(
            warn_error_file,
            level="WARNING",
            rotation=rotation,
            retention=retention,
            encoding=encoding,
            mode=mode
        )
    # 所有类型的日志文件
    if enable_all_log:
        log_file = LOG_PATH / log_file
        logger.add(
            log_file,
            level="DEBUG",
            rotation=rotation,
            retention=retention,
            encoding=encoding,
            mode=mode
        )

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
