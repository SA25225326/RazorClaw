"""事件系统模块测试

测试覆盖：
    - 事件类型定义
    - 事件数据类
    - EventEmitter 订阅/取消订阅
    - EventEmitter 事件发射
    - Agent 事件集成
"""

import pytest

from poiclaw.core.events import (
    AgentEndEvent,
    AgentStartEvent,
    ContextCompactEvent,
    ErrorEvent,
    MessageUpdateEvent,
    ToolCallEndEvent,
    ToolCallErrorEvent,
    ToolCallStartEvent,
    TurnEndEvent,
    TurnStartEvent,
    EventType,
    EventEmitter,
    create_event_summary,
)
from poiclaw.core.agent import Agent, AgentConfig
from poiclaw.core.tools import ToolRegistry
from poiclaw.llm import Message


class TestEventType:
    """事件类型测试"""

    def test_event_type_values(self):
        """测试事件类型枚举值"""
        assert EventType.AGENT_START == "agent_start"
        assert EventType.AGENT_END == "agent_end"
        assert EventType.TURN_START == "turn_start"
        assert EventType.TURN_END == "turn_end"
        assert EventType.MESSAGE_UPDATE == "message_update"
        assert EventType.TOOL_CALL_START == "tool_call_start"
        assert EventType.TOOL_CALL_END == "tool_call_end"
        assert EventType.TOOL_CALL_ERROR == "tool_call_error"
        assert EventType.CONTEXT_COMPACT == "context_compact"
        assert EventType.ERROR == "error"


class TestEventClasses:
    """事件数据类测试"""

    def test_agent_start_event(self):
        """AgentStartEvent 创建"""
        event = AgentStartEvent(
            agent_id="test-agent",
            user_input="Hello",
        )
        assert event.agent_id == "test-agent"
        assert event.user_input == "Hello"
        assert event.type == EventType.AGENT_START
        assert event.timestamp is not None

    def test_agent_end_event(self):
        """AgentEndEvent 创建"""
        from poiclaw.core.agent import AgentState

        event = AgentEndEvent(
            agent_id="test-agent",
            final_response="Done",
            state=AgentState(step=5, total_tool_calls=3, finished=True),
        )
        assert event.agent_id == "test-agent"
        assert event.final_response == "Done"
        assert event.state.step == 5
        assert event.type == EventType.AGENT_END

    def test_turn_start_event(self):
        """TurnStartEvent 创建"""
        event = TurnStartEvent(
            agent_id="test-agent",
            turn_number=1,
        )
        assert event.turn_number == 1
        assert event.type == EventType.TURN_START

    def test_turn_end_event(self):
        """TurnEndEvent 创建"""
        event = TurnEndEvent(
            agent_id="test-agent",
            turn_number=1,
            llm_response="OK",
            tool_calls_made=2,
        )
        assert event.turn_number == 1
        assert event.llm_response == "OK"
        assert event.tool_calls_made == 2
        assert event.type == EventType.TURN_END

    def test_message_update_event(self):
        """MessageUpdateEvent 创建"""
        msg = Message.user("Hello world")
        event = MessageUpdateEvent(
            agent_id="test-agent",
            message=msg,
            role=msg.role.value,
            content_preview="Hello world",
        )
        assert event.role == "user"
        assert event.content_preview == "Hello world"
        assert event.type == EventType.MESSAGE_UPDATE

    def test_tool_call_start_event(self):
        """ToolCallStartEvent 创建"""
        event = ToolCallStartEvent(
            agent_id="test-agent",
            turn_number=1,
            tool_name="bash",
            tool_arguments={"cmd": "ls"},
        )
        assert event.tool_name == "bash"
        assert event.tool_arguments == {"cmd": "ls"}
        assert event.type == EventType.TOOL_CALL_START

    def test_tool_call_end_event(self):
        """ToolCallEndEvent 创建"""
        event = ToolCallEndEvent(
            agent_id="test-agent",
            turn_number=1,
            tool_name="bash",
            success=True,
            result_preview="file1.txt",
            duration_ms=150,
        )
        assert event.tool_name == "bash"
        assert event.success is True
        assert event.duration_ms == 150
        assert event.type == EventType.TOOL_CALL_END

    def test_tool_call_error_event(self):
        """ToolCallErrorEvent 创建"""
        event = ToolCallErrorEvent(
            agent_id="test-agent",
            turn_number=1,
            tool_name="bash",
            error_type="CommandNotFound",
            error_message="Command not found: xyz",
        )
        assert event.tool_name == "bash"
        assert event.error_type == "CommandNotFound"
        assert event.type == EventType.TOOL_CALL_ERROR

    def test_context_compact_event(self):
        """ContextCompactEvent 创建"""
        event = ContextCompactEvent(
            agent_id="test-agent",
            tokens_before=100000,
            tokens_after=25000,
            tokens_saved=75000,
            summary_preview="User wanted to analyze project...",
        )
        assert event.tokens_before == 100000
        assert event.tokens_after == 25000
        assert event.tokens_saved == 75000
        assert event.type == EventType.CONTEXT_COMPACT

    def test_error_event(self):
        """ErrorEvent 创建"""
        event = ErrorEvent(
            agent_id="test-agent",
            error_type="ValueError",
            error_message="Invalid input",
            context={"input": "bad"},
        )
        assert event.error_type == "ValueError"
        assert event.error_message == "Invalid input"
        assert event.context == {"input": "bad"}
        assert event.type == EventType.ERROR


