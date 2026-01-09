.PHONY: proto proto-python proto-go proto-clean help

# 项目根目录
ROOT_DIR := $(shell pwd)
PROTO_DIR := $(ROOT_DIR)/proto
PYTHON_OUT := $(ROOT_DIR)/src/agent/agent_grpc
GO_OUT := $(ROOT_DIR)/src/web_client/agent_grpc

# 默认目标
.DEFAULT_GOAL := help

## help: 显示帮助信息
help:
	@echo "========================================"
	@echo "PgoAgent 构建工具"
	@echo "========================================"
	@echo ""
	@echo "可用命令："
	@echo "  make proto          - 生成所有 gRPC 代码（Python + Go）"
	@echo "  make proto-python   - 仅生成 Python gRPC 代码"
	@echo "  make proto-go       - 仅生成 Go gRPC 代码"
	@echo "  make proto-clean    - 清理生成的 gRPC 代码"
	@echo "  make help           - 显示此帮助信息"
	@echo ""

## proto: 生成所有 gRPC 代码（Python + Go）
proto: proto-python proto-go
	@echo ""
	@echo "========================================"
	@echo "所有协议文件生成完成！"
	@echo "========================================"
	@echo ""
	@echo "生成的文件："
	@echo "  Python: $(PYTHON_OUT)/agent_pb2.py"
	@echo "  Python: $(PYTHON_OUT)/agent_pb2_grpc.py"
	@echo "  Go:     $(GO_OUT)/agent.pb.go"
	@echo "  Go:     $(GO_OUT)/agent_grpc.pb.go"
	@echo ""

## proto-python: 生成 Python gRPC 代码
proto-python:
	@echo "========================================"
	@echo "生成 Python gRPC 代码"
	@echo "========================================"
	@echo ""
	@mkdir -p $(PYTHON_OUT)
	@python -m grpc_tools.protoc \
		--python_out=$(PYTHON_OUT) \
		--grpc_python_out=$(PYTHON_OUT) \
		--proto_path=$(PROTO_DIR) \
		$(PROTO_DIR)/agent.proto
	@if [ $$? -eq 0 ]; then \
		echo "[成功] Python 代码已生成到 $(PYTHON_OUT)/"; \
	else \
		echo "[错误] Python 代码生成失败！"; \
		echo "请确保已安装: pip install grpcio grpcio-tools"; \
		exit 1; \
	fi
	@echo ""

## proto-go: 生成 Go gRPC 代码
proto-go:
	@echo "========================================"
	@echo "生成 Go gRPC 代码"
	@echo "========================================"
	@echo ""
	@mkdir -p $(GO_OUT)
	@protoc \
		--go_out=$(GO_OUT) \
		--go_opt=paths=source_relative \
		--go-grpc_out=$(GO_OUT) \
		--go-grpc_opt=paths=source_relative \
		--proto_path=$(PROTO_DIR) \
		$(PROTO_DIR)/agent.proto
	@if [ $$? -eq 0 ]; then \
		echo "[成功] Go 代码已生成到 $(GO_OUT)/"; \
	else \
		echo "[错误] Go 代码生成失败！"; \
		echo "请确保已安装："; \
		echo "  1. protoc 编译器"; \
		echo "  2. go install google.golang.org/protobuf/cmd/protoc-gen-go@latest"; \
		echo "  3. go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest"; \
		echo "  4. 确保 $$GOPATH/bin 或 $$GOBIN 在 PATH 中"; \
		exit 1; \
	fi
	@echo ""

## proto-clean: 清理生成的 gRPC 代码
proto-clean:
	@echo "清理生成的 gRPC 代码..."
	@rm -f $(PYTHON_OUT)/agent_pb2.py
	@rm -f $(PYTHON_OUT)/agent_pb2_grpc.py
	@rm -f $(GO_OUT)/agent.pb.go
	@rm -f $(GO_OUT)/agent_grpc.pb.go
	@echo "[完成] 已清理所有生成的 gRPC 代码"
