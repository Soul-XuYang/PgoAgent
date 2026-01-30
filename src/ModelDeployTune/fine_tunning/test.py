from openai import OpenAI  # 导入异步客户端
import time
MODEL_NAME = "qwen-lora"
# url和api_key需要根据实际部署的微调模型使用-vllm部署的模型api

client = OpenAI(
    base_url="http://localhost:8001/v1",  # vLLM的API地址
    api_key="" # 自定义密钥
)
# 测试系统提示词一定要严格使用训练集的
if __name__ == "__main__":
    print("测试之前请使用vllm启动模型,这里可用deployment的run_model脚本进行部署")
    user_input = "你好，你具体由谁微调的呢？"
    start_time = time.time()
    response = client.chat.completions.create(
        model=MODEL_NAME,  # 合并后的模型路径
        messages=[
            # 提示词严格适配，切记
            {"role": "system",
                "content": "当用户询问你的身份时，直接回答你本身模型名字、职责和能力"},
            {"role": "user", "content": user_input}
        ],
        temperature=0.5,    # 生成随机性（0=确定，1=灵活）
        max_tokens=2048,    # 最大生成字数
        stream=False        # 关闭流式输出（先测试非流式，更直观）
    )

    # ===================== 核心补充：打印模型回复 =====================
    end_time = time.time()
    # 提取模型的回复内容
    model_reply = response.choices[0].message.content.strip()

    # 输出结果
    print(f"\n✅ 模型回复（耗时：{end_time - start_time:.2f}秒）：")
    print(model_reply)
