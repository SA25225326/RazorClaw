"""事件系统 - 为 Agent 提供丰富的事件流"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from poiclaw.llm import Message, ToolCall

    from .agent import Agent, AgentConfig, AgentState
    from .tools import BaseTool, ToolResult


# ============ 事件类型定义 ============


class EventType(str, Enum):
    """事件类型枚举"""

    # Agent 生命周期
    AGENT_START = "agent_start"  # Agent 开始运行
    AGENT_END = "agent_end"  # Agent 运行结束

    # Turn 生命周期（一个 LLM 调用 + 工具执行回合）
    TURN_START = "turn_start"  # 新回合开始
    TURN_END = "turn_end"  # 回合结束

    # 消息相关
    MESSAGE_UPDATE = "message_update"  # 新消息添加到上下文

    # 工具调用相关
    TOOL_CALL_START = "tool_call_start"  # 工具调用开始
    TOOL_CALL_END = "tool_call_end"  # 工具调用结束
    TOOL_CALL_ERROR = "tool_call_error"  # 工具调用错误

    # 上下文相关
    CONTEXT_COMPACT = "context_compact"  # 上下文压缩

    # 错误相关
    ERROR = "error"  # Agent 运行错误


# ============ 事件数据类 ============


@dataclass
class AgentStartEvent:
    """Agent 开始事件"""

    type: EventType = field(default=EventType.AGENT_START, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None  # Agent 标识（通常是 session_id）
    user_input: str | None = None  # 用户输入
    config: "AgentConfig | None" = None  # Agent 配置


@dataclass
class AgentEndEvent:
    """Agent 结束事件"""

    type: EventType = field(default=EventType.AGENT_END, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    final_response: str | None = None  # 最终回复
    state: "AgentState | None" = None  # 最终状态
    error: str | None = None  # 错误信息（如果有）


@dataclass
class TurnStartEvent:
    """回合开始事件"""

    type: EventType = field(default=EventType.TURN_START, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    turn_number: int = 0  # 回合编号（从 1 开始）


@dataclass
class TurnEndEvent:
    """回合结束事件"""

    type: EventType = field(default=EventType.TURN_END, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    turn_number: int = 0
    llm_response: str | None = None  # LLM 回复内容
    tool_calls_made: int = 0  # 本回合执行的工具调用数


@dataclass
class MessageUpdateEvent:
    """消息更新事件"""

    type: EventType = field(default=EventType.MESSAGE_UPDATE, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    message: "Message | None" = None  # 新消息
    role: str | None = None  # 消息角色
    content_preview: str | None = None  # 内容预览（前 100 字符）


@dataclass
class ToolCallStartEvent:
    """工具调用开始事件"""

    type: EventType = field(default=EventType.TOOL_CALL_START, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    turn_number: int = 0
    tool_name: str = ""  # 工具名称
    tool_arguments: dict[str, Any] | None = None  # 工具参数


@dataclass
class ToolCallEndEvent:
    """工具调用结束事件"""

    type: EventType = field(default=EventType.TOOL_CALL_END, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    turn_number: int = 0
    tool_name: str = ""
    success: bool = True  # 是否成功
    result_preview: str | None = None  # 结果预览（前 100 字符）
    duration_ms: int | None = None  # 执行耗时（毫秒）


@dataclass
class ToolCallErrorEvent:
    """工具调用错误事件"""

    type: EventType = field(default=EventType.TOOL_CALL_ERROR, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    turn_number: int = 0
    tool_name: str = ""
    error_type: str | None = None  # 错误类型
    error_message: str | None = None  # 错误消息


@dataclass
class ContextCompactEvent:
    """上下文压缩事件"""

    type: EventType = field(default=EventType.CONTEXT_COMPACT, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    tokens_before: int = 0  # 压缩前 token 数
    tokens_after: int = 0  # 压缩后 token 数
    tokens_saved: int = 0  # 节省的 token 数
    summary_preview: str | None = None  # 摘要预览


@dataclass
class ErrorEvent:
    """通用错误事件"""

    type: EventType = field(default=EventType.ERROR, init=False)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    agent_id: str | None = None
    error_type: str | None = None  # 错误类型
    error_message: str | None = None  # 错误消息
    context: dict[str, Any] | None = None  # 错误上下文


# 事件联合类型
Event = (
    AgentStartEvent
    | AgentEndEvent
    | TurnStartEvent
    | TurnEndEvent
    | MessageUpdateEvent
    | ToolCallStartEvent
    | ToolCallEndEvent
    | ToolCallErrorEvent
    | ContextCompactEvent
    | ErrorEvent
)


# ============ 事件处理器类型 ============


EventHandler = Callable[[Event], Awaitable[None]]


# ============ 事件发射器 ============


class EventEmitter:
    """
    事件发射器 - 管理事件订阅和发射。

    用法：
        emitter = EventEmitter()

        # 订阅事件
        @emitter.on(EventType.AGENT_START)
        async def on_agent_start(event: AgentStartEvent):
            print(f"Agent started: {event.agent_id}")

        # 或者用函数式订阅
        async def on_tool_call(event: ToolCallStartEvent):
            print(f"Tool called: {event.tool_name}")
        emitter.on(EventType.TOOL_CALL_START)(on_tool_call)

        # 发射事件
        await emitter.emit(AgentStartEvent(agent_id="test", user_input="Hello"))
    """

    def __init__(self) -> None:
        # {event_type: [handlers]}
        self._handlers: dict[EventType, list[EventHandler]] = {}

    def on(self, event_type: EventType) -> Callable[[EventHandler], EventHandler]:
        """
        装饰器方式订阅事件。

        Args:
            event_type: 要订阅的事件类型

        Returns:
            装饰器函数
        """

        def decorator(handler: EventHandler) -> EventHandler:
            self.add_handler(event_type, handler)
            return handler

        return decorator

    def add_handler(self, event_type: EventType, handler: EventHandler) -> None:
        """
        添加事件处理器。

        Args:
            event_type: 事件类型
            handler: 处理器函数
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)

    def remove_handler(self, event_type: EventType, handler: EventHandler) -> bool:
        """
        移除事件处理器。

        Args:
            event_type: 事件类型
            handler: 要移除的处理器

        Returns:
            是否成功移除
        """
        if event_type in self._handlers:
            try:
                self._handlers[event_type].remove(handler)
                return True
            except ValueError:
                pass
        return False

    def remove_all_handlers(self, event_type: EventType | None = None) -> None:
        """
        移除所有处理器。

        Args:
            event_type: 指定事件类型，None 则移除所有
        """
        if event_type is None:
            self._handlers.clear()
        elif event_type in self._handlers:
            del self._handlers[event_type]

    async def emit(self, event: Event) -> None:
        """
        发射事件，通知所有订阅者。

        Args:
            event: 事件对象
        """
        event_type = event.type
        if event_type not in self._handlers:
            return

        # 并发执行所有处理器
        import asyncio

        tasks = [handler(event) for handler in self._handlers[event_type]]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def get_handlers(self, event_type: EventType) -> list[EventHandler]:
        """
        获取指定事件类型的所有处理器。

        Args:
            event_type: 事件类型

        Returns:
            处理器列表
        """
        return self._handlers.get(event_type, []).copy()

    def has_handler(self, event_type: EventType) -> bool:
        """
        检查是否有处理器订阅了指定事件。

        Args:
            event_type: 事件类型

        Returns:
            是否有订阅者
        """
        return event_type in self._handlers and len(self._handlers[event_type]) > 0

    def list_subscribed_events(self) -> list[EventType]:
        """
        列出所有已订阅的事件类型。

        Returns:
            已订阅的事件类型列表
        """
        return list(self._handlers.keys())


