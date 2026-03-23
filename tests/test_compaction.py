"""
上下文压缩模块测试

测试覆盖：
    - Token 估算
    - 压缩判断
    - 切割点查找
    - 消息序列化
"""

import pytest

from poiclaw.core.compaction import (
    estimate_tokens,
    estimate_total_tokens,
    find_cut_point,
    serialize_messages_for_summary,
    should_compact,
)
from poiclaw.core.session import CompactionSettings
from poiclaw.llm import Message


class TestEstimateTokens:
    """Token 估算测试"""

    def test_estimate_text_only(self):
        """纯文本消息估算"""
        msg = Message.user("Hello world")
        tokens = estimate_tokens(msg)
        # len("Hello world") = 11, 11 // 4 = 2
        assert tokens == 2

    def test_estimate_empty_content(self):
        """空内容估算"""
        msg = Message.user("")
        tokens = estimate_tokens(msg)
        assert tokens == 1  # max(1, 0)

    def test_estimate_long_text(self):
        """长文本估算"""
        text = "x" * 1000
        msg = Message.user(text)
        tokens = estimate_tokens(msg)
        assert tokens == 250  # 1000 // 4

    def test_estimate_with_tool_calls(self):
        """带工具调用的消息估算"""
        from poiclaw.llm import FunctionCall, ToolCall

        msg = Message(
            role="assistant",
            content="Let me check that.",
            tool_calls=[
                ToolCall(
                    id="call_123",
                    function=FunctionCall(
                        name="read_file",
                        arguments='{"path": "/src/main.py"}',
                    ),
                )
            ],
        )
        tokens = estimate_tokens(msg)
        # content: 20 chars, name: 9 chars, args: 22 chars, id: 8 chars
        # total: 59 chars, 59 // 4 = 14
        assert tokens > 0

    def test_estimate_tool_result(self):
        """工具结果消息估算"""
        msg = Message.tool_result(
            tool_call_id="call_123",
            content="File contents here..." * 100,
        )
        tokens = estimate_tokens(msg)
        assert tokens > 0


class TestEstimateTotalTokens:
    """总 Token 估算测试"""

    def test_empty_list(self):
        """空列表估算"""
        tokens = estimate_total_tokens([])
        assert tokens == 0

    def test_multiple_messages(self):
        """多消息估算"""
        messages = [
            Message.user("Hello"),
            Message.assistant("Hi there!"),
            Message.user("How are you?"),
        ]
        tokens = estimate_total_tokens(messages)
        assert tokens > 0

        # 验证总和
        expected = sum(estimate_tokens(m) for m in messages)
        assert tokens == expected


class TestShouldCompact:
    """压缩判断测试"""

    def test_disabled(self):
        """禁用压缩"""
        settings = CompactionSettings(enabled=False)
        messages = [Message.user("x" * 1000000)]  # 非常长的消息
        assert should_compact(messages, settings) is False

    def test_below_threshold(self):
        """低于阈值"""
        settings = CompactionSettings(
            enabled=True,
            context_window=128000,
            reserve_tokens=16384,
        )
        messages = [Message.user("Hello")]
        assert should_compact(messages, settings) is False

    def test_above_threshold(self):
        """超过阈值"""
        settings = CompactionSettings(
            enabled=True,
            context_window=1000,  # 很小的窗口用于测试
            reserve_tokens=100,
            keep_recent_tokens=100,  # 保持较小的保留窗口
        )
        # 创建超过阈值的消息（每条 400 字符 = 100 tokens）
        # 3 条消息 = 300 tokens，但 context_window - reserve_tokens = 900
        # 需要创建更多消息来超过阈值
        messages = [Message.user("x" * 400) for _ in range(10)]  # 1000 tokens
        assert should_compact(messages, settings) is True


class TestFindCutPoint:
    """切割点查找测试"""

    def test_empty_messages(self):
        """空消息列表"""
        cut = find_cut_point([], keep_tokens=1000)
        assert cut == 0

    def test_keep_all(self):
        """保留所有消息（keep_tokens 很大）"""
        messages = [Message.user(f"Message {i}") for i in range(10)]
        cut = find_cut_point(messages, keep_tokens=10000)
        # cut == 0 表示从第一条消息开始保留（即保留所有）
        # 但实际实现是返回切割点，如果不需要切割则返回 len(messages)
        assert cut == len(messages)  # 不需要切割，返回消息总数

    def test_cut_middle(self):
        """中间切割"""
        messages = [Message.user(f"Message {i}" + "x" * 100) for i in range(100)]
        cut = find_cut_point(messages, keep_tokens=500)
        assert cut > 0
        assert cut < len(messages)

    def test_cut_at_user_message(self):
        """在用户消息处切割（保持 Turn 完整性）"""
        # 创建多轮对话
        messages = []
        for i in range(20):
            messages.append(Message.user(f"User message {i}"))
            messages.append(Message.assistant(f"Assistant reply {i}"))

        cut = find_cut_point(messages, keep_tokens=200)
        # 切割点应该在 user 消息上
        assert cut % 2 == 0  # 索引应该是偶数（user 消息）


class TestSerializeMessages:
    """消息序列化测试"""

    def test_user_message(self):
        """用户消息序列化"""
        messages = [Message.user("Hello world")]
        text = serialize_messages_for_summary(messages)
        assert "[User]: Hello world" in text

    def test_assistant_message(self):
        """助手消息序列化"""
        messages = [Message.assistant("Hi there!")]
        text = serialize_messages_for_summary(messages)
        assert "[Assistant]: Hi there!" in text

    def test_tool_result_truncation(self):
        """工具结果截断"""
        long_content = "x" * 5000
        messages = [
            Message.tool_result(tool_call_id="call_123", content=long_content)
        ]
        text = serialize_messages_for_summary(messages)
        # 应该被截断
        assert len(text) < len(long_content) + 100
        assert "截断" in text

    def test_tool_calls(self):
        """工具调用序列化"""
        from poiclaw.llm import FunctionCall, ToolCall

        messages = [
            Message(
                role="assistant",
                tool_calls=[
                    ToolCall(
                        id="call_123",
                        function=FunctionCall(
                            name="read_file",
                            arguments='{"path": "/src/main.py"}',
                        ),
                    )
                ],
            )
        ]
        text = serialize_messages_for_summary(messages)
        assert "[Assistant tool calls]" in text
        assert "read_file" in text


class TestCompactionSettings:
    """压缩配置测试"""

    def test_default_settings(self):
        """默认配置"""
        settings = CompactionSettings()
        assert settings.enabled is True
        assert settings.context_window == 128000
        assert settings.reserve_tokens == 16384
        assert settings.keep_recent_tokens == 20000

    def test_threshold_calculation(self):
        """阈值计算"""
        settings = CompactionSettings(
            context_window=128000,
            reserve_tokens=16384,
        )
        assert settings.threshold == 111616  # 128000 - 16384

    def test_custom_settings(self):
        """自定义配置"""
        settings = CompactionSettings(
            enabled=False,
            context_window=32000,
            reserve_tokens=4000,
            keep_recent_tokens=8000,
        )
        assert settings.enabled is False
        assert settings.context_window == 32000
        assert settings.reserve_tokens == 4000
        assert settings.keep_recent_tokens == 8000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
