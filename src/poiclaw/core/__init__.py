"""
PoiClaw Agent 核心模块。

提供：
- Agent: ReAct 循环 Agent
- BaseTool: 工具基类
- ToolRegistry: 工具注册器
- HookManager: 安全拦截钩子管理器
"""

from .agent import Agent, AgentConfig, AgentState
from .hooks import (
    BeforeExecuteHook,
    HookContext,
    HookManager,
    HookResult,
    create_bash_safety_hook,
)
from .tools import BaseTool, ToolRegistry, ToolResult

__all__ = [
    # Agent
    "Agent",
    "AgentConfig",
    "AgentState",
    # Tools
    "BaseTool",
    "ToolRegistry",
    "ToolResult",
    # Hooks
    "HookManager",
    "HookContext",
    "HookResult",
    "BeforeExecuteHook",
    "create_bash_safety_hook",
]
