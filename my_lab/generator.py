import time
def get_ai_reply_with_yield():
    # 模拟AI逐字生成，边生成边返回
    time.sleep(0.5)
    yield "我"  # 先返回第一个字，暂停函数
    time.sleep(0.5)
    yield "叫"  # 下次循环时继续，返回第二个字，再暂停
    time.sleep(0.5)
    yield "PgoAgent"  # 最后返回剩余内容

# 模拟“生成AI回复”的普通函数（只用return）
def get_ai_reply_no_yield():
    # 模拟AI逐字生成：我 → 叫 → PgoAgent
    time.sleep(1)  # 模拟生成耗时
    full_reply = "我叫PgoAgent"  # 只能等全部生成完
    return full_reply  # 一次性返回所有内容

# 可以看到是直接输出的
try:
    for chunk in get_ai_reply_no_yield(): # 这里直接是对字符串处理了for循环并非我们所需的yield
        print(chunk)
except TypeError as e:
    print(f"报错如下：{e}")  # 输出：报错：'str' object is not iterable

print("-----------------------")
# 正确用法：只能一次性接收
reply = get_ai_reply_no_yield()
print("一次性输出：", reply)  # 输出：一次性输出：我叫PgoAgent

# 可以用for循环逐段遍历！
print("流式输出：", end="")
for chunk in get_ai_reply_with_yield():
    print(chunk, end="", flush=True)  # 输出：流式输出：我叫PgoAgent（逐字出现，间隔0.5s）
print()
# 流水线：读取文本 → 清洗 → 分词 → 统计
def read_text():
    yield "hello world 123"
    time.sleep(1)
    yield "python generator is good"

def clean_text(text_gen):
    for text in text_gen:
        yield text.replace("123", "").strip()  # 清洗数据

def split_word(clean_gen):
    for text in clean_gen:
        yield text.split()  # 分词

# 串联流水线，逐段处理
for words in split_word(clean_text(read_text())):
    print(words)  # 输出：['hello', 'world']；['python', 'generator', 'is', 'good']

