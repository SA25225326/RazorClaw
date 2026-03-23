"""会话管理模块测试"""

import asyncio
import tempfile
from pathlib import Path

import pytest

from poiclaw.core.session import (
    FileSessionManager,
    SessionData,
    SessionMetadata,
    UsageStats,
)
from poiclaw.llm import Message, MessageRole


class TestUsageStats:
    """UsageStats 测试"""

    def test_zero(self):
        """测试零值创建"""
        stats = UsageStats.zero()
        assert stats.input == 0
        assert stats.output == 0
        assert stats.total_tokens == 0

    def test_merge(self):
        """测试合并"""
        stats1 = UsageStats(input=100, output=50, total_tokens=150)
        stats2 = UsageStats(input=200, output=80, total_tokens=280)

        merged = stats1.merge(stats2)

        assert merged.input == 300
        assert merged.output == 130
        assert merged.total_tokens == 430


class TestFileSessionManager:
    """FileSessionManager 测试"""

    @pytest.fixture
    def temp_dir(self):
        """创建临时目录"""
        with tempfile.TemporaryDirectory() as d:
            yield d

    @pytest.fixture
    def manager(self, temp_dir):
        """创建会话管理器"""
        return FileSessionManager(base_path=temp_dir)

    @pytest.fixture
    def sample_messages(self):
        """示例消息列表"""
        return [
            Message.user("你好，请帮我写一个 Python 函数"),
            Message.assistant("好的，你想写什么函数？"),
            Message.user("一个计算斐波那契数列的函数"),
            Message.assistant("```python\ndef fib(n):\n    ...\n```"),
        ]

    def test_generate_id(self):
        """测试 ID 生成"""
        id1 = FileSessionManager.generate_id()
        id2 = FileSessionManager.generate_id()

        assert id1 != id2
        assert len(id1) == 36  # UUID 格式

    @pytest.mark.asyncio
    async def test_save_and_load_session(self, manager, sample_messages):
        """测试保存和加载会话"""
        session_id = manager.generate_id()
        usage = UsageStats(input=100, output=50, total_tokens=150)

        # 保存
        success = await manager.save_session(
            session_id=session_id,
            messages=sample_messages,
            title="测试会话",
            usage=usage,
        )
        assert success is True

        # 加载
        loaded = await manager.load_session(session_id)
        assert loaded is not None
        assert len(loaded) == 4
        assert loaded[0].content == "你好，请帮我写一个 Python 函数"

    @pytest.mark.asyncio
    async def test_get_metadata(self, manager, sample_messages):
        """测试获取元数据"""
        session_id = manager.generate_id()

        await manager.save_session(
            session_id=session_id,
            messages=sample_messages,
            title="元数据测试",
        )

        metadata = await manager.get_metadata(session_id)
        assert metadata is not None
        assert metadata.title == "元数据测试"
        assert metadata.message_count == 4
        assert "你好" in metadata.preview

    @pytest.mark.asyncio
    async def test_list_sessions(self, manager, sample_messages):
        """测试列出会话"""
        # 创建多个会话
        for i in range(3):
            session_id = manager.generate_id()
            await manager.save_session(
                session_id=session_id,
                messages=sample_messages,
                title=f"会话 {i + 1}",
            )
            await asyncio.sleep(0.01)  # 确保时间戳不同

        sessions = await manager.list_sessions()
        assert len(sessions) == 3
        # 按最后修改时间降序
        assert sessions[0].title == "会话 3"

    @pytest.mark.asyncio
    async def test_delete_session(self, manager, sample_messages):
        """测试删除会话"""
        session_id = manager.generate_id()

        await manager.save_session(
            session_id=session_id,
            messages=sample_messages,
        )

        # 确认存在
        metadata = await manager.get_metadata(session_id)
        assert metadata is not None

        # 删除
        success = await manager.delete_session(session_id)
        assert success is True

        # 确认已删除
        metadata = await manager.get_metadata(session_id)
        assert metadata is None

    @pytest.mark.asyncio
    async def test_update_title(self, manager, sample_messages):
        """测试更新标题"""
        session_id = manager.generate_id()

        await manager.save_session(
            session_id=session_id,
            messages=sample_messages,
            title="原标题",
        )

        # 更新标题
        success = await manager.update_title(session_id, "新标题")
        assert success is True

        # 验证
        metadata = await manager.get_metadata(session_id)
        assert metadata.title == "新标题"

    @pytest.mark.asyncio
    async def test_title_protection(self, manager, sample_messages):
        """测试标题保护（title=None 时保留原标题）"""
        session_id = manager.generate_id()

        # 首次保存
        await manager.save_session(
            session_id=session_id,
            messages=sample_messages,
            title="初始标题",
        )

        # 再次保存，title=None
        await manager.save_session(
            session_id=session_id,
            messages=sample_messages + [Message.user("继续对话")],
            title=None,  # 不传标题
        )

        # 验证标题未被覆盖
        metadata = await manager.get_metadata(session_id)
        assert metadata.title == "初始标题"

    @pytest.mark.asyncio
    async def test_auto_generate_title(self, manager):
        """测试自动生成标题（从首条用户消息）"""
        session_id = manager.generate_id()

        messages = [
            Message.user("这是一段很长的用户输入，用来测试标题自动生成功能，应该只取前50个字符作为标题"),
            Message.assistant("好的"),
        ]

        await manager.save_session(
            session_id=session_id,
            messages=messages,
            title=None,  # 不传标题，应该自动生成
        )

        metadata = await manager.get_metadata(session_id)
        assert "这是一段很长的用户输入" in metadata.title

    @pytest.mark.asyncio
    async def test_load_nonexistent_session(self, manager):
        """测试加载不存在的会话"""
        loaded = await manager.load_session("nonexistent-id")
        assert loaded is None

    @pytest.mark.asyncio
    async def test_usage_accumulation(self, manager, sample_messages):
        """测试使用量累积"""
        session_id = manager.generate_id()

        # 首次保存
        usage1 = UsageStats(input=100, output=50, total_tokens=150)
        await manager.save_session(
            session_id=session_id,
            messages=sample_messages[:2],
            usage=usage1,
        )

        # 再次保存（累积）
        usage2 = UsageStats(input=200, output=80, total_tokens=280)
        await manager.save_session(
            session_id=session_id,
            messages=sample_messages,
            usage=usage2,
        )

        # 验证累积
        metadata = await manager.get_metadata(session_id)
        assert metadata.usage.input == 300  # 100 + 200
        assert metadata.usage.output == 130  # 50 + 80


