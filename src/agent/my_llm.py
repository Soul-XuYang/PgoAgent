from langchain_openai import ChatOpenAI
from config import API_KEY, BASE_URL
from typing import Tuple, List
from PgoModel import ChatAI
# 只要继承ChatOpenAI 就可以使用，这里对它进行了改造
llm = ChatAI(
    model="moonshot-v1-8k",  # 改为 model 而不是 model_name
    temperature=0.3,
    openai_api_key=API_KEY,  # 改为 openai_api_key
    openai_api_base=BASE_URL,  # 改为 openai_api_base
    deep_thinking=False,
    timeout = 300,
)

def stream_output(model: ChatAI, prompt: str, print_choice: bool = True) -> Tuple[str, List[str]]:
    full_response = []
    token_usage = {}  # 初始化 token_usage 字典
    try:
        # stream() 返回生成器，逐个迭代 chunk
        resp_generator = model.stream(prompt)
        for chunk in resp_generator:  # 迭代生成器，获取每个响应片段
            if chunk is None:
                continue

            # 提取当前 chunk 的文本内容（兼容不同格式）
            if isinstance(chunk, str):
                text = chunk
            elif hasattr(chunk, "content"):
                text = chunk.content
            elif isinstance(chunk, dict):
                text = chunk.get("content") or chunk.get("text") or ""
            else:
                text = str(chunk)

            if not text:
                continue

            # 累加完整响应
            full_response.append(text)

            # 从当前 chunk 提取 response_metadata（更新 token_usage）
            if hasattr(chunk, "response_metadata"):
                token_usage.update(chunk.response_metadata.get("token_usage", {}))

            # 实时打印当前 chunk 的文本
            if print_choice:
                print(text, end="", flush=True)

        # 所有 chunk 输出完成后，统一打印 token 用量（关键修正）
        if print_choice and token_usage:
            print("\n" + "-" * 50)
            print(f"输入token (prompt_tokens): {token_usage.get('prompt_tokens', 0)}")
            print(f"输出token (completion_tokens): {token_usage.get('completion_tokens', 0)}")
            print(f"总token (total_tokens): {token_usage.get('total_tokens', 0)}")

    except Exception as e:
        print(f"\n请求失败: {e}")

    finally:
        final_text = "".join(full_response)
        return final_text, full_response
def invoke_output(model: ChatOpenAI, prompt: str,print_choice: bool = True)->str:
    text = ""
    try:
        resp = model.invoke(prompt)
        token_usage = resp.response_metadata.get('token_usage', {}) # 后面是默认值
        if resp is not None:
            if isinstance(resp, str):
                text = resp
            elif hasattr(resp, "content"): # 如果是对象属性找对应的内容
                text = resp.content
            elif isinstance(resp, dict):
                text = resp.get("content") or resp.get("text") or ""
            else:
                text = str(resp)
        else:
            raise Exception("resp is None")
        if print_choice:
            print(text)
            print(f"输入token (prompt_tokens): {token_usage.get('prompt_tokens', 0)}")
            print(f"输出token (completion_tokens): {token_usage.get('completion_tokens', 0)}")
            print(f"总token (total_tokens): {token_usage.get('total_tokens', 0)}")
    except Exception as e:
        print(f"\n请求失败: {e}")
    finally:
        return text

# 测试使用-基本的模型调用
if __name__ == '__main__':
    print("本脚本代码结构化输出的测试，正在生成文本中:")
    ans1, _ = stream_output(llm, "你好,请介绍下深度学习的基本概念!")
    ans2 = invoke_output(llm, "你好,请介绍下机器学习的基本概念!")
    from pydantic import BaseModel, Field
    from langchain_core.prompts import ChatPromptTemplate

    class Movie(BaseModel):
        title: str = Field(..., description="电影标题", max_length=100)
        year: int = Field(..., description="电影发行年份", ge=1900)
        director: str = Field(..., description="电影导演", min_length=2)
        rating: str = Field(..., description="电影评分，格式为1位整数+小数点+1位小数，例如9.7", pattern=r"^\d\.\d$")


    structured_prompt = ChatPromptTemplate.from_messages([
        ("system",
         "你是一个数据提取助手，仅输出JSON格式数据，不要任何自然语言解释、前缀或后缀。严格按照以下JSON schema生成数据，字段必须完整，格式必须正确：\n{schema}"),
        ("human", "{question}")
    ])
    # 使用with_structured_output，但不直接传入prompt
    model_with_structure1 = llm.with_structured_output(Movie)
    # 创建链，将提示模板和模型连接起来
    chain = structured_prompt | model_with_structure1
    # 调用链并传入参数
    try:
        response = chain.invoke({
            "schema": Movie.model_json_schema(),  # 使用model_json_schema()替代schema()
            "question": "提供盗梦空间的详细信息"
        })
        print(response)
        print(f"标题: {response.title}")
        print(f"年份: {response.year}")
        print(f"导演: {response.director}")
        print(f"评分: {response.rating}")
    except Exception as e:
        print(f"请求失败: {e}")


