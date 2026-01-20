import asyncio
import sys
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from langchain_core.messages import HumanMessage
from langgraph.store.postgres import AsyncPostgresStore
from agent.config import DATABASE_DSN
from graph import create_graph
from agent.config import logger
from typing import TypedDict
import time
import threading
import queue
from config import animated_banner


class Configurable(TypedDict):
    thread_id: str
    user_id: str
    chat_mode: str


class UserConfig(TypedDict):
    configurable: Configurable
    recursion_limit: int


class StreamOutput(TypedDict):
    """流式输出"""
    output: str
    final_response: bool
    node_name:str
    token: int

class AgentState(TypedDict):
    """流式输出"""
    CumulativeUsage: int
    summary: str
    latest_conversation: list

def node_output(node: str) -> str:
    node_dict = {
        "planner_node": "Pgo正在大模型计划...",
        "decision_node": "Pgo大模型正在决策...",
        "tools_node": "Pgo大模型正在使用工具...",
        "summary_node": "Pgo大模型正在总结当前内容...",
        "agent_node": "Pgo大模型正在执行相应计划步骤...",
    }
    return node_dict.get(node, "Pgo大模型正在思考中...")


class CancelListener:
    """后台监听用户取消输入的类 - 使用独立线程监听"""

    def __init__(self):
        self.should_cancel = False # 标志位
        self.input_queue = queue.Queue()
        self.listener_thread = None
        self.stop_flag = threading.Event()

    def _input_listener(self):
        """独立线程监听输入-跨平台使用"""
        while not self.stop_flag.is_set():
            try:
                # 使用非阻塞方式检查是否该停止
                if self.stop_flag.wait(0.1):
                    break
                # 检查是否有输入（带超时）
                import sys
                import select
                if sys.platform == "win32":
                    # Windows 上使用 msvcrt
                    import msvcrt
                    if msvcrt.kbhit():
                        line = input()
                        if line.strip().lower() in {"cancel", "c", "取消"}:
                            self.should_cancel = True
                            break
                else:
                    # Unix/Linux 使用 select
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        line = sys.stdin.readline().strip()
                        if line.lower() in {"cancel", "c", "取消"}:
                            self.should_cancel = True
                            break
            except KeyboardInterrupt:
                # 处理 用户的Ctrl+C 中断
                self.should_cancel = True
                break
            except Exception as e:
                logger. warning(f"中断错误：{e}")



    def start(self):
        """启动监听线程"""
        self.should_cancel = False
        self.stop_flag.clear()
        self.listener_thread = threading.Thread(target=self._input_listener, daemon=True)
        self.listener_thread.start()

    def stop(self):
        """停止监听线程"""
        self.stop_flag.set()
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=0.5)

    def is_cancelled(self):
        """检查是否被取消"""
        return self.should_cancel

    def reset(self):
        """重置取消状态"""
        self.stop()
        self.should_cancel = False


