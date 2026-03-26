"""
会话迁移工具 - v1 扁平格式 → v2 树形格式

迁移策略：
    1. 检测旧格式（JSON 文件，有 messages 数组）
    2. 为每条消息生成 8 位短 ID
    3. 链接 parentId（线性链，模拟旧格式）
    4. 转换 first_kept_msg_idx → first_kept_entry_id
    5. 写入新 JSONL 文件
    6. 备份原文件为 .json.bak

使用方式：
    from poiclaw.core.session_migration import migrate_all_sessions

    results = migrate_all_sessions(Path(".poiclaw"))
    for result in results:
        print(f"{result.session_id}: {result.success}")
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from .session_tree import (
    CURRENT_SESSION_VERSION,
    BranchSummaryEntry,
    CompactionEntry,
    CustomEntry,
    LabelEntry,
    ModelChangeEntry,
    SessionHeader,
    SessionMessageEntry,
    SessionInfoEntry,
    generate_id,
)


# ============================================================================
# 迁移结果
# ============================================================================


class MigrationResult(BaseModel):
    """迁移操作结果"""

    success: bool
    session_id: str
    old_format: str  # "v1_flat"
    new_format: str  # "v2_tree"
    entries_migrated: int
    compactions_migrated: int
    old_file: str
    new_file: str = ""
    error: str | None = None


# ============================================================================
# 格式检测
# ============================================================================


def detect_format(file_path: Path) -> str | None:
    """
    检测会话文件格式。

    Args:
        file_path: 文件路径

    Returns:
        "v1_flat" - 旧格式（JSON + messages 数组）
        "v2_tree" - 新格式（JSONL）
        None - 无法识别
    """
    if not file_path.exists():
        return None

    try:
        content = file_path.read_text(encoding="utf-8").strip()
        if not content:
            return None

        # 检查第一行是否为 JSONL Header
        first_line = content.split("\n")[0]
        try:
            first_entry = json.loads(first_line)
            if first_entry.get("type") == "session" and first_entry.get("version", 1) >= 2:
                return "v2_tree"
        except json.JSONDecodeError:
            pass

        # 检查是否为旧 JSON 格式
        try:
            data = json.loads(content)
            if "messages" in data and isinstance(data["messages"], list):
                return "v1_flat"
        except json.JSONDecodeError:
            pass

        return None

    except Exception:
        return None


def is_migration_needed(base_path: Path) -> bool:
    """
    检查是否有需要迁移的会话。

    Args:
        base_path: 基础路径（如 .poiclaw）

    Returns:
        是否有旧格式会话
    """
    data_dir = base_path / "sessions" / "data"
    if not data_dir.exists():
        return False

    for json_file in data_dir.glob("*.json"):
        # 跳过备份文件
        if json_file.suffix == ".bak" or ".bak" in json_file.name:
            continue

        if detect_format(json_file) == "v1_flat":
            return True

    return False


# ============================================================================
# 单个会话迁移
# ============================================================================


def migrate_v1_to_v2(data_path: Path, backup: bool = True) -> MigrationResult:
    """
    迁移单个会话从 v1 到 v2 格式。

    v1 格式（JSON）：
    {
        "id": "uuid",
        "title": "...",
        "created_at": "...",
        "last_modified": "...",
        "messages": [{...}, {...}],
        "compactions": [{"first_kept_msg_idx": 5, ...}],
        "usage": {...}
    }

    v2 格式（JSONL）：
    {"type":"session","version":2,"id":"uuid","timestamp":"...","cwd":"..."}
    {"type":"message","id":"abc123","parentId":null,"timestamp":"...","message":{...}}
    {"type":"message","id":"def456","parentId":"abc123","timestamp":"...","message":{...}}
    {"type":"compaction","id":"ghi789","parentId":"def456","firstKeptEntryId":"abc123",...}

    Args:
        data_path: 旧格式数据文件路径
        backup: 是否创建备份

    Returns:
        MigrationResult
    """
    try:
        # 读取旧数据
        old_content = data_path.read_text(encoding="utf-8")
        old_data = json.loads(old_content)

        # 提取字段
        session_id = old_data.get("id", "")
        title = old_data.get("title", "")
        created_at = old_data.get("created_at", datetime.now().isoformat())
        messages = old_data.get("messages", [])
        compactions = old_data.get("compactions", [])

        # 生成 Entry ID 映射
        existing_ids: set[str] = set()
        entry_ids: list[str] = []

        for _ in messages:
            entry_id = generate_id(existing_ids)
            entry_ids.append(entry_id)
            existing_ids.add(entry_id)

        # 构建新 Entry 列表
        new_entries: list[dict[str, Any]] = []

        # 1. Header
        header = SessionHeader(
            type="session",
            version=CURRENT_SESSION_VERSION,
            id=session_id,
            timestamp=created_at,
            cwd="",
        )
        new_entries.append(header.model_dump(mode="json"))

        # 2. 消息（线性链）
        prev_id: str | None = None
        for i, msg_dict in enumerate(messages):
            entry_id = entry_ids[i]
            entry = SessionMessageEntry(
                type="message",
                id=entry_id,
                parent_id=prev_id,
                timestamp=created_at,  # 使用会话时间戳
                message=msg_dict,
            )
            new_entries.append(entry.model_dump(mode="json"))
            prev_id = entry_id

        # 3. 压缩记录（转换 first_kept_msg_idx → first_kept_entry_id）
        for old_comp in compactions:
            # 生成压缩 Entry ID
            comp_entry_id = generate_id(existing_ids)
            existing_ids.add(comp_entry_id)

            # 转换索引到 ID
            first_kept_idx = old_comp.get("first_kept_msg_idx", 0)
            if isinstance(first_kept_idx, int) and 0 <= first_kept_idx < len(entry_ids):
                first_kept_entry_id = entry_ids[first_kept_idx]
            else:
                first_kept_entry_id = entry_ids[0] if entry_ids else ""

            comp_entry = CompactionEntry(
                type="compaction",
                id=comp_entry_id,
                parent_id=prev_id,
                timestamp=old_comp.get("timestamp", created_at),
                summary=old_comp.get("summary", ""),
                first_kept_entry_id=first_kept_entry_id,
                tokens_before=old_comp.get("tokens_before", 0),
                tokens_after=old_comp.get("tokens_after", 0),
            )
            new_entries.append(comp_entry.model_dump(mode="json"))
            prev_id = comp_entry_id

        # 4. 添加 session_info（保存标题）
        if title:
            info_entry_id = generate_id(existing_ids)
            info_entry = SessionInfoEntry(
                type="session_info",
                id=info_entry_id,
                parent_id=prev_id,
                timestamp=datetime.now().isoformat(),
                name=title,
            )
            new_entries.append(info_entry.model_dump(mode="json"))

        # 写入新 JSONL 文件
        file_timestamp = created_at.replace(":", "-").replace(".", "-")
        new_filename = f"{file_timestamp}_{session_id}.jsonl"
        new_path = data_path.parent / new_filename

        lines = [json.dumps(e, ensure_ascii=False) for e in new_entries]
        new_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # 备份旧文件
        if backup:
            backup_path = data_path.with_suffix(".json.bak")
            if not backup_path.exists():
                data_path.rename(backup_path)
            else:
                # 备份已存在，直接删除旧文件
                data_path.unlink()

        return MigrationResult(
            success=True,
            session_id=session_id,
            old_format="v1_flat",
            new_format="v2_tree",
            entries_migrated=len(messages),
            compactions_migrated=len(compactions),
            old_file=str(data_path),
            new_file=str(new_path),
        )

    except Exception as e:
        return MigrationResult(
            success=False,
            session_id="",
            old_format="v1_flat",
            new_format="v2_tree",
            entries_migrated=0,
            compactions_migrated=0,
            old_file=str(data_path),
            error=str(e),
        )


# ============================================================================
# 批量迁移
# ============================================================================


def migrate_all_sessions(base_path: Path, backup: bool = True) -> list[MigrationResult]:
    """
    迁移所有旧格式会话。

    Args:
        base_path: 基础路径（如 .poiclaw）
        backup: 是否创建备份

    Returns:
        迁移结果列表
    """
    data_dir = base_path / "sessions" / "data"
    if not data_dir.exists():
        return []

    results: list[MigrationResult] = []

    for json_file in data_dir.glob("*.json"):
        # 跳过备份文件
        if json_file.suffix == ".bak" or ".bak" in json_file.name:
            continue

        old_format = detect_format(json_file)
        if old_format == "v1_flat":
            result = migrate_v1_to_v2(json_file, backup=backup)
            results.append(result)

    return results


# ============================================================================
# 异步包装（用于 API 兼容）
# ============================================================================


async def migrate_v1_to_v2_async(data_path: Path, backup: bool = True) -> MigrationResult:
    """
    异步迁移单个会话。

    Args:
        data_path: 旧格式数据文件路径
        backup: 是否创建备份

    Returns:
        MigrationResult
    """
    import asyncio

    return await asyncio.to_thread(migrate_v1_to_v2, data_path, backup)


async def migrate_all_sessions_async(
    base_path: Path, backup: bool = True
) -> list[MigrationResult]:
    """
    异步迁移所有会话。

    Args:
        base_path: 基础路径
        backup: 是否创建备份

    Returns:
        迁移结果列表
    """
    import asyncio

    return await asyncio.to_thread(migrate_all_sessions, base_path, backup)


# ============================================================================
# CLI 工具
# ============================================================================


def main() -> None:
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="迁移 PoiClaw 会话到 v2 格式")
    parser.add_argument(
        "--base-path",
        type=Path,
        default=Path(".poiclaw"),
        help="基础存储路径（默认 .poiclaw）",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="不创建备份文件",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只检查，不执行迁移",
    )

    args = parser.parse_args()

    print(f"检查 {args.base_path}...")

    data_dir = args.base_path / "sessions" / "data"
    if not data_dir.exists():
        print("未找到会话数据目录")
        return

    # 统计
    v1_count = 0
    v2_count = 0

    for json_file in data_dir.glob("*.json"):
        if json_file.suffix == ".bak" or ".bak" in json_file.name:
            continue

        fmt = detect_format(json_file)
        if fmt == "v1_flat":
            v1_count += 1
            print(f"  [v1] {json_file.name}")
        elif fmt == "v2_tree":
            v2_count += 1

    # 检查 JSONL 文件
    for jsonl_file in data_dir.glob("*.jsonl"):
        v2_count += 1

    print(f"\n统计: {v1_count} 个旧格式, {v2_count} 个新格式")

    if args.dry_run:
        return

    if v1_count == 0:
        print("无需迁移")
        return

    print(f"\n开始迁移 {v1_count} 个会话...")

    results = migrate_all_sessions(args.base_path, backup=not args.no_backup)

    success_count = sum(1 for r in results if r.success)
    fail_count = len(results) - success_count

    print(f"\n迁移完成: {success_count} 成功, {fail_count} 失败")

    for result in results:
        if result.success:
            print(f"  ✓ {result.session_id}: {result.entries_migrated} 条消息")
        else:
            print(f"  ✗ {result.old_file}: {result.error}")


if __name__ == "__main__":
    main()
