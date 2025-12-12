import statistics
import uuid
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, Optional, List
from mcp.types import PromptMessage

server = FastMCP(
    name="mymcp",
    host="127.0.0.1",
    port=7070,
    log_level="DEBUG",
)

@server.tool()
def echo(text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"text": text, "metadata": metadata or {}}

@server.tool()
def echo(text: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]: # 默认metadata是None
    """
    Return the same text with optional metadata.
    常用于：测试 MCP server 是否可用、agent 调试、链路对齐。
    """
    return {
        "text": text,
        "metadata": metadata or {},
    }

@server.tool(name="build_uuid")
def uuid4() -> str:
    """Generate a random UUID4 string."""
    return str(uuid.uuid4())

@server.tool()
#     https://example.com/search?q=initial#top 会被拆成
#     scheme: https
#     netloc: example.com
#     path: /search
#     query: q=initial
#     fragment: top
def url_build(base_url: str, params: Dict[str, Any], doseq: bool = True) -> str:
    """
    Build url by merging params into base_url.
    """
    p = urlparse(base_url)
    old_q = parse_qs(p.query) # 转为字典
    for k, v in params.items():
        old_q[k] = v if isinstance(v, list) else [v]
    new_query = urlencode(old_q, doseq=doseq)
    return urlunparse((p.scheme, p.netloc, p.path, p.params, new_query, p.fragment))

@server.tool()
def stats(values: List[float]) -> Dict[str, float]:
    """Basic statistics for a numeric list."""
    if not values:
        raise ValueError("values is empty")
    return {
        "count": float(len(values)),
        "min": float(min(values)),
        "max": float(max(values)),
        "mean": float(statistics.mean(values)),
        "median": float(statistics.median(values)), # 中位数
        "stdev": float(statistics.pstdev(values)), # 标准差
    }

@server.tool(name="say_hello")
def sayhello(username: str) -> str:
    return f"hello, {username} my friend!"


@server.prompt(name="ask_topic")
def ask_topic(topic:str)->str:
    return f"请你解释一下{topic}这个概念?"
@server.prompt(name="generate_code_request")
def generate_code_request(langguage:str,task:str)->PromptMessage:
    return PromptMessage(
        content=f"请用{langguage}语言实现{task}这个功能",
        role="user",
        metadata={"lang":langguage,"task":task}
    )
@server.resource("data://config")
def get_config() -> Dict[str, Any]:
    return {
        "name": "mcp",
        "version": "0.1.0",
        "description": "A simple MCP server example."
    }

# 测试文件
if __name__ == "__main__":
    server.run(transport="sse")