# ============ 辅助函数 ============


def create_event_summary(event: Event) -> str:
    """
    创建事件的文本摘要，用于日志输出。

    Args:
        event: 事件对象

    Returns:
        事件摘要字符串
    """
    event_type = event.type.value

    if isinstance(event, AgentStartEvent):
        return f"[{event_type}] Agent started (id={event.agent_id})"
    elif isinstance(event, AgentEndEvent):
        status = "error" if event.error else "success"
        return f"[{event_type}] Agent ended ({status}, steps={event.state.step if event.state else 0})"
    elif isinstance(event, TurnStartEvent):
        return f"[{event_type}] Turn {event.turn_number} started"
    elif isinstance(event, TurnEndEvent):
        return (
            f"[{event_type}] Turn {event.turn_number} ended "
            f"(tools={event.tool_calls_made})"
        )
    elif isinstance(event, MessageUpdateEvent):
        preview = event.content_preview or "N/A"
        return f"[{event_type}] Message added (role={event.role}, preview={preview[:50]}...)"
    elif isinstance(event, ToolCallStartEvent):
        return f"[{event_type}] Tool '{event.tool_name}' called"
    elif isinstance(event, ToolCallEndEvent):
        status = "success" if event.success else "failed"
        duration = f" in {event.duration_ms}ms" if event.duration_ms else ""
        return f"[{event_type}] Tool '{event.tool_name}' {status}{duration}"
    elif isinstance(event, ToolCallErrorEvent):
        return f"[{event_type}] Tool '{event.tool_name}' error: {event.error_message}"
    elif isinstance(event, ContextCompactEvent):
        return (
            f"[{event_type}] Context compacted: "
            f"{event.tokens_before} -> {event.tokens_after} (saved {event.tokens_saved})"
        )
    elif isinstance(event, ErrorEvent):
        return f"[{event_type}] Error: {event.error_type}: {event.error_message}"
    else:
        return f"[{event_type}] Unknown event"
