import shutil
import time
import json
from typing import Type, Any, List, Optional
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
import os

max_size = 100 * 1024 * 1024
ALLOWED_TEXT_SUFFIXES = {".go", ".md", ".py", ".json", ".txt", ".java", ".c",".yaml"}


# pydantic强制遍历进行声明使用
# ========== Args Schemas ==========
# 以下都为数据模型类
class ReadFileArgs(BaseModel):
    file_path: str = Field(..., description="需要读取的文件的路径")


class SaveFileArgs(BaseModel):
    file_path: str = Field(..., description="需要保存的文件的路径")
    content: str = Field(default="", description="保存文件的内容")

class AppendFileArgs(BaseModel):
    file_path: str = Field(..., description="要追加内容的文件路径，不存在则可创建")
    content: str = Field(..., description="要追加的内容")
    create_if_missing: bool = Field(default=True, description="文件不存在时是否创建，默认创建")

class CreateFileArgs(BaseModel):
    file_path: str = Field(..., description="要创建的文件路径")
    content: str = Field(default="", description="创建时写入的初始内容，默认空文件")
    overwrite: bool = Field(default=False, description="若文件已存在是否覆盖，默认不覆盖")

class SearchInFileArgs(BaseModel):
    file_path: str = Field(..., description="要搜索的文件路径")
    keyword: str = Field(..., description="要查找的关键词（大小写可选）")
    case_sensitive: bool = Field(default=False, description="是否区分大小写，默认不区分")
    max_matches: int = Field(default=20, description="最多返回的匹配条数，默认 20")


class ListDirArgs(BaseModel):
    dir_path: Optional[str] = Field(default="", description="需要列出的目录路径，默认当前工作目录")
    recursive: bool = Field(
        default=False,
        description="是否递归列出子目录，不提供 dir_path 参数或传入空字符串时，将自动使用当前工作目录，recursive=False打印当前目录，True打印当前目录的目录树路径。",
    )
    max_items: int = Field(default=200, description="最多返回多少项，防止过大目录")
    max_depth: Optional[int] = Field(default=None, description="递归最大深度（根为0，1表示仅当前目录）。None 为不限")
    absolute: bool = Field(default=True, description="是否输出绝对路径，默认输出绝对路径")


class ReadJsonArgs(BaseModel):
    file_path: str = Field(..., description="对应JSON 文件路径")


class WriteJsonArgs(BaseModel):
    file_path: str = Field(..., description="对应JSON 文件路径")
    data: dict = Field(default_factory=dict, description="要写入的 JSON 数据")
    indent: int = Field(default=2, description="缩进")


class StatArgs(BaseModel):
    file_path: str = Field(..., description="对应的文件路径")


class RemoveArgs(BaseModel):
    path: str = Field(..., description="要删除的文件或目录路径")
    recursive: bool = Field(default=False, description="删除目录时是否递归")

class DeleteFilesArgs(BaseModel):
    file_paths: List[str] = Field(..., description="要删除的文件路径列表")

# 无参工具的占位参数
class EmptyArgs(BaseModel):
    pass
# ========== Tools ==========
class read_file(BaseTool):
    name: str = "read_file"
    description: str = (
        "这个工具读取文本文件的内容，支持 100MB 以内文件，默认 UTF-8 编码（若为 GBK 编码需手动说明）"
    )
    args_schema: Type[BaseModel] = ReadFileArgs

    def _run(self, file_path: str) -> str:
        try:
            if not os.path.exists(file_path):
                return f"错误：文件 {file_path} 不存在"
            if not os.path.isfile(file_path):
                return f"错误：{file_path} 不是一个文件（可能是目录）"

            file_size = os.path.getsize(file_path)
            if file_size > max_size:
                return (
                    f"错误：文件过大（{file_size / 1024 / 1024:.1f}MB），仅支持 100MB 以内文件"
                )

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="gbk") as f:
                    content = f.read()

            if content.strip() == "":
                return "文件为空"
            return content

        except PermissionError:
            return f"错误：无权限读取文件 {file_path}（请检查文件权限）"
        except Exception as e:
            return f"读取失败：{str(e)}（可能是二进制文件，该工具仅支持文本文件）"


class write_file(BaseTool):
    name: str = "write_file"
    description: str = "使用这个工具可以将内容写入或者创建对应的文件"
    args_schema: Type[BaseModel] = SaveFileArgs

    def _run(self, file_path: str, content: str) -> str:
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"保存成功：{file_path}"

        except PermissionError:
            return f"错误：无权限写入文件 {file_path}（请检查文件/目录权限）"
        except Exception as e:
            return f"保存失败：{str(e)}"


