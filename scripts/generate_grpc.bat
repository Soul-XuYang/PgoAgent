@echo off
REM Generate all gRPC code (Python + Go)
REM Execute from project root directory

cd /d %~dp0\..

echo ==================================================
echo Generating gRPC code for Pgo project (Python + Go)
echo ==================================================
echo.

REM Check if necessary directories exist
if not exist "proto" (
    echo [Error] proto directory does not exist!
    echo Please ensure you are running this script from the project root directory
    pause
    exit /b 1
)

if not exist "proto\agent.proto" (
    echo [Error] proto\agent.proto file does not exist!
    echo Please ensure the proto file is in the correct location
    pause
    exit /b 1
)

REM Check and create output directories
if not exist "src\agent\agent_grpc" (
    echo [Info] Creating Python output directory...
    mkdir "src\agent\agent_grpc"
    if %errorlevel% neq 0 (
        echo [Error] Failed to create Python output directory!
        pause
        exit /b 1
    )
)

if not exist "src\web_client\agent_grpc" (
    echo [Info] Creating Go output directory...
    mkdir "src\web_client\agent_grpc"
    if %errorlevel% neq 0 (
        echo [Error] Failed to create Go output directory!
        pause
        exit /b 1
    )
)

echo [1/2] Generating Python gRPC code...
REM Check if Python tools are installed
python -c "import grpc_tools" 2>nul
if %errorlevel% neq 0 (
    echo [Error] grpc_tools not found!
    echo Please run: pip install grpcio grpcio-tools
    pause
    exit /b 1
)

python -m grpc_tools.protoc --python_out=src/agent/agent_grpc --grpc_python_out=src/agent/agent_grpc --proto_path=proto proto/agent.proto
if %errorlevel% neq 0 (
    echo [Error] Failed to generate Python gRPC code!
    echo Possible reasons:
    echo   1. Proto file syntax error
    echo   2. Output directory permission issue
    echo   3. Python environment issue
    pause
    exit /b 1
)

REM Generate Python type stubs (.pyi files) using native protoc
protoc --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [Info] Generating Python type stubs...
    protoc --pyi_out=src/agent/agent_grpc --proto_path=proto proto/agent.proto
    if %errorlevel% equ 0 (
        echo [Success] Type stubs generated
    ) else (
        echo [Warning] Failed to generate type stubs, but continuing...
    )
) else (
    echo [Warning] protoc not found, skipping type stub generation
)

echo [Success] Python code generated to src/agent/agent_grpc/
echo.

echo [2/2] Generating Go gRPC code...
REM Check if Go tools are installed
protoc --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] protoc compiler not found!
    echo Please download and install from https://protobuf.dev/downloads/
    pause
    exit /b 1
)

go version >nul 2>&1
if %errorlevel% neq 0 (
    echo [Error] Go environment not found!
    echo Please download and install from https://golang.org/dl/
    pause
    exit /b 1
)

protoc --go_out=src/web_client/agent_grpc --go_opt=paths=source_relative --go-grpc_out=src/web_client/agent_grpc --go-grpc_opt=paths=source_relative --proto_path=proto proto/agent.proto
if %errorlevel% neq 0 (
    echo [Error] Failed to generate Go gRPC code!
    echo Possible reasons:
    echo   1. Required Go plugins not installed:
    echo      go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
    echo      go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
    echo   2. $GOPATH/bin or $GOBIN not in PATH
    echo   3. Proto file syntax error
    echo   4. Output directory permission issue
    pause
    exit /b 1
)
echo [Success] Go code generated to src/web_client/agent_grpc/
echo.

echo ==================================================
echo All protocol files generated successfully!
echo ==================================================
echo Generated gRPC files:
echo   Python: src/agent/agent_grpc/agent_pb2.py
echo   Python: src/agent/agent_grpc/agent_pb2.pyi (type stubs)
echo   Python: src/agent/agent_grpc/agent_pb2_grpc.py
echo   Go:     src/web_client/agent_grpc/agent.pb.go
echo   Go:     src/web_client/agent_grpc/agent_grpc.pb.go
echo.
pause
