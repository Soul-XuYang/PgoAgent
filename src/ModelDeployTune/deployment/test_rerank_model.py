"""
使用 Transformers 测试 bge-reranker-base 模型的基本重排序功能。

配置全部来自根目录下的 deployment_config.toml，
对标 test_chat 的“统一配置 + 清晰输出”风格。
"""

import os
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

# 添加项目根目录到路径，确保可以导入 deployment_config.ConfigLoader
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from config import ConfigLoader

# -------------------------- 配置项（来自 deployment_config.toml） --------------------------

config_loader = ConfigLoader()

# rerank 模型部署配置
rerank_config = config_loader.get_rerank_config()

# 测试配置（[test.rerank]）
test_root_config = config_loader.get_test_config()
test_rerank_config = test_root_config.get("rerank", {})

MODEL_PATH = rerank_config.get("model_path", "./models/bge-reranker-base")
TEST_QUERY = test_rerank_config.get("query", "什么是机器学习？")
TEST_DOCUMENTS = test_rerank_config.get(
    "documents",
    [
        "机器学习是人工智能的一个分支，通过算法让计算机从数据中学习。",
        "今天天气很好，适合出门游玩。",
        "机器学习包括监督学习、无监督学习和强化学习等多种方法。",
        "深度学习是机器学习的一个子领域，使用神经网络进行学习。",
    ],
)
MAX_LENGTH = int(test_rerank_config.get("max_length", 512))

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if DEVICE == "cuda" else torch.float32


def test_rerank_basic():
    """基本测试：使用 Transformers 库测试 rerank 模型"""
    try:
        # 检查模型路径
        if not os.path.exists(MODEL_PATH):
            print(f"⚠️ 警告：模型路径不存在：{MODEL_PATH}")
            print("   将使用在线模型进行测试...")
            model_path = "BAAI/bge-reranker-base"
        else:
            model_path = MODEL_PATH

        print(f"📌 测试配置：")
        print(f"   - 模型路径：{model_path}")
        print(f"   - 设备：{DEVICE}")
        print(f"   - 查询：{TEST_QUERY}")
        print(f"   - 文档数量：{len(TEST_DOCUMENTS)}")
        print("-" * 50)

        # 加载模型和分词器
        print("🔄 正在加载模型...")
        tokenizer = AutoTokenizer.from_pretrained(model_path)
        model = AutoModelForSequenceClassification.from_pretrained(
            model_path,
            torch_dtype=DTYPE
        ).to(DEVICE)
        model.eval()

        print("✅ 模型加载成功！")
        print("-" * 50)

        # 计算相关性分数
        print("🔄 正在计算相关性分数...")
        pairs = [[TEST_QUERY, doc] for doc in TEST_DOCUMENTS]
        
        with torch.no_grad():
            inputs = tokenizer(
                pairs,
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            ).to(DEVICE)

            scores = model(**inputs, return_dict=True).logits.view(-1, ).float()
            scores = scores.cpu().numpy()

        # 输出结果
        print("✅ 计算完成！")
        print("-" * 50)
        print("📊 测试结果（按相关性分数降序）：")
        
        doc_scores = list(zip(TEST_DOCUMENTS, scores))
        doc_scores.sort(key=lambda x: x[1], reverse=True)
        
        for i, (doc, score) in enumerate(doc_scores, 1):
            print(f"{i}. 分数：{score:.4f} - {doc[:50]}...")

        print("\n" + "=" * 50)
        print("🎉 测试通过！")

    except Exception as e:
        print(f"❌ 测试失败：{str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("=" * 50)
    print("🚀 开始测试 bge-reranker-base 模型")
    print("=" * 50)
    test_rerank_basic()
