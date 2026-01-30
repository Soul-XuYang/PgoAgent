import torch
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer

import os

BASE_MODEL = "../models/Qwen2.5-3B-Instruct" 
LORA_WEIGHTS = "./lora" # 加载的权重
MERGED_MODEL = "../models/qwen2.5-3b-lora-merged" # 合并后的模型

try:
    # 加载基座模型和tokenizer
    os.path.exists(BASE_MODEL)
    os.path.exists(LORA_WEIGHTS)
    os.path.exists(MERGED_MODEL)
    tokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL, trust_remote_code=True)  # 使用基础模型对应的分词器
    model = AutoModelForCausalLM.from_pretrained(  # 使用基础模型
        BASE_MODEL,
        trust_remote_code=True,
        dtype=torch.float16,
        device_map="auto"
    )

    # 合并LoRA权重（核心）
    # PeftModel 包装对象，它在前向传播时会自动应用 LoRA 的低秩增量矩阵
    model = PeftModel.from_pretrained(model, LORA_WEIGHTS)
    model = model.merge_and_unload()  # 永久性地将 LoRA 的增量 ΔW 加到原始权重 W 上

    # 保存合并后的模型（只需运行一次）
    model.save_pretrained(MERGED_MODEL)
    tokenizer.save_pretrained(MERGED_MODEL)

    print(f"✅ 目前已合并完成！完整模型已保存到：{MERGED_MODEL}")
    print("请部署该模型并加以测试")


except FileExistsError:
    print(f"合并路径 {MERGED_MODEL} 不存在!")
except Exception as e:
    print(f"合并失败: {e}")
