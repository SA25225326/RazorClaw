"""
会话持久化管理 - 分离存储方案（支持 v1/v2 格式）

存储结构：
    .poiclaw/
    └── sessions/
        ├── metadata/
        │   └── {uuid}.json     # SessionMetadata（轻量，用于列表展示）
        └── data/
            ├── {uuid}.json     # SessionData（v1 格式，完整消息列表）
            └── {timestamp}_{uuid}.jsonl  # SessionData（v2 格式，树形结构）

核心特性：
    - 分离存储：metadata 用于快速列表展示，data 存储完整数据
    - 双格式支持：v1（扁平 JSON）和 v2（树形 JSONL）
    - 自动迁移：首次加载旧格式时自动迁移到新格式
    - 标题保护：title=None 时保留原标题
    - 内存保护：Agent 只在 messages 为空时加载历史
    - 异步 I/O：使用 asyncio.to_thread 包装文件操作
    - 容错机制：失败打印警告但不中断主程序

v2 格式特性（树形结构）：
    - 每条 Entry 有 id 和 parentId
    - 支持分支/回溯（类似 Git）
    - JSONL 格式存储（每行一个 Entry）
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from poiclaw.llm import Message

# v2 格式支持
from poiclaw.core.session_tree import (
    SessionEntry,
    SessionHeader,
    SessionMessageEntry,
    CompactionEntry as CompactionEntryV2,
    build_session_context,
    load_jsonl_file,
    parse_jsonl_entries,
)
from poiclaw.core.session_migration import (
    detect_format,
    migrate_v1_to_v2_async,
    is_migration_needed,
)


# ============================================================================
# 数据模型
# ============================================================================


class UsageStats(BaseModel):
    """Token 使用统计"""

    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0
    total_tokens: int = 0

    def merge(self, other: UsageStats) -> UsageStats:
        """合并两个统计（用于累积）"""
        return UsageStats(
            input=self.input + other.input,
            output=self.output + other.output,
            cache_read=self.cache_read + other.cache_read,
            cache_write=self.cache_write + other.cache_write,
            total_tokens=self.total_tokens + other.total_tokens,
        )

    @classmethod
    def zero(cls) -> UsageStats:
        """创建零值统计"""
        return cls()


# ============================================================================
# Compaction 数据模型
# ============================================================================


class CompactionEntry(BaseModel):
    """
    压缩条目，存储在 SessionData.compactions 中。

    Attributes:
        id: 唯一标识符（UUID）
        timestamp: 压缩发生时间（ISO 8601）
        summary: LLM 生成的结构化摘要
        first_kept_msg_idx: 第一个保留的消息在原始列表中的索引
        tokens_before: 压缩前的 token 估算值
        tokens_after: 压缩后的 token 估算值（摘要 + 保留消息）
    """

    id: str
    timestamp: str
    summary: str
    first_kept_msg_idx: int
    tokens_before: int
    tokens_after: int


class CompactionSettings(BaseModel):
    """
    压缩配置。

    Attributes:
        enabled: 是否启用自动压缩
        context_window: 模型上下文窗口大小
        reserve_tokens: 保留的 token 缓冲区（用于 LLM 响应）
        keep_recent_tokens: 保留最近 N tokens 的消息（不被压缩）
    """

    enabled: bool = True
    context_window: int = 128000
    reserve_tokens: int = 16384
    keep_recent_tokens: int = 20000

    @property
    def threshold(self) -> int:
        """压缩触发阈值：context_window - reserve_tokens"""
        return self.context_window - self.reserve_tokens


class SessionMetadata(BaseModel):
    """
    会话元数据（轻量，用于列表展示）。

    存储路径: .poiclaw/sessions/metadata/{id}.json
    """

    id: str  # UUID
    title: str  # 会话标题
    created_at: str  # ISO 8601
    last_modified: str  # ISO 8601
    message_count: int = 0
    usage: UsageStats = Field(default_factory=UsageStats)
    preview: str = ""  # 前 2KB 预览


class SessionData(BaseModel):
    """
    会话完整数据（包含消息列表）。

    存储路径: .poiclaw/sessions/data/{id}.json
    """

    id: str  # UUID
    title: str
    created_at: str  # ISO 8601
    last_modified: str  # ISO 8601
    messages: list[dict]  # Message 的序列化形式
    usage: UsageStats = Field(default_factory=UsageStats)
    compactions: list[CompactionEntry] = Field(default_factory=list)  # 压缩历史


# ============================================================================
# FileSessionManager
# ============================================================================


class FileSessionManager:
    """
    基于文件系统的会话管理器（分离存储方案）。

    存储结构：
        .poiclaw/sessions/metadata/{id}.json  - 元数据（轻量）
        .poiclaw/sessions/data/{id}.json      - 完整数据

    用法：
        manager = FileSessionManager()

        # 创建新会话
        session_id = manager.generate_id()

        # 保存会话
        await manager.save_session(session_id, messages, title="我的会话", usage=stats)

        # 加载会话
        messages = await manager.load_session(session_id)

        # 列出所有会话
        sessions = await manager.list_sessions()

        # 删除会话
        await manager.delete_session(session_id)
    """

    METADATA_DIR = "sessions/metadata"
    DATA_DIR = "sessions/data"
    PREVIEW_MAX_LENGTH = 2000

    def __init__(self, base_path: str | Path = ".poiclaw"):
        """
        初始化会话管理器。

        Args:
            base_path: 基础存储路径，默认为 .poiclaw
        """
        self.base_path = Path(base_path)
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """确保目录存在"""
        (self.base_path / self.METADATA_DIR).mkdir(parents=True, exist_ok=True)
        (self.base_path / self.DATA_DIR).mkdir(parents=True, exist_ok=True)

    # ========================================================================
    # 路径辅助
    # ========================================================================

    def _get_metadata_path(self, session_id: str) -> Path:
        """获取元数据文件路径"""
        return self.base_path / self.METADATA_DIR / f"{session_id}.json"

    def _get_data_path(self, session_id: str) -> Path:
        """获取数据文件路径"""
        return self.base_path / self.DATA_DIR / f"{session_id}.json"

    # ========================================================================
    # ID 生成
    # ========================================================================

    @staticmethod
    def generate_id() -> str:
        """生成 UUID"""
        return str(uuid.uuid4())

    # ========================================================================
    # 预览和标题生成
    # ========================================================================

    def _generate_preview(self, messages: list[Message]) -> str:
        """
        生成预览（仅截取 user/assistant 前 2000 字符）。

        Args:
            messages: 消息列表

        Returns:
            预览文本
        """
        preview_parts: list[str] = []

        for msg in messages:
            if msg.role.value in ("user", "assistant"):
                content = msg.content or ""
                if content:
                    # 添加角色标识
                    role_label = "[用户]" if msg.role.value == "user" else "[助手]"
                    preview_parts.append(f"{role_label} {content}")

        preview = "\n".join(preview_parts)

        # 截断到最大长度
        if len(preview) > self.PREVIEW_MAX_LENGTH:
            preview = preview[: self.PREVIEW_MAX_LENGTH - 3] + "..."

        return preview

    def _generate_title(self, messages: list[Message]) -> str:
        """
        从首条用户消息生成标题。

        Args:
            messages: 消息列表

        Returns:
            生成的标题
        """
        for msg in messages:
            if msg.role.value == "user" and msg.content:
                # 取第一行或前 50 个字符
                first_line = msg.content.split("\n")[0].strip()
                if len(first_line) > 50:
                    return first_line[:47] + "..."
                return first_line or "新会话"

        return "新会话"

    # ========================================================================
    # 文件 I/O（异步包装）
    # ========================================================================

    async def _read_json_async(self, path: Path) -> dict | None:
        """
        异步读取 JSON 文件。

        Args:
            path: 文件路径

        Returns:
            解析后的字典，文件不存在返回 None
        """
        try:

            def _read() -> str | None:
                if not path.exists():
                    return None
                return path.read_text(encoding="utf-8")

            content = await asyncio.to_thread(_read)
            if content is None:
                return None
            return json.loads(content)

        except json.JSONDecodeError as e:
            print(f"[SessionManager] 警告：JSON 解析失败 {path}: {e}")
            return None
        except Exception as e:
            print(f"[SessionManager] 警告：读取文件失败 {path}: {e}")
            return None

    async def _write_json_async(self, path: Path, data: dict) -> bool:
        """
        异步写入 JSON 文件。

        Args:
            path: 文件路径
            data: 要写入的数据

        Returns:
            是否成功
        """
        try:

            def _write() -> None:
                content = json.dumps(data, ensure_ascii=False, indent=2)
                path.write_text(content, encoding="utf-8")

            await asyncio.to_thread(_write)
            return True

        except Exception as e:
            print(f"[SessionManager] 警告：写入文件失败 {path}: {e}")
            return False

    async def _delete_file_async(self, path: Path) -> bool:
        """
        异步删除文件。

        Args:
            path: 文件路径

        Returns:
            是否成功
        """
        try:

            def _delete() -> None:
                if path.exists():
                    path.unlink()

            await asyncio.to_thread(_delete)
            return True

        except Exception as e:
            print(f"[SessionManager] 警告：删除文件失败 {path}: {e}")
            return False

    # ========================================================================
    # 核心接口
    # ========================================================================

    async def save_session(
        self,
        session_id: str,
        messages: list[Message],
        title: str | None = None,
        usage: UsageStats | None = None,
        compactions: list[CompactionEntry] | None = None,
    ) -> bool:
        """
        保存会话（同时保存 metadata 和 data）。

        标题保护逻辑：
            - 如果 title 为 None，读取现有 metadata 保留原标题
            - 如果是新会话且无标题，从首条用户消息生成

        压缩保护逻辑：
            - 如果 compactions 为 None，读取现有 data 保留原压缩历史
            - 如果 compactions 提供则更新

        Args:
            session_id: 会话 ID
            messages: 消息列表
            title: 会话标题（None 时保留原标题）
            usage: Token 使用统计
            compactions: 压缩历史（None 时保留原压缩历史）

        Returns:
            是否成功
        """
        now = datetime.now().isoformat()
        usage = usage or UsageStats.zero()

        # 序列化消息
        messages_data = [msg.model_dump(mode="json") for msg in messages]

        # 标题保护：如果 title 为 None，尝试读取现有标题
        if title is None:
            existing_metadata = await self.get_metadata(session_id)
            if existing_metadata:
                title = existing_metadata.title
            else:
                title = self._generate_title(messages)
        else:
            title = title.strip() or self._generate_title(messages)

        # 生成预览
        preview = self._generate_preview(messages)

        # 检查是否是新会话（通过检查现有 metadata）
        existing_metadata = await self.get_metadata(session_id)
        if existing_metadata:
            created_at = existing_metadata.created_at
            # 合并 usage
            usage = existing_metadata.usage.merge(usage)
        else:
            created_at = now

        # 压缩保护：如果 compactions 为 None，读取现有压缩历史
        if compactions is None:
            existing_data = await self._read_json_async(self._get_data_path(session_id))
            if existing_data and "compactions" in existing_data:
                try:
                    compactions = [
                        CompactionEntry.model_validate(c) for c in existing_data["compactions"]
                    ]
                except Exception:
                    compactions = []
            else:
                compactions = []

        # 构建 metadata
        metadata = SessionMetadata(
            id=session_id,
            title=title,
            created_at=created_at,
            last_modified=now,
            message_count=len(messages),
            usage=usage,
            preview=preview,
        )

        # 构建 data
        data = SessionData(
            id=session_id,
            title=title,
            created_at=created_at,
            last_modified=now,
            messages=messages_data,
            usage=usage,
            compactions=compactions,
        )

        # 并行写入
        metadata_task = self._write_json_async(
            self._get_metadata_path(session_id), metadata.model_dump(mode="json")
        )
        data_task = self._write_json_async(
            self._get_data_path(session_id), data.model_dump(mode="json")
        )

        results = await asyncio.gather(metadata_task, data_task)
        return all(results)

    async def load_session(self, session_id: str, auto_migrate: bool = True) -> list[Message] | None:
        """
        加载完整消息列表（支持 v1/v2 双格式）。

        自动检测格式：
            - v2: {timestamp}_{uuid}.jsonl 文件
            - v1: {uuid}.json 文件

        如果 auto_migrate=True，首次加载 v1 格式时会自动迁移到 v2。

        Args:
            session_id: 会话 ID
            auto_migrate: 是否自动迁移旧格式

        Returns:
            消息列表，不存在返回 None
        """
        messages, fmt = await self.load_session_with_format(session_id, auto_migrate)
        return messages

    async def get_metadata(self, session_id: str) -> SessionMetadata | None:
        """
        获取单个元数据。

        Args:
            session_id: 会话 ID

        Returns:
            元数据，不存在返回 None
        """
        metadata_dict = await self._read_json_async(self._get_metadata_path(session_id))
        if metadata_dict is None:
            return None

        try:
            return SessionMetadata.model_validate(metadata_dict)
        except Exception as e:
            print(f"[SessionManager] 警告：元数据解析失败: {e}")
            return None

    async def list_sessions(self) -> list[SessionMetadata]:
        """
        列出所有元数据（按 last_modified 降序）。

        Returns:
            元数据列表
        """
        metadata_dir = self.base_path / self.METADATA_DIR

        if not metadata_dir.exists():
            return []

        # 收集所有 metadata 文件
        metadata_files = list(metadata_dir.glob("*.json"))

        # 并行加载
        async def load_metadata(path: Path) -> SessionMetadata | None:
            data = await self._read_json_async(path)
            if data is None:
                return None
            try:
                return SessionMetadata.model_validate(data)
            except Exception:
                return None

        tasks = [load_metadata(path) for path in metadata_files]
        results = await asyncio.gather(*tasks)

        # 过滤 None 并按 last_modified 降序排序
        sessions = [r for r in results if r is not None]
        sessions.sort(key=lambda s: s.last_modified, reverse=True)

        return sessions

    async def delete_session(self, session_id: str) -> bool:
        """
        删除对应的 metadata 和 data。

        Args:
            session_id: 会话 ID

        Returns:
            是否成功
        """
        metadata_task = self._delete_file_async(self._get_metadata_path(session_id))
        data_task = self._delete_file_async(self._get_data_path(session_id))

        results = await asyncio.gather(metadata_task, data_task)
        return all(results)

    async def update_title(self, session_id: str, title: str) -> bool:
        """
        更新标题。

        Args:
            session_id: 会话 ID
            title: 新标题

        Returns:
            是否成功
        """
        # 读取现有数据
        metadata = await self.get_metadata(session_id)
        if metadata is None:
            print(f"[SessionManager] 警告：会话不存在 {session_id}")
            return False

        data_dict = await self._read_json_async(self._get_data_path(session_id))
        if data_dict is None:
            print(f"[SessionManager] 警告：会话数据不存在 {session_id}")
            return False

        # 更新标题
        new_title = title.strip() or metadata.title
        now = datetime.now().isoformat()

        # 更新 metadata
        metadata.title = new_title
        metadata.last_modified = now

        # 更新 data
        try:
            data = SessionData.model_validate(data_dict)
            data.title = new_title
            data.last_modified = now
        except Exception as e:
            print(f"[SessionManager] 警告：会话数据解析失败: {e}")
            return False

        # 并行写入
        metadata_task = self._write_json_async(
            self._get_metadata_path(session_id), metadata.model_dump(mode="json")
        )
        data_task = self._write_json_async(
            self._get_data_path(session_id), data.model_dump(mode="json")
        )

        results = await asyncio.gather(metadata_task, data_task)
        return all(results)

    # ========================================================================
    # 便捷方法
    # ========================================================================

    async def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在。

        Args:
            session_id: 会话 ID

        Returns:
            是否存在
        """
        return self._get_metadata_path(session_id).exists()

    async def get_usage_stats(self, session_id: str) -> UsageStats | None:
        """
        获取会话的 Token 使用统计。

        Args:
            session_id: 会话 ID

        Returns:
            使用统计，不存在返回 None
        """
        metadata = await self.get_metadata(session_id)
        return metadata.usage if metadata else None

    async def get_compactions(self, session_id: str) -> list[CompactionEntry]:
        """
        获取会话的压缩历史。

        Args:
            session_id: 会话 ID

        Returns:
            压缩条目列表，不存在返回空列表
        """
        data_dict = await self._read_json_async(self._get_data_path(session_id))
        if data_dict is None or "compactions" not in data_dict:
            return []

        try:
            return [CompactionEntry.model_validate(c) for c in data_dict["compactions"]]
        except Exception:
            return []

    async def add_compaction(self, session_id: str, compaction: CompactionEntry) -> bool:
        """
        添加压缩条目到会话。

        Args:
            session_id: 会话 ID
            compaction: 压缩条目

        Returns:
            是否成功
        """
        # 读取现有压缩历史
        compactions = await self.get_compactions(session_id)
        compactions.append(compaction)

        # 读取现有 data 并更新
        data_dict = await self._read_json_async(self._get_data_path(session_id))
        if data_dict is None:
            print(f"[SessionManager] 警告：会话数据不存在 {session_id}")
            return False

        data_dict["compactions"] = [c.model_dump(mode="json") for c in compactions]
        data_dict["last_modified"] = datetime.now().isoformat()

        return await self._write_json_async(self._get_data_path(session_id), data_dict)

    # ========================================================================
    # v2 格式支持（JSONL 树形结构）
    # ========================================================================

    def _find_jsonl_file(self, session_id: str) -> Path | None:
        """
        查找会话对应的 JSONL 文件。

        Args:
            session_id: 会话 ID

        Returns:
            JSONL 文件路径，不存在返回 None
        """
        data_dir = self.base_path / self.DATA_DIR
        if not data_dir.exists():
            return None

        # 查找匹配的 JSONL 文件
        for jsonl_file in data_dir.glob(f"*_{session_id}.jsonl"):
            return jsonl_file

        return None

    async def _load_session_v2(self, jsonl_path: Path) -> list[Message] | None:
        """
        加载 v2 格式会话（JSONL 树形结构）。

        Args:
            jsonl_path: JSONL 文件路径

        Returns:
            消息列表，失败返回 None
        """
        try:

            def _load() -> list[Message] | None:
                entries = load_jsonl_file(jsonl_path)
                if not entries:
                    return None

                # 验证 Header
                header = entries[0] if entries else None
                if not header or header.get("type") != "session":
                    return None

                # 构建 Entry 列表和索引
                session_entries: list[SessionEntry] = []
                by_id: dict[str, SessionEntry] = {}

                for e in entries[1:]:  # 跳过 header
                    try:
                        entry_type = e.get("type")
                        if entry_type == "message":
                            entry = SessionMessageEntry.model_validate(e)
                        elif entry_type == "compaction":
                            entry = CompactionEntryV2.model_validate(e)
                        else:
                            continue  # 跳过其他类型
                        session_entries.append(entry)
                        by_id[entry.id] = entry
                    except Exception:
                        continue

                # 找到叶子节点（最后一个 entry）
                leaf_id = session_entries[-1].id if session_entries else None

                # 构建上下文
                context = build_session_context(session_entries, leaf_id, by_id)
                return context.messages

            return await asyncio.to_thread(_load)

        except Exception as e:
            print(f"[SessionManager] 警告：加载 v2 格式失败 {jsonl_path}: {e}")
            return None

    async def _detect_and_load(self, session_id: str) -> tuple[list[Message] | None, str]:
        """
        检测格式并加载会话。

        Args:
            session_id: 会话 ID

        Returns:
            (消息列表, 格式字符串) - 格式为 "v1" 或 "v2"
        """
        # 先尝试 v2 格式
        jsonl_path = self._find_jsonl_file(session_id)
        if jsonl_path:
            messages = await self._load_session_v2(jsonl_path)
            if messages is not None:
                return messages, "v2"

        # 回退到 v1 格式
        v1_path = self._get_data_path(session_id)
        if v1_path.exists():
            # 检测格式
            fmt = await asyncio.to_thread(detect_format, v1_path)
            if fmt == "v2_tree":
                # 可能是误命名，尝试作为 JSONL 加载
                messages = await self._load_session_v2(v1_path)
                if messages is not None:
                    return messages, "v2"
            elif fmt == "v1_flat":
                messages = await self._load_session_v1(v1_path)
                if messages is not None:
                    return messages, "v1"

        return None, ""

    async def _load_session_v1(self, json_path: Path) -> list[Message] | None:
        """
        加载 v1 格式会话（原有逻辑）。

        Args:
            json_path: JSON 文件路径

        Returns:
            消息列表，失败返回 None
        """
        data_dict = await self._read_json_async(json_path)
        if data_dict is None:
            return None

        try:
            data = SessionData.model_validate(data_dict)
            messages: list[Message] = []
            for msg_dict in data.messages:
                try:
                    messages.append(Message.model_validate(msg_dict))
                except Exception as e:
                    print(f"[SessionManager] 警告：消息解析失败: {e}")
                    continue
            return messages
        except Exception as e:
            print(f"[SessionManager] 警告：会话数据解析失败: {e}")
            return None

    async def load_session_with_format(
        self, session_id: str, auto_migrate: bool = True
    ) -> tuple[list[Message] | None, str]:
        """
        加载会话并返回格式信息。

        Args:
            session_id: 会话 ID
            auto_migrate: 是否自动迁移旧格式

        Returns:
            (消息列表, 格式字符串) - 格式为 "v1" 或 "v2"
        """
        messages, fmt = await self._detect_and_load(session_id)

        # 自动迁移
        if auto_migrate and fmt == "v1" and messages is not None:
            v1_path = self._get_data_path(session_id)
            if v1_path.exists():
                try:
                    result = await migrate_v1_to_v2_async(v1_path, backup=True)
                    if result.success:
                        print(f"[SessionManager] 已迁移会话 {session_id} 到 v2 格式")
                        # 删除旧的 metadata 文件中的 data 引用
                        # metadata 仍然有效，用于列表展示
                except Exception as e:
                    print(f"[SessionManager] 警告：迁移失败: {e}")

        return messages, fmt

    # ========================================================================
    # 树形操作 API（仅 v2 格式支持）
    # ========================================================================

    async def get_tree(self, session_id: str) -> dict | None:
        """
        获取会话树结构（仅 v2 格式）。

        Args:
            session_id: 会话 ID

        Returns:
            树结构字典，不支持返回 None
        """
        from poiclaw.core.session_tree import TreeSessionManager

        jsonl_path = self._find_jsonl_file(session_id)
        if not jsonl_path:
            return None

        try:

            def _get_tree():
                manager = TreeSessionManager.open(jsonl_path)
                tree = manager.get_tree()
                # 序列化树结构
                return {
                    "session_id": session_id,
                    "leaf_id": manager.leaf_id,
                    "roots": [self._serialize_tree_node(n) for n in tree],
                }

            return await asyncio.to_thread(_get_tree)

        except Exception as e:
            print(f"[SessionManager] 警告：获取树结构失败: {e}")
            return None

    def _serialize_tree_node(self, node) -> dict:
        """序列化树节点"""
        return {
            "entry": node.entry.model_dump(mode="json"),
            "label": node.label,
            "children": [self._serialize_tree_node(c) for c in node.children],
        }

    async def get_branch(
        self, session_id: str, entry_id: str | None = None
    ) -> list[dict] | None:
        """
        获取从根到指定节点的路径（仅 v2 格式）。

        Args:
            session_id: 会话 ID
            entry_id: 目标节点 ID（None 表示当前叶子）

        Returns:
            Entry 列表，不支持返回 None
        """
        from poiclaw.core.session_tree import TreeSessionManager

        jsonl_path = self._find_jsonl_file(session_id)
        if not jsonl_path:
            return None

        try:

            def _get_branch():
                manager = TreeSessionManager.open(jsonl_path)
                entries = manager.get_branch(entry_id)
                return [e.model_dump(mode="json") for e in entries]

            return await asyncio.to_thread(_get_branch)

        except Exception as e:
            print(f"[SessionManager] 警告：获取分支路径失败: {e}")
            return None

    async def get_children(self, session_id: str, parent_id: str) -> list[dict] | None:
        """
        获取指定节点的子节点（仅 v2 格式）。

        Args:
            session_id: 会话 ID
            parent_id: 父节点 ID

        Returns:
            子节点 Entry 列表，不支持返回 None
        """
        from poiclaw.core.session_tree import TreeSessionManager

        jsonl_path = self._find_jsonl_file(session_id)
        if not jsonl_path:
            return None

        try:

            def _get_children():
                manager = TreeSessionManager.open(jsonl_path)
                entries = manager.get_children(parent_id)
                return [e.model_dump(mode="json") for e in entries]

            return await asyncio.to_thread(_get_children)

        except Exception as e:
            print(f"[SessionManager] 警告：获取子节点失败: {e}")
            return None
