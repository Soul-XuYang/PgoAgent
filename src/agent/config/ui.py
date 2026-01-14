import time
import sys
import os
from .config import VERSION

# 方法一的ASCII字符串
ascii_art = [
    "░█████████                           ░███                                        ░██    ",
    "░██     ░██                         ░██░██                                       ░██    ",
    "░██     ░██  ░████████  ░███████   ░██  ░██   ░████████  ░███████  ░████████  ░████████ ",
    "░█████████  ░██    ░██ ░██    ░██ ░█████████ ░██    ░██ ░██    ░██ ░██    ░██    ░██    ",
    "░██         ░██    ░██ ░██    ░██ ░██    ░██ ░██    ░██ ░█████████ ░██    ░██    ░██    ",
    "░██         ░██   ░███ ░██    ░██ ░██    ░██ ░██   ░███ ░██        ░██    ░██    ░██    ",
    "░██          ░█████░██  ░███████  ░██    ░██  ░█████░██  ░███████  ░██    ░██     ░████ ",
    "                   ░██                              ░██                                 ",
    "             ░███████                         ░███████                                  ",
    "                                                                                        "
]

color_bar = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "white": "37",
}
font_type = {
    "bold": "1",
    "dark": "2",
    "italic": "3",
    "underline": "4",
    "blink": "5",
    "reverse": "7",
    "concealed": "8",
}
def get_terminal_width(default_width: int = 88) -> int:
    """
    安全获取终端宽度
    :param default_width: 获取失败时的默认宽度
    :return: 终端宽度
    """
    try:
        # 尝试获取终端实际宽度
        return os.get_terminal_size().columns
    except (OSError, AttributeError):
        # 捕获句柄无效/不支持的错误，返回默认值
        return default_width
def colored_print(text:str, color_code:str="30",end:str="\n",center:bool=False):# 36=青色
    """彩色打印函数"""
    terminal_width = get_terminal_width()
    # 居中处理
    display_text = text.center(terminal_width) if center else text
    print(f"\033[{color_code}m{display_text }\033[0m",end = end)
def animated_banner():
    """带动画效果的横幅显示"""
    print("\n" * 2)

    # 逐行打印，带有打字机效果
    for line in ascii_art:
        for char in line:
            print(char, end="", flush=True)
            time.sleep(0.001)  # 控制打印速度
        print()
        time.sleep(0.05)

    print("\n" + "═" * 88)
    colored_print(f" PgoAgent: {VERSION} | system: {sys.platform} | python: {sys.version.split()[0]} ", color_code = font_type["bold"]+";"+color_bar["yellow"],center=True)  # 32=绿色
    colored_print(" start_time: " + time.strftime("%Y-%m-%d %H:%M:%S"), font_type["italic"]+";"+color_bar["cyan"],center=True)
    print("═" * 88 + "\n")

def simple_banner():
    """简单快速显示横幅"""
    print("\n".join(ascii_art))
    print("\n" + "═" * 88)
    colored_print(f" PgoAgent {VERSION}", "32", center=True)  # 32=绿色
    colored_print("Server: start_time: " + time.strftime("%Y-%m-%d %H:%M:%S"), "33",center=True)  # 33=黄色
    print("═" * 88 + "\n")

# 使用示例
if __name__ == "__main__":
    # 根据参数选择显示方式
    # if len(sys.argv) > 1 and sys.argv[1] == "--animated":
    #     animated_banner()
    # else:
    #     simple_banner()
    animated_banner()
    # 这里可以继续你的主程序逻辑
    print("开始初始化数据库连接...")
    time.sleep(0.5)
    print("加载配置文件...")
    time.sleep(0.5)
    print("系统启动完成！\n")



