import os
from pathlib import Path
from typing import Dict, Any, Optional
import tomllib

TOML_LOADER = tomllib.load
TOML_ERROR = tomllib.TOMLDecodeError

class ConfigLoader:
    """配置加载器类"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置加载器
        
        Args:
            config_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_path is None:
            # 默认配置文件路径（相对于项目根目录）
            # 当前项目中配置文件位于项目根目录下：deployment_config.toml
            script_dir = Path(__file__).parent
            project_root = script_dir.parent
            config_path = project_root / "deployment_config.toml"
        
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self):
        """加载TOML配置文件"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(
                    f"配置文件不存在：{self.config_path}\n"
                    f"请确保配置文件存在于指定路径"
                )
            
            with open(self.config_path, 'rb') as f:
                self.config = TOML_LOADER(f)
            
            if self.config is None:
                raise ValueError("配置文件为空或格式错误")
            
            print(f"成功加载配置文件：{self.config_path}")
            
        except TOML_ERROR as e:
            raise ValueError(f"TOML配置文件解析错误：{e}")
        except Exception as e:
            raise RuntimeError(f"加载配置文件失败：{e}")
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        return self.config.get("global", {})
    
    def get_chat_config(self) -> Dict[str, Any]:
        """获取Chat模型配置"""
        chat_config = self.config.get("chat", {})
        # 合并全局配置作为默认值
        global_config = self.get_global_config()
        return {**global_config, **chat_config}
    
    def get_embedding_config(self) -> Dict[str, Any]:
        """获取Embedding模型配置"""
        embedding_config = self.config.get("embedding", {})
        # 合并全局配置作为默认值
        global_config = self.get_global_config()
        return {**global_config, **embedding_config}
    
    def get_rerank_config(self) -> Dict[str, Any]:
        """获取Rerank模型配置"""
        rerank_config = self.config.get("rerank", {})
        # 合并全局配置作为默认值
        global_config = self.get_global_config()
        return {**global_config, **rerank_config}
    
    def get_test_config(self) -> Dict[str, Any]:
        """获取测试配置"""
        return self.config.get("test", {})
    
    def build_vllm_command(self, model_type: str) -> list:
        """
        根据模型类型构建vLLM启动命令
        
        Args:
            model_type: 模型类型，可选值：'chat', 'embedding', 'rerank'
        
        Returns:
            vLLM命令参数列表
        """
        import sys
        
        # 获取对应模型的配置
        if model_type == "chat":
            config = self.get_chat_config()
        elif model_type == "embedding":
            config = self.get_embedding_config()
        elif model_type == "rerank":
            config = self.get_rerank_config()
        else:
            raise ValueError(f"不支持的模型类型：{model_type}，可选值：'chat', 'embedding', 'rerank'")
        
        # 构建命令
        cmd = [
            sys.executable,
            "-m",
            "vllm.entrypoints.openai.api_server",
            "--model", config["model_path"],
            "--served-model-name", config["served_model_name"],
            "--tensor-parallel-size", str(config["tensor_parallel_size"]),
            "--host", config.get("host", self.get_global_config().get("default_host", "0.0.0.0")),
            "--port", str(config.get("port", 8000)),
            "--gpu-memory-utilization", str(config.get("gpu_memory_utilization", 
                                                          self.get_global_config().get("default_gpu_memory_utilization", 0.9))),
            "--max-num-batched-tokens", str(config.get("max_num_batched_tokens", 8192)),
            "--max-model-len", str(config.get("max_model_len", 8192)),
            "--dtype", config.get("dtype", self.get_global_config().get("default_dtype", "bfloat16")),
            "--max-num-seqs", str(config.get("max_num_seqs", 
                                              self.get_global_config().get("default_max_num_seqs", 128))),
        ]
        
        # 添加日志配置
        if not config.get("enable_log_requests", 
                          not self.get_global_config().get("enable_log_requests", False)):
            cmd.append("--no-enable-log-requests")
        
        if not config.get("enable_log_stats",
                          not self.get_global_config().get("enable_log_stats", False)):
            cmd.append("--disable-log-stats")
        
        # 添加API密钥
        api_key = config.get("api_key", self.get_global_config().get("api_key", ""))
        if api_key:
            cmd.extend(["--api-key", api_key])
        
        return cmd
    
    def get_cuda_visible_devices(self, model_type: str) -> str:
        """
        获取指定模型类型的CUDA设备配置
        Args:
            model_type: 模型类型
        
        Returns:
            CUDA设备字符串，如 "0,1,2"
        """
        if model_type == "chat":
            config = self.get_chat_config()
        elif model_type == "embedding":
            config = self.get_embedding_config()
        elif model_type == "rerank":
            config = self.get_rerank_config()
        else:
            raise ValueError(f"不支持的模型类型：{model_type}")
        
        return config.get("cuda_visible_devices", "0")


def main():
    """测试配置加载器"""
    try:
        loader = ConfigLoader()
        
        print("\n" + "=" * 50)
        print("当前的配置信息预览")
        print("=" * 50)
        
        print("\n1.Chat模型配置：")
        chat_config = loader.get_chat_config()
        print(f"   模型名称：{chat_config.get('model_name')}")
        print(f"   模型路径：{chat_config.get('model_path')}")
        print(f"   GPU设备：{chat_config.get('cuda_visible_devices')}")
        print(f"   端口：{chat_config.get('port')}")
        
        print("\n2.Embedding模型配置：")
        embedding_config = loader.get_embedding_config()
        print(f"   模型名称：{embedding_config.get('model_name')}")
        print(f"   模型路径：{embedding_config.get('model_path')}")
        print(f"   GPU设备：{embedding_config.get('cuda_visible_devices')}")
        print(f"   端口：{embedding_config.get('port')}")
        
        print("\n3.Rerank模型配置：")
        rerank_config = loader.get_rerank_config()
        print(f"   模型名称：{rerank_config.get('model_name')}")
        print(f"   模型路径：{rerank_config.get('model_path')}")
        print(f"   GPU设备：{rerank_config.get('cuda_visible_devices')}")
        print(f"   端口：{rerank_config.get('port')}")
        
        print("\n" + "=" * 50)
        print("✅ 配置加载器测试通过！")
        print("=" * 50)
        
    except Exception as e:
        print(f"❌ 测试失败：{e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
