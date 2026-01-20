# agent_grpc_server服务端
import asyncio
from concurrent import futures
from typing import Dict
import sys
import os
# 忽略jieba 分词库内部使用了已弃用的 pkg_resources API警告
import warnings
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
# 添加项目路径
from agent.agent_grpc import agent_pb2, agent_pb2_grpc
from agent.main_cli import AgentRunner, UserConfig # 相关的封装agent模块和用户数据
from agent.graph import create_graph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from agent.config import logger, animated_banner
from typing import Any
from agent.main_cli import test_db_connection
from langchain_core.messages import HumanMessage
import time
from agent.grpc_server import JWTInterceptor, load_server_credentials, GlobalRateLimitInterceptor, UserRateLimitInterceptor
from datetime import datetime
from agent.config import VERSION,DATABASE_DSN,SERVER_CONFIG
import grpc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..')) # 添加项目根目录到路径

def calculate_time_diff(start_date, end_date):
    """计算年份差,采用借位法"""
    years = end_date.year - start_date.year
    months = end_date.month - start_date.month
    days = end_date.day - start_date.day
    hours = end_date.hour - start_date.hour
    minutes = end_date.minute - start_date.minute

    # 处理借位
    if minutes < 0:
        minutes += 60
        hours -= 1

    if hours < 0:
        hours += 24
        days -= 1

    if days < 0:
        # 获取上个月的天数
        if end_date.month == 1: # 特殊年份-易错
            last_month = 12
            last_year = end_date.year - 1
        else:
            last_month = end_date.month - 1
            last_year = end_date.year

        # 计算上个月的天数
        if last_month in [4, 6, 9, 11]:
            days_in_last_month = 30
        elif last_month == 2:
            # 检查闰年
            if (last_year % 400 == 0) or (last_year % 100 != 0 and last_year % 4 == 0):
                days_in_last_month = 29
            else:
                days_in_last_month = 28
        else:
            days_in_last_month = 31
        # 借位计算
        days += days_in_last_month
        months -= 1

    if months < 0:
        months += 12
        years -= 1

    return years, months, days, hours, minutes

