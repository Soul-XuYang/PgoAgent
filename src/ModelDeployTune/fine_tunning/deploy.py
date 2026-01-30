import subprocess
import os
import sys
import argparse


def build_vllm_cmd(args):
    cmd = [
        "vllm", "serve",
        args.path,
        "--host", args.host,
        "--port", str(args.port),
        "--served-model-name", args.name
    ]
    # 可选参数：按需开启
    if args.dtype:
        cmd += ["--dtype", args.dtype]
    if args.max_model_len:
        cmd += ["--max-model-len", str(args.max_model_len)]
    return cmd


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="启动 vLLM OpenAI API 服务")
    parser.add_argument("--device", type=str, default="0",
                        help="GPU 设备号，如 '0' 或 '0,1'（多卡）")
    parser.add_argument("--name", type=str, default="qwen2.5-3b-lora-merged",
                        help="对外服务的模型名称 served-model-name")
    parser.add_argument("--path", type=str, default="../models/qwen2.5-3b-lora-merged",
                        help="模型路径（HF目录或本地目录）")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8000, help="端口号")
    parser.add_argument("--dtype", type=str, default="auto",
                        choices=["auto", "half", "float16",
                                 "bfloat16", "float32"],
                        help="推理精度")
    parser.add_argument("--max-model-len", type=int, default=None,
                        help="最大上下文长度（不填则使用模型默认）")
    args = parser.parse_args()

    os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
    os.environ["CUDA_VISIBLE_DEVICES"] = args.device

    vllm_cmd = build_vllm_cmd(args)

    try:
        print("=" * 60)
        print("开始启动 Chat 模型 vLLM OpenAI API 服务")
        print(f"  served-model-name : {args.name}")
        print(f"  model path        : {args.path}")
        print(f"  CUDA devices      : {args.device}")
        print(f"  host:port         : {args.host}:{args.port}")
        print("=" * 60)
        print("启动命令：")
        print(" ".join(vllm_cmd))
        print("=" * 60)

        subprocess.run(vllm_cmd, check=True)

    except subprocess.CalledProcessError as e:
        print(f"❌ vLLM 启动失败：{e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n⚠️ 用户中断，关闭 vLLM 服务...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ 启动失败：{e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
