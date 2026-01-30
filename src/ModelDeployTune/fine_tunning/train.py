import matplotlib.pyplot as plt
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoTokenizer, AutoModelForCausalLM,
    TrainingArguments, Trainer,
    DataCollatorForSeq2Seq
)
from transformers import EarlyStoppingCallback
import torch
import loguru
import os
import torch.distributed as dist


logger = loguru.logger


# AutoTokenizer依据模型名加载对应的分词器和词编号
# AutoModelForCausalLM依据模型名加载并初始化对应的模型
# TrianingArguments则是训练超参数的配置容器
# Trainer是训练总控器，负责协调训练过程，包括数据加载、模型训练、评估等
# DataCollatorForSeq2Seq是数据集的预处理函数，用于将数据集转换为模型可以接受的格式,其作用是
# ① 把零散样本拼成批次（比如一次训 8 条）；
# ② 填充短样本（比如有的样本 100 个 ID，有的 200 个，统一填充到 200 个）；
# ③ 对齐输入和标签的填充（填充位置的标签置 - 100，模型忽略）；

MODEL_PATH = "../models/Qwen2.5-3B-Instruct"
OUTPUT_DIR = "./lora"
TRAIN_DATA_PATH = "./temp/train_dataset.jsonl"
VAL_DATA_PATH = "./temp/validate_dataset.jsonl"
MAX_LEN = 2048  # 这里依据训练集的长度配合-实际上判断用户的问题、使用工具以及用户画像必须要很大的长度

# 太大长度会导致填充过大导致训练过慢，消耗成本
model_name = os.path.basename(MODEL_PATH)  # 获取模型名称
# 分词器设置
tokenizer = AutoTokenizer.from_pretrained(
    MODEL_PATH, trust_remote_code=True)  # 运行执行本地的分词器
tokenizer.truncation_side = "left"  # 尽量保留结尾（assistant）-截断方向为左侧
if tokenizer.pad_token is None:  # 看当前的分词器是否自带填充
    tokenizer.pad_token = tokenizer.eos_token


model = AutoModelForCausalLM.from_pretrained(
    MODEL_PATH,
    trust_remote_code=True,
    dtype=torch.float16,  # 保留float16，减少显存占用
)


def print_model_device_distribution(model):
    device_count = {}
    for _, param in model.named_parameters():
        dev = param.device
        device_count[dev] = device_count.get(dev, 0) + 1
    logger.info("\n模型层的设备分布：")
    for dev, count in device_count.items():
        logger.info(f"设备 {dev} | 包含 {count} 层参数")


# 加载模型后调用
print_model_device_distribution(model)
logger.info(
    f"model total parameters:{sum(p.numel() for p in model.parameters())}")
logger.info(f"model dtype: {next(model.parameters()).dtype}")


model.config.max_length = MAX_LEN
model.config.pad_token_id = tokenizer.pad_token_id  # 告知填充id
model.config.use_cache = False  # 关闭注意力缓存
model.gradient_checkpointing_enable()  # 启用梯度检查点

# lora参数设置
lora_config = LoraConfig(
    r=16,  # 设置秩16
    lora_alpha=32,  # 比例参数
    lora_dropout=0.05,  # 稀疏参数
    bias="none",
    task_type="CAUSAL_LM",  # 从左到右的因果生成
    target_modules=["q_proj", "k_proj", "v_proj",
                    "o_proj", "gate_proj", "up_proj", "down_proj"],  # 激活函数层（像模型的“神经元开关”）
)
model = get_peft_model(model, lora_config)  # 注入lora
print("lora parameters:")
print(model.print_trainable_parameters())  # 打印可训练参数


def load_and_preprocess_data(train_path: str, val_path: str):
    # 加载训练集和验证集-这里加载jsonl文件只能用train格式
    train_dataset = load_dataset("json", data_files=train_path, split="train")
    val_dataset = load_dataset("json", data_files=val_path, split="train")

    def preprocess_function(example):
        """
        核心预处理逻辑：
        1. 按role筛选system/user/assistant消息
        2. 用官方Chat模板构建prompt
        3. 构造input_ids和labels（prompt部分置-100，只训练回答部分）
        """
        # 步骤1：按role提取消息（兼容消息顺序异常的情况）
        messages = example["messages"]
        system_msg = next(m for m in messages if m["role"] == "system")
        user_msg = next(m for m in messages if m["role"] == "user")
        assistant_msg = next(m for m in messages if m["role"] == "assistant")

        # 步骤2：构建Chat模板（Qwen2.5官方格式）
        chat_template = [
            system_msg,
            user_msg,
            {"role": "assistant", "content": ""}  # 生成prompt的结尾标记
        ]
        # 生成prompt（不分词，只拼接模板）
        prompt = tokenizer.apply_chat_template(
            chat_template,
            tokenize=False,
            add_generation_prompt=True,  # 必须加，标记assistant开始
        )
        # 回答内容
        answer = assistant_msg["content"]

        # 步骤3：拼接完整文本并分词
        full_text = prompt + answer
        tokenized_full = tokenizer(
            full_text,
            truncation=True,
            max_length=MAX_LEN,
            padding=False,
            return_attention_mask=True,
        )
        input_ids = tokenized_full["input_ids"]
        attention_mask = tokenized_full["attention_mask"]

        # 步骤4：构造labels（prompt部分置-100，不计算loss）
        labels = input_ids.copy()
        # 计算prompt的token长度
        tokenized_prompt = tokenizer(
            prompt,
            truncation=True,
            max_length=MAX_LEN,
            padding=False,
            add_special_tokens=False,  # 避免重复加特殊token
        )
        prompt_len = len(tokenized_prompt["input_ids"])
        # 屏蔽prompt部分的loss
        if prompt_len < len(labels):
            labels[:prompt_len] = [-100] * prompt_len

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels
        }

    # 应用上述写的序列编号的预处理函数
    processed_train = train_dataset.map(
        preprocess_function,
        remove_columns=train_dataset.column_names,  # 删除原始列，只保留处理后的列
        num_proc=4  # 多进程加速
    )
    processed_val = val_dataset.map(
        preprocess_function,
        remove_columns=val_dataset.column_names,
        num_proc=4
    )

    return processed_train, processed_val