class create_file(BaseTool): # 下述前三参数
    name: str = "create_file"
    description: str = "创建一个文件，可选择写入初始内容；默认不覆盖已存在文件"
    args_schema: Type[BaseModel] = CreateFileArgs

    def _run(self, file_path: str, content: str = "", overwrite: bool = False) -> str:
        try:
            ext = os.path.splitext(file_path)[1].lower() # 先分割然后获取后缀名，其中0是文件路径，1是扩展名
            # 后缀名是否存在
            if ext not in ALLOWED_TEXT_SUFFIXES:
                allowed = ", ".join(ALLOWED_TEXT_SUFFIXES)
                return f"错误：仅允许创建以下文本类型文件：{allowed}，当前扩展名为 {ext or '空'}"
            # 查看文件是否存在
            if os.path.exists(file_path) and not overwrite: # 尝试看看文件是否存在并且不覆写
                return f"错误：文件已存在，未覆盖：{file_path}"

            dir_path = os.path.dirname(file_path) # 目录路径
            if dir_path and not os.path.exists(dir_path): # 不存在则创建
                os.makedirs(dir_path)

            # 简单大小限制，防止一次写入超大内容
            if content and len(content.encode("utf-8")) > max_size:
                return f"错误：初始内容过大，超过 {max_size / 1024 / 1024:.1f}MB 限制，请分割内容并使用write_file工具按批次写入数据"

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)
            return f"创建成功：{file_path}"

        except PermissionError:
            return f"错误：无权限创建文件 {file_path}"
        except Exception as e:
            return f"创建失败：{str(e)}"


class append_file(BaseTool):
    name: str = "append_file"
    description: str = "向文件追加内容，可选不存在时创建，默认创建"
    args_schema: Type[BaseModel] = AppendFileArgs

    def _run(self, file_path: str, content: str, create_if_missing: bool = True) -> str:
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                if create_if_missing:
                    os.makedirs(dir_path)
                else:
                    return f"错误：目录不存在：{dir_path}"

            if not os.path.exists(file_path):
                if not create_if_missing:
                    return f"错误：文件不存在且未创建：{file_path}"
                open(file_path, "a", encoding="utf-8").close()

            if content and len(content.encode("utf-8")) > max_size:
                return f"错误：追加内容过大，超过 {max_size / 1024 / 1024:.1f}MB 限制，请分批次内容添加"

            with open(file_path, "a", encoding="utf-8") as f:
                f.write(content) # 以a模式添加内容
            return f"追加成功：{file_path}"
        except PermissionError:
            return f"错误：无权限写入文件 {file_path}"
        except Exception as e:
            return f"追加失败：{str(e)}"


class search_in_file(BaseTool):
    name: str = "search_in_file"
    description: str = "按关键词搜索文本文件，返回匹配行及上下文"
    args_schema: Type[BaseModel] = SearchInFileArgs

    def _run(
        self,
        file_path: str,
        keyword: str,
        case_sensitive: bool = False,
        max_matches: int = 20,
    ) -> str:
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在"
        if not os.path.isfile(file_path):
            return f"错误：{file_path} 不是文件"
        # 路径和文件判断，下方为参数判断
        if max_matches <= 0:
            return "错误：max_matches 必须大于 0"
        try:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            except UnicodeDecodeError:
                with open(file_path, "r", encoding="gbk") as f:
                    lines = f.readlines()
            # 上述为文件以行打开数据
            matches = []
            needle = keyword if case_sensitive else keyword.lower()
            for idx, line in enumerate(lines):
                hay = line if case_sensitive else line.lower()  # 如果敏感则区分大小写
                if needle in hay:
                    matches.append(f"[行 {idx+1}] {line}")
                    if len(matches) >= max_matches:
                        break

            if not matches:
                return "未找到匹配内容"
            suffix = "" if len(matches) < max_matches else f"\n...已截断，超过 {max_matches} 条"
            return "\n\n".join(matches) + suffix
        except Exception as e:
            return f"搜索失败：{str(e)}"


class delete_files(BaseTool):
    name: str = "delete_files"
    description: str = "使用该工具可删除一个或多个文件"
    args_schema: Type[BaseModel] = DeleteFilesArgs

    def _run(self, file_paths: List[str]) -> str:
        results = []
        for file_path in file_paths: # 一一遍历
            try:
                if not os.path.exists(file_path):
                    results.append(f"警告：文件 {file_path} 不存在")
                    continue

                if os.path.isdir(file_path):
                    results.append(f"错误：{file_path} 是目录，不是文件")
                    continue

                os.remove(file_path)
                results.append(f"成功删除：{file_path}")

            except PermissionError:
                results.append(f"错误：无权限删除文件 {file_path}（请检查文件权限）")
            except Exception as e:
                results.append(f"删除 {file_path} 失败：{str(e)}")

        return "\n".join(results)

class remove_path(BaseTool):
    name: str = "remove_path"
    description: str = "删除对应路径的文件或目录（目录需 recursive=True）"
    args_schema: Type[BaseModel] = RemoveArgs

    def _run(self, path: str, recursive: bool = False) -> str:
        if not os.path.exists(path):
            return f"错误：{path} 不存在"
        try:
            if os.path.isfile(path):
                os.remove(path)
                return f"已删除文件：{path}"

            if os.path.isdir(path):
                if not recursive:
                    return f"错误：{path} 是目录，请设置 recursive=True"
                shutil.rmtree(path)
                return f"已删除目录：{path}"

            return "错误：不支持的路径类型"

        except PermissionError:
            return f"错误：无权限删除 {path}"
        except Exception as e:
            return f"删除失败：{str(e)}"