# 一个服务实现类
class AgentServiceImpl(agent_pb2_grpc.AgentServiceServicer): # gRPC 框架要求服务实现类必须继承对应的 Servicer 类
    """gRPC 服务实现类"""

    def __init__(self, graph):
        self.shared_graph = graph
        self.cancel_listeners_table: Dict[str, Any] = {} # 同一个公共变量
        self._table_lock = asyncio.Lock()
        self.start_time = datetime.now()



    async def Chat(self, request,context): # 这个方法严格遵循proto文件中定义的接口
        """非流式对话"""
        try:
            logger.info(f"GRPC | Chat 请求收到: user_id={request.user_config.user_id}, thread_id={request.user_config.thread_id}, input_length={len(request.user_input)}")
            if request.user_config.thread_id == "" or request.user_config.user_id == "":
                logger.warning("GRPC | Chat 请求缺少 user_config")
                return agent_pb2.ChatResponse(
                    success=False,
                    error_message="user_config is null"
                )
            # 请求的数据
            user_config:UserConfig = {
                "configurable": {
                    "thread_id": request.user_config.thread_id,
                    "user_id": request.user_config.user_id,
                    "chat_mode": request.user_config.chat_mode or "normal"
                },
                "recursion_limit": request.user_config.recursion_limit or 50
            }

            # 上述转换请求
            from agent.main_cli import CancelListener
            cancel_listener = CancelListener()
            thread_key = f"{request.user_config.user_id}_{request.user_config.thread_id}"
            async with self._table_lock:
                if thread_key in self.cancel_listeners_table:
                    old_listener = self.cancel_listeners_table[thread_key]
                    old_listener.should_cancel = True  # 取消旧请求
                self.cancel_listeners_table[thread_key] = cancel_listener

            try:
                logger.info(f"GRPC | Chat 开始处理，调用 agent_runner.chat()")
                logger.info(f"GRPC | Chat 参数: user_input='{request.user_input[:50]}...', user_config={user_config}")
                agent_runner = AgentRunner(self.shared_graph)
                logger.info(f"GRPC | Chat AgentRunner 创建成功，开始调用 chat()")
                start_time = time.time()
                reply, token_usage = await agent_runner.chat(
                    request.user_input,
                    user_config,
                    cancel_listener
                )
                elapsed_time = time.time() - start_time
                logger.info(f"GRPC | Chat 处理完成，耗时 {elapsed_time:.2f}秒，reply_length={len(reply)}, token_usage={token_usage}")
                logger.info(f"GRPC | Chat 准备返回响应")
                response = agent_pb2.ChatResponse(
                    reply=reply,
                    token_usage=token_usage,
                    success=True
                )
                logger.info(f"GRPC | Chat 响应对象创建成功，准备返回")
                return response
            finally:
                async with self._table_lock:
                    if thread_key in self.cancel_listeners_table:
                        # 检查是否是自己的 listener（更安全）
                        current_listener = self.cancel_listeners_table[thread_key]
                        if current_listener is cancel_listener:
                            del self.cancel_listeners_table[thread_key]


        except Exception as e:
            logger.error(f"GRPC | Chat error: {e}")
            return agent_pb2.ChatResponse(
                success=False,
                error_message=str(e)
            )

    async def ChatStream(self, request, context):
        """流式对话"""
        try:
            user_config = {
                "configurable": {
                    "thread_id": request.user_config.thread_id,
                    "user_id": request.user_config.user_id,
                    "chat_mode": "stream"
                },
                "recursion_limit": request.user_config.recursion_limit or 50
            }

            from agent.main_cli import CancelListener
            cancel_listener = CancelListener()
            thread_key = f"{request.user_config.user_id}_{request.user_config.thread_id}"
            async with self._table_lock:
                if thread_key in self.cancel_listeners_table:
                    old_listener = self.cancel_listeners_table[thread_key]
                    old_listener.should_cancel = True  # 取消旧请求
                self.cancel_listeners_table[thread_key] = cancel_listener

            try:
                agent_runner = AgentRunner(self.shared_graph) # 本graph
                async for chunk in agent_runner.chat_stream(
                        request.user_input,
                        user_config,
                        cancel_listener
                ):
                    # 值是函数返回的chunk
                    yield agent_pb2.StreamChunk( # 流式输出对应的值
                        output=chunk.get("output", ""),
                        final_response=chunk.get("final_response", False),
                        token=chunk.get("token", 0),
                        node_name=chunk.get("node_name", "")
                    )
            finally:
                async with self._table_lock:
                    if thread_key in self.cancel_listeners_table:
                        # 可选：检查是否是自己的 listener（更安全）
                        current_listener = self.cancel_listeners_table[thread_key]
                    if current_listener is cancel_listener:
                        del self.cancel_listeners_table[thread_key]

        except Exception as e:
            logger.error(f"ChatStream error: {e}")
            yield agent_pb2.StreamChunk(
                output=f"错误: {str(e)}",
                final_response=True,
                token=0
            )

    async def GetConversationHistory(self, request, context):
        """获取对话历史"""
        try:
            user_config = {
                "configurable": {
                    "thread_id": request.user_config.thread_id,
                    "user_id": request.user_config.user_id,
                    "chat_mode": request.user_config.chat_mode or "normal"
                },
                "recursion_limit": request.user_config.recursion_limit or 50
            }

            agent_runner = AgentRunner(self.shared_graph)
            history = await agent_runner.get_conversation_history(user_config) # 获取对应用户的历史对话

            conversation_pairs = []
            for pair in history.get("latest_conversation", []): # 遍历message列表

                role = "user" if isinstance(pair, HumanMessage) else "assistant"
                content = pair.content if hasattr(pair, 'content') else str(pair)
                conversation_pairs.append(
                    agent_pb2.ConversationPair(
                        role=role,
                        content=content,
                        timestamp=int(time.time())
                    )
                )

            return agent_pb2.HistoryResponse( # 最后的返回接口
                latest_conversation=conversation_pairs,
                cumulative_usage=history.get("CumulativeUsage", 0),
                summary=history.get("summary", "")
            )
        except Exception as e:
            logger.error(f"|GRPC|获取对话历史失败: {e}")
            return agent_pb2.HistoryResponse(
                latest_conversation=[],
                cumulative_usage=0,
                summary=""
            )

    async def CancelTask(self, request, context):
        """取消当前任务"""
        try:
            thread_key = f"{request.user_id}_{request.thread_id}"
            # 取消并删除对应的id需要加锁来保证线程安全
            async with self._table_lock:
                if thread_key in self.cancel_listeners_table:
                    cancel_listener = self.cancel_listeners_table[thread_key]
                    cancel_listener.should_cancel = True
                    return agent_pb2.CancelResponse(
                        success=True,
                        message="当前任务取消已请求"
                    )
                else:
                    return agent_pb2.CancelResponse(
                        success=False,
                        message="未找到对应的任务"
                    )
        except Exception as e:
            logger.error(f"CancelTask error: {e}")
            return agent_pb2.CancelResponse(
                success=False,
                message=f"取消任务失败: {str(e)}"
            )
    async def GetServerInfo(self, request, context):
        """获取当前服务器信息"""
        now_time = datetime.now()
        years,months,days,hours,minutes = calculate_time_diff(self.start_time, now_time)
        time_parts = []
        if years > 0:
            time_parts.append(str(years))
        if months > 0:
            time_parts.append(str(months))
        if days > 0:
            time_parts.append(str(days))
        if hours > 0:
            time_parts.append(str(hours))
        if not time_parts:
            time_parts.append("0")
        return agent_pb2.ServerInfo(
            version=VERSION,
            start_time= datetime.now().strftime("%Y-%m-%d %H:%M"),
            run_time = '-'.join(time_parts)
        )


