# PgoAgent
本项目是一个具备长期与短期记忆、多代理协作处理能力、本地工具集成及检索增强生成功能的**PgoAgent**的智能体系统(基于Langgraph + chromadb + Agentic Rag系统)。它采用**vllm**本地部署的大语言模型(**LLM**)与**PostgreSQL**存储用户数据，后端则通过**gRPC**、**GORM**及**Gin**框架协调代理输出。

---

This is an intelligent agent system named **PgoAgent**, featuring long-term and short-term memory, multi-agent collaboration capabilities, local tool integration, and retrieval-augmented generation functions (based on **Langgraph** + **chromadb ** + **Agentic Rag**). It employs a locally deployed large language model(**LLM**) using **vllm** and stores user data with **PostgreSQL**, while the backend coordinates agent outputs via **gRPC**, **GORM**, and **Gin** framework.

# 技术栈
**langgraph**: 本次项目使用**langgraph**框架作为agent的运行框架。
**RAG系统**: 本项目的RAG(Retrieval Augmented Generation)采用双阈值+混合检索(BM25:TF-IDF)+Rerank的方式进行检索，采用的数据库为本地的chromadb。
**本地部署**: **langgraph**语言模型部署在本网的linux服务器上，使用vllm框架进行部署,同时也可以兼容市面上的openAI接口、嵌入模型和重排序模型api接口(自定义的类接口接受数据)等。
# 本地部署
- **本地大模型**：本次项目使用的是在服务器上使用VLLM部署的大模型(可自己配置使用)，配置的命令行CLI如下:
- **用户数据库** 使用docker镜像下载PostgresSQL并用其容器进行链接
# 微调
可见本文项目的的workflow图

其中关于plan、decide和memory子图的用户画像的刻画这三个部分是针对特定的应用场景，可依据实际需求进行部分微调