class TestModels:
    """数据模型测试"""

    def test_usage_stats_model_dump(self):
        """测试 UsageStats 序列化"""
        stats = UsageStats(input=100, output=50, total_tokens=150)
        data = stats.model_dump()

        assert data["input"] == 100
        assert data["output"] == 50

    def test_session_metadata_model_validate(self):
        """测试 SessionMetadata 反序列化"""
        data = {
            "id": "test-id",
            "title": "测试",
            "created_at": "2024-01-01T00:00:00",
            "last_modified": "2024-01-01T00:00:00",
            "message_count": 10,
            "usage": {"input": 100, "output": 50, "cache_read": 0, "cache_write": 0, "total_tokens": 150},
            "preview": "预览内容",
        }

        metadata = SessionMetadata.model_validate(data)
        assert metadata.id == "test-id"
        assert metadata.usage.input == 100

    def test_session_data_model_validate(self):
        """测试 SessionData 反序列化"""
        data = {
            "id": "test-id",
            "title": "测试",
            "created_at": "2024-01-01T00:00:00",
            "last_modified": "2024-01-01T00:00:00",
            "messages": [
                {"role": "user", "content": "你好"},
                {"role": "assistant", "content": "你好！"},
            ],
            "usage": {"input": 100, "output": 50, "cache_read": 0, "cache_write": 0, "total_tokens": 150},
        }

        session_data = SessionData.model_validate(data)
        assert len(session_data.messages) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
