"""
PoiClaw Agent 核心模块。

提供：
- Agent: ReAct 循环 Agent
- BaseTool: 工具基类
- ToolRegistry: 工具注册器
- HookManager: 安全拦截钩子管理器
- EventEmitter: 事件发射器
- FileSessionManager: 会话持久化管理器（v1/v2 双格式支持）
- TreeSessionManager: 树形会话管理器（v2 格式）
- CompactionManager: 上下文压缩管理器
"""

from .agent import Agent, AgentConfig, AgentState
from .events import (
    AgentEndEvent,
    AgentStartEvent,
    ContextCompactEvent,
    ErrorEvent,
    EventHandler,
    EventType,
    MessageUpdateEvent,
    ToolCallEndEvent,
    ToolCallErrorEvent,
    ToolCallStartEvent,
    TurnEndEvent,
    TurnStartEvent,
    EventEmitter,
    create_event_summary,
)
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
from .session_tree import (
    TreeSessionManager,
    SessionHeader,
    SessionMessageEntry,
    CompactionEntry as CompactionEntryV2,
    ModelChangeEntry,
    ThinkingLevelChangeEntry,
    BranchSummaryEntry,
    CustomEntry,
    CustomMessageEntry,
    LabelEntry,
    SessionInfoEntry,
    SessionTreeNode,
    SessionContext,
    build_session_context,
    CURRENT_SESSION_VERSION,
)
from .session_migration import (
    MigrationResult,
    detect_format,
    migrate_v1_to_v2,
    migrate_all_sessions,
    is_migration_needed,
)
from .tools import BaseTool, ToolRegistry, ToolResult
from .system_prompt import (
    BuildSystemPromptOptions,
    ContextFile,
    ToolInfo,
    build_default_system_prompt,
    build_system_prompt,
    load_context_file,
)

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
    # Session (v1/v2 双格式)
    "FileSessionManager",
    "SessionMetadata",
    "SessionData",
    "UsageStats",
    # Session Tree (v2 格式)
    "TreeSessionManager",
    "SessionHeader",
    "SessionMessageEntry",
    "CompactionEntryV2",
    "ModelChangeEntry",
    "ThinkingLevelChangeEntry",
    "BranchSummaryEntry",
    "CustomEntry",
    "CustomMessageEntry",
    "LabelEntry",
    "SessionInfoEntry",
    "SessionTreeNode",
    "SessionContext",
    "build_session_context",
    "CURRENT_SESSION_VERSION",
    # Migration
    "MigrationResult",
    "detect_format",
    "migrate_v1_to_v2",
    "migrate_all_sessions",
    "is_migration_needed",
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
    # Events
    "EventType",
    "EventEmitter",
    "EventHandler",
    "AgentStartEvent",
    "AgentEndEvent",
    "TurnStartEvent",
    "TurnEndEvent",
    "MessageUpdateEvent",
    "ToolCallStartEvent",
    "ToolCallEndEvent",
    "ToolCallErrorEvent",
    "ContextCompactEvent",
    "ErrorEvent",
    "create_event_summary",
    # System Prompt
    "ToolInfo",
    "ContextFile",
    "BuildSystemPromptOptions",
    "build_system_prompt",
    "build_default_system_prompt",
    "load_context_file",
]
