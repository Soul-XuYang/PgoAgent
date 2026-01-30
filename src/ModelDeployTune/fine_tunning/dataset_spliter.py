# 数据集划分的代码
import json
from pathlib import Path
from sklearn.model_selection import train_test_split  # 使用对应的模块划分
from collections import Counter


# 这里未考虑内存优化，因为是几千条的样本数据


def split_dataset(
    input_file_path: str = "./temp/dataset_cleansing.jsonl",
    train_file_path: str = "./temp/train_dataset.jsonl",
    val_file_path: str = "./temp/validate_dataset.jsonl",
    val_ratio: float = 0.1,
    stratify_by_task: bool = True,
    seed: int = 42
):
    """划分训练集和验证集"""
    samples = []
    task_types = []
    line_num = 0
    failed_lines = 0
    with Path(input_file_path).open("r", encoding="utf-8") as f:
        for line in f:  # 按行遍历
            line = line.strip()
            line_num += 1
            if not line:
                continue
            try:
                sample = json.loads(line)
                samples.append(sample)
                # 提取任务类型用于分层抽样
                user_content = next(
                    (msg["content"] for msg in sample["messages"]
                     if msg["role"] == "user"), ""
                )  # 这里主要提取第一个用户消息，因为其本身为首要的用户问题和意图
                if "<TASK=DECISION>" in user_content:
                    task_types.append("decision")
                elif "<TASK=MEMORY>" in user_content:
                    task_types.append("memory")
                elif "<TASK=PLANNER>" in user_content:
                    task_types.append("planner")
                else:
                    task_types.append("others")
            except json.JSONDecodeError as e:
                print(f"第{line_num}行：JSON解析失败 - {e}，跳过")
                failed_lines += 1
            except Exception as e:
                print(f"第{line_num}行：未知错误 - {e}，跳过")
                failed_lines += 1
    total_samples = len(samples)
    print(
        f"数据解析完成 | 总行数：{line_num} | 有效样本：{total_samples} | 失败行数：{failed_lines}")
    print(f"任务类型分布（总）：{dict(Counter(task_types))}")
    # 分层抽样保证任务分布一致
    if stratify_by_task and len(set(task_types)) > 1:
        train_idx, val_idx = train_test_split(
            range(len(samples)),
            test_size=val_ratio,
            stratify=task_types,  # 分层抽样，按照标签划分数据集
            random_state=seed
        )
    else:
        train_idx, val_idx = train_test_split(
            range(len(samples)),
            test_size=val_ratio,
            random_state=seed
        )

    # 写入训练集
    with Path(train_file_path).open("w", encoding="utf-8") as f:
        for idx in train_idx:
            f.write(json.dumps(samples[idx], ensure_ascii=False) + "\n")

    # 写入验证集
    with Path(val_file_path).open("w", encoding="utf-8") as f:
        for idx in val_idx:
            f.write(json.dumps(samples[idx], ensure_ascii=False) + "\n")
    print("数据集划分完成! | 数据集统计结果如下")
    print(f"训练集: {len(train_idx)} 条")
    print(f"验证集: {len(val_idx)} 条")
    print(f"验证集比例: {len(val_idx)/len(samples)*100:.2f}%")


if __name__ == "__main__":
    split_dataset(val_ratio=0.1, stratify_by_task=True, seed=42)  # 分层抽样
