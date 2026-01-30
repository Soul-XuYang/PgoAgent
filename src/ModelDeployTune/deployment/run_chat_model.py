import subprocess
import os
import sys
from pathlib import Path
import argparse

# 添加scripts目录到路径，以便导入config_loader
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from config import ConfigLoader

# 加载配置
config_loader = ConfigLoader()

# 获取Chat模型配置
chat_config = config_loader.get_chat_config()

# 设置CUDA设备
os.environ["CUDA_VISIBLE_DEVICES"] = config_loader.get_cuda_visible_devices("chat")
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"

# 从配置构建vLLM启动命令
vllm_cmd = config_loader.build_vllm_command("chat")

# 启动vLLM API服务（阻塞运行，等同于直接在终端执行命令）
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="启动Chat模型vLLM API服务")
    try:
        print("=" * 50)
        print(f"开始启动Chat模型vLLM API服务")
        print(f"   模型：{chat_config.get('model_name')}")
        print(f"   路径：{chat_config.get('model_path')}")
        print(f"   GPU设备：{chat_config.get('cuda_visible_devices')}")
        print(f"   端口：{chat_config.get('port')}")
        print("=" * 50)
        print(f"启动命令：{' '.join(vllm_cmd)}")
        print("=" * 50)
        # 执行命令，输出重定向到终端（也可指定日志文件）
        subprocess.run(vllm_cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"❌ vLLM启动失败：{e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，关闭vLLM服务...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 启动失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

