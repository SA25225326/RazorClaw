"""读取 Skill 详情的工具"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from poiclaw.core import BaseTool, ToolResult

if TYPE_CHECKING:
    from poiclaw.skills import SkillRegistry


class ReadSkillTool(BaseTool):
    """
    读取 Skill 完整内容 - 渐进式披露。

    这个工具实现了 Skills 的渐进式加载：
    1. Agent 启动时只注入 Skill 简介到 system prompt
    2. 当 Agent 决定使用某个技能时，调用此工具获取详细指导
    3. 这样可以大幅节省初始 Token 消耗

    用法：
        # 创建 Agent 时注册
        tools.register(ReadSkillTool(skill_registry))
    """

    def __init__(self, registry: SkillRegistry) -> None:
        """
        初始化工具。

        Args:
            registry: Skill 注册表
        """
        self.registry = registry

    @property
    def name(self) -> str:
        return "read_skill"

    @property
    def description(self) -> str:
        return "读取指定技能的完整指令和示例。当你决定使用某个技能时，先调用此工具获取详细指导。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "技能名称，如 commit、review-pr、test-runner",
                }
            },
            "required": ["skill_name"],
        }

    async def execute(self, skill_name: str) -> ToolResult:
        """
        执行工具：获取 Skill 完整内容。

        Args:
            skill_name: 技能名称

        Returns:
            ToolResult: 包含完整技能内容或错误信息
        """
        skill = self.registry.get(skill_name)

        if skill is None:
            available = ", ".join(self.registry.get_all_names()) or "(无)"
            return ToolResult(
                success=False,
                content="",
                error=f"技能 '{skill_name}' 不存在。可用技能: {available}",
            )

        return ToolResult(
            success=True,
            content=skill.to_full_prompt(),
        )


class ListSkillsTool(BaseTool):
    """
    列出所有可用技能。

    用于让 Agent 查询当前有哪些技能可用。
    """

    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    @property
    def name(self) -> str:
        return "list_skills"

    @property
    def description(self) -> str:
        return "列出所有可用的技能名称和简介。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    async def execute(self) -> ToolResult:
        """执行工具：列出所有技能"""
        if not self.registry.get_all():
            return ToolResult(
                success=True,
                content="当前没有可用的技能。",
            )

        brief = self.registry.to_brief_list()
        return ToolResult(
            success=True,
            content=brief,
        )
