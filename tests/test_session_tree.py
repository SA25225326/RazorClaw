"""树形会话管理测试"""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from poiclaw.core.session_tree import (
    BranchSummaryEntry,
    CompactionEntry,
    CustomEntry,
    LabelEntry,
    ModelChangeEntry,
    SessionHeader,
    SessionInfoEntry,
    SessionMessageEntry,
    SessionTreeNode,
    TreeSessionManager,
    build_session_context,
    generate_id,
    load_jsonl_file,
    parse_jsonl_entries,
)
from poiclaw.llm import Message


# ============================================================================
# Helper Fixtures
# ============================================================================


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_messages():
    """示例消息列表"""
    return [
        Message.user("你好，请帮我写一个 Python 函数"),
        Message.assistant("好的，你想写什么函数？"),
        Message.user("一个计算斐波那契数列的函数"),
        Message.assistant("```python\ndef fib(n):\n    ...\n```"),
    ]


# ============================================================================
# ID 生成测试
# ============================================================================


class TestGenerateId:
    """ID 生成测试"""

    def test_generate_id_length(self):
        """测试 ID 长度为 8"""
        id1 = generate_id()
        assert len(id1) == 8

    def test_generate_id_uniqueness(self):
        """测试 ID 唯一性"""
        ids = {generate_id() for _ in range(100)}
        assert len(ids) == 100

    def test_generate_id_avoids_collision(self):
        """测试避免冲突"""
        existing = {"abc12345"}
        new_id = generate_id(existing)
        assert new_id != "abc12345"


# ============================================================================
# Entry 模型测试
# ============================================================================


class TestSessionEntryModels:
    """Session Entry 模型测试"""

    def test_session_header_validation(self):
        """测试 SessionHeader 验证"""
        header = SessionHeader(
            id="test-uuid",
            timestamp="2024-01-01T00:00:00",
            cwd="/test/path",
        )
        assert header.type == "session"
        assert header.version == 2
        assert header.id == "test-uuid"

    def test_session_message_entry_validation(self):
        """测试 SessionMessageEntry 验证"""
        entry = SessionMessageEntry(
            type="message",
            id="abc123",
            parent_id=None,
            timestamp="2024-01-01T00:00:00",
            message={"role": "user", "content": "Hello"},
        )
        assert entry.type == "message"
        assert entry.id == "abc123"
        assert entry.parent_id is None

    def test_compaction_entry_id_reference(self):
        """测试 CompactionEntry 使用 first_kept_entry_id"""
        entry = CompactionEntry(
            type="compaction",
            id="comp123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            summary="摘要内容",
            first_kept_entry_id="msg123",
            tokens_before=1000,
            tokens_after=200,
        )
        assert entry.first_kept_entry_id == "msg123"

    def test_model_change_entry(self):
        """测试 ModelChangeEntry"""
        entry = ModelChangeEntry(
            type="model_change",
            id="mc123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            provider="openai",
            model_id="gpt-4",
        )
        assert entry.provider == "openai"
        assert entry.model_id == "gpt-4"

    def test_branch_summary_entry(self):
        """测试 BranchSummaryEntry"""
        entry = BranchSummaryEntry(
            type="branch_summary",
            id="bs123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            from_id="msg456",
            summary="被放弃的分支摘要",
        )
        assert entry.from_id == "msg456"
        assert entry.summary == "被放弃的分支摘要"

    def test_custom_entry(self):
        """测试 CustomEntry"""
        entry = CustomEntry(
            type="custom",
            id="cust123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            custom_type="my_extension",
            data={"key": "value"},
        )
        assert entry.custom_type == "my_extension"
        assert entry.data == {"key": "value"}

    def test_label_entry(self):
        """测试 LabelEntry"""
        entry = LabelEntry(
            type="label",
            id="lbl123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            target_id="msg789",
            label="重要节点",
        )
        assert entry.target_id == "msg789"
        assert entry.label == "重要节点"

    def test_session_info_entry(self):
        """测试 SessionInfoEntry"""
        entry = SessionInfoEntry(
            type="session_info",
            id="si123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            name="我的会话",
        )
        assert entry.name == "我的会话"


# ============================================================================
# JSONL 解析测试
# ============================================================================


