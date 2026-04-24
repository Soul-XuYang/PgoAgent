from agent.skills.base import BaseSkill
from agent.tools import LOCAL_TOOLS

class RAGSkill(BaseSkill):
    """
    RAG 技能：专门处理知识库检索和重写逻辑，并携带 RAG 领域知识
    """
    def __init__(self):
        super().__init__(
            name="rag_retrieve",
            description="处理知识库检索、查询重写及结果纠错"
        )
        self._metadata = {
            "capabilities": ["知识检索", "语义重写", "多轮纠错"],
            "usage_header": "使用 rag_retrieve 获取专业背景知识"
        }

    def load_resources(self):
        """加载相关的 RAG 工具并加载领域知识文档"""
        # 1. 加载工具
        rag_tool_names = ["rag_retrieve", "rag_rewrite_query"]
        self._tools = [t for t in LOCAL_TOOLS if t.name in rag_tool_names]
        
        # 2. 从当前文件夹下的 skill.md 加载领域知识 (包含 YAML frontmatter)
        self._load_knowledge_from_md("skill.md", __file__)
