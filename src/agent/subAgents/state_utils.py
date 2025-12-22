from typing import List
from langchain_core.messages import HumanMessage, BaseMessage


def get_latest_HumanMessage(messages: List[BaseMessage]) -> HumanMessage:
    """
    获取最新的HumanMessage
    """
    latest_user_msg = None
    for msg in reversed(messages):
        if isinstance(msg, HumanMessage):
            latest_user_msg = msg
            break
    return latest_user_msg

# 最新的工具调用信息
PROFILE_KEYWORDS = [
    # 基本信息
    "职业", "工作", "行业", "岗位", "公司", "地区", "城市", "居住地", "家乡","性别","姓名","称呼","上班"
    "年龄", "学历", "学校", "专业", "婚姻", "婚姻状况", "婚姻状态","工程师","研究生","大学生","中学","小学","幼儿园","高中生","初中生",
    "教师","医生","护士","律师","公务员","军人","消防员","医生","护士","律师","警察","公务员","会计",
    "国","省","市","中文","英文","日文","韩文","法文","english","chinese","japanese","korean","france"
    # 偏好
    "喜欢", "偏好", "习惯", "常用", "不喜欢", "讨厌", "倾向于",
    # 长期目标/计划
    "学习", "备考", "考证", "目标", "计划", "长期", "打算", "准备", "想要"
]
def has_obvious_profile_info(user_messages: List[HumanMessage]) -> bool: # 只查看用户的最新发言，时间复杂度
    """
    检测对话中是否有明显的用户画像信息
    规则：只看用户发言，包含至少1个核心关键词，且是关于用户自身的表述
    """
    # 只提取用户的发言（过滤助手消息）
    # 核心关键词（覆盖用户画像的核心维度
    # 遍历用户发言，检测关键词
    for msg in user_messages:
        content = msg.content.lower()
        # 1. 包含至少一个核心关键词
        if any(keyword in content for keyword in PROFILE_KEYWORDS):
            # 2. 排除非自身表述（比如"我朋友是程序员"不算，"我是程序员"才算）
            if "我" in content or "本人" in content or "自己" in content:
                return True
    return False