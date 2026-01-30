# 数据清洗
import json
from pathlib import Path
from collections import Counter
from tqdm import tqdm
IN_FILE = "./temp/dataset_message.jsonl"
OUT_FILE = "./temp/dataset_cleansing.jsonl"


def is_valid_sample(sample: dict) -> bool:
    """检查样本是否有效
    - 至少包含 system + user + assistant
    - 长度
    - 内容非空
    """
    if "messages" not in sample:
        return False

    messages = sample["messages"]
    if not isinstance(messages, list) or len(messages) < 3:
        return False

    # 必须有 system + user + assistant
    roles = [msg.get("role") for msg in messages]
    if "system" not in roles or "user" not in roles or "assistant" not in roles:
        return False

    # 检查内容是否为空
    for msg in messages:
        content = msg.get("content", "").strip()
        if not content:
            return False

    # 检查长度（避免过长或过短）
    total_len = sum(len(msg.get("content", "")) for msg in messages)
    if total_len < 10 or total_len > 10000:  # 可根据需要调整
        return False

    return True


def get_sample_key(sample: dict) -> str:
    """生成样本的唯一标识（用于去重）"""
    messages = sample["messages"]
    user_content = next((msg["content"]
                        for msg in messages if msg["role"] == "user"), "")
    assistant_content = next(
        (msg["content"] for msg in messages if msg["role"] == "assistant"), "")
    if not user_content or not assistant_content:
        print("警告:在样本内，该数据为空！")
    return f"{user_content}|{assistant_content}"


def detect_task_type(sample: dict) -> str:
    """检测任务类型-进行统计"""
    messages = sample["messages"]
    user_content = next((msg["content"]
                        for msg in messages if msg["role"] == "user"), "")

    if "<TASK=DECISION>" in user_content:
        return "decision"
    elif "<TASK=MEMORY>" in user_content:
        return "memory"
    elif "<TASK=PLANNER>" in user_content:
        return "planner"
    else:
        return "others"


def clean_text(text: str) -> str:
    """清理文本中的特殊字符和多余空格"""
    # 替换特殊字符
    text = text.replace("\t", " ").replace("\\", " ").replace("\r", " ")
    # 去除多余空格
    text = text.strip()
    return text


def clean_data(file_in_path: str = IN_FILE, file_out_path: str = OUT_FILE, max_duplicates: int = 3, top_n: int = 5):
    checkpoint = {}  # 用于记录每个样本的重复次数和对应的key
    stats = Counter()
    valid_count = 0
    invalid_count = 0
    excessive_duplicate_count = 0
    empty_line_count = 0
    in_path = Path(file_in_path)
    out_path = Path(file_out_path)
    # Path对象打开对应的文本
    with in_path.open("r", encoding="utf-8") as file_in, out_path.open("w", encoding="utf-8") as file_out:
        for line in tqdm(file_in, desc="清洗当前的数据"):
            line = line.strip()
            if not line:
                empty_line_count += 1
                continue

            try:
                sample = json.loads(line)  # 加载当前样本的数据
            except json.JSONDecodeError:  # 仅捕获JSON解析错误
                invalid_count += 1
                continue
            except Exception as e:  # 其他异常单独记录（便于排查）
                print(f"非预期异常：{str(e)}，行内容：{line[:50]}...")
                invalid_count += 1
                continue

            # 格式验证
            if not is_valid_sample(sample):
                invalid_count += 1
                continue

            # 去重
            key = get_sample_key(sample)
            current_count = checkpoint.get(key, 0)

            if current_count >= max_duplicates:
                # 超过允许的重复次数，跳过
                excessive_duplicate_count += 1
                continue

            checkpoint[key] = current_count + 1  # 更新对应的重复次数
            # 统计任务类型
            task_type = detect_task_type(sample)
            stats[task_type] += 1

            # 写入清洗后的数据
            for msg in sample["messages"]:
                if "content" in msg and isinstance(msg["content"], str):
                    msg["content"] = clean_text(msg["content"])
            file_out.write(json.dumps(sample, ensure_ascii=False) + "\n")
            valid_count += 1

    print("\n" + "=" * 40)
    print("当前数据集的样本数据清洗完成！")
    print("=" * 40)
    print(f"有效样本: {valid_count}")
    print(f"无效样本: {invalid_count}")
    print(f"空样本  : {empty_line_count}")
    print(f"重复样本: {excessive_duplicate_count}")
    print(f"\n任务分布:")
    for task, count in stats.most_common(top_n):  # 前top_n个类别展示哈希表
        print(f"任务:{task} | 总数:{count}")
    print("=" * 40)


if __name__ == "__main__":
    clean_data(max_duplicates=4, top_n=5)  # 实际上只有极个别重复很多
