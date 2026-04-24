from typing import Dict, List, Optional, Set
from agent.skills.base import BaseSkill

class SkillManager:
    """
    本项目的skill的技能管理器：统一管理所有 AgentSkill
    """
    _instance = None
    _skills: Dict[str, BaseSkill] = {}
    _loaded: Set[str] = set()  # 记录已调用过 load_resources 的技能名

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SkillManager, cls).__new__(cls)
        return cls._instance

    def register_skill(self, skill: BaseSkill):
        """注册一个技能（仅登记，不立即加载资源）"""
        self._skills[skill.name] = skill

    def get_skill(self, skill_name: str) -> Optional[BaseSkill]:
        """获取指定名称的技能，首次访问时才加载资源（lazy loading）"""
        skill = self._skills.get(skill_name)
        if skill is None:
            return None
        if skill_name not in self._loaded:
            skill.load_resources()
            self._loaded.add(skill_name)
        return skill

    def list_skills_metadata(self) -> List[dict]:
        """返回所有已注册技能的元信息，用于给 Planner 提示"""
        return [skill.metadata for skill in self._skills.values()]

# 全局唯一实例
skill_manager = SkillManager()
