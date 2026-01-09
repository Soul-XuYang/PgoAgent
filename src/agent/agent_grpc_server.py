import asyncio
import grpc
from concurrent import futures
from typing import Dict
import sys
import os
# 添加项目路径
from agent.agent_grpc import agent_pb2, agent_pb2_grpc
from agent.main_cli import AgentRunner, UserConfig # 相关的封装agent模块和用户数据
from agent.graph import create_graph
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.store.postgres import AsyncPostgresStore
from agent.config import logger
from typing import Any
from agent.main_cli import test_db_connection
from langchain_core.messages import HumanMessage
import time
from datetime import datetime
from agent.config import VERSION,DATABASE_DSN
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..')) # 添加项目根目录到路径
date_time = datetime.now() # 全局变量
def calculate_time_diff(start_date, end_date):
    # 计算年份差
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

    def __init__(self, store, checkpointer):
        self.store = store
        self.checkpointer = checkpointer
        self.cancel_listeners_table: Dict[str, Any] = {}

    async def _create_agent_runner(self, user_config: dict):
        """为每个用户请求创建独立的langgraph的agent_runner"""
        graph = await create_graph(self.store, user_config, checkpointer=self.checkpointer)
        return AgentRunner(graph)

    async def Chat(self, request,context): # 这个方法严格遵循proto文件中定义的接口
        """非流式对话"""
        try:
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
            self.cancel_listeners_table[thread_key] = cancel_listener # 构建一个共享id，到时候可以依据id来取消请求

            try:
                agent_runner = await self._create_agent_runner(user_config) # 创建agent_runner
                reply, token_usage = await agent_runner.chat( # 调用当前的chat函数
                    request.user_input,
                    user_config,
                    cancel_listener
                )
                return agent_pb2.ChatResponse(
                    reply=reply,
                    token_usage=token_usage,
                    success=True
                )
            finally:
                if thread_key in self.cancel_listeners_table:
                    del self.cancel_listeners_table[thread_key] # 删除对应的id防止冲突

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
            self.cancel_listeners_table[thread_key] = cancel_listener

            try:
                agent_runner = await self._create_agent_runner(user_config)
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
                if thread_key in self.cancel_listeners_table:
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

            agent_runner = await self._create_agent_runner(user_config)
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
    async def GetServiceInfo(self, request, context):
        """获取当前服务器信息"""
        now_time = datetime.now()
        years,months,days,hours,minutes = calculate_time_diff(date_time, now_time)
        time_parts = []
        if years > 0:
            time_parts.append(str(years))
        if months > 0:
            time_parts.append(str(months))
        if days > 0:
            time_parts.append(str(days))
        if hours > 0:
            time_parts.append(str(hours))
        return agent_pb2.ServerInfo(
            version=VERSION,
            run_time = '-'.join(time_parts)
        )


async def serve(host: str = "[::]", port: int = 50051, DATABASE_DSN: str = "",max_threadings: int = 10):
    """启动 gRPC 服务器"""
    if not await test_db_connection(DATABASE_DSN): # 测试数据库连接
        logger.error("数据库连接失败，无法启动服务")
        return
    async with AsyncPostgresStore.from_conn_string(DATABASE_DSN) as store:
        await store.setup()
        logger.info("Postgresql Store 初始化成功!")

        async with AsyncPostgresSaver.from_conn_string(DATABASE_DSN) as checkpointer:
            await checkpointer.setup()
            logger.info("PostgresSaver checkpoint 初始化成功!")
            # 正式启动服务器
            server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=max_threadings)) # 启动异步服务器
            agent_pb2_grpc.add_AgentServiceServicer_to_server( # 将上述的服务和服务器添加到对应的服务函数里
                AgentServiceImpl(store, checkpointer),
                server
            )

            listen_addr = f'{host}:{port}'
            server.add_insecure_port(listen_addr)
            await server.start()
            logger.info(f"gRPC 服务器已启动，运行地址为: {listen_addr}")

            try:
                await server.wait_for_termination() # 一直等待直到服务器终止
            except KeyboardInterrupt:
                logger.info("当前正在关闭服务器...")
                await server.stop(5) # 等待5秒后关闭服务器


if __name__ == "__main__":
    import sys
    logger.info(f"开始启动当前的PgoAgent gRPC服务端服务,版本号: {VERSION}")
    if sys.platform.startswith("win"): # 如果是windows系统
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # 设置事件循环策略Selector
    else:
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy()) # 其他系统使用默认策略
    asyncio.run(serve(port=50051, DATABASE_DSN=DATABASE_DSN, max_threadings=10))
