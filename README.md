# PgoAgent

## 项目概述-Abstract

本项目是一个具备长期与短期记忆、多代理协作处理能力、本地工具集成及检索增强生成功能的**PgoAgent**的智能体系统(基于**Langgraph + chromadb + Agentic Rag**系统)。它采用**vllm**本地部署的大语言模型(**LLM**)与**PostgreSQL**存储用户数据，后端则通过**gRPC**、**GORM**及**Gin**框架协调代理输出。

---

This is an intelligent agent system named **PgoAgent**, featuring long-term and short-term memory, multi-agent collaboration capabilities, local tool integration, and retrieval-augmented generation functions (based on **Langgraph** + **chromadb ** + **Agentic Rag**). It employs a locally deployed large language model(**LLM**) using **vllm** and stores user data with **PostgreSQL**, while the backend coordinates agent outputs via **gRPC**, **GORM**, and **Gin** framework.

### 核心特性

- 🧠 **智能对话与任务执行**：基于LangGraph的多节点工作流，支持复杂任务分解与执行
- 📚 **RAG知识检索**：集成Chroma向量数据库，支持文档加载、分割、索引和检索
- 💾 **长期记忆管理**：基于PostgreSQL的持久化记忆系统，记录用户偏好和对话历史
- 🛠️ **工具调用系统**：支持文件操作、代码执行、网页浏览等多种工具
- 🌐 **Web界面**：Go+Gin构建的Web客户端，提供直观的用户交互界面
- ⚡ **高性能通信**：gRPC协议实现Python后端与Go客户端间的高效通信
- 🔒 **安全特性**：JWT认证、令牌桶速率限制、TLS证书、敏感工具审核等安全机制

## 技术架构


### 技术栈


## 项目结构

```
PgoAgent/
├── src/
│   ├── agent/                # PgoAgent Agent核心模块(python)
│   │   ├── graph.py          # 主工作流图
│   │   ├── main_cli.py       # CLI命令行入口,可在终端运行调试使用
│   │   ├── main_server.py    # gRPC服务入口,可是适配网络服务端
│   │   ├── subAgents/        # 子Agent模块
│   │   │   ├── planAgent.py  # 计划Agent子图
│   │   │   ├── memoryAgent.py # 记忆Agent子图
│   │   │   └── decisionAgent.py # 决策Agent子图
│   │   ├── rag/              # RAG模块
│   │   │   ├── RAGEngine.py  # RAG引擎
│   │   │   ├── loader.py     # 文档加载
│   │   │   ├── spliter.py    # 文本分割
│   │   │   └── indexer.py    # 索引构建
│   │   ├── tools/            # 工具集合
│   │   ├── grpc_server/      # gRPC服务
│   │   └── mcp_server/       # MCP服务器
│   ├── WebServer/           # PgoAgent Web客户端(go)
│   │   ├── controllers/      # 控制器
│   │   ├── models/           # 数据模型
│   │   ├── services/         # 服务层
│   │   ├── router/           # 网络路由
│   │   ├──config/            # 配置
│   │   ├── utils/            # 自定义的各类工具函数
│   │   └── main.go           # 服务端主入口
│   └── PgoModel/             # 模型接口
├── scripts/                  # 脚本工具,包含构建protobuff脚本文件以及本地TLS证书生成脚本
├── config.toml               # 配置文件
├── .env                      # 环境变量
├── .gitignore                # Git忽略文件
├── LICENSE                   # 许可协议
├── README.md                 # 项目说明
└── pyproject.toml            # Python项目配置
```

## 快速开始

### 环境要求

- Python 3.12+
- Go 1.21+
- PostgreSQL 12+
- Git

### 安装步骤

1. **克隆项目**
```bash
git clone git@github.com:Soul-XuYang/PgoAgent.git
cd PgoAgent
```

2. **Python环境设置**
```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# 或
.venv\Scripts\activate     # Windows

# 安装依赖
pip install -e .
```

