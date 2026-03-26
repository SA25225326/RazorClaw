"""
树形会话管理器 - 支持 Git-like 分支和回溯

核心概念：
    - Entry: 每条记录（消息、压缩、模型切换等）有 id 和 parent_id
    - Leaf: 当前叶子节点，新 Entry 会成为 Leaf 的子节点
    - Branch: 从任意节点创建分支，不修改历史
    - JSONL: 每行一个 JSON 对象，追加写入

存储格式（JSONL）：
    {"type":"session","version":2,"id":"...","timestamp":"...","cwd":"..."}
    {"type":"message","id":"abc123","parentId":null,"timestamp":"...","message":{...}}
    {"type":"message","id":"def456","parentId":"abc123","timestamp":"...","message":{...}}
    {"type":"compaction","id":"ghi789","parentId":"def456","firstKeptEntryId":"abc123",...}

设计参考：
    - pi-mono 的 SessionManager 实现
    - Git 的分支模型
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Union

from pydantic import BaseModel, Field

from poiclaw.llm import Message


# ============================================================================
# 常量
# ============================================================================

CURRENT_SESSION_VERSION = 2


# ============================================================================
# Session Header
# ============================================================================


class SessionHeader(BaseModel):
    """
    会话头部 - JSONL 文件的第一行。

    Attributes:
        type: 固定为 "session"
        version: 会话格式版本（当前为 2）
        id: 会话 UUID
        timestamp: 创建时间（ISO 8601）
        cwd: 工作目录
        parent_session: 父会话路径（用于 fork 的会话）
    """

    type: Literal["session"] = "session"
    version: int = CURRENT_SESSION_VERSION
    id: str
    timestamp: str
    cwd: str = ""
    parent_session: str | None = None


# ============================================================================
# Session Entry Base
# ============================================================================


class SessionEntryBase(BaseModel):
    """
    所有 Session Entry 的基类。

    Attributes:
        type: Entry 类型
        id: 唯一标识符（8 位短 ID）
        parent_id: 父节点 ID（None 表示根节点）
        timestamp: 创建时间（ISO 8601）
    """

    type: str
    id: str
    parent_id: str | None = None
    timestamp: str


# ============================================================================
# Message Entry
# ============================================================================


class SessionMessageEntry(SessionEntryBase):
    """
    消息 Entry - 存储用户/助手消息。

    Attributes:
        type: 固定为 "message"
        message: Message 的序列化形式（dict）
    """

    type: Literal["message"] = "message"
    message: dict[str, Any]


# ============================================================================
# Compaction Entry
# ============================================================================


class CompactionEntry(SessionEntryBase):
    """
    压缩 Entry - 上下文压缩记录。

    与旧版 CompactionEntry 的区别：
    - first_kept_entry_id: 使用 ID 引用而非索引
    - 继承自 SessionEntryBase，有 id 和 parent_id

    Attributes:
        type: 固定为 "compaction"
        summary: LLM 生成的摘要
        first_kept_entry_id: 第一个保留的消息 Entry ID
        tokens_before: 压缩前的 token 数
        tokens_after: 压缩后的 token 数
        details: 扩展数据（可选）
        from_hook: 是否由 hook 生成
    """

    type: Literal["compaction"] = "compaction"
    summary: str
    first_kept_entry_id: str
    tokens_before: int
    tokens_after: int
    details: dict[str, Any] | None = None
    from_hook: bool = False


# ============================================================================
# Model Change Entry
# ============================================================================


class ModelChangeEntry(SessionEntryBase):
    """
    模型切换 Entry - 记录模型/提供商变更。

    Attributes:
        type: 固定为 "model_change"
        provider: 提供商名称
        model_id: 模型 ID
    """

    type: Literal["model_change"] = "model_change"
    provider: str
    model_id: str


# ============================================================================
# Thinking Level Change Entry
# ============================================================================


class ThinkingLevelChangeEntry(SessionEntryBase):
    """
    思考模式切换 Entry - 记录 thinking level 变化。

    pi-mono 支持 extended thinking（扩展思考）模式，
    此 Entry 记录思考模式的变化（如 "off" → "medium" → "high"）。

    Attributes:
        type: 固定为 "thinking_level_change"
        thinking_level: 思考级别（"off" | "low" | "medium" | "high"）
    """

    type: Literal["thinking_level_change"] = "thinking_level_change"
    thinking_level: str  # "off" | "low" | "medium" | "high"


# ============================================================================
# Branch Summary Entry
# ============================================================================


class BranchSummaryEntry(SessionEntryBase):
    """
    分支摘要 Entry - 切换分支时记录被放弃路径的摘要。

    当用户从某个节点创建新分支时，可以附带一个摘要，
    记录被放弃的对话路径的关键信息。

    Attributes:
        type: 固定为 "branch_summary"
        from_id: 分支起始点 ID（None 表示从根）
        summary: 被放弃路径的摘要
        details: 扩展数据（可选）
        from_hook: 是否由 hook 生成
    """

    type: Literal["branch_summary"] = "branch_summary"
    from_id: str | None
    summary: str
    details: dict[str, Any] | None = None
    from_hook: bool = False


# ============================================================================
# Custom Entry
# ============================================================================


class CustomEntry(SessionEntryBase):
    """
    自定义 Entry - 扩展存储自定义数据。

    用于扩展存储不参与 LLM 上下文的元数据。
    扩展可以通过 custom_type 识别自己的 Entry。

    Attributes:
        type: 固定为 "custom"
        custom_type: 扩展标识符
        data: 自定义数据
    """

    type: Literal["custom"] = "custom"
    custom_type: str
    data: dict[str, Any] | None = None


# ============================================================================
# Custom Message Entry
# ============================================================================


class CustomMessageEntry(SessionEntryBase):
    """
    自定义消息 Entry - 扩展可注入消息到 LLM 上下文。

    与 CustomEntry 不同，这个 Entry 会参与 LLM 上下文构建。
    内容会被转换为 user 消息注入到 buildSessionContext() 的结果中。

    用途：
    - 扩展向对话注入额外的上下文信息
    - 记录用户自定义的系统提示
    - 注入外部数据源的信息

    Attributes:
        type: 固定为 "custom_message"
        custom_type: 扩展标识符
        content: 消息内容（字符串或结构化内容）
        display: 是否在 UI 中显示（用于前端渲染）
        details: 扩展元数据（不发送给 LLM）
    """

    type: Literal["custom_message"] = "custom_message"
    custom_type: str
    content: str | list[dict[str, Any]]  # 字符串或 TextContent/ImageContent 数组
    display: bool = True
    details: dict[str, Any] | None = None


# ============================================================================
# Label Entry
# ============================================================================


class LabelEntry(SessionEntryBase):
    """
    标签 Entry - 用户定义的书签/标记。

    Attributes:
        type: 固定为 "label"
        target_id: 被标记的 Entry ID
        label: 标签文本（None 表示清除标签）
    """

    type: Literal["label"] = "label"
    target_id: str
    label: str | None = None


# ============================================================================
# Session Info Entry
# ============================================================================


class SessionInfoEntry(SessionEntryBase):
    """
    会话信息 Entry - 会话级别的元数据。

    Attributes:
        type: 固定为 "session_info"
        name: 用户定义的会话显示名称
    """

    type: Literal["session_info"] = "session_info"
    name: str | None = None


# ============================================================================
# Union Types
# ============================================================================


SessionEntry = Union[
    SessionMessageEntry,
    CompactionEntry,
    ModelChangeEntry,
    ThinkingLevelChangeEntry,
    BranchSummaryEntry,
    CustomEntry,
    CustomMessageEntry,
    LabelEntry,
    SessionInfoEntry,
]

FileEntry = Union[SessionHeader, SessionEntry]


# ============================================================================
# Tree Node & Context
# ============================================================================


class SessionTreeNode(BaseModel):
    """
    树节点 - 用于 get_tree() 返回值。

    Attributes:
        entry: 对应的 SessionEntry
        children: 子节点列表
        label: 解析后的标签（如果有）
    """

    entry: SessionEntry
    children: list[SessionTreeNode] = Field(default_factory=list)
    label: str | None = None


class SessionContext(BaseModel):
    """
    解析后的会话上下文 - 用于 LLM 调用。

    Attributes:
        messages: 消息列表（已处理 compaction）
        model: 当前模型信息
        thinking_level: 当前思考级别
    """

    messages: list[Message] = Field(default_factory=list)
    model: dict[str, str] | None = None  # {provider, model_id}
    thinking_level: str = "off"  # "off" | "low" | "medium" | "high"


# ============================================================================
# Helper Functions
# ============================================================================


def generate_id(existing_ids: set[str] | None = None) -> str:
    """
    生成唯一的 8 位短 ID。

    Args:
        existing_ids: 已存在的 ID 集合（用于避免冲突）

    Returns:
        8 位十六进制字符串
    """
    existing_ids = existing_ids or set()
    for _ in range(100):
        short_id = uuid.uuid4().hex[:8]
        if short_id not in existing_ids:
            return short_id
    # 回退到完整 UUID
    return uuid.uuid4().hex[:8]


def parse_jsonl_entries(content: str) -> list[dict[str, Any]]:
    """
    解析 JSONL 内容为 Entry 列表。

    Args:
        content: JSONL 文件内容

    Returns:
        解析后的 dict 列表
    """
    entries: list[dict[str, Any]] = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def load_jsonl_file(file_path: Path) -> list[dict[str, Any]]:
    """
    加载 JSONL 文件。

    Args:
        file_path: 文件路径

    Returns:
        解析后的 Entry 列表
    """
    if not file_path.exists():
        return []
    content = file_path.read_text(encoding="utf-8")
    return parse_jsonl_entries(content)


def validate_session_header(entries: list[dict[str, Any]]) -> SessionHeader | None:
    """
    验证并提取 Session Header。

    Args:
        entries: Entry 列表

    Returns:
        SessionHeader 或 None（如果无效）
    """
    if not entries:
        return None
    first = entries[0]
    if first.get("type") != "session":
        return None
    try:
        return SessionHeader.model_validate(first)
    except Exception:
        return None


# ============================================================================
# TreeSessionManager
# ============================================================================


class TreeSessionManager:
    """
    树形会话管理器。

    核心特性：
        - 追加写入：Entry 只能添加，不能修改或删除
        - 树形结构：每个 Entry 有 id 和 parent_id
        - 叶子指针：跟踪当前位置，新 Entry 成为叶子节点的子节点
        - 分支支持：移动叶子指针即可创建分支

    用法：
        manager = TreeSessionManager.create("/path/to/project")

        # 追加消息
        entry_id = manager.append_message(Message.user("你好"))

        # 获取当前路径
        path = manager.get_branch()

        # 创建分支
        manager.branch(some_entry_id)
        manager.append_message(Message.user("换个话题"))

        # 获取完整树
        tree = manager.get_tree()
    """

    METADATA_DIR = "sessions/metadata"
    DATA_DIR = "sessions/data"

    def __init__(
        self,
        cwd: str,
        session_dir: str | Path,
        session_file: str | Path | None = None,
        persist: bool = True,
    ):
        """
        初始化会话管理器。

        Args:
            cwd: 工作目录
            session_dir: 会话存储目录
            session_file: 会话文件路径（用于加载现有会话）
            persist: 是否持久化到文件
        """
        self._cwd = cwd
        self._session_dir = Path(session_dir)
        self._persist = persist
        self._flushed = False

        # 内存结构
        self._file_entries: list[FileEntry] = []
        self._by_id: dict[str, SessionEntry] = {}
        self._labels_by_id: dict[str, str] = {}
        self._leaf_id: str | None = None
        self._session_file: Path | None = None

        # 确保目录存在
        if persist and session_dir:
            self._session_dir.mkdir(parents=True, exist_ok=True)

        if session_file:
            self._set_session_file(Path(session_file))
        else:
            self._new_session()

    # ========================================================================
    # 属性
    # ========================================================================

    @property
    def session_id(self) -> str:
        """获取会话 ID"""
        header = self._get_header()
        return header.id if header else ""

    @property
    def session_file(self) -> Path | None:
        """获取会话文件路径"""
        return self._session_file

    @property
    def cwd(self) -> str:
        """获取工作目录"""
        return self._cwd

    @property
    def leaf_id(self) -> str | None:
        """获取当前叶子 ID"""
        return self._leaf_id

    # ========================================================================
    # 会话管理
    # ========================================================================

    def _new_session(self, session_id: str | None = None) -> str:
        """创建新会话"""
        self._session_id = session_id or str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        header = SessionHeader(
            type="session",
            version=CURRENT_SESSION_VERSION,
            id=self._session_id,
            timestamp=timestamp,
            cwd=self._cwd,
        )

        self._file_entries = [header]
        self._by_id.clear()
        self._labels_by_id.clear()
        self._leaf_id = None
        self._flushed = False

        if self._persist:
            file_timestamp = timestamp.replace(":", "-").replace(".", "-")
            self._session_file = self._session_dir / f"{file_timestamp}_{self._session_id}.jsonl"

        return str(self._session_file) if self._session_file else ""

    def _set_session_file(self, file_path: Path) -> None:
        """设置并加载会话文件"""
        self._session_file = file_path

        if file_path.exists():
            entries = load_jsonl_file(file_path)

            if not entries:
                # 空文件，创建新会话
                self._new_session()
                self._session_file = file_path
                self._rewrite_file()
                self._flushed = True
                return

            header = validate_session_header(entries)
            if not header:
                # 无效文件，创建新会话
                self._new_session()
                self._session_file = file_path
                self._rewrite_file()
                self._flushed = True
                return

            self._file_entries = []
            for e in entries:
                if e.get("type") == "session":
                    self._file_entries.append(SessionHeader.model_validate(e))
                else:
                    self._file_entries.append(self._parse_entry(e))

            self._session_id = header.id
            self._build_index()
            self._flushed = True
        else:
            self._new_session()
            self._session_file = file_path

    def _parse_entry(self, data: dict[str, Any]) -> SessionEntry:
        """解析 Entry 数据"""
        entry_type = data.get("type")
        parsers = {
            "message": SessionMessageEntry,
            "compaction": CompactionEntry,
            "model_change": ModelChangeEntry,
            "branch_summary": BranchSummaryEntry,
            "custom": CustomEntry,
            "label": LabelEntry,
            "session_info": SessionInfoEntry,
        }
        parser = parsers.get(entry_type, SessionMessageEntry)
        return parser.model_validate(data)

    def _build_index(self) -> None:
        """构建内存索引"""
        self._by_id.clear()
        self._labels_by_id.clear()
        self._leaf_id = None

        for entry in self._file_entries:
            if isinstance(entry, SessionHeader):
                continue
            self._by_id[entry.id] = entry
            self._leaf_id = entry.id

            if isinstance(entry, LabelEntry):
                if entry.label:
                    self._labels_by_id[entry.target_id] = entry.label
                else:
                    self._labels_by_id.pop(entry.target_id, None)

    def _get_header(self) -> SessionHeader | None:
        """获取会话头部"""
        for entry in self._file_entries:
            if isinstance(entry, SessionHeader):
                return entry
        return None

    # ========================================================================
    # 文件 I/O
    # ========================================================================

    def _rewrite_file(self) -> None:
        """重写整个文件"""
        if not self._persist or not self._session_file:
            return
        lines = [json.dumps(e.model_dump(mode="json"), ensure_ascii=False) for e in self._file_entries]
        self._session_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _persist_entry(self, entry: SessionEntry) -> None:
        """持久化单个 Entry（追加）"""
        if not self._persist or not self._session_file:
            return

        # 检查是否有助手消息（首次持久化策略）
        has_assistant = any(
            isinstance(e, SessionMessageEntry) and e.message.get("role") == "assistant"
            for e in self._file_entries
        )

        if not has_assistant:
            self._flushed = False
            return

        if not self._flushed:
            # 首次写入所有 Entry
            for e in self._file_entries:
                line = json.dumps(e.model_dump(mode="json"), ensure_ascii=False)
                with open(self._session_file, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
            self._flushed = True
        else:
            # 追加单个 Entry
            line = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False)
            with open(self._session_file, "a", encoding="utf-8") as f:
                f.write(line + "\n")

    # ========================================================================
    # 树导航
    # ========================================================================

    def get_leaf_id(self) -> str | None:
        """获取当前叶子节点 ID"""
        return self._leaf_id

    def get_leaf_entry(self) -> SessionEntry | None:
        """获取当前叶子节点 Entry"""
        return self._leaf_id and self._by_id.get(self._leaf_id)

    def get_entry(self, entry_id: str) -> SessionEntry | None:
        """根据 ID 获取 Entry"""
        return self._by_id.get(entry_id)

    def get_children(self, parent_id: str) -> list[SessionEntry]:
        """
        获取指定节点的直接子节点。

        Args:
            parent_id: 父节点 ID

        Returns:
            子节点列表（按时间戳排序）
        """
        children = [e for e in self._by_id.values() if e.parent_id == parent_id]
        children.sort(key=lambda e: e.timestamp)
        return children

    def get_branch(self, from_id: str | None = None) -> list[SessionEntry]:
        """
        获取从根到指定节点的路径。

        Args:
            from_id: 起始节点 ID（None 表示当前叶子）

        Returns:
            路径上的 Entry 列表（从根到叶子）
        """
        path: list[SessionEntry] = []
        start_id = from_id or self._leaf_id
        current = start_id and self._by_id.get(start_id)

        while current:
            path.insert(0, current)
            current = current.parent_id and self._by_id.get(current.parent_id)

        return path

    def get_tree(self) -> list[SessionTreeNode]:
        """
        获取完整树结构。

        Returns:
            根节点列表（每个节点包含子节点）
        """
        entries = self.get_entries()
        node_map: dict[str, SessionTreeNode] = {}
        roots: list[SessionTreeNode] = []

        # 创建节点
        for entry in entries:
            label = self._labels_by_id.get(entry.id)
            node_map[entry.id] = SessionTreeNode(entry=entry, children=[], label=label)

        # 构建树
        for entry in entries:
            node = node_map[entry.id]
            if entry.parent_id is None:
                roots.append(node)
            else:
                parent = node_map.get(entry.parent_id)
                if parent:
                    parent.children.append(node)
                else:
                    roots.append(node)  # 孤儿节点

        # 递归排序子节点
        self._sort_tree_children(roots)

        return roots

    def _sort_tree_children(self, nodes: list[SessionTreeNode]) -> None:
        """按时间戳排序子节点"""
        stack = list(nodes)
        while stack:
            node = stack.pop()
            node.children.sort(key=lambda n: n.entry.timestamp)
            stack.extend(node.children)

    def get_entries(self) -> list[SessionEntry]:
        """获取所有 Entry（排除 Header）"""
        return [e for e in self._file_entries if not isinstance(e, SessionHeader)]

    def get_label(self, entry_id: str) -> str | None:
        """获取 Entry 的标签"""
        return self._labels_by_id.get(entry_id)

    # ========================================================================
    # 追加操作
    # ========================================================================

    def _generate_id(self) -> str:
        """生成唯一 ID"""
        return generate_id(set(self._by_id.keys()))

    def _append_entry(self, entry: SessionEntry) -> None:
        """内部：追加 Entry 并更新索引"""
        self._file_entries.append(entry)
        self._by_id[entry.id] = entry
        self._leaf_id = entry.id
        self._persist_entry(entry)

    def append_message(self, message: Message) -> str:
        """
        追加消息 Entry。

        Args:
            message: 消息对象

        Returns:
            Entry ID
        """
        entry = SessionMessageEntry(
            type="message",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            message=message.model_dump(mode="json"),
        )
        self._append_entry(entry)
        return entry.id

    def append_compaction(
        self,
        summary: str,
        first_kept_entry_id: str,
        tokens_before: int,
        tokens_after: int,
        details: dict[str, Any] | None = None,
        from_hook: bool = False,
    ) -> str:
        """
        追加压缩 Entry。

        Args:
            summary: LLM 生成的摘要
            first_kept_entry_id: 第一个保留的消息 Entry ID
            tokens_before: 压缩前的 token 数
            tokens_after: 压缩后的 token 数
            details: 扩展数据
            from_hook: 是否由 hook 生成

        Returns:
            Entry ID
        """
        entry = CompactionEntry(
            type="compaction",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            summary=summary,
            first_kept_entry_id=first_kept_entry_id,
            tokens_before=tokens_before,
            tokens_after=tokens_after,
            details=details,
            from_hook=from_hook,
        )
        self._append_entry(entry)
        return entry.id

    def append_model_change(self, provider: str, model_id: str) -> str:
        """
        追加模型切换 Entry。

        Args:
            provider: 提供商名称
            model_id: 模型 ID

        Returns:
            Entry ID
        """
        entry = ModelChangeEntry(
            type="model_change",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            provider=provider,
            model_id=model_id,
        )
        self._append_entry(entry)
        return entry.id

    def append_branch_summary(
        self,
        branch_from_id: str | None,
        summary: str,
        details: dict[str, Any] | None = None,
        from_hook: bool = False,
    ) -> str:
        """
        追加分支摘要 Entry。

        Args:
            branch_from_id: 分支起始点 ID（None 表示从根）
            summary: 被放弃路径的摘要
            details: 扩展数据
            from_hook: 是否由 hook 生成

        Returns:
            Entry ID
        """
        entry = BranchSummaryEntry(
            type="branch_summary",
            id=self._generate_id(),
            parent_id=branch_from_id,
            timestamp=datetime.now().isoformat(),
            from_id=branch_from_id or "root",
            summary=summary,
            details=details,
            from_hook=from_hook,
        )
        self._append_entry(entry)
        return entry.id

    def append_custom(self, custom_type: str, data: dict[str, Any] | None = None) -> str:
        """
        追加自定义 Entry。

        Args:
            custom_type: 扩展标识符
            data: 自定义数据

        Returns:
            Entry ID
        """
        entry = CustomEntry(
            type="custom",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            custom_type=custom_type,
            data=data,
        )
        self._append_entry(entry)
        return entry.id

    def append_label(self, target_id: str, label: str | None = None) -> str:
        """
        追加标签 Entry。

        Args:
            target_id: 被标记的 Entry ID
            label: 标签文本（None 表示清除）

        Returns:
            Entry ID
        """
        if target_id not in self._by_id:
            raise ValueError(f"Entry {target_id} not found")

        entry = LabelEntry(
            type="label",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            target_id=target_id,
            label=label,
        )
        self._append_entry(entry)

        # 更新内存索引
        if label:
            self._labels_by_id[target_id] = label
        else:
            self._labels_by_id.pop(target_id, None)

        return entry.id

    def append_thinking_level_change(self, thinking_level: str) -> str:
        """
        追加思考级别变更 Entry。

        Args:
            thinking_level: 思考级别（"off" | "low" | "medium" | "high"）

        Returns:
            Entry ID
        """
        entry = ThinkingLevelChangeEntry(
            type="thinking_level_change",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            thinking_level=thinking_level,
        )
        self._append_entry(entry)
        return entry.id

    def append_custom_message(
        self,
        custom_type: str,
        content: str | list[dict[str, Any]],
        display: bool = True,
        details: dict[str, Any] | None = None,
    ) -> str:
        """
        追加自定义消息 Entry（参与 LLM 上下文）。

        与 CustomEntry 不同，这个 Entry 会参与 LLM 上下文构建。
        content 会被转换为 user 消息注入到 buildSessionContext() 的结果中。

        Args:
            custom_type: 扩展标识符
            content: 消息内容（字符串或结构化内容）
            display: 是否在 UI 中显示
            details: 扩展元数据（不发送给 LLM）

        Returns:
            Entry ID
        """
        entry = CustomMessageEntry(
            type="custom_message",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            custom_type=custom_type,
            content=content,
            display=display,
            details=details,
        )
        self._append_entry(entry)
        return entry.id

    def append_session_info(self, name: str | None = None) -> str:
        """
        追加会话信息 Entry（设置会话显示名称）。

        Args:
            name: 会话名称（None 清除名称）

        Returns:
            Entry ID
        """
        entry = SessionInfoEntry(
            type="session_info",
            id=self._generate_id(),
            parent_id=self._leaf_id,
            timestamp=datetime.now().isoformat(),
            name=name,
        )
        self._append_entry(entry)
        return entry.id

    def get_session_name(self) -> str | None:
        """
        获取会话显示名称。

        从最新的 session_info Entry 中获取名称。

        Returns:
            会话名称或 None
        """
        entries = self.get_entries()
        for entry in reversed(entries):
            if isinstance(entry, SessionInfoEntry):
                return entry.name
        return None

    # ========================================================================
    # 分支操作
    # ========================================================================

    def branch(self, branch_from_id: str) -> None:
        """
        从指定节点创建分支。

        移动叶子指针到指定 Entry，下次 append 会成为该 Entry 的子节点。
        历史记录不会被修改或删除。

        Args:
            branch_from_id: 分支起始点 ID

        Raises:
            ValueError: Entry 不存在
        """
        if branch_from_id not in self._by_id:
            raise ValueError(f"Entry {branch_from_id} not found")
        self._leaf_id = branch_from_id

    def reset_leaf(self) -> None:
        """
        重置叶子指针到根之前。

        下次 append 会创建根节点（parent_id = None）。
        用于重新编辑第一条用户消息。
        """
        self._leaf_id = None

    def branch_with_summary(
        self,
        branch_from_id: str | None,
        summary: str,
        details: dict[str, Any] | None = None,
        from_hook: bool = False,
    ) -> str:
        """
        创建分支并附带摘要。

        与 branch() 相同，但同时追加一个 branch_summary Entry，
        记录被放弃路径的关键信息。

        Args:
            branch_from_id: 分支起始点 ID（None 表示从根）
            summary: 被放弃路径的摘要
            details: 扩展数据
            from_hook: 是否由 hook 生成

        Returns:
            branch_summary Entry ID
        """
        if branch_from_id and branch_from_id not in self._by_id:
            raise ValueError(f"Entry {branch_from_id} not found")

        self._leaf_id = branch_from_id
        return self.append_branch_summary(branch_from_id, summary, details, from_hook)

    # ========================================================================
    # 上下文构建
    # ========================================================================

    def build_session_context(self) -> SessionContext:
        """
        构建 LLM 上下文。

        从当前叶子节点遍历到根，处理 compaction 和 branch_summary。

        Returns:
            SessionContext 包含 messages 和 model 信息
        """
        entries = self.get_entries()
        return build_session_context(entries, self._leaf_id, self._by_id)

    # ========================================================================
    # 工厂方法
    # ========================================================================

    @classmethod
    def create(cls, cwd: str, session_dir: str | None = None) -> TreeSessionManager:
        """
        创建新会话。

        Args:
            cwd: 工作目录
            session_dir: 会话存储目录（None 使用默认）

        Returns:
            TreeSessionManager 实例
        """
        if session_dir is None:
            session_dir = Path.home() / ".poiclaw" / "sessions" / cls._encode_cwd(cwd)
        return cls(cwd, session_dir, None, True)

    @classmethod
    def open(cls, file_path: str | Path, session_dir: str | None = None) -> TreeSessionManager:
        """
        打开现有会话。

        Args:
            file_path: 会话文件路径
            session_dir: 会话存储目录（None 从文件路径推断）

        Returns:
            TreeSessionManager 实例
        """
        file_path = Path(file_path)

        # 从 Header 读取 cwd
        entries = load_jsonl_file(file_path)
        header = validate_session_header(entries)
        cwd = header.cwd if header else str(Path.cwd())

        if session_dir is None:
            session_dir = file_path.parent

        return cls(cwd, session_dir, file_path, True)

    @classmethod
    def in_memory(cls, cwd: str = "") -> TreeSessionManager:
        """
        创建内存会话（不持久化）。

        Args:
            cwd: 工作目录

        Returns:
            TreeSessionManager 实例
        """
        return cls(cwd, "", None, False)

    @classmethod
    def continue_recent(cls, cwd: str, session_dir: str | None = None) -> TreeSessionManager:
        """
        继续最近的会话，如果没有则创建新会话。

        Args:
            cwd: 工作目录
            session_dir: 会话存储目录（None 使用默认）

        Returns:
            TreeSessionManager 实例
        """
        if session_dir is None:
            session_dir = Path.home() / ".poiclaw" / "sessions" / cls._encode_cwd(cwd)

        session_dir_path = Path(session_dir)
        most_recent = cls._find_most_recent_session(session_dir_path)

        if most_recent:
            return cls.open(most_recent, str(session_dir_path))
        else:
            return cls.create(cwd, str(session_dir_path))

    @classmethod
    def fork_from(
        cls,
        source_path: str | Path,
        target_cwd: str,
        target_session_dir: str | None = None,
    ) -> TreeSessionManager:
        """
        从另一个项目目录 fork 会话到当前项目。

        创建新会话，包含源会话的完整历史，设置 parent_session 引用。

        Args:
            source_path: 源会话文件路径
            target_cwd: 目标工作目录
            target_session_dir: 目标会话目录（None 使用默认）

        Returns:
            新的 TreeSessionManager 实例
        """
        source_path = Path(source_path)

        # 加载源会话
        source_entries = load_jsonl_file(source_path)
        source_header = validate_session_header(source_entries)

        if not source_header:
            raise ValueError(f"Invalid session file: {source_path}")

        # 创建目标会话
        if target_session_dir is None:
            target_session_dir = Path.home() / ".poiclaw" / "sessions" / cls._encode_cwd(target_cwd)

        target_session_dir_path = Path(target_session_dir)
        target_session_dir_path.mkdir(parents=True, exist_ok=True)

        # 创建新会话
        manager = cls.create(target_cwd, str(target_session_dir_path))

        # 设置 parent_session 引用
        header = manager._get_header()
        if header:
            header.parent_session = str(source_path)

        # 复制所有 Entry（保留 ID 和 parent_id 关系）
        manager._file_entries = [header] if header else []
        manager._by_id.clear()

        for entry in source_entries:
            if entry.get("type") == "session":
                continue  # 跳过源 header
            parsed = manager._parse_entry(entry)
            manager._file_entries.append(parsed)
            if hasattr(parsed, "id"):
                manager._by_id[parsed.id] = parsed
                manager._leaf_id = parsed.id

        # 重写文件
        manager._rewrite_file()
        manager._flushed = True

        return manager

    def create_branched_session(self, leaf_id: str) -> str | None:
        """
        从指定叶子节点创建新会话文件。

        创建包含从根到指定叶子节点路径的新会话。
        用于从分支会话中提取单条对话路径。

        Args:
            leaf_id: 叶子节点 ID

        Returns:
            新会话文件路径，如果不持久化则返回 None

        Raises:
            ValueError: Entry 不存在
        """
        if leaf_id not in self._by_id:
            raise ValueError(f"Entry {leaf_id} not found")

        if not self._persist:
            return None

        # 获取路径
        path = self.get_branch(leaf_id)
        if not path:
            return None

        # 过滤掉 LabelEntry（会重新创建）
        path_without_labels = [e for e in path if not isinstance(e, LabelEntry)]

        # 创建新会话
        new_session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        file_timestamp = timestamp.replace(":", "-").replace(".", "-")
        new_session_file = self._session_dir / f"{file_timestamp}_{new_session_id}.jsonl"

        # 创建新 Header
        new_header = SessionHeader(
            type="session",
            version=CURRENT_SESSION_VERSION,
            id=new_session_id,
            timestamp=timestamp,
            cwd=self._cwd,
            parent_session=str(self._session_file) if self._session_file else None,
        )

        # 收集路径中的标签
        path_entry_ids = {e.id for e in path_without_labels}
        labels_to_write: list[tuple[str, str]] = []
        for target_id, label in self._labels_by_id.items():
            if target_id in path_entry_ids:
                labels_to_write.append((target_id, label))

        # 构建 LabelEntry
        new_entries: list[FileEntry] = [new_header, *path_without_labels]
        last_entry_id = path_without_labels[-1].id if path_without_labels else None

        existing_ids = {e.id for e in path_without_labels}
        for target_id, label in labels_to_write:
            label_entry = LabelEntry(
                type="label",
                id=generate_id(existing_ids),
                parent_id=last_entry_id,
                timestamp=datetime.now().isoformat(),
                target_id=target_id,
                label=label,
            )
            new_entries.append(label_entry)
            existing_ids.add(label_entry.id)
            last_entry_id = label_entry.id

        # 写入文件
        lines = [json.dumps(e.model_dump(mode="json"), ensure_ascii=False) for e in new_entries]
        new_session_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        return str(new_session_file)

    @staticmethod
    def _find_most_recent_session(session_dir: Path) -> Path | None:
        """
        查找目录中最近的会话文件。

        Args:
            session_dir: 会话目录

        Returns:
            最近的会话文件路径，没有则返回 None
        """
        if not session_dir.exists():
            return None

        try:
            jsonl_files = list(session_dir.glob("*.jsonl"))
            if not jsonl_files:
                return None

            # 过滤有效会话文件并按修改时间排序
            valid_files = []
            for f in jsonl_files:
                if TreeSessionManager._is_valid_session_file(f):
                    valid_files.append((f, f.stat().st_mtime))

            if not valid_files:
                return None

            valid_files.sort(key=lambda x: x[1], reverse=True)
            return valid_files[0][0]

        except Exception:
            return None

    @staticmethod
    def _is_valid_session_file(file_path: Path) -> bool:
        """
        验证是否为有效的会话文件。

        Args:
            file_path: 文件路径

        Returns:
            是否有效
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
                if not first_line:
                    return False
                header = json.loads(first_line)
                return header.get("type") == "session" and isinstance(header.get("id"), str)
        except Exception:
            return False

    @staticmethod
    def list_sessions(session_dir: str | Path) -> list[dict[str, Any]]:
        """
        列出目录中的所有会话。

        Args:
            session_dir: 会话目录

        Returns:
            会话信息列表（包含 id, timestamp, cwd, message_count）
        """
        session_dir = Path(session_dir)
        if not session_dir.exists():
            return []

        sessions = []
        for jsonl_file in session_dir.glob("*.jsonl"):
            try:
                entries = load_jsonl_file(jsonl_file)
                header = validate_session_header(entries)
                if not header:
                    continue

                # 统计消息数量
                message_count = sum(1 for e in entries if e.get("type") == "message")

                sessions.append({
                    "id": header.id,
                    "timestamp": header.timestamp,
                    "cwd": header.cwd,
                    "message_count": message_count,
                    "file_path": str(jsonl_file),
                })
            except Exception:
                continue

        # 按时间戳降序排序
        sessions.sort(key=lambda x: x["timestamp"], reverse=True)
        return sessions

    @staticmethod
    def _encode_cwd(cwd: str) -> str:
        """编码 cwd 为安全目录名"""
        safe_path = cwd.replace("/", "-").replace("\\", "-").replace(":", "-")
        safe_path = safe_path.lstrip("-")
        return f"--{safe_path}--"


