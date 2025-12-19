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
def load_database_config(env: str = "dev")->DatabaseConfig:
    """读取相关的配置文件"""
    try:
        config_path = Path(__file__).parent.parent.parent / "config.toml"
        with open(config_path, "rb") as f: # 二进制加载
            config = tomllib.load(f)
        if env not in ["dev", "prod"] or env not in config:
            raise ValueError(f"配置环境输入错误: {env}")
        db_config = config[env]
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
def get_dsn(env:str ='dev')->str:
    database_config = load_database_config(env)
    return f"{database_config.type}://{database_config.user}:{database_config.password}@{database_config.host}:{database_config.port}/{database_config.dbname}"
DATABASE_DSN=get_dsn()




