import time
print("开始下载")
# for  i in range(10):
#     status = f"当前进度{i+1}/10...."
#     print(f"\r{status}\033[K", end="", flush=True)
#     time.sleep(0.5)
print("\rHello", end="", flush=True)
time.sleep(1)
print("\rHi   ", end="", flush=True)  # 注意这里加了空格，确保覆盖整个旧行
time.sleep(1)
print("\n下载完成！")
