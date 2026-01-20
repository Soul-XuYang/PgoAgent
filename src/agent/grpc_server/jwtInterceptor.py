import grpc
from typing import Optional
from agent.config import logger
import jwt
from cachetools import TTLCache
from .abort import _abort_like_handler
import pathlib
from agent.config.basic_config import PROJECT_ROOT


# JWT 拦截器
class JWTInterceptor(grpc.aio.ServerInterceptor):
    """
    JWT 认证拦截器
    从请求的 metadata 中提取 JWT token 并验证
    """
    def __init__(self, secret_key: str, token_header: str = "authorization",
            skip_methods: Optional[list] = None):
        """
        初始化 JWT 拦截器

        Args:
            secret_key: JWT 签名密钥，需要自定义设置当然也可以生成一个
            token_header: metadata 中 token 的 key，默认为 "authorization"
            skip_methods: 不需要验证的方法列表，默认为空
        """
        self.secret_key = secret_key
        self.token_header = token_header.lower()  # gRPC metadata 的 key 是小写的
        self.skip_methods = skip_methods or []
        self.cache = TTLCache(maxsize=1000,ttl =600)



    # 规定拦截方法-输入为continuation和handler_call_details,一个是服务端注册的函数，一个是handler_call_details输入
    async def intercept_service(self, continuation, handler_call_details):
        """拦截服务调用"""
        method_name = handler_call_details.method.split('/')[-1]  # 获取方法名
        # 跳过不需要验证的方法
        if method_name in self.skip_methods:
            return await continuation(handler_call_details) # 继续处理请求

        # 从 metadata 中获取 token
        metadata = dict(handler_call_details.invocation_metadata)
        token = None
        # 尝试从不同的 header 名称获取 token
        for key in [self.token_header, "authorization", "token"]: # 尝试不同的键
            if key in metadata:
                token = metadata[key]
                break

        if not token:
            logger.warning(f"JWT拦截器已拦截该请求: 该方法 {method_name} 缺少 token")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.UNAUTHENTICATED,
                "该请求缺少认证 token，请在 metadata 中提供 authorization"
            )

        # 移除 "Bearer " 前缀（如果存在）
        if token.startswith("Bearer "):
            token = token[7:] # 赋值

        try:
            if token in self.cache:
                is_valid,payload = self.cache[token]
                if not is_valid:
                    handler = await continuation(handler_call_details)
                    return _abort_like_handler(
                        handler,
                        grpc.StatusCode.UNAUTHENTICATED,
                        "当前token 已过期"
                    )
            else:
                # 保证不在缓存里肯定要，else保证再缓存里无需解析，验证和解析 JWT
                payload = jwt.decode(
                    token,
                    self.secret_key,
                    algorithms=["HS256"]  # HS256加密解密
                )
                # 将对应的payload信息加载进去
                self.cache[token] = (True, payload)

            # 将用户信息添加到 metadata 中，防止每次都需要解析JWT
            new_metadata = list(handler_call_details.invocation_metadata)
            new_metadata.append(("user_id", payload.get("user_id", "")))
            new_metadata.append(("user_name", payload.get("user_name", "")))

            # HandlerCallDetails 不能直接构造，创建一个包装类来传递更新的 metadata
            class UpdatedHandlerCallDetails:
                def __init__(self, original_details, new_metadata):
                    self.method = original_details.method
                    self.invocation_metadata = new_metadata
                    # 保留其他可能的属性
                    for attr in ['timeout', 'request_metadata']:
                        if hasattr(original_details, attr):
                            setattr(self, attr, getattr(original_details, attr))
            
            updated_details = UpdatedHandlerCallDetails(handler_call_details, new_metadata)

            logger.debug(f"JWT拦截器: 方法 {method_name} 认证成功，用户: {payload.get('user_id')}")

            return await continuation(updated_details) # 使用更新后的 details

        except jwt.ExpiredSignatureError: # 捕获过期的token错误
            logger.warning(f"JWT拦截器: token 已过期")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.UNAUTHENTICATED,
                "token 已过期"
            )
        except jwt.InvalidTokenError as e: # 捕获无效的token错误
            logger.warning(f"JWT拦截器: token 无效 - {e}")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.UNAUTHENTICATED,
                f"token 无效: {str(e)}"
            )
        except Exception as e: # 捕获其他错误
            logger.error(f"JWT拦截器: 验证 token 时发生异常错误 - {e}")
            handler = await continuation(handler_call_details)
            return _abort_like_handler(
                handler,
                grpc.StatusCode.INTERNAL,
                f"认证过程发生异常错误: {str(e)}"
            )


def load_server_credentials(
    cert_path: str = "certs/server.crt",
    key_path: str = "certs/server.key",
) -> grpc.ServerCredentials:
    """从文件加载 TLS 证书，生成 gRPC 用的 ServerCredentials"""
    # PROJECT_ROOT 指向的是 src 目录，这里取它的上一级作为项目根目录
    base_dir = pathlib.Path(PROJECT_ROOT).parent
    cert_file = pathlib.Path(cert_path)
    key_file = pathlib.Path(key_path)

    # 如果是相对路径，则默认相对于项目根目录 PROJECT_ROOT
    if not cert_file.is_absolute():
        cert_file = base_dir / cert_file
    if not key_file.is_absolute():
        key_file = base_dir / key_file

    if not cert_file.exists() or not key_file.exists():
        raise FileNotFoundError(
            f"TLS 证书或私钥不存在:"
            f"  cert: {cert_file}"
            f"  key : {key_file}"
        )

    # read_bytes(): 读取文件的二进制内容
    cert_chain = cert_file.read_bytes()
    private_key = key_file.read_bytes()
    return grpc.ssl_server_credentials([(private_key, cert_chain)])