class TestJsonlParsing:
    """JSONL 解析测试"""

    def test_parse_jsonl_entries(self):
        """测试解析 JSONL 内容"""
        content = """{"type":"session","version":2,"id":"test","timestamp":"2024-01-01"}
{"type":"message","id":"abc","parentId":null,"timestamp":"2024-01-01","message":{"role":"user"}}
"""
        entries = parse_jsonl_entries(content)
        assert len(entries) == 2
        assert entries[0]["type"] == "session"
        assert entries[1]["type"] == "message"

    def test_parse_jsonl_empty_content(self):
        """测试解析空内容"""
        entries = parse_jsonl_entries("")
        assert entries == []

    def test_parse_jsonl_skip_malformed(self):
        """测试跳过格式错误的行"""
        content = """{"type":"session","version":2}
invalid json
{"type":"message","id":"abc","parentId":null}
"""
        entries = parse_jsonl_entries(content)
        assert len(entries) == 2

    def test_load_jsonl_file(self, temp_dir):
        """测试加载 JSONL 文件"""
        file_path = temp_dir / "test.jsonl"
        file_path.write_text(
            '{"type":"session","version":2,"id":"test","timestamp":"2024-01-01"}\n'
            '{"type":"message","id":"abc","parentId":null,"timestamp":"2024-01-01","message":{}}\n',
            encoding="utf-8",
        )
        entries = load_jsonl_file(file_path)
        assert len(entries) == 2


# ============================================================================
# TreeSessionManager 测试
# ============================================================================


class TestTreeSessionManager:
    """TreeSessionManager 测试"""

    def test_create_new_session(self, temp_dir):
        """测试创建新会话"""
        manager = TreeSessionManager.create(str(temp_dir))
        assert manager.session_id != ""
        assert manager.leaf_id is None

    def test_append_message_creates_tree(self, temp_dir, sample_messages):
        """测试追加消息创建树结构"""
        manager = TreeSessionManager.create(str(temp_dir))

        # 追加消息
        entry_id1 = manager.append_message(sample_messages[0])
        entry_id2 = manager.append_message(sample_messages[1])

        assert entry_id1 != entry_id2
        assert manager.leaf_id == entry_id2

        # 验证父子关系
        entry1 = manager.get_entry(entry_id1)
        entry2 = manager.get_entry(entry_id2)
        assert entry1.parent_id is None  # 根节点
        assert entry2.parent_id == entry_id1

    def test_get_children(self, temp_dir, sample_messages):
        """测试获取子节点"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])
        manager.append_message(sample_messages[1])

        # 创建分支
        manager.branch(id1)
        id3 = manager.append_message(sample_messages[2])

        children = manager.get_children(id1)
        assert len(children) == 2

    def test_get_branch_path(self, temp_dir, sample_messages):
        """测试获取分支路径"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])
        id3 = manager.append_message(sample_messages[2])

        path = manager.get_branch()
        assert len(path) == 3
        assert path[0].id == id1
        assert path[1].id == id2
        assert path[2].id == id3

    def test_get_tree_structure(self, temp_dir, sample_messages):
        """测试获取树结构"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])

        # 创建分支
        manager.branch(id1)
        id3 = manager.append_message(sample_messages[2])

        tree = manager.get_tree()
        assert len(tree) == 1  # 一个根节点
        assert len(tree[0].children) == 2  # 两个分支

    def test_branch_creates_fork(self, temp_dir, sample_messages):
        """测试分支创建分叉"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])

        # 从 id1 创建分支
        manager.branch(id1)
        id3 = manager.append_message(sample_messages[2])

        # 验证分支
        entry3 = manager.get_entry(id3)
        assert entry3.parent_id == id1

        # 原有节点不受影响
        entry2 = manager.get_entry(id2)
        assert entry2.parent_id == id1

    def test_branch_with_summary(self, temp_dir, sample_messages):
        """测试带摘要的分支"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])

        # 带摘要分支
        summary_id = manager.branch_with_summary(id1, "放弃的分支摘要")

        # 验证摘要 Entry
        entry = manager.get_entry(summary_id)
        assert isinstance(entry, BranchSummaryEntry)
        assert entry.summary == "放弃的分支摘要"
        assert entry.from_id == id1

    def test_reset_leaf(self, temp_dir, sample_messages):
        """测试重置叶子指针"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])

        # 重置
        manager.reset_leaf()
        assert manager.leaf_id is None

        # 新消息成为新根
        id3 = manager.append_message(sample_messages[2])
        entry3 = manager.get_entry(id3)
        assert entry3.parent_id is None

    def test_append_label(self, temp_dir, sample_messages):
        """测试追加标签"""
        manager = TreeSessionManager.create(str(temp_dir))

        id1 = manager.append_message(sample_messages[0])

        # 添加标签
        manager.append_label(id1, "重要")

        # 验证标签
        label = manager.get_label(id1)
        assert label == "重要"

    def test_persistence(self, temp_dir, sample_messages):
        """测试持久化"""
        session_dir = temp_dir / "sessions"
        session_dir.mkdir()

        # 创建并保存
        manager1 = TreeSessionManager.create(str(temp_dir), str(session_dir))
        session_id = manager1.session_id
        id1 = manager1.append_message(sample_messages[0])
        id2 = manager1.append_message(sample_messages[1])

        # 加载
        jsonl_files = list(session_dir.glob("*.jsonl"))
        assert len(jsonl_files) == 1

        manager2 = TreeSessionManager.open(jsonl_files[0])
        assert manager2.session_id == session_id

        # 验证树结构
        path = manager2.get_branch()
        assert len(path) == 2

    def test_in_memory_session(self, sample_messages):
        """测试内存会话"""
        manager = TreeSessionManager.in_memory()

        manager.append_message(sample_messages[0])
        manager.append_message(sample_messages[1])

        assert len(manager.get_entries()) == 2
        assert manager.session_file is None  # 不持久化


