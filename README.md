# PgoAgent
This is a multi-agent processing system with long-term and short-term memory+mcp+local tools+rag. It uses the LLM locally deployed by ollma and PostgreSQL to store user's data, and the back-end uses grpc,gorm and gin to coordinate the output of the agent.

# 技术栈
**langgraph**: 本次项目使用**langgraph**框架作为agent的运行框架。
**RAG系统**: 本项目的RAG(Retrieval Augmented Generation)采用双阈值+混合检索(BM25:TF-IDF)+Rerank的方式进行检索，采用的数据库为本地的chromadb。
**本地部署**: **langgraph**语言模型部署在本网的linux服务器上，使用vllm框架进行部署,同时也可以兼容市面上的openAI接口、嵌入模型和重排序模型api接口(自定义的类接口接受数据)等。
# 本地部署
- **本地大模型**：本次项目使用的是在服务器上使用VLLM部署的大模型(可自己配置使用)，配置的命令行CLI如下:
- **用户数据库** 使用docker镜像下载PostgresSQL并用其容器进行链接
