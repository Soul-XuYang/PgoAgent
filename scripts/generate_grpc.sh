# 生成所有 gRPC 代码（Python + Go）
# 从项目根目录执行

# 获取脚本所在目录的绝对路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "================================================="
echo "Generating gRPC code for Pgo project (Python + Go)"
echo "================================================="
echo ""

# 检查必要的目录是否存在
if [ ! -d "proto" ]; then
    echo "[Error] proto directory does not exist!"
    echo "Please ensure you are running this script from the project root directory"
    exit 1
fi

if [ ! -f "proto/agent.proto" ]; then
    echo "[Error] proto/agent.proto file does not exist!"
    echo "Please ensure the proto file is in the correct location"
    exit 1
fi

# 检查并创建输出目录
if [ ! -d "src/agent/agent_grpc" ]; then
    echo "[Info] Creating Python output directory..."
    mkdir -p "src/agent/agent_grpc"
    if [ $? -ne 0 ]; then
        echo "[Error] Failed to create Python output directory!"
        exit 1
    fi
fi

if [ ! -d "src/web_client/agent_grpc" ]; then
    echo "[Info] Creating Go output directory..."
    mkdir -p "src/web_client/agent_grpc"
    if [ $? -ne 0 ]; then
        echo "[Error] Failed to create Go output directory!"
        exit 1
    fi
fi

echo "[1/3] Generating Python gRPC code..."
# 检查 Python 工具是否安装
python -c "import grpc_tools" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[Error] grpc_tools not found!"
    echo "Please run: pip install grpcio grpcio-tools"
    exit 1
fi

python -m grpc_tools.protoc \
    --python_out=src/agent/agent_grpc \
    --grpc_python_out=src/agent/agent_grpc \
    --proto_path=proto \
    proto/agent.proto

if [ $? -ne 0 ]; then
    echo "[Error] Failed to generate Python gRPC code!"
    echo "Possible reasons:"
    echo "  1. Proto file syntax error"
    echo "  2. Output directory permission issue"
    echo "  3. Python environment issue"
    exit 1
fi

# Generate Python type stubs (.pyi files) using native protoc
if command -v protoc &> /dev/null; then
    echo "[Info] Generating Python type stubs..."
    protoc \
        --pyi_out=src/agent/agent_grpc \
        --proto_path=proto \
        proto/agent.proto
    if [ $? -eq 0 ]; then
        echo "[Success] Type stubs generated"
    else
        echo "[Warning] Failed to generate type stubs, but continuing..."
    fi
else
    echo "[Warning] protoc not found, skipping type stub generation"
fi

echo "[Success] Python code generated to src/agent/agent_grpc/"
echo ""

echo "[Info] Fixing gRPC Python imports..."
python scripts/fix_grpc_imports.py
if [ $? -ne 0 ]; then
    echo "[Warning] Failed to fix imports, but continuing..."
fi
echo ""

echo "[2/3] Generating Go gRPC code..."
# 检查 Go 工具是否安装
if ! command -v protoc &> /dev/null; then
    echo "[Error] protoc compiler not found!"
    echo "Please download and install from https://protobuf.dev/downloads/"
    exit 1
fi

if ! command -v go &> /dev/null; then
    echo "[Error] Go environment not found!"
    echo "Please download and install from https://golang.org/dl/"
    exit 1
fi

protoc \
    --go_out=src/web_client/agent_grpc \
    --go_opt=paths=source_relative \
    --go-grpc_out=src/web_client/agent_grpc \
    --go-grpc_opt=paths=source_relative \
    --proto_path=proto \
    proto/agent.proto

if [ $? -ne 0 ]; then
    echo "[Error] Failed to generate Go gRPC code!"
    echo "Possible reasons:"
    echo "  1. Required Go plugins not installed:"
    echo "     go install google.golang.org/protobuf/cmd/protoc-gen-go@latest"
    echo "     go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest"
    echo "  2. \$GOPATH/bin or \$GOBIN not in PATH"
    echo "  3. Proto file syntax error"
    echo "  4. Output directory permission issue"
    exit 1
fi
echo "[Success] Go code generated to src/web_client/agent_grpc/"
echo ""

echo "[3/3] Generating TLS certificates..."
python -c "import cryptography" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[Info] Installing cryptography library..."
    pip install cryptography
fi

python scripts/tls.py
if [ $? -eq 0 ]; then
    echo "[Success] TLS certificates generated"
else
    echo "[Warning] Failed to generate TLS certificates"
    echo "You can generate them later by running: python scripts/tls.py"
fi
echo ""



echo "================================================="
echo "All protocol files and local tls certificates generated successfully!"
echo "================================================="
echo ""
echo "Generated gRPC files:"
echo "  Python: src/agent/agent_grpc/agent_pb2.py"
echo "  Python: src/agent/agent_grpc/agent_pb2.pyi (type stubs)"
echo "  Python: src/agent/agent_grpc/agent_pb2_grpc.py"
echo "  Go:     src/web_client/agent_grpc/agent.pb.go"
echo "  Go:     src/web_client/agent_grpc/agent_grpc.pb.go"
echo "  TLS:    certs/server.crt"
echo "  TLS:    certs/server.key"
echo ""