class AgentRunner:
    """简单封装一层，复用 _chat_impl 的思路"""

    def __init__(self, graph):
        self._graph = graph  # 构建所需的graph

    async def chat(self, user_input: str, user_config: UserConfig, cancel_listener: CancelListener = None) -> (
    str, int):
        logger.info(f"AgentRunner.chat() 开始: user_input长度={len(user_input)}, user_config={user_config}")
        if not user_config:
            raise ValueError("请提供用户配置信息")
        chat_state = {
            "messages": [HumanMessage(content=user_input)],
            "context": {},
        }
        logger.info(f"AgentRunner.chat() chat_state 创建完成")

        # 如果有对应的监听器，启动监听
        if cancel_listener:
            cancel_listener.start()
            logger.info(f"AgentRunner.chat() cancel_listener 已启动")

        try:
            logger.info(f"AgentRunner.chat() 准备调用 graph.ainvoke()")
            # 创建主任务
            main_task = asyncio.create_task(self._graph.ainvoke(chat_state, config=user_config))
            logger.info(f"AgentRunner.chat() graph.ainvoke() 任务已创建，开始等待完成")
            # 轮询检查取消状态
            poll_count = 0
            while not main_task.done():
                if cancel_listener and cancel_listener.is_cancelled():
                    logger.warning(f"AgentRunner.chat() 检测到取消信号")
                    main_task.cancel()
                    try:
                        await main_task
                    except asyncio.CancelledError:
                        pass
                    return "⚠️ 任务已被用户取消",  0
                await asyncio.sleep(0.1)  # 避免busy-wait
                poll_count += 1
                if poll_count % 50 == 0:  # 每5秒打印一次
                    logger.info(f"AgentRunner.chat() 等待中... 已等待 {poll_count * 0.1:.1f} 秒")

            logger.info(f"AgentRunner.chat() graph.ainvoke() 任务完成，开始处理结果")
            result = main_task.result()
            logger.info(f"AgentRunner.chat() 结果获取成功，messages数量={len(result.get('messages', []))}")
            final_msg = result["messages"][-1]
            final_token = result.get("usages", {}).get("total", 0)
            logger.info(f"AgentRunner.chat() 准备返回: reply_length={len(final_msg.content)}, token={final_token}")
            return final_msg.content, final_token

        except Exception as e:
            logger.error(f"AgentRunner.chat() 发生异常: {e}", exc_info=True)
            raise
        finally:
            if cancel_listener:
                cancel_listener.stop()
                logger.info(f"AgentRunner.chat() cancel_listener 已停止")

    async def chat_stream(self, user_input: str, user_config: UserConfig, cancel_listener: CancelListener = None):
        """流式返回响应内容"""
        if not user_config:
            raise ValueError("请提供用户配置信息")

        chat_state = {
            "messages": [HumanMessage(content=user_input)],
            "context": {},
        }
        full_reply = ""
        total_token = 0
        valid_nodes = {"chat_node", "answer-thinking", "long_memory_node"}

        # 如果有对应的监听器，启动监听
        if cancel_listener:
            cancel_listener.start()

        try:
            stream_generator = self._graph.astream(chat_state, config=user_config)

            async for chunk in stream_generator:
                # 检查是否被取消
                if cancel_listener and cancel_listener.is_cancelled():
                    yield StreamOutput(
                        output="⚠️ 任务已被用户取消",
                        final_response=True,
                        token=total_token,
                        node_name=""
                    )
                    return

                for node, output in chunk.items():
                    node_token = output.get("usages", {}).get("total", 0)
                    total_token += node_token
                    if node not in valid_nodes:
                        yield StreamOutput(
                            output=node_output(node),
                            final_response=False,
                            node_name=node,
                            token=node_token
                        )
                        continue
                    if node in valid_nodes and node != "long_memory_node":
                        full_reply = output.get("messages")[-1].content
                        continue
                    if node == "long_memory_node":
                        yield StreamOutput(
                            output=full_reply,
                            final_response=True,
                            node_name=node,
                            token=total_token
                        )
        finally:
            if cancel_listener:
                cancel_listener.stop()

    async def get_conversation_history(self, user_config: UserConfig) -> dict:
        """依据用户ID获取当前会话的对话历史和状态信息"""
        try:
            # 从 checkpoint 获取当前状态
            state_snapshot = await self._graph.aget_state(user_config)  # 这个是graph里的一个函数方法
            if not state_snapshot or not state_snapshot.values:
                return AgentState(
                    latest_conversation=[],
                    CumulativeUsage=0,
                    summary="",
                )

            state = state_snapshot.values
            conversation_pairs = state.get("conversation_pairs", [])
            context = state.get("context", {})
            usages = state.get("usages", {})

            return AgentState(
                    latest_conversation=conversation_pairs,
                    CumulativeUsage=usages.get("total", 0),
                    summary=context.get("summary", ""),
                )
        except Exception as e:
            logger.error(f"获取对话历史失败: {e}")
            return AgentState(
                    latest_conversation=[],
                    CumulativeUsage=0,
                    summary="",
                )

