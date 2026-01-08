import asyncio


async def async_input(prompt: str = "") -> str:
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, input, prompt) # 将一个同步函数放入到线程执行


async def counter(cancel_event: asyncio.Event):
    """每 0.3 秒打印一次数字，直到收到取消信号"""
    i = 0
    while not cancel_event.is_set():
        print(f"[counter] i={i}")
        i += 1
        await asyncio.sleep(1)  # 这里会让出控制权给事件循环
    print("[counter] cancelled, stop.")


async def wait_for_cancel(cancel_event: asyncio.Event):
    """等待用户输入 cancel/c/取消，然后触发取消信号"""
    while not cancel_event.is_set():
        text = await async_input("Type 'cancel' / 'c' / '取消' to stop > ")

        if text.strip().lower() in {"cancel", "c", "取消"}:
            cancel_event.set()
            print("[cancel] received.")
            return
        else:
            print(f"[cancel] ignored input: {text!r}")


async def main():
    cancel_event = asyncio.Event()

    # 并发启动两个任务：
    # 1) counter：持续输出
    # 2) wait_for_cancel：等待你的输入
    t1 = asyncio.create_task(counter(cancel_event))
    t2 = asyncio.create_task(wait_for_cancel(cancel_event))

    # 等到两个任务都结束（cancel 后它们都会结束）
    await asyncio.gather(t1, t2)
    print("[main] all done.")


if __name__ == "__main__":
    asyncio.run(main())