async def serve(host: str = "[::]", port: int = 50051, DSN: str = "", max_threading: int = 10,send_size = 50 * 1024 * 1024,receive_size = 50 * 1024 * 1024 ):
    """启动 gRPC 服务器"""
    if not await test_db_connection(DSN): # 测试数据库连接
        logger.error("数据库连接失败，无法启动服务")
        return
    async with AsyncPostgresStore.from_conn_string(DATABASE_DSN) as store:
        await store.setup()
        logger.info("Postgresql Store 初始化成功!")

        async with AsyncPostgresSaver.from_conn_string(DATABASE_DSN) as checkpointer:
            await checkpointer.setup()
            logger.info("PostgresSaver checkpoint 初始化成功!")
            default_config = {
                "configurable": {
                    "thread_id": "init",
                    "user_id": "system",
                    "chat_mode": "normal"
                },
                "recursion_limit": 50
            }
            shared_graph = await create_graph(store, default_config, checkpointer=checkpointer)
            logger.info("graph任务图当前已创建") # 之所以可以共享创建任务图是因为对应的函数可以传入用户参数从而保持不同的状态

            # 创建对应的服务端的限流器对象-参数设置
            enable_jwt =SERVER_CONFIG.enable_jwt
            enable_global_rate_limit = SERVER_CONFIG.enable_global_rate_limit
            enable_user_rate_limit = SERVER_CONFIG.enable_user_rate_limit
            # TLS 现在默认启用，不再需要配置开关

            interceptors = []
            skip_methods = ["GetServerInfo"]
            if enable_global_rate_limit:
                ip_rate_interceptor = GlobalRateLimitInterceptor(
                    global_rate_per_sec=SERVER_CONFIG.global_rate_limit,
                    global_burst=SERVER_CONFIG.global_burst,
                    skip_methods=skip_methods,
                )
                interceptors.append(ip_rate_interceptor)
                logger.info("gRPC: 全体限流拦截器已启用")
            if enable_jwt:
                secret_key = os.getenv("GRPC_TOKEN", "MY_SECRET_KEY")
                jwt_interceptor = JWTInterceptor(
                    secret_key=secret_key,
                    token_header="authorization",
                    skip_methods=skip_methods  # GetServerInfo 不需要认证
                )
                interceptors.append(jwt_interceptor)
                logger.info("gRPC: JWT 拦截器已启用")

            # 3. 用户限流拦截器（基于用户ID）
            if enable_user_rate_limit:
                user_rate_interceptor = UserRateLimitInterceptor(
                    user_rate_per_minute=SERVER_CONFIG.user_rate_limit,  # 每个用户每分钟60个请求
                    user_burst=SERVER_CONFIG.user_burst,              # 突发120个请求
                    user_id_metadata_key="user_id",
                    skip_methods=skip_methods,
                    shards=64,                   # 64个分片减少锁竞争
                    bucket_ttl_sec=30 * 60,     # 30分钟未访问清理
                    cleanup_interval_sec=60
                )
                interceptors.append(user_rate_interceptor)
                logger.info("gRPC: 用户限流拦截器已启用")

            server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=max_threading),
                interceptors=interceptors, # 按顺序执行拦截器
                options=[('grpc.default_compression_algorithm', grpc.Compression.Gzip),
                        ('grpc.enable_retry',1),
                        ('grpc.keepalive_time_ms', 30000),
                        ('grpc.max_send_message_length', send_size),  # 50MB 发送
                        ('grpc.max_receive_message_length', receive_size),]  # 50MB 接收
                        )
            agent_pb2_grpc.add_AgentServiceServicer_to_server(
                AgentServiceImpl(shared_graph),
                server
            )

            listen_addr = f'{host}:{port}'
            # 默认使用 TLS，先添加端口，然后启动服务器（gRPC Python 的正确顺序）
            creds = load_server_credentials()  # 加载 TLS 证书
            server.add_secure_port(listen_addr, creds)
            await server.start()
            logger.info(f"gRPC: 服务器已启动（TLS），运行地址为: {listen_addr}")
            try:
                await server.wait_for_termination()
            except KeyboardInterrupt:
                logger.info("当前正在关闭服务器中...")
                await server.stop(5)
            finally:
                await store.teardown()
                await checkpointer.teardown()




if __name__ == "__main__":
    animated_banner()
    if sys.platform.startswith("win"): # 如果是windows系统
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # 设置事件循环策略Selector
    else:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy()) # 其他系统使用默认策略
    asyncio.run(serve(host= SERVER_CONFIG.host,
        port=SERVER_CONFIG.port,
        DSN=DATABASE_DSN,
        max_threading=SERVER_CONFIG.max_threads,
        send_size=SERVER_CONFIG.send_size,
        receive_size=SERVER_CONFIG.receive_size,
        ))