# ============================================================================
# build_session_context 测试
# ============================================================================


class TestBuildSessionContext:
    """build_session_context 测试"""

    def test_no_compaction(self, sample_messages):
        """测试无压缩的上下文构建"""
        manager = TreeSessionManager.in_memory()

        id1 = manager.append_message(sample_messages[0])
        manager.append_message(sample_messages[1])

        context = manager.build_session_context()

        assert len(context.messages) == 2
        assert context.messages[0].content == sample_messages[0].content

    def test_with_compaction(self):
        """测试带压缩的上下文构建"""
        manager = TreeSessionManager.in_memory()

        # 添加消息
        id1 = manager.append_message(Message.user("消息1"))
        id2 = manager.append_message(Message.assistant("回复1"))
        id3 = manager.append_message(Message.user("消息2"))
        id4 = manager.append_message(Message.assistant("回复2"))

        # 添加压缩
        manager.append_compaction(
            summary="压缩摘要",
            first_kept_entry_id=id3,
            tokens_before=1000,
            tokens_after=200,
        )

        # 添加更多消息
        manager.append_message(Message.user("消息3"))

        context = manager.build_session_context()

        # 应该包含：摘要 + 消息2 + 回复2 + 消息3
        assert len(context.messages) == 4
        assert "压缩摘要" in context.messages[0].content

    def test_with_branch_summary(self):
        """测试带分支摘要的上下文构建"""
        manager = TreeSessionManager.in_memory()

        id1 = manager.append_message(Message.user("消息1"))
        id2 = manager.append_message(Message.assistant("回复1"))

        # 带摘要分支
        manager.branch_with_summary(id1, "放弃的分支摘要")

        manager.append_message(Message.user("消息2"))

        context = manager.build_session_context()

        # 应该包含：消息1 + 分支摘要 + 消息2
        assert len(context.messages) == 3
        assert "放弃的分支摘要" in context.messages[1].content


# ============================================================================
# 集成测试
# ============================================================================


class TestIntegration:
    """集成测试"""

    def test_full_workflow(self, temp_dir, sample_messages):
        """测试完整工作流"""
        session_dir = temp_dir / "sessions"
        session_dir.mkdir()

        # 1. 创建会话
        manager = TreeSessionManager.create(str(temp_dir), str(session_dir))

        # 2. 添加消息
        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])
        id3 = manager.append_message(sample_messages[2])
        id4 = manager.append_message(sample_messages[3])

        # 3. 创建分支
        manager.branch(id2)
        id5 = manager.append_message(Message.user("分支消息"))

        # 4. 获取树
        tree = manager.get_tree()
        # 分支从 id2 创建，id2 是第一个助手消息，是根节点的第一个子节点
        # 所以第一层应该只有一个根节点
        assert len(tree) == 1
        # id2（助手回复1）应该有两个子节点：主线（id3）和分支（id5）
        first_child = tree[0].children[0]
        assert len(first_child.children) == 2  # 主线 + 分支

        # 5. 切换回主线
        manager.branch(id4)
        path = manager.get_branch()
        assert len(path) == 4
        assert path[-1].id == id4

        # 6. 持久化并重新加载
        jsonl_files = list(session_dir.glob("*.jsonl"))
        manager2 = TreeSessionManager.open(jsonl_files[0])

        # 验证树结构保持
        tree2 = manager2.get_tree()
        # 验证分支结构：第一个子节点应该有两个子分支
        first_child = tree2[0].children[0]
        assert len(first_child.children) == 2  # 主线 + 分支


# ============================================================================
# 新增功能测试
# ============================================================================


