import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DatabaseConfig:
    type:str
    host:str
    port:int
    user:str
    password:str
    dbname:str
@dataclass
class ModelUseConfig:
    chat: bool
    embedding: bool
    rerank: bool
@dataclass
class ModelChatConfig:
    host: str
    port: int
    version: str
    name: str
    token:int
@dataclass
class EmbeddingModelConfig:
    host: str
    name: str
    version: str
    embedding_dim: int
    port: int
@dataclass
class RerankModelConfig:
    host: str
    name: str
    version: str
    reranking_dim: int
    port: int

def load_database_config(env: str = "dev")->DatabaseConfig:
    """读取相关的配置文件"""
    try:
        config_path = Path(__file__).parent.parent.parent / "config.toml"
        with open(config_path, "rb") as f: # 二进制加载
            config = tomllib.load(f)
        db_config = config["database"][env]
        return DatabaseConfig(
            type=db_config["type"],
            host=db_config["host"],
            port=db_config["port"],
            user=db_config["user"],
            password=db_config["password"],
            dbname=db_config["db_name"]
        )
    except FileNotFoundError:
        raise FileNotFoundError(f"配置文件未找到")
    except KeyError as e:
        raise ValueError(f"配置文件缺少必要的字段: {e}")
def load_model_use() -> ModelUseConfig:
    """
    读取 config.toml 中 [model.use] 配置，判断是否使用本地部署的大模型。
    """
    try:
        config_path = Path(__file__).parent.parent.parent / "config.toml"
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        use_cfg = config["model"]["use"]

        return ModelUseConfig(
            chat=use_cfg["chat"],
            embedding=use_cfg["embedding"],
            rerank=use_cfg["rerank"],
        )
    except FileNotFoundError:
        raise FileNotFoundError("配置文件未找到")
    except KeyError as e:
        raise ValueError(f"配置文件缺少必要的字段: {e}")

def load_model_chat(env: str = "chat") -> ModelChatConfig:
    """
    读取 config.toml 中 [model.chat] 配置并返回 dataclass。
    默认 section 为 "chat"，如以后有多套模型配置可以通过 env 区分。
    """
    try:
        config_path = Path(__file__).parent.parent.parent / "config.toml"
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        chat_config = config["model"][env]

        return ModelChatConfig(
            host=chat_config["host"],
            port=chat_config["port"],
            version=chat_config["version"],
            name=chat_config["name"],
            token=chat_config["token"], 
        )
    except FileNotFoundError:
        raise FileNotFoundError("配置文件未找到")
    except KeyError as e:
        raise ValueError(f"配置文件缺少必要的字段: {e}")
def load_embedding_model() -> EmbeddingModelConfig:
    """
    读取 config.toml 中 [model.embedding] 配置。
    """
    try:
        config_path = Path(__file__).parent.parent.parent / "config.toml"
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        emb_cfg = config["model"]["embedding"]

        return EmbeddingModelConfig(
            host=emb_cfg["host"],
            name=emb_cfg["name"],
            version=emb_cfg["version"],
            embedding_dim=emb_cfg["embedding_dim"],
            port=emb_cfg["port"],
        )
    except FileNotFoundError:
        raise FileNotFoundError("配置文件未找到")
    except KeyError as e:
        raise ValueError(f"配置文件缺少必要的字段: {e}")


def load_rerank_model() -> RerankModelConfig:
    """
    读取 config.toml 中 [model.rerank] 配置。
    """
    try:
        config_path = Path(__file__).parent.parent.parent / "config.toml"
        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        rerank_cfg = config["model"]["rerank"]

        return RerankModelConfig(
            host=rerank_cfg["host"],
            name=rerank_cfg["name"],
            version=rerank_cfg["version"],
            reranking_dim=rerank_cfg["reranking_dim"],
            port=rerank_cfg["port"],
        )
    except FileNotFoundError:
        raise FileNotFoundError("配置文件未找到")
    except KeyError as e:
        raise ValueError(f"配置文件缺少必要的字段: {e}")

def get_dsn(env:str ='dev')->str:
    database_config = load_database_config(env)
    return f"{database_config.type}://{database_config.user}:{database_config.password}@{database_config.host}:{database_config.port}/{database_config.dbname}"

# 全局函数变量
DATABASE_DSN=get_dsn()


if __name__ == "__main__":
    print(DATABASE_DSN)
    if load_model_use().chat:
        MODEL_CHAT, MODEL_NAME = load_model_chat()
        print(MODEL_CHAT, MODEL_NAME)
    else:
        print("未使用本地部署的大模型")






