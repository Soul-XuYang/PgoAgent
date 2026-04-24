from agent.skills.base import BaseSkill
from agent.tools import LOCAL_TOOLS

class TerminalSkill(BaseSkill):
    """
    Terminal 技能：封装 Shell 执行能力及操作系统交互的最佳实践
    """
    def __init__(self):
        super().__init__(
            name="code_exec",
            description="在系统终端执行 Shell 命令，处理文件系统、环境配置及代码运行"
        )
        self._metadata = {
            "capabilities": ["执行 Shell 命令", "环境检查", "系统资源管理"],
            "usage_header": "使用 shell_exec 执行系统级指令"
        }

    def load_resources(self):
        """加载相关的 Shell 工具并加载领域知识文档"""
        # 专门的shell工具
        shell_tool_names = ["shell_exec"]
        self._tools = [t for t in LOCAL_TOOLS if t.name in shell_tool_names]
        
        # 从当前文件夹下的 skill.md 加载领域知识 (包含 YAML frontmatter)
        self._load_knowledge_from_md("skill.md", __file__)