3. **数据库设置**
```bash
# 创建PostgreSQL数据库
createdb pgoagent

# 配置数据库连接（编辑.env文件）
DATABASE_DSN=postgresql://user:password@localhost:5432/pgoagent
```

4. **Go客户端设置**
```bash
cd src/web_client
go mod download
go build -o pgoagent main.go
```

### 配置说明

主要配置文件为`config.toml`，包含以下配置项：

- **数据库配置**：PostgreSQL连接参数
- **Web服务器配置**：端口、超时等
- **Agent服务器配置**：gRPC端口、线程数等
- **模型配置**：本地/云端模型选择

### 运行服务

1. **启动Python Agent后端**
```bash
cd src
python -m agent.main_cli
```

2. **启动Go Web客户端**
```bash
cd src/web_client
./pgoagent
```

3. **访问Web界面**
打开浏览器访问 `http://localhost:8080`

## 核心功能

### 1. 智能对话系统

- 基于LangGraph的多节点工作流
- 支持流式和普通输出模式
- 自动对话摘要和上下文管理
- 支持中断和取消操作

### 2. RAG知识检索

- 支持多种文档格式(PDF、DOCX、MD、HTML等)
- 智能文本分割(标题分割、语义分割)
- 混合检索(向量检索+BM25)
- 重排序优化结果

### 3. 长期记忆管理

- 用户画像存储
- 对话历史记录
- 偏好学习
- 个性化回复

### 4. 工具调用系统

- 文件操作(读取、写入、删除)
- 目录浏览
- 代码执行
- 时间获取
- 计算功能
- 网页浏览

### 5. 安全机制

- JWT身份认证
- 速率限制(全局和用户级别)
- 敏感工具审核
- 输入验证和过滤

## API文档

### gRPC接口

主要服务接口定义在`proto/agent.proto`：

- `Chat`: 对话接口
- `StreamChat`: 流式对话
- `GetConversationHistory`: 获取对话历史
- `CreateConversation`: 创建会话

### REST API

Web客户端提供以下REST接口：

- `POST /api/conversation`: 创建对话
- `POST /api/conversation/{id}/message`: 发送消息
- `GET /api/conversation/{id}/history`: 获取历史
- `DELETE /api/conversation/{id}`: 删除对话

## 开发指南

### 添加新工具

1. 在`src/agent/tools/`目录创建新工具文件
2. 继承`BaseTool`类
3. 实现`invoke`或`ainvoke`方法
4. 在`src/agent/tools/__init__.py`中注册

### 添加新Agent

1. 在`src/agent/subAgents/`创建新Agent文件
2. 定义State和节点函数
3. 构建StateGraph
4. 在主图中集成

### 自定义RAG处理器

1. 继承`RAGEngine`类
2. 重写加载、分割或检索方法
3. 注册到系统中



### 生产环境配置

1. 使用PostgreSQL集群
2. 配置Redis缓存
3. 设置负载均衡
4. 启用日志监控
5. 配置备份策略

## 常见问题

### Q: 如何切换到本地模型？
A: 修改`config.toml`中的`[model.use]`配置，设置对应模型为`true`并配置本地模型服务地址。

### Q: 如何添加新的文档类型支持？
A: 在`src/agent/rag/loader.py`中添加新的加载器，并在`DocumentLoader`中注册。

### Q: 如何调整RAG检索参数？
A: 修改`src/agent/rag/RAGEngine.py`中的阈值参数，如`query_distance_threshold`和`rerank_distance_threshold`。

## 贡献指南

1. Fork项目
2. 创建特性分支
3. 提交更改
4. 推送到分支
5. 创建Pull Request

## 许可证

本项目采用MIT许可证，详见[LICENSE](LICENSE)文件。

## 联系方式

- 项目主页：https://github.com/Soul-XuYang/PgoAgent
- 问题反馈：https://github.com/Soul-XuYang/PgoAgent/issues

---

感谢使用PgoAgent！如有问题或建议，欢迎提交Issue或Pull Request。