# ============================================================================
# 上下文构建函数
# ============================================================================


def build_session_context(
    entries: list[SessionEntry],
    leaf_id: str | None,
    by_id: dict[str, SessionEntry],
) -> SessionContext:
    """
    构建 LLM 上下文。

    从叶子节点遍历到根，处理 compaction 和 branch_summary。

    Args:
        entries: 所有 Entry
        leaf_id: 叶子节点 ID
        by_id: ID → Entry 映射

    Returns:
        SessionContext
    """
    # 找到叶子节点
    leaf: SessionEntry | None = None
    if leaf_id is None:
        # 显式 None - 返回空上下文
        return SessionContext(messages=[], model=None)
    if leaf_id:
        leaf = by_id.get(leaf_id)
    if not leaf and entries:
        leaf = entries[-1]

    if not leaf:
        return SessionContext(messages=[], model=None)

    # 从叶子遍历到根
    path: list[SessionEntry] = []
    current: SessionEntry | None = leaf
    while current:
        path.insert(0, current)
        current = current.parent_id and by_id.get(current.parent_id)

    # 提取模型信息和最新 compaction
    model: dict[str, str] | None = None
    compaction: CompactionEntry | None = None

    for entry in path:
        if isinstance(entry, ModelChangeEntry):
            model = {"provider": entry.provider, "model_id": entry.model_id}
        elif isinstance(entry, CompactionEntry):
            compaction = entry

    # 构建消息列表
    messages: list[Message] = []

    if compaction:
        # 发送摘要
        summary_content = f"""[上下文摘要]

{compaction.summary}

---
*以上是对之前对话的摘要，保留关键信息以便继续工作。*
"""
        messages.append(Message.system(summary_content))

        # 找到 compaction 在 path 中的索引
        compaction_idx = -1
        for i, e in enumerate(path):
            if isinstance(e, CompactionEntry) and e.id == compaction.id:
                compaction_idx = i
                break

        # 发送保留的消息（从 first_kept_entry_id 开始）
        found_first_kept = False
        for i in range(compaction_idx):
            entry = path[i]
            if entry.id == compaction.first_kept_entry_id:
                found_first_kept = True
            if found_first_kept and isinstance(entry, SessionMessageEntry):
                try:
                    messages.append(Message.model_validate(entry.message))
                except Exception:
                    pass

        # 发送 compaction 之后的消息
        for i in range(compaction_idx + 1, len(path)):
            entry = path[i]
            if isinstance(entry, SessionMessageEntry):
                try:
                    messages.append(Message.model_validate(entry.message))
                except Exception:
                    pass
            elif isinstance(entry, BranchSummaryEntry) and entry.summary:
                summary_msg = f"[分支摘要]\n\n{entry.summary}"
                messages.append(Message.system(summary_msg))
            elif isinstance(entry, CustomMessageEntry):
                # 注入自定义消息到上下文
                content = entry.content
                if isinstance(content, str):
                    messages.append(Message.user(f"[{entry.custom_type}]\n\n{content}"))
                elif isinstance(content, list):
                    # 结构化内容 - 转换为文本
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "image":
                                text_parts.append("[图片]")
                    messages.append(Message.user(f"[{entry.custom_type}]\n\n" + "\n".join(text_parts)))
    else:
        # 没有 compaction - 发送所有消息
        for entry in path:
            if isinstance(entry, SessionMessageEntry):
                try:
                    messages.append(Message.model_validate(entry.message))
                except Exception:
                    pass
            elif isinstance(entry, BranchSummaryEntry) and entry.summary:
                summary_msg = f"[分支摘要]\n\n{entry.summary}"
                messages.append(Message.system(summary_msg))
            elif isinstance(entry, CustomMessageEntry):
                # 注入自定义消息到上下文
                content = entry.content
                if isinstance(content, str):
                    messages.append(Message.user(f"[{entry.custom_type}]\n\n{content}"))
                elif isinstance(content, list):
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif block.get("type") == "image":
                                text_parts.append("[图片]")
                    messages.append(Message.user(f"[{entry.custom_type}]\n\n" + "\n".join(text_parts)))

    return SessionContext(messages=messages, model=model)
