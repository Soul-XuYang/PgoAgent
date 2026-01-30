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

    for py_file in tools_dir.glob("*tool.py"): # 遍历路径当前所有可用的工具
        module_name = py_file.stem
        full_module_name = f"{package_name}.{module_name}"
        try:
            module = importlib.import_module(full_module_name)
        except Exception as e:
            print(f"[tools] 无法导入模块 {full_module_name}: {e}")
            continue

        # 1) class 工具：BaseTool 子类
        for name, obj in inspect.getmembers(module):
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
                        # print(f"[tools] 已加载类工具: {inst.name}")
                except Exception as e:
                    # print(f"[tools] skip class {obj.__name__}: {e}")
                    pass

        # 2) @tool 函数生成的工具实例（StructuredTool 等）
        for name, obj in inspect.getmembers(module):
            if isinstance(obj, BaseTool):
                try:
                    if obj.name not in EXCLUDE_TOOL_NAMES and obj.name not in seen:
                        tools.append(obj)
                        seen.add(obj.name)
                        print(f"[tools] 已加载装饰器工具: {obj.name}")
                except Exception as e:
                    print(f"[tools] skip tool {name}: {e}")
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


