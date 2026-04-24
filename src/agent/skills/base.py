import yaml
import re
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from pathlib import Path
from langchain_core.tools import BaseTool

class BaseSkill(ABC):
    """
    AgentSkill 基础类：封装领域特定的工具集、元信息（Metadata）和领域知识（Domain Knowledge）
    """
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._tools: List[BaseTool] = []
        self._knowledge: str = "" # 存放从 .md 文件加载的详细领域知识
        self._metadata: Dict[str, Any] = {} # 存放技能的元信息，用于 Planner 阶段的“轻量披露”

    @property
    def tools(self) -> List[BaseTool]:
        return self._tools

    @property
    def knowledge(self) -> str:
        return self._knowledge

    @property
    def metadata(self) -> Dict[str, Any]:
        """返回技能的元信息，包括名称、描述、核心能力等信息"""
        # 基础元数据，确保 name 和 description 始终反映最新状态
        base_meta = {
            "name": self.name,
            "description": self.description,
            "capabilities": self._metadata.get("capabilities", []),
            "usage_header": self._metadata.get("usage_header", ""),
            "trigger_keywords": self._metadata.get("trigger_keywords", [])
        }
        # 合并所有元数据
        return {**self._metadata, **base_meta}

    def _load_knowledge_from_md(self, file_path: str, skill_file: str):
        """
        从 Markdown 加载领域知识，支持 ClaudeCode 风格的 YAML frontmatter。
        通过正则严格区分 YAML 区块（开头 --- 到 ---）和 Markdown 正文。
        """
        try:
            skill_dir = Path(skill_file).parent
            md_path = skill_dir / file_path
            if md_path.exists():
                with open(md_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 1. 使用正则匹配顶部的 YAML frontmatter
                # ^--- 表示必须从文件开头开始匹配
                # (.*?) 是 YAML 内容，使用 re.DOTALL 包含换行符
                # \n--- 匹配结束标记
                frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n', re.DOTALL)
                match = frontmatter_pattern.match(content)
                
                if match:
                    yaml_content = match.group(1)
                    try:
                        # 2. 解析 YAML 部分
                        frontmatter = yaml.safe_load(yaml_content)
                        if isinstance(frontmatter, dict):
                            self._metadata.update(frontmatter)
                            # 如果 frontmatter 中定义了核心字段，同步到 Python 属性
                            if 'name' in frontmatter:
                                self.name = frontmatter['name']
                            if 'description' in frontmatter:
                                self.description = frontmatter['description']
                        
                        # 3. 提取 Markdown 正文
                        # match.end() 之后的所有内容都是正文
                        self._knowledge = content[match.end():].strip()
                    except yaml.YAMLError as e:
                        print(f"解析 YAML 失败: {e}，将全文视为正文")
                        self._knowledge = content
                else:
                    # 如果没找到 frontmatter，全文都是知识正文
                    self._knowledge = content
            else:
                self._knowledge = f"未找到领域知识文档: {md_path}"
        except Exception as e:
            self._knowledge = f"加载领域知识文档失败: {e}"

    @abstractmethod
    def load_resources(self):
        """加载本技能所需的资源（如工具、加载领域知识等）"""
        pass