class TestEventEmitter:
    """EventEmitter 测试"""

    @pytest.mark.asyncio
    async def test_add_and_emit(self):
        """测试添加处理器和发射事件"""
        emitter = EventEmitter()
        received_events = []

        async def handler(event: AgentStartEvent):
            received_events.append(event)

        emitter.add_handler(EventType.AGENT_START, handler)
        await emitter.emit(AgentStartEvent(agent_id="test"))

        assert len(received_events) == 1
        assert received_events[0].agent_id == "test"

    @pytest.mark.asyncio
    async def test_decorator_subscription(self):
        """测试装饰器方式订阅"""
        emitter = EventEmitter()
        received_events = []

        @emitter.on(EventType.AGENT_START)
        async def handler(event: AgentStartEvent):
            received_events.append(event)

        await emitter.emit(AgentStartEvent(agent_id="test"))

        assert len(received_events) == 1
        assert received_events[0].agent_id == "test"

    @pytest.mark.asyncio
    async def test_multiple_handlers(self):
        """测试多个处理器"""
        emitter = EventEmitter()
        results = []

        async def handler1(event):
            results.append("handler1")

        async def handler2(event):
            results.append("handler2")

        emitter.add_handler(EventType.AGENT_START, handler1)
        emitter.add_handler(EventType.AGENT_START, handler2)

        await emitter.emit(AgentStartEvent(agent_id="test"))

        assert len(results) == 2
        assert "handler1" in results
        assert "handler2" in results

    @pytest.mark.asyncio
    async def test_remove_handler(self):
        """测试移除处理器"""
        emitter = EventEmitter()
        received_events = []

        async def handler(event):
            received_events.append(event)

        emitter.add_handler(EventType.AGENT_START, handler)
        await emitter.emit(AgentStartEvent(agent_id="test1"))
        assert len(received_events) == 1

        emitter.remove_handler(EventType.AGENT_START, handler)
        await emitter.emit(AgentStartEvent(agent_id="test2"))
        assert len(received_events) == 1  # 没有增加

    @pytest.mark.asyncio
    async def test_remove_all_handlers(self):
        """测试移除所有处理器"""
        emitter = EventEmitter()

        async def handler1(event):
            pass

        async def handler2(event):
            pass

        emitter.add_handler(EventType.AGENT_START, handler1)
        emitter.add_handler(EventType.AGENT_END, handler2)

        assert emitter.has_handler(EventType.AGENT_START)
        assert emitter.has_handler(EventType.AGENT_END)

        # 移除特定类型的处理器
        emitter.remove_all_handlers(EventType.AGENT_START)
        assert not emitter.has_handler(EventType.AGENT_START)
        assert emitter.has_handler(EventType.AGENT_END)

        # 移除所有处理器
        emitter.remove_all_handlers()
        assert not emitter.has_handler(EventType.AGENT_END)

    @pytest.mark.asyncio
    async def test_emit_without_handlers(self):
        """测试没有订阅者时发射事件（不应报错）"""
        emitter = EventEmitter()
        # 不应该抛出异常
        await emitter.emit(AgentStartEvent(agent_id="test"))

    @pytest.mark.asyncio
    async def test_get_handlers(self):
        """测试获取处理器列表"""
        emitter = EventEmitter()

        async def handler1(event):
            pass

        async def handler2(event):
            pass

        emitter.add_handler(EventType.AGENT_START, handler1)
        emitter.add_handler(EventType.AGENT_START, handler2)

        handlers = emitter.get_handlers(EventType.AGENT_START)
        assert len(handlers) == 2

    @pytest.mark.asyncio
    async def test_list_subscribed_events(self):
        """测试列出已订阅的事件"""
        emitter = EventEmitter()

        async def handler(event):
            pass

        emitter.add_handler(EventType.AGENT_START, handler)
        emitter.add_handler(EventType.AGENT_END, handler)

        events = emitter.list_subscribed_events()
        assert EventType.AGENT_START in events
        assert EventType.AGENT_END in events

    def test_event_summary(self):
        """测试事件摘要生成"""
        event = AgentStartEvent(agent_id="test", user_input="Hello")
        summary = create_event_summary(event)
        assert "agent_start" in summary  # 小写
        assert "test" in summary


