from typing import Optional, List, Dict, Any, Union
from langchain_openai import ChatOpenAI
from langchain_core.outputs import ChatResult, ChatGeneration
from pydantic import Field


class ChatAI(ChatOpenAI): # 这一类型兼容多种
    """
    增强版 ChatOpenAI，支持深度思考模式、自动思维链注入等功能。
    """
    deep_thinking: bool = False
    thinking_config: Dict[str, Any] = Field(default_factory=dict)
    def __init__(self,model: str = "gpt-4.0",
        temperature: float = 0.5,
        openai_api_key: str = "",
        openai_api_base: str = "",
        deep_thinking: bool = False,
        max_tokens: int = 2048,
        thinking_config: Optional[Dict[str, Any]] = None, # Dict[str, Any] | None 或者不传
        **kwargs: Any, # 为了兼容父类 ChatOpenAI 的其他参数-就是不管了
    ):
        if not openai_api_key:
            raise ValueError("openai_api_key is required")

        if not 0 <= temperature <= 2:
            raise ValueError("temperature must be between 0 and 2")

        super().__init__(
            model=model,
            temperature=temperature,
            openai_api_key=openai_api_key,
            openai_api_base=openai_api_base,
            max_tokens=max_tokens,
            **kwargs,
        )
        self.deep_thinking = deep_thinking
        self.thinking_config = thinking_config or {}

    # ------------------------------------------------
    # 核心：重写 _generate
    # ------------------------------------------------
    def _generate( # 前面的 _ 是约定非公开
        self,
        messages: List[Dict[str, Any]],
        stop: Optional[List[str]] = None,
        run_manager: Optional[Any] = None,
        **kwargs: Any,
    ) -> ChatResult: # 返回lang_chain的对象
        if self.deep_thinking and model_supports_internal_reasoning(self.model) : # 如果支持深度思考
            messages = self._inject_thinking_prompt(messages)
        result: ChatResult = super()._generate(
            messages=messages,
            stop=stop,
            run_manager=run_manager,
            **kwargs,
        )
        return result

    def _inject_thinking_prompt(
            self,
            messages: List[Union[Dict[str, Any], Any]] # messages可以为空-Union[...] 是说：两种类型都允许
    ): # 使用稳健的深度思考
        """
        更稳健的深度思考 prompt 注入：
        兼容 dict 消息（role/content）与 LangChain BaseMessage
        """
        think_instructions = self.thinking_config.get( # 获取介绍如果配置文件里面有初始的介绍就插入没有否否则就默认
            "instructions",
            "Before answering, think step-by-step and reason carefully. "
            "Provide the final answer only after internal reasoning."
        )
        # ---- 工具函数：识别消息类型 & 读写 role/content ----
        def is_dict_msg(msg):
            return isinstance(msg, dict) and "role" in m and "content" in m

        def get_role(msg):
            if is_dict_msg(msg):
                return msg.get("role")
            # LangChain BaseMessage: type 通常是 "system"/"human"/"ai"/"tool"
            return getattr(msg, "type", None) # 如果对象有type属性就用没有就异常

        def get_content(msg):
            if is_dict_msg(m):
                return msg.get("content", "")
            return getattr(msg, "content", "")

        def make_system_msg(content: str):
            # 尽量保持与输入类型一致
            if messages and not is_dict_msg(messages[0]): # 且信息不是dict类型
                # LangChain 消息
                try:
                    from langchain_core.messages import SystemMessage
                    return SystemMessage(content=content) # 创建一个
                except Exception:
                    # 兜底：退回 dict
                    return {"role": "system", "content": content} # 创建一个dict使用
            else:
                return {"role": "system", "content": content}

        # ---- 1) 如果已经注入过相同思考指令，则直接返回 ----
        for m in messages:
            if get_role(m) == "system" and get_content(m).strip() == think_instructions.strip(): # strip移除各种字符
                return messages
        injected_msg = make_system_msg(think_instructions) # 构建对应的对象类型
        # ---- 2) 找最后一个 system 的位置，插在其后 ----
        last_system_idx = -1
        for i, m in enumerate(messages): # 找到最后一个system的位置
            if get_role(m) == "system":
                last_system_idx = i
        if last_system_idx >= 0:
            return messages[: last_system_idx + 1] + [injected_msg] + messages[last_system_idx + 1:] #放在中间
        else:
            return [injected_msg] + messages # 默认放在前面

def model_supports_internal_reasoning(model_name: str) -> bool:
    """
    判断模型是否内置“深度思考模式”（R1/o1-style）
    """
    model_name = model_name.lower()
    keywords = [
        "r1",
        "o1",
        "thinking",
        "reasoning",
    ]
    return any(k in model_name for k in keywords) # any的一个用法 内置判断使用是否有True or False

