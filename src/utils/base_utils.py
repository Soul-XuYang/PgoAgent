import asyncio
from typing import Dict

from langchain_core.messages import SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
import time

def format_time(time):
    if time<60:
        return f"{int(time)}s"
    elif 60 < time < 3600:
        return f"{time//60}m{time%60}s"
    elif 3600 <time < 86400:
        return f"{time//3600}h{time%3600//60}m{time%3600%60}s"
    else:
        raise Exception("time out of range")
def estimate_tools_tokens(tools):
    # 这部分只是一个粗估：把工具的 json schema dump 出来数一下
    serialized = []
    for t in tools:
        serialized.append(t.json())  # 或 t.invoke_schema / t.args_schema / str(t)
    text = "\n".join(serialized)
    return count_tokens_approximately([SystemMessage(content=text)])


def run_time(func):
    async def async_wrapper(*args, **kwargs):
        start = time.time()
        result = await func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} run time: {format_time(end - start)}")
        return result

    def sync_wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} run time: {format_time(end - start)}")
        return result
    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

def extract_token_usage(msg) -> Dict[str, int]:
    """获取每个消息的token数据"""
    meta = getattr(msg, "response_metadata", {}) or {} # 获取响应的元数据
    usage = meta.get("token_usage") or meta.get("usage") or {} # 获取消耗量
    input_tokens = (
        usage.get("prompt_tokens")
        or usage.get("input_tokens")
        or usage.get("prompt_tokens_cache", 0) + usage.get("prompt_tokens_no_cache", 0)
        or 0
    )
    output_tokens = usage.get("completion_tokens") or usage.get("output_tokens") or 0

    # 忽略 usage["total_tokens"]，避免把 provider 的累计值当增量
    if not (input_tokens or output_tokens): # 如果没有输入和输出就从usage_metadata中获取
        meta2 = getattr(msg, "usage_metadata", {}) or {}
        input_tokens = meta2.get("input_tokens", 0)
        output_tokens = meta2.get("output_tokens", 0)

    total_tokens = input_tokens + output_tokens
    return {"input": input_tokens, "output": output_tokens, "total": total_tokens}

def accumulate_usage(old, new):
    """
    old: dict, 当前 state 中的 usage
    new: dict, 节点返回的 usage（增量）
    """
    if old is None:
        return new
    return {
        "input": old.get("input", 0) + new.get("input", 0),
        "output": old.get("output", 0) + new.get("output", 0),
        "total": old.get("total", 0) + new.get("total", 0),
    }
