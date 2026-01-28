# PgoAgent 项目介绍

## 项目概述

PgoAgent 是一个具备长期与短期记忆、多代理协作处理能力、本地工具集成及检索增强生成功能的智能体系统。该系统基于 Langgraph + ChromaDB + Agentic RAG 架构，采用 VLLM 本地部署的大语言模型(LLM)与 PostgreSQL 存储用户数据，后端通过 gRPC、GORM 及 Gin 框架协调代理输出。

**版本**: v0.0.3  
**作者**: yongzhiyin (610415432@qq.com)  
**许可证**: MIT  

## 技术架构

### 核心技术栈

#### Python 后端 (智能体核心)
- **Langgraph**: 代理运行框架，支持复杂的工作流编排
- **Agentic RAG**: 检索增强生成系统
- **ChromaDB**: 向量数据库，用于知识检索
- **PostgreSQL**: 用户数据和长期记忆存储
- **VLLM**: 本地大语言模型部署框架

#### Go Web 服务端
- **Gin**: 高性能 Web 框架
- **GORM**: ORM 框架，数据库操作
- **gRPC**: 跨语言通信机制
- **Swagger**: RESTful API 文档生成

### 系统架构特点

1. **双服务架构**: Python 智能体服务 + Go Web 服务，通过 gRPC 通信
2. **多代理协作**: 包含决策代理、计划代理、记忆代理等专业化子代理
3. **混合检索**: BM25 + TF-IDF 双阈值检索机制 + Rerank 重排序
4. **记忆系统**: 支持长期记忆和短期记忆管理
5. **本地部署**: 支持本地大模型部署，保护数据隐私

## 项目结构

```
PgoAgent/
├── src/
│   ├── agent/                    # Python 智能体核心
│   │   ├── graph.py             # 主工作流图
│   │   ├── main_cli.py          # CLI 启动入口
│   │   ├── main_grpc.py         # gRPC 服务入口
│   │   ├── subAgents/           # 子代理模块
│   │   │   ├── decisionAgent.py # 决策代理
│   │   │   ├── planAgent.py     # 计划代理
│   │   │   └── memoryAgent.py   # 记忆代理
│   │   ├── rag/                 # RAG 检索模块
│   │   ├── tools/               # 工具集成
│   │   └── grpc_server/         # gRPC 服务实现
│   ├── WebServer/               # Go Web 服务
│   │   ├── controllers/         # 控制器
│   │   ├── models/              # 数据模型
│   │   ├── services/            # 业务服务
│   │   └── router/              # 路由配置
│   └── Finetunning/             # 微调模块
├── config.toml                  # 系统配置
├── proto/                       # gRPC 协议定义
└── scripts/                     # 部署脚本
```

## 核心功能

### 1. 智能对话系统
- 支持多轮对话上下文管理
- 集成短期记忆和长期记忆
- 支持用户画像个性化

### 2. 检索增强生成 (RAG)
- 双阈值混合检索 (BM25 + TF-IDF)
- Rerank 重排序优化
- 支持多种文档格式处理

### 3. 多代理协作
- **决策代理**: 负责任务分解和决策
- **计划代理**: 制定执行计划
- **记忆代理**: 管理用户记忆和画像

### 4. 工具集成
- 文件操作工具
- Shell 命令执行
- RAG 检索工具
- MCP (Model Context Protocol) 外部工具

### 5. Web API 服务
- RESTful API 接口
- 用户认证和授权
- 对话历史管理
- 实时通信支持

## 配置说明

### 数据库配置
```toml
[database.dev]
type = "postgresql"
host = "localhost"
port = 5432
user = "postgres"
db_name = "postgres"
```

### 服务端口配置
```toml
[web.server]
host = "localhost"
port = 8080

[agent.server]
host = "localhost"
port = 50051
```

### 模型配置
支持本地部署的大语言模型，包括:
- 对话模型 (Chat Model)
- 嵌入模型 (Embedding Model)  
- 重排序模型 (Rerank Model)

## 部署说明

### 环境要求
- Python 3.12+
- Go 1.19+
- PostgreSQL 12+
- Docker (可选)

### 本地部署步骤

1. **启动 PostgreSQL**
   ```bash
   docker run --name postgres -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres
   ```

2. **启动 Python 智能体服务**
   ```bash
   cd src/agent
   python main_grpc.py
   ```

3. **启动 Go Web 服务**
   ```bash
   cd src/WebServer
   go run main.go
   ```

4. **生成 API 文档**
   ```bash
   cd src/WebServer
   swag init --parseDependency --parseInternal -g main.go -o ./docs
   ```

## API 接口

### 主要接口
- `POST /api/v1/auth/login` - 用户登录
- `POST /api/v1/conversation/chat` - 对话接口
- `GET /api/v1/conversation/history` - 对话历史
- `POST /api/v1/memory/update` - 更新用户记忆
- `GET /api/v1/profile` - 用户画像

### API 文档
启动服务后访问: `http://localhost:8080/swagger/index.html`

## 微调支持

项目支持针对特定应用场景的微调，主要包括:
- 计划代理微调
- 决策代理微调  
- 记忆代理的用户画像刻画微调

## 特色功能

1. **本地化部署**: 完全本地运行，保护数据隐私
2. **多模态支持**: 支持文本、图像等多种输入格式
3. **记忆管理**: 智能的长期和短期记忆管理
4. **工具生态**: 丰富的本地工具集成
5. **可扩展性**: 模块化设计，易于扩展新功能

## 开发计划

- [x] 支持更多大语言模型
- [ ] 增强多模态处理能力
- [ ] 优化 RAG 检索效果
- [ ] 完善监控系统
- [ ] 增加更多预置工具

## 联系方式

- **作者**: yongzhiyin
- **邮箱**: 610415432@qq.com
- **项目地址**: https://github.com/Soul-XuYang/PgoAgent

---

*本项目采用 MIT 许可证，欢迎贡献代码和提出建议。*