import subprocess
import os
import platform
from typing import  Optional, TypedDict, NotRequired
from langchain_core.tools import tool
class ShellResult(TypedDict):
    """
    Shell命令执行结果
    """
    success: bool
    stdout: NotRequired[str]
    stderr: NotRequired[str]
    return_code: NotRequired[int]
    error: NotRequired[str]
    os: NotRequired[str]

@tool("shell_exec")
def shell_exec(command: str, timeout: Optional[int] = 30, work_dir: Optional[str] = None) -> ShellResult:
    """
    在指定的shell会话中安全地执行命令。
    参数:
        command (str): 要执行的shell命令
        timeout (int, optional): 命令执行超时时间（秒），默认30秒
        work_dir (str, optional): 命令执行的工作目录，默认为当前目录
    返回:
        dict: 包含以下字段：
            - success: bool, 命令是否成功执行
            - stdout: str, 命令的标准输出
            - stderr: str, 命令的标准错误
            - return_code: 命令的返回码
            - error: str, 如果发生错误,输出对应的错误信息
            - os:操作系统
    Example:
        shell_exec.run("ls -la") -> {'success': True, 'stdout': '...', 'stderr': '', 'returncode': 0}
    """
    # 危险命令列表
    DANGEROUS_COMMANDS = {
        'Windows': [
            'del /f /s /q',
            'format',
            'rmdir /s /q',
            'shutdown',
        ],
        'Linux': [
            'rm -rf /',
            'chmod -R 777',
            'dd if=/dev/zero',
            'mkfs',
            'format',
            'fdisk',
        ],
        'Darwin': [  # macOS
            'rm -rf /',
            'sudo rm -rf',
            'chmod -R 777',
        ]
    }

    try:
        # 获取当前操作系统
        current_os = platform.system()
        if current_os not in DANGEROUS_COMMANDS:
            current_os = 'Linux'  # 默认使用Linux的危险命令列表

        # 检查危险命令
        if any(danger in command.lower() for danger in DANGEROUS_COMMANDS[current_os]): # 遍历对应操作系统的错误信息
            return {
                "success": False,
                "error": f"检测到潜在危险命令，执行被阻止"
            }

        # 设置工作目录
        work_directory = work_dir if work_dir else os.getcwd()

        # 根据操作系统设置允许的目录
        if current_os == 'Windows':
            allowed_dirs = [
                os.environ.get('TEMP', 'C:\\temp'),
                os.getcwd(),
                os.path.dirname(os.getcwd())
            ]
        else:
            allowed_dirs = [
                '/tmp',
                '/home',
                os.getcwd(),
                os.path.dirname(os.getcwd())
            ]

        if not any(work_directory.startswith(allowed_dir) for allowed_dir in allowed_dirs):
            return {
                "success": False,
                "error": f"不允许在目录 {work_directory} 中执行命令"
            }


        # 执行命令
        if current_os == "Windows":
            args = ["cmd", "/c", command]
        else:
            args = ["/bin/sh", "-c", command]

        result = subprocess.run(
            args,
            shell=False,
            cwd=work_directory,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            encoding="utf-8",
            errors="replace",
        )

        # 限制输出大小
        max_output_size = 2000
        stdout = result.stdout[:max_output_size]
        stderr = result.stderr[:max_output_size]

        # 如果输出被截断，添加提示
        if len(result.stdout) > max_output_size:
            stdout += "\n... (输出被截断)"
        if len(result.stderr) > max_output_size:
            stderr += "\n... (错误输出被截断)"

        return {
            "success": result.returncode == 0,
            "stdout": stdout,
            "stderr": stderr,
            "return_code": result.returncode,
            "os": current_os
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"命令执行超时（{timeout}秒）"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


# 测试代码
def test_shell_exec():
    """测试shell_exec函数的各种场景"""
    print("开始测试shell_exec函数...")

    # 测试1: 基本命令
    print("\n测试1: 基本命令")
    if platform.system() == 'Windows':
        result = shell_exec.run("python basic_tool.py")
    else:
        result = shell_exec.run("ls -la")
    print(f"结果: {result}")

    # 测试2: 错误命令
    print("\n测试2: 错误命令")
    result = shell_exec.run("invalid_command")
    print(f"结果: {result}")

    # 测试3: 超时测试
    print("\n测试3: 超时测试")
    if platform.system() == 'Windows':
        result = shell_exec.run("timeout 5", timeout=2)
    else:
        result = shell_exec.run("sleep 5", timeout=2)
    print(f"结果: {result}")

    # 测试4: 工作目录测试 - 其中对 LangChain @tool 包装后的工具，参数必须通过 invoke({...})（或 run({...}) 的字典入参形式）传递
    print("\n测试4: 工作目录测试")
    cur = shell_exec.invoke({"command": "cd"})
    print(f"当前目录: {cur}")
    cur_dir = cur.get("stdout", "").strip()
    parent_dir = os.path.normpath(os.path.dirname(cur_dir))
    up = shell_exec.invoke({"command": "cd && dir", "work_dir": parent_dir})
    print(f"上级目录内容: {up}")
    # 测试5: 危险命令测试
    print("\n测试5: 危险命令测试")
    if platform.system() == 'Windows':
        result = shell_exec.run("format c:")
    else:
        result = shell_exec.run("rm -rf /")
    print(f"结果: {result}")






if __name__ == "__main__":
    test_shell_exec()