# 记录训练指标
def write_train_metrics(log_history, txt_path):
    """修复：添加字段判空，避免None值格式化报错"""
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("step,epoch,loss,learning_rate,grad_norm\n")
        for log in log_history:
            if "loss" not in log or "step" not in log:
                continue  # 跳过无训练Loss的条目
            # 判空：给None值默认值
            step = log.get("step", 0)
            epoch = log.get("epoch", 0.0)
            loss = log.get("loss", 0.0)
            lr = log.get("learning_rate", 0.0)
            grad_norm = log.get("grad_norm", 0.0)
            # 格式化写入
            f.write(f"{step},{epoch:.4f},{loss:.4f},{lr:.6f},{grad_norm:.4f}\n")


def write_eval_metrics(log_history, txt_path):
    """修复：添加字段判空，避免None值格式化报错"""
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write("step,epoch,eval_loss,learning_rate,grad_norm\n")
        for log in log_history:
            if "eval_loss" not in log or "step" not in log:
                continue  # 跳过无验证Loss的条目
            # 判空：给None值默认值
            step = log.get("step", 0)
            epoch = log.get("epoch", 0.0)
            eval_loss = log.get("eval_loss", 0.0)
            lr = log.get("learning_rate", 0.0)
            grad_norm = log.get("grad_norm", 0.0)
            # 格式化写入
            f.write(
                f"{step},{epoch:.4f},{eval_loss:.4f},{lr:.6f},{grad_norm:.4f}\n")


# 加载预处理后的数据集
train_dataset, val_dataset = load_and_preprocess_data(
    TRAIN_DATA_PATH, VAL_DATA_PATH)

data_collator = DataCollatorForSeq2Seq(  # 整理序列数据
    tokenizer=tokenizer,  # 分词器结构一致
    padding="longest",  # 按照最长填充
    model=model,  # 传入模型结构
    label_pad_token_id=-100,  # 表示忽略
)

args = TrainingArguments(
    output_dir=OUTPUT_DIR,
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    gradient_accumulation_steps=2,
    num_train_epochs=5,
    learning_rate=1e-4,          # 更稳的起点
    warmup_ratio=0.05,  # 预热比例
    lr_scheduler_type="cosine",  # 余弦调度下降学习率
    fp16=True,                   # 本身支持float16
    logging_steps=100,
    save_steps=100,
    eval_strategy="steps",   # 测试
    eval_steps=100,  # 每100步评估一次（和save_steps对齐）
    save_total_limit=2,
    group_by_length=True,
    remove_unused_columns=False,  # 不要删除
    logging_dir=f"{OUTPUT_DIR}/logs",
    ddp_find_unused_parameters=False,  # 多卡必须设为False
    report_to="none",
    run_name="finetune",
    load_best_model_at_end=True,  # 加载最好的模型
)

trainer = Trainer(
    model=model,
    args=args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,  # 传入验证集
    data_collator=data_collator,
    callbacks=[EarlyStoppingCallback(early_stopping_patience=5,
                                     early_stopping_threshold=0.01)],  # 早停法 -防止过拟合
)
if trainer.is_world_process_zero():
    logger.add(f"{OUTPUT_DIR}/fine_tune.log")
trainer.train()
if trainer.is_world_process_zero():
    logger.info("训练完成")
    log_history = trainer.state.log_history
    # 调用函数，写入TXT
    write_train_metrics(log_history, f"{OUTPUT_DIR}/training_metrics.txt")
    write_eval_metrics(log_history, f"{OUTPUT_DIR}/eval_metrics.txt")
    train_steps, train_losses = [], []
    val_steps, val_losses = [], []
    for log in log_history:
        # 训练loss
        if "loss" in log and "step" in log:
            train_steps.append(log["step"])
            train_losses.append(log["loss"])
        # 验证loss
        if "eval_loss" in log and "step" in log:
            val_steps.append(log["step"])
            val_losses.append(log["eval_loss"])

    # 绘图
    plt.figure(figsize=(12, 6))
    plt.plot(train_steps, train_losses, label="Train_Loss",
             color="red", linewidth=1.5)
    plt.plot(val_steps, val_losses, label="Eval_Loss",
             color="blue", linewidth=1.5)
    plt.xlabel("Global_Steps")
    plt.ylabel("Loss")
    plt.title(f"{os.path.basename(MODEL_PATH)} LoRA Fine-Tune Loss Curve")
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(f"../pictures/loss_curve.png", dpi=300, bbox_inches="tight")

    # 保存模型
    trainer.save_model()
    tokenizer.save_pretrained(OUTPUT_DIR)
    logger.info(f"模型已保存到 {OUTPUT_DIR}")
    if dist.is_initialized():
        dist.destroy_process_group()
    logger.info("请合并模型并测试")
