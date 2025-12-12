import os
from dotenv import load_dotenv

load_dotenv()  # 加载环境变量
API_KEY= os.getenv("OPENAI_API_KEY")  # 从环境变量中获取OPENAI_API_KEY的值
BASE_URL = os.getenv("OPENAI_BASE_URL")  # 从环境变量中获取OPENAI_BASE_URL的值
DATABASE_URL = os.getenv("DATABASE_URL")
PRINT_SWITCH = True # DEBUG各个节点的token数

# 基本模型的输入token设置
MODEL_MAX_INPUT = {
    # 1M/2M 级：90% 规则
    "gpt-4.1": 900_000,
    "gpt-4.1-mini": 900_000,
    "gpt-4.1-nano": 900_000,
    "gemini-1.5-pro": 1_800_000,
    "gemini-1.5-flash": 900_000,
    "qwen2.5-turbo": 900_000,
    "qwen2.5-1m": 900_000,
    # 200K 级
    "claude-3.5-sonnet": 180_000,
    "claude-3.5-haiku": 180_000,
    "claude-3-opus": 180_000,
    "glm-4.6": 180_000,  # 或 160_000 更保守

    # 128K 级（预留≥8K）
    "gpt-4o": 120_000,
    "gpt-4o-mini": 120_000,
    "mistral-large-2": 120_000,
    "llama-3.1-8b-instruct": 120_000,
    "llama-3.1-70b-instruct": 120_000,
    "llama-3.1-405b-instruct": 120_000,
    "qwen2.5-7b-instruct": 120_000,
    "qwen2.5-72b-instruct": 120_000,
    "deepseek-v3.2": 120_000,
    "kimi-k2-instruct": 120_000,
    "command-r": 120_000,
    "command-r-plus": 120_000,
    "moonshot-v1-8k": 8192,
    "kimi-k2-thinking": 230_000,
}