class TestThinkingLevelChange:
    """思考级别变更测试"""

    def test_thinking_level_entry_validation(self):
        """测试 ThinkingLevelChangeEntry 验证"""
        from poiclaw.core.session_tree import ThinkingLevelChangeEntry

        entry = ThinkingLevelChangeEntry(
            type="thinking_level_change",
            id="tl123",
            parent_id="msg456",
            timestamp="2024-01-01T00:00:00",
            thinking_level="high",
        )
        assert entry.thinking_level == "high"

    def test_append_thinking_level_change(self):
        """测试追加思考级别变更"""
        manager = TreeSessionManager.in_memory()

        id1 = manager.append_message(Message.user("你好"))
        id2 = manager.append_thinking_level_change("high")
        id3 = manager.append_message(Message.assistant("让我仔细想想..."))

        assert id1 != id2 != id3

        # 验证 Entry 存在
        entry = manager.get_entry(id2)
        assert entry is not None
        assert entry.thinking_level == "high"


class TestCustomMessageEntry:
    """自定义消息 Entry 测试"""

    def test_custom_message_entry_validation(self):
        """测试 CustomMessageEntry 验证"""
        from poiclaw.core.session_tree import CustomMessageEntry

        # 字符串内容
        entry1 = CustomMessageEntry(
            type="custom_message",
            id="cm123",
            parent_id=None,
            timestamp="2024-01-01T00:00:00",
            custom_type="my_extension",
            content="自定义内容",
            display=True,
        )
        assert entry1.content == "自定义内容"

        # 结构化内容
        entry2 = CustomMessageEntry(
            type="custom_message",
            id="cm456",
            parent_id=None,
            timestamp="2024-01-01T00:00:00",
            custom_type="my_extension",
            content=[{"type": "text", "text": "文本块"}],
            display=False,
        )
        assert entry2.display is False

    def test_append_custom_message(self):
        """测试追加自定义消息"""
        manager = TreeSessionManager.in_memory()

        manager.append_message(Message.user("你好"))
        custom_id = manager.append_custom_message(
            custom_type="context_injector",
            content="这是额外的上下文信息",
            display=True,
            details={"source": "external"},
        )

        # 验证 Entry 存在
        entry = manager.get_entry(custom_id)
        assert entry is not None
        assert entry.custom_type == "context_injector"

    def test_custom_message_in_context(self):
        """测试自定义消息出现在上下文中"""
        manager = TreeSessionManager.in_memory()

        manager.append_message(Message.user("你好"))
        manager.append_custom_message(
            custom_type="reminder",
            content="记住这个重要信息",
        )

        context = manager.build_session_context()

        # 上下文应该包含自定义消息
        assert len(context.messages) == 2
        assert "记住这个重要信息" in context.messages[1].content


class TestCustomMessageEntry:
    """自定义消息 Entry 测试"""

    def test_custom_message_entry_validation(self):
        """测试 CustomMessageEntry 验证"""
        from poiclaw.core.session_tree import CustomMessageEntry

        # 字符串内容
        entry1 = CustomMessageEntry(
            type="custom_message",
            id="cm123",
            parent_id=None,
            timestamp="2024-01-01T00:00:00",
            custom_type="my_extension",
            content="自定义内容",
            display=True,
        )
        assert entry1.content == "自定义内容"

        # 结构化内容
        entry2 = CustomMessageEntry(
            type="custom_message",
            id="cm456",
            parent_id=None,
            timestamp="2024-01-01T00:00:00",
            custom_type="my_extension",
            content=[{"type": "text", "text": "文本块"}],
            display=False,
        )
        assert entry2.display is False

    def test_append_custom_message(self):
        """测试追加自定义消息"""
        manager = TreeSessionManager.in_memory()

        manager.append_message(Message.user("你好"))
        custom_id = manager.append_custom_message(
            custom_type="context_injector",
            content="这是额外的上下文信息",
            display=True,
            details={"source": "external"},
        )

        # 验证 Entry 存在
        entry = manager.get_entry(custom_id)
        assert entry is not None
        assert entry.custom_type == "context_injector"

    def test_custom_message_in_context(self):
        """测试自定义消息出现在上下文中"""
        manager = TreeSessionManager.in_memory()

        manager.append_message(Message.user("你好"))
        manager.append_custom_message(
            custom_type="reminder",
            content="记住这个重要信息",
        )

        context = manager.build_session_context()

        # 上下文应该包含自定义消息
        assert len(context.messages) == 2
        assert "记住这个重要信息" in context.messages[1].content


