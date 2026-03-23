"""
PoiClaw Agent 核心模块。

提供：
- Agent: ReAct 循环 Agent
- BaseTool: 工具基类
- ToolRegistry: 工具注册器
- HookManager: 安全拦截钩子管理器
- FileSessionManager: 会话持久化管理器
- CompactionManager: 上下文压缩管理器
"""

from .agent import Agent, AgentConfig, AgentState
from .compaction import (
    CompactionResult,
    compact,
    estimate_tokens,
    estimate_total_tokens,
    find_cut_point,
    generate_summary,
    serialize_messages_for_summary,
    should_compact,
)
from .hooks import (
    BeforeExecuteHook,
    HookContext,
    HookManager,
    HookResult,
    create_bash_safety_hook,
)
from .session import (
    CompactionEntry,
    CompactionSettings,
    FileSessionManager,
    SessionData,
    SessionMetadata,
    UsageStats,
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
    # Session
    "FileSessionManager",
    "SessionMetadata",
    "SessionData",
    "UsageStats",
    # Compaction
    "CompactionEntry",
    "CompactionSettings",
    "CompactionResult",
    "compact",
    "estimate_tokens",
    "estimate_total_tokens",
    "find_cut_point",
    "generate_summary",
    "serialize_messages_for_summary",
    "should_compact",
]