async def test_db_connection(dsn: str, timeout: int = 10) -> bool:
    """直接测试数据库连接，快速失败"""
    try:
        logger.info(f"正在测试数据库连接...")
        conn = await asyncio.wait_for(AsyncConnection.connect(dsn), timeout=timeout) # 给一个异步协程设置超时时间
        await conn.close()
        await conn.close()
        logger.info("当前数据库连接成功!")
        return True
    except TimeoutError:
        logger.error("❌ 数据库连接超时，请检查数据库服务是否运行正常")
        return False
    except Exception as e:
        logger.error(f"❌ 数据库连接失败: {e}")
        logger.error(f"   请检查 PostgreSQL 服务是否运行，以及 DATABASE_DSN 配置是否正确")
        return False

async def main(user_config: UserConfig):
    # 先测试数据库连接
    if not await test_db_connection(DATABASE_DSN):
        logger.error("数据库连接失败，程序退出")
        return
    if not user_config:
        logger.error(f"当前用户的配置信息为空，请传入对应参数")
        return
    # checkpointer 和 Store 都是上下文管理
    async with AsyncPostgresStore.from_conn_string(DATABASE_DSN) as store:
        await store.setup()
        logger.info("Postgresql Store 数据初始化成功!")
        async with AsyncPostgresSaver.from_conn_string(DATABASE_DSN) as checkpointer:
            await checkpointer.setup()
            logger.info("PostgresSaver checkpoint 初始化成功!")

             # 这里是一个测试的用户配置输入
            graph = await create_graph(store, user_config, checkpointer=checkpointer)
            agent = AgentRunner(graph)
            logger.info("Graph 构建完成，进入终端对话模式...(输入 exit/quit 退出)")
            print("=" * 60)
            print("1. 输入 'exit'/'quit' 退出程序")
            print("2. 输入 'stream' 切换流式输出，'normal' 切换普通输出")
            print("3. 在 Agent 执行过程中，可输入 'cancel'/'c'/'取消' 来中断")
            print("=" * 60)
            init_state= await agent.get_conversation_history(user_config)
            total_token = init_state.get("CumulativeUsage", 0)
            mode = user_config["configurable"].get("chat_mode", "normal")
            while True:
                user_input = input("用户> ").strip()
                if user_input == "" or user_input == "\n":
                    print("输入为空，请重新输入内容!")
                    continue
                if user_input.lower() in {"exit", "quit", "q", "e"}:
                    print("退出当前对话")
                    break

                if user_input.lower() == "stream":
                    mode = "stream"
                    print("已切换到流式输出模式")
                    continue

                if user_input.lower() == "normal":
                    mode = "normal"
                    print("已切换到普通输出模式")
                    continue

                # 输入对应的内容
                start_time = time.time()
                # 创建取消监听器
                cancel_listener = CancelListener()
                try:
                    if mode == "stream":
                        async for chunk in agent.chat_stream(user_input, user_config, cancel_listener):
                            if isinstance(chunk, dict) and chunk.get("final_response") == True:
                                reply = chunk.get("output", "")
                                print("\nPgoAgent> ", reply)
                                current_token = chunk.get("token", 0)
                            else:
                                print("\r" + chunk.get("output", ""), end="", flush=True)
                        print(f"|系统信息| token用量:{current_token}, 耗时:{time.time() - start_time:.2f}s")
                    else:
                        reply, current_token = await agent.chat(user_input, user_config, cancel_listener)
                        usage_delta = current_token-total_token
                        total_token = current_token
                        print("PgoAgent> ", reply)
                        print(f"|系统信息| token用量:{usage_delta}, 耗时:{time.time() - start_time:.2f}s")

                except asyncio.CancelledError:
                    print("\n⚠️ 任务已被取消")
                except Exception as e:
                    print("调用出错：", e)
                    import traceback
                    logger.error(traceback.format_exc())
                finally:
                    # 重置取消监听器
                    cancel_listener.reset()
    print("当前Pgo CLI程序已结束")




if __name__ == "__main__":
    animated_banner()
    if sys.platform.startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy()) # 设置事件循环策略-专门对于win系统的
    # 测试用户的数据 - 对应的对话ID和用户ID
    asyncio.run(main(user_config = {"configurable": {"thread_id": "002", "user_id": "user_003", "chat_mode": "stream"},"recursion_limit": 50  }))
    # 你好，我叫jack，请问你叫什么呢?
