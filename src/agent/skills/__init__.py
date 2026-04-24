from agent.skills.manager import skill_manager
from agent.skills.rag.rag_skill import RAGSkill
from agent.skills.terminal.terminal_skill import TerminalSkill

# 默认注册rag和终端操作的skill
skill_manager.register_skill(RAGSkill())
skill_manager.register_skill(TerminalSkill())

def get_skill(skill_name: str):
    """根据技能名称获取技能，如果技能不存在则返回 None"""
    return skill_manager.get_skill(skill_name)