class TestSessionInfo:
    """会话信息测试"""

    def test_append_session_info(self):
        """测试追加会话信息"""
        manager = TreeSessionManager.in_memory()

        manager.append_session_info("我的重要会话")

        name = manager.get_session_name()
        assert name == "我的重要会话"

    def test_update_session_name(self):
        """测试更新会话名称"""
        manager = TreeSessionManager.in_memory()

        manager.append_session_info("旧名称")
        manager.append_session_info("新名称")

        name = manager.get_session_name()
        assert name == "新名称"

    def test_clear_session_name(self):
        """测试清除会话名称"""
        manager = TreeSessionManager.in_memory()

        manager.append_session_info("有名称")
        manager.append_session_info(None)  # 清除

        name = manager.get_session_name()
        assert name is None


class TestContinueRecent:
    """继续最近会话测试"""

    def test_continue_recent_with_existing(self, temp_dir):
        """测试继续现有会话"""
        session_dir = temp_dir / "sessions"
        session_dir.mkdir()

        # 创建一个会话（需要包含助手消息才能持久化）
        manager1 = TreeSessionManager.create(str(temp_dir), str(session_dir))
        manager1.append_message(Message.user("之前的消息"))
        manager1.append_message(Message.assistant("之前的回复"))

        # 继续最近会话
        manager2 = TreeSessionManager.continue_recent(str(temp_dir), str(session_dir))

        # 应该是同一个会话（消息内容相同）
        path = manager2.get_branch()
        assert len(path) == 2
        assert path[0].message["content"] == "之前的消息"
        assert path[1].message["content"] == "之前的回复"

    def test_continue_recent_without_existing(self, temp_dir):
        """测试没有现有会话时创建新会话"""
        session_dir = temp_dir / "sessions"

        manager = TreeSessionManager.continue_recent(str(temp_dir), str(session_dir))

        # 应该是新会话
        assert manager.session_id != ""
        assert len(manager.get_entries()) == 0


class TestCreateBranchedSession:
    """创建分支会话测试"""

    def test_create_branched_session(self, temp_dir, sample_messages):
        """测试从分支创建新会话"""
        session_dir = temp_dir / "sessions"
        session_dir.mkdir()

        # 创建会话并添加消息
        manager = TreeSessionManager.create(str(temp_dir), str(session_dir))
        id1 = manager.append_message(sample_messages[0])
        id2 = manager.append_message(sample_messages[1])
        id3 = manager.append_message(sample_messages[2])
        id4 = manager.append_message(sample_messages[3])

        # 创建分支
        manager.branch(id2)
        manager.append_message(Message.user("分支消息"))

        # 从主线叶子创建新会话
        new_file = manager.create_branched_session(id4)

        assert new_file is not None
        assert Path(new_file).exists()

        # 加载新会话
        new_manager = TreeSessionManager.open(new_file)

        # 应该只有主线路径
        path = new_manager.get_branch()
        assert len(path) == 4  # 4条消息

        # 不应该包含分支消息
        for entry in path:
            if isinstance(entry, SessionMessageEntry):
                assert "分支消息" not in str(entry.message.get("content", ""))


class TestListSessions:
    """列出会话测试"""

    def test_list_sessions(self, temp_dir):
        """测试列出会话"""
        session_dir = temp_dir / "sessions"
        session_dir.mkdir()

        # 创建多个会话（需要包含助手消息才能持久化）
        for i in range(3):
            manager = TreeSessionManager.create(str(temp_dir), str(session_dir))
            manager.append_message(Message.user(f"会话 {i}"))
            manager.append_message(Message.assistant(f"回复 {i}"))

        # 列出会话
        sessions = TreeSessionManager.list_sessions(session_dir)

        assert len(sessions) == 3
        assert all("id" in s for s in sessions)
        assert all("message_count" in s for s in sessions)


class TestForkFrom:
    """跨目录 Fork 测试"""

    def test_fork_from(self, temp_dir):
        """测试从另一个目录 fork 会话"""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        target_dir = temp_dir / "target"

        # 创建源会话（需要包含助手消息才能持久化）
        source_manager = TreeSessionManager.create(str(source_dir), str(source_dir / "sessions"))
        source_manager.append_message(Message.user("源会话消息"))
        source_manager.append_message(Message.assistant("源会话回复"))

        # Fork 到目标目录
        target_manager = TreeSessionManager.fork_from(
            source_manager.session_file,
            str(target_dir),
            str(target_dir / "sessions"),
        )

        # 验证目标会话包含源会话内容
        path = target_manager.get_branch()
        assert len(path) == 2
        assert path[0].message["content"] == "源会话消息"
        assert path[1].message["content"] == "源会话回复"

        # 验证 parent_session 引用
        header = target_manager._get_header()
        assert header.parent_session is not None
