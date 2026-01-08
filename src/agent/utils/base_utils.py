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
from functools import wraps
def run_time(func):
    @wraps(func) # 保证原函数的元数据属性
    def wrapper(*args, **kwargs):
            start = time.time()
            result = func(*args, **kwargs)
            end = time.time()
            print(f"函数{func.__name__}运行时间为{end-start}s")
            return result
    return wrapper

def retry(max_retries :int =3,delay:float = 1.0,):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            retries_count = 0
            while retries_count < max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries_count += 1
                    time.sleep(delay)
                    if retries_count >= max_retries:
                        raise RuntimeError(f"Function {func.__name__} failed after {max_retries} retries.")
                    time.sleep(delay)
        return wrapper
    return decorator


