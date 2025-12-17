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
__all__ = ["LOCAL_TOOLS", "BLACK_LIST"] # 只能是字符串
