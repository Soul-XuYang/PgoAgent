import asyncio
from pathlib import Path
import json
import os
from typing import Any
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from agent.my_llm import llm

# python_mcp_server_config = {
#     "url": "http://127.0.0.1:7070/sse",
#     "transport": "sse",
# }
user ="admin"
BASE_DIR = Path(__file__).resolve().parents[3]  # your-project/  获取文件路径并向上走
MCP_CONFIG_DIR = BASE_DIR /  os.path.join("mcp_configs", user)# my-project/mcp_configs/


# 这种配置肯定是字典类型的
def transport_to_type(mcp_list: Any) -> dict:
    if isinstance(mcp_list,dict):
        if "type" in mcp_list:
            mcp_list["transport"] = mcp_list.pop("type")
        for _ ,value in mcp_list.items():
            if isinstance(value,dict):
                # value["transport"] = value.pop("type")
                transport_to_type(value) # 上面多余了，因为之后会继续判断
            elif isinstance(value,list): # 找列表里的字典
                for v in value:
                    if isinstance(v,dict):
                        transport_to_type(v)
    return mcp_list # 从尾巴向根走-返回的值在if里没有用实际上就不接受，之所以返回只是最后返回递归的值


def load_all_mcp_configs():
    if not MCP_CONFIG_DIR.exists():
        raise FileNotFoundError(f"MCP配置目录不存在: {MCP_CONFIG_DIR}")
    connections = {}
    for path in MCP_CONFIG_DIR.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # 兼容两种写法：
            # 1) Cursor 风格：{"mcpServers": {...}}
            # 2) 直接字典：{"howtocook-mcp": {...}}
            servers = data["mcpServers"] if "mcpServers" in data else data
            connections.update(servers)

        except json.JSONDecodeError as e:
            print(f"警告：无法解析配置文件 {path}: {e}")
        except Exception as e:
            print(f"警告：读取配置文件 {path} 时出错: {e}")
    # 统一处理transport字段
    return transport_to_type(connections)


async def get_mcp_tools():
    try:
        mcp_client = MultiServerMCPClient(load_all_mcp_configs())
        mcp_tools = await mcp_client.get_tools()
        return mcp_tools
    except Exception as e:
    # 开发环境下连不上就直接用空工具，避免拖死 graph
        print("[MCP] 加载 MCP 工具失败，使用空工具列表。错误：", repr(e))
        return []
# 测试函数
async def test():
    mcp_client = MultiServerMCPClient(load_all_mcp_configs())
    tools = await mcp_client.get_tools()  # 这里拿到的就是 [StructuredTool(...)]，包含 webSearchPrime
    print(f"加载的mcp工具如下:\n{tools}")
    agent = create_agent(
        llm,
        tools=tools,
    )
    # 测试搜索功能
    test_query = "你手头有几个mcp工具呢，说明下，并且你可以联网搜索吗?"
    print(f"测试搜索: {test_query}")
    try:
        # 使用新的异步执行方法
        response = await agent.ainvoke({
            "messages": [HumanMessage(content=test_query)]
        })
        print("搜索结果:", response['messages'][-1].content)
    except Exception as e:
        print("执行出错:", repr(e))

if __name__ == "__main__":
    print("the test program has run !")
    print(f"配置文件如下:\n{load_all_mcp_configs()}")
    asyncio.run(test())

