"""
内置工具模块。

提供 5 个核心编程工具：
- BashTool: 执行 bash 命令
- ReadFileTool: 读取文件
- WriteFileTool: 写入文件
- EditFileTool: 编辑文件（字符串替换）
- SubagentTool: 多智能体协作工具 (Fork-Join 模式)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from poiclaw.core import ToolRegistry

from .bash import BashTool
from .edit_file import EditFileTool
from .read_file import ReadFileTool
from .subagent import SubagentTool
from .write_file import WriteFileTool

if TYPE_CHECKING:
    from poiclaw.core import HookManager
    from poiclaw.llm import LLMClient

__all__ = [
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "SubagentTool",
    "register_all_tools",
    "register_subagent_tool",
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