class TestEventSummary:
    """事件摘要测试"""

    def test_agent_start_summary(self):
        """AgentStartEvent 摘要"""
        event = AgentStartEvent(agent_id="test-agent", user_input="Help me")
        summary = create_event_summary(event)
        assert "agent_start" in summary
        assert "test-agent" in summary

    def test_agent_end_summary_success(self):
        """AgentEndEvent 摘要（成功）"""
        from poiclaw.core.agent import AgentState

        event = AgentEndEvent(
            agent_id="test-agent",
            final_response="Done",
            state=AgentState(step=3),
        )
        summary = create_event_summary(event)
        assert "agent_end" in summary
        assert "success" in summary
        assert "3" in summary

    def test_agent_end_summary_error(self):
        """AgentEndEvent 摘要（错误）"""
        event = AgentEndEvent(
            agent_id="test-agent",
            error="Something went wrong",
        )
        summary = create_event_summary(event)
        assert "agent_end" in summary
        assert "error" in summary

    def test_turn_start_summary(self):
        """TurnStartEvent 摘要"""
        event = TurnStartEvent(turn_number=5)
        summary = create_event_summary(event)
        assert "turn_start" in summary
        assert "5" in summary

    def test_turn_end_summary(self):
        """TurnEndEvent 摘要"""
        event = TurnEndEvent(turn_number=3, tool_calls_made=2)
        summary = create_event_summary(event)
        assert "turn_end" in summary
        assert "3" in summary
        assert "2" in summary

    def test_message_update_summary(self):
        """MessageUpdateEvent 摘要"""
        event = MessageUpdateEvent(
            role="user",
            content_preview="Hello world, this is a test message",
        )
        summary = create_event_summary(event)
        assert "message_update" in summary
        assert "user" in summary

    def test_tool_call_start_summary(self):
        """ToolCallStartEvent 摘要"""
        event = ToolCallStartEvent(tool_name="bash")
        summary = create_event_summary(event)
        assert "tool_call_start" in summary
        assert "bash" in summary

    def test_tool_call_end_summary_success(self):
        """ToolCallEndEvent 摘要（成功）"""
        event = ToolCallEndEvent(
            tool_name="bash",
            success=True,
            duration_ms=150,
        )
        summary = create_event_summary(event)
        assert "tool_call_end" in summary
        assert "success" in summary
        assert "150ms" in summary

    def test_tool_call_error_summary(self):
        """ToolCallErrorEvent 摘要"""
        event = ToolCallErrorEvent(
            tool_name="bash",
            error_message="Command not found",
        )
        summary = create_event_summary(event)
        assert "tool_call_error" in summary
        assert "Command not found" in summary

    def test_context_compact_summary(self):
        """ContextCompactEvent 摘要"""
        event = ContextCompactEvent(
            tokens_before=100000,
            tokens_after=25000,
            tokens_saved=75000,
        )
        summary = create_event_summary(event)
        assert "context_compact" in summary
        assert "100000" in summary
        assert "25000" in summary
        assert "75000" in summary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
