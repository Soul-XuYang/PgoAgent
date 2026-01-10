"""
修复 gRPC 生成的 Python 代码中的导入问题

gRPC Python 代码生成器默认使用绝对导入，但在包结构中需要使用相对导入。
此脚本自动将绝对导入修复为相对导入。

使用方法：
    python scripts/fix_grpc_imports.py
"""
import os
import re
import sys
from pathlib import Path


def fix_grpc_imports(grpc_file_path: str) -> bool:
    """
    修复 gRPC 文件中的绝对导入为相对导入
    
    Args:
        grpc_file_path: gRPC 文件的路径
        
    Returns:
        bool: 是否进行了修改
    """
    if not os.path.exists(grpc_file_path):
        print(f"❌ File not found: {grpc_file_path}")
        return False
    
    try:
        with open(grpc_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # 替换绝对导入为相对导入
        # 匹配: import agent_pb2 as agent__pb2
        # 替换为: from . import agent_pb2 as agent__pb2
        pattern = r'^import agent_pb2 as agent__pb2$'
        replacement = 'from . import agent_pb2 as agent__pb2'
        
        new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        if new_content != original_content:
            with open(grpc_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"[OK] Fixed imports in {grpc_file_path}")
            return True
        else:
            print(f"[INFO] No changes needed in {grpc_file_path}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error fixing {grpc_file_path}: {e}")
        return False


def main():
    """主函数"""
    # 获取脚本所在目录的绝对路径
    script_dir = Path(__file__).parent.absolute()
    project_root = script_dir.parent
    
    # 构建 gRPC 文件路径
    grpc_file = project_root / "src" / "agent" / "agent_grpc" / "agent_pb2_grpc.py"
    
    if not grpc_file.exists():
        print(f"[ERROR] File not found: {grpc_file}")
        print(f"        Please ensure gRPC code has been generated first.")
        sys.exit(1)
    
    success = fix_grpc_imports(str(grpc_file))
    sys.exit(0 if success or True else 1)  # 即使没有修改也返回成功


if __name__ == "__main__":
    main()
