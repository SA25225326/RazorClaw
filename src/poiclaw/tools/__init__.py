"""
内置工具模块。

提供 6 个核心编程工具：
- BashTool: 执行 bash 命令
- ReadFileTool: 读取文件
- WriteFileTool: 写入文件
- EditFileTool: 编辑文件（字符串替换）
- SubagentTool: 多智能体协作工具 (Fork-Join 模式)
- ListToolsTool: 渐进式工具查询
- ReadSkillTool: 渐进式技能加载
- ListSkillsTool: 列出可用技能
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from poiclaw.core import ToolRegistry

from .bash import BashTool
from .edit_file import EditFileTool
from .list_tools import ListToolsTool
from .read_file import ReadFileTool
from .read_skill import ListSkillsTool, ReadSkillTool
from .subagent import SubagentTool
from .write_file import WriteFileTool

if TYPE_CHECKING:
    from poiclaw.core import HookManager
    from poiclaw.llm import LLMClient

    from ..skills import SkillRegistry

__all__ = [
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "SubagentTool",
    "ListToolsTool",
    "ReadSkillTool",
    "ListSkillsTool",
    "register_all_tools",
    "register_subagent_tool",
    "register_progressive_tools",
    "register_skill_tools",
]


def register_all_tools(registry: ToolRegistry) -> None:
    """
    注册所有基础内置工具到 ToolRegistry（不含 SubagentTool）。

    注意：SubagentTool 需要额外注入 llm_client 和 hooks，
    请使用 register_subagent_tool() 单独注册。

    用法：
        from poiclaw.core import ToolRegistry
        from poiclaw.tools import register_all_tools

        registry = ToolRegistry()
        register_all_tools(registry)
    """
    registry.register(BashTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())


def register_subagent_tool(
    registry: ToolRegistry,
    llm_client: LLMClient,
    hooks: HookManager,
) -> SubagentTool:
    """
    注册 SubagentTool 到 ToolRegistry。

    SubagentTool 需要额外注入依赖：
    - llm_client: 用于创建子 Agent
    - hooks: 安全钩子（必须传递，确保子 Agent 继承沙箱规则）

    用法：
        from poiclaw.tools import register_all_tools, register_subagent_tool

        tools = ToolRegistry()
        register_all_tools(tools)

        # 注册 SubagentTool（需要额外依赖）
        register_subagent_tool(tools, llm_client=llm, hooks=hooks)

    Args:
        registry: 工具注册器
        llm_client: LLM 客户端
        hooks: 钩子管理器（必须传递，确保安全沙箱继承）

    Returns:
        SubagentTool: 注册的工具实例
    """
    subagent_tool = SubagentTool(
        llm_client=llm_client,
        base_tools=registry,
        hooks=hooks,
    )
    registry.register(subagent_tool)
    return subagent_tool


def register_progressive_tools(registry: ToolRegistry) -> None:
    """
    注册渐进式加载所需的辅助工具。

    在 progressive_tools=True 模式下，Agent 初始只获得工具简介，
    需要通过 ListToolsTool 按需查询工具详情。

    用法：
        from poiclaw.core import ToolRegistry
        from poiclaw.tools import register_all_tools, register_progressive_tools

        registry = ToolRegistry()
        register_all_tools(registry)
        register_progressive_tools(registry)

        # 创建 Agent 时启用渐进式加载
        agent = Agent(llm_client=llm, tools=registry, progressive_tools=True)

    Args:
        registry: 工具注册器
    """
    registry.register(ListToolsTool(registry))


def register_skill_tools(registry: ToolRegistry, skill_registry: SkillRegistry) -> None:
    """
    注册 Skills 相关工具。

    在启用 Skills 的模式下，Agent 可以通过这些工具：
    - list_skills: 查看所有可用技能
    - read_skill: 按需加载完整技能内容

    用法：
        from poiclaw.skills import SkillRegistry
        from poiclaw.tools import register_all_tools, register_skill_tools

        # 加载技能
        skills = SkillRegistry()
        skills.load_from_dir("skills/")

        # 注册工具
        tools = ToolRegistry()
        register_all_tools(tools)
        register_skill_tools(tools, skills)

    Args:
        registry: 工具注册器
        skill_registry: 技能注册表
    """
    registry.register(ListSkillsTool(skill_registry))
    registry.register(ReadSkillTool(skill_registry))