class read_json(BaseTool):
    name: str = "read_json"
    description: str = "读取 JSON 文件并返回 dict（仅支持文本 JSON）"
    args_schema: Type[BaseModel] = ReadJsonArgs

    def _run(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在"
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                obj = json.load(f)
            return json.dumps(obj, ensure_ascii=False, indent=2)  # 转化为dict
        except Exception as e:
            return f"读取 JSON 失败：{str(e)}"


class write_json(BaseTool):
    name: str = "write_json"
    description: str = "将 dict 写入 JSON 文件（utf-8）"
    args_schema: Type[BaseModel] = WriteJsonArgs

    def _run(self, file_path: str, data: dict, indent: int = 2) -> str:
        try:
            dir_path = os.path.dirname(file_path)
            if dir_path and not os.path.exists(dir_path):
                os.makedirs(dir_path)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=indent)
            return f"JSON 保存成功：{file_path}"
        except Exception as e:
            return f"保存 JSON 失败：{str(e)}"


class file_stat(BaseTool):
    name: str = "file_stat"
    description: str = "返回文件大小、修改时间信息"
    args_schema: Type[BaseModel] = StatArgs

    def _run(self, file_path: str) -> str:
        if not os.path.exists(file_path):
            return f"错误：文件 {file_path} 不存在"
        if not os.path.isfile(file_path):
            return f"错误：{file_path} 不是文件"

        st = os.stat(file_path)
        return (
            f"size: {st.st_size} bytes ({st.st_size / 1024 / 1024:.2f} MB)\n"
            f"mtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(st.st_mtime))}\n"
        )


class list_dir(BaseTool):
    name: str = "list_dir"
    description: str = "列出目录下的文件/子目录(可选择递归)，支持深度限制、数量上限，可选绝对路径输出，默认当前工作目录"
    args_schema: Type[BaseModel] = ListDirArgs

    def _run(self, dir_path: str = "", recursive: bool = False, max_items: int = 200, max_depth: Optional[int] = None, absolute: bool = True) -> str:
        if not dir_path or dir_path.strip() == "":
            dir_path = os.getcwd()
        if not os.path.exists(dir_path):
            return f"错误：目录 {dir_path} 不存在"
        if not os.path.isdir(dir_path):
            return f"错误：{dir_path} 非目录"
        if max_items <= 0:
            return "错误：max_items 必须大于 0"
        if max_depth is not None and max_depth < 0:
            return "错误：max_depth 不能为负数"
        # 非递归时强制深度为 1（仅当前层）
        effective_max_depth = 1 if not recursive else max_depth

        results: list[str] = []
        truncated_items = False
        truncated_depth = False
        try:
            queue = [(dir_path, 0)]
            while queue:
                current, depth = queue.pop(0)
                try:
                    entries = sorted(os.listdir(current))
                except PermissionError:
                    results.append(f"{'  '*depth}[无权限] {os.path.relpath(current, dir_path)}")
                    continue

                for name in entries:
                    full = os.path.join(current, name)
                    is_dir = os.path.isdir(full)
                    indent = "  " * depth
                    display = os.path.abspath(full) if absolute else name
                    label = f"{indent}{display}/" if is_dir else f"{indent}{display}"
                    results.append(label)

                    if len(results) >= max_items:
                        truncated_items = True
                        break

                    if is_dir and recursive:
                        next_depth = depth + 1
                        if effective_max_depth is None or next_depth < effective_max_depth:
                            queue.append((full, next_depth))
                        else:
                            truncated_depth = True
                if truncated_items:
                    break

            suffix_parts = []
            if truncated_items:
                suffix_parts.append(f"...已截断，超过 {max_items} 项")
            if truncated_depth and effective_max_depth is not None:
                suffix_parts.append(f"...已停止递归，达到最大深度 {effective_max_depth}")
            if suffix_parts:
                results.append("\n".join(suffix_parts))

            return "\n".join(results) if results else "目录为空"

        except PermissionError:
            return f"错误：无权限访问目录 {dir_path}"
        except Exception as e:
            return f"列目录失败：{str(e)}"


class current_workdir(BaseTool):
    name: str = "current_workdir"
    description: str = "返回当前工作目录的绝对路径"
    args_schema: Type[BaseModel] = EmptyArgs

    def _run(self) -> str:
        try:
            return os.getcwd()
        except Exception as e:
            return f"获取当前工作目录失败：{str(e)}"

if __name__ == "__main__":
    list_dir_tool = list_dir()
    tool = list_dir()
    print(tool.name)
    print(tool.description)
    print(tool.run(""))
