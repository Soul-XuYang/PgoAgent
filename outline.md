# 该LLM项目初始的大纲
## 技术栈
编程语言:python+go
Langchain:python+langgraph+fastapi+langchain-community+mongoDB
Go+Gin+Gorm(Postgresql)+gRPC
技术栈总览

```
Gorm + Postgresql +Redis(缓存) - 选用,重点是下面5个
    ↓
Go（Gin + gRPC）
    ↓（RPC/REST）
Python（LangChain / LangGraph / FastAPI）
    ↓（HTTP/OpenAI API）
推理引擎：vLLM（本地模型服务）
    ↓
大模型权 Python-Pytorch（Qwen / Llama / DeepSeek / 自训模型-后续进行微调
    ↓
向量数据库（Chroma / Qdrant）
    ↓
普通数据库（MongoDB / PostgreSQL）
```
### 核心学习点与学习技术大纲
✔ gRPC
- Go 和 Python 之间的高速通信
- 强类型
- 支持流式输出（LLM 必须）
- 工业级，企业内部用得最多

✔ LangChain（**AI 应用框架，地位类似Java中的springboot**）
- RAG（检索增强生成）
- Memory(长短期记忆)
- 与各种模型（OpenAI / vLLM / HuggingFace）对接

✔ LangGraph（增强版 Agent 工作流）
- 多 Agent 协作
- Plan & Execute
- 状态机（AgentState）
- 多节点 workflow（DAG）
- 可视化执行图
- 展现给用户：Agent 能力 = LangGraph 实现。

✔ FastAPI（Python 的 API 层）-基本使用即可无需深入理解操作
- 把 Python Agent 封装成服务
- 暴露给 Go / 前端
- 作为 gRPC 的 fallback
- 开发速度快、支持 async

✔ Python 基本库（会用即可）
- pydantic（数据模型）
- numpy
- pandas
- requests / httpx

✔ vLLM（本地大模型推理引擎）
- 把你的本地大模型变成 OpenAI 格式 API
- 1 行命令部署本地模型
- 高性能 / 高并发
- 支持 GPU 优化
- 模型选择:Qwen2-7B / Qwen2.5/Llama3.1/ DeepSeek 或你自己训练的模型
  
✔ 向量数据库：Chroma（新手必选）
- 存文本 embedding
- 相似度检索
- RAG 的前半部分（知识召回）
选择理由：
- 本地即可运行（不用 docker）：代码量小和 LangChain、Langgraph 配合最好
✔ 普通数据库（用于长期记忆）
- MongoDB（存用户偏好、历史事实、Memory）
- JSON 结构容易适配
- 与 Python 生态完美结合
- 也可换 PostgreSQL- 但是这里推荐用MongoDB-因为其结构可以想变就变
📌 长期记忆 != RAG
两者互补：
- RAG：查知识
- Memory：存用户信息（偏好 / 历史 / 个人资料）
  
✔ LLM API 层（入门阶段用的）
- 不用一开始就部署本地模型，API 模型更快上手。
- 包含：
- OpenAI（最稳定）
- Gemini（便宜+好用）
- DeepSeek（中文极强）
- Claude（擅长推理）
- 这里最好先用 API 学 Agent → 再切到本地 vLLM。
✔ LLM API 层（入门阶段用的）
## 项目
入手项目
主推荐项目：Agent-with-RAG-and-Long-Term-Memory
我前面已解释为什么该项目适合你：覆盖了 Agent、RAG、长期记忆这些核心点。用 Python，适合你现在阶段，结构清晰，容易上手，不用你一开始就搭建本地模型，适合从外到内路线。
