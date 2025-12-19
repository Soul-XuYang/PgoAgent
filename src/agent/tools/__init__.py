# tools 软件包
__version__ = "0.0.1"
__author__ = "xu yang"

import importlib
import inspect
from pathlib import Path
from typing import List, Set, Type

from langchain_core.tools import BaseTool

# 不想暴露的工具名字写这里
EXCLUDE_TOOL_NAMES = {
    # "debug_tool",
}

def _load_all_tools() -> List[BaseTool]:
    tools: List[BaseTool] = []
    seen: Set[str] = set()

    tools_dir = Path(__file__).parent
    package_name = __name__  # agent.tools

    for py_file in tools_dir.glob("tool*.py"):
        module_name = py_file.stem
        full_module_name = f"{package_name}.{module_name}"
        module = importlib.import_module(full_module_name)

        # 1) class 工具：BaseTool 子类
        for _, obj in inspect.getmembers(module):
            if (
                inspect.isclass(obj)
                and issubclass(obj, BaseTool)
                and obj is not BaseTool
            ):
                try:
                    inst = obj()
                    if inst.name not in EXCLUDE_TOOL_NAMES and inst.name not in seen:
                        tools.append(inst)
                        seen.add(inst.name)
                except Exception as e:
                    print(f"[tools] skip class {obj.__name__}: {e}")

        # 2) @tool 函数生成的工具实例（StructuredTool 等）
        for _, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool):
                if obj.name not in EXCLUDE_TOOL_NAMES and obj.name not in seen:
                    tools.append(obj)
                    seen.add(obj.name)
    return tools


LOCAL_TOOLS = _load_all_tools()

BLACK_LIST = {
    "write_file",
    "delete_file",
    "write_json",
    "append_file",
}
# 正确的 __all__
__all__ = ["LOCAL_TOOLS", "BLACK_LIST","rag_system_prompt"] # 只能是字符串

rag_system_prompt = """
RAG工作协议（严格执行指南）

【检索流程】
当需要访问本地知识库时，请遵循以下顺序：
1. 执行 rag_decide_strategy（检索策略决策）
2. 执行 rag_retrieve（实际检索操作）

【异常处理】
若 rag_retrieve 返回以下情况：
- hits 为空列表
- hits 内容与查询明显不相关

则执行以下补救措施：
1. 调用 rag_rewrite_query 生成优化后的查询词/关键词
2. 重新执行完整检索流程（rag_decide_strategy -> rag_retrieve）

【重试限制】
- 最大检索尝试次数：2轮
- 达到上限后：
  * 停止检索
  * 直接进行总结回答
  * 必须说明："知识库未检索到足够证据"

【回答规范】
- 所有回答必须引用 rag_retrieve 返回的来源（source）
- 严禁编造或臆测信息
"""
