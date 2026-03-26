"""
上下文压缩管理器 - LLM 摘要压缩

核心功能：
    - Token 估算：估算消息列表的 token 数量
    - 压缩判断：判断是否需要触发压缩
    - 切割点查找：找到合适的消息切割点（保持 Turn 完整性）
    - 摘要生成：调用 LLM 生成结构化摘要
    - 压缩执行：执行压缩并返回结果

v2 格式支持：
    - CompactionResult 包含 first_kept_entry_id（用于树形结构）
    - 向后兼容：同时保留 first_kept_msg_idx

设计参考：
    - pi-mono 的 Context Compaction 最佳实践
    - 短期完整对话 + 长期 LLM 摘要的分级记忆机制
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from poiclaw.core.session import CompactionEntry, CompactionSettings
from poiclaw.llm import Message

if TYPE_CHECKING:
    from poiclaw.llm import LLMClient


# ============================================================================
# 数据模型
# ============================================================================


@dataclass
class CompactionResult:
    """压缩操作结果"""

    entry: CompactionEntry  # 压缩条目（用于持久化）
    summary_message: Message  # 摘要消息（用于注入上下文）
    kept_messages: list[Message]  # 保留的消息
    tokens_saved: int  # 节省的 token 数
    # v2 格式支持：树形 Entry ID
    first_kept_entry_id: str | None = None  # 第一个保留消息的 Entry ID


# ============================================================================
# Token 估算
# ============================================================================

# 图像 token 估算（保守值）
IMAGE_TOKEN_ESTIMATE = 1200

# 字符到 token 的估算比率（保守估算：4 字符 ≈ 1 token）
CHARS_PER_TOKEN = 4


def estimate_tokens(message: Message) -> int:
    """
    估算单条消息的 token 数量。

    估算策略：
        - 文本内容：len(text) // CHARS_PER_TOKEN
        - 工具调用：name + 序列化 arguments 的长度 // CHARS_PER_TOKEN
        - 图像：固定 IMAGE_TOKEN_ESTIMATE

    Args:
        message: 消息对象

    Returns:
        估算的 token 数量
    """
    total_chars = 0

    # 1. 文本内容
    if message.content:
        total_chars += len(message.content)

    # 2. 工具调用
    if message.tool_calls:
        for tc in message.tool_calls:
            total_chars += len(tc.function.name)
            total_chars += len(tc.function.arguments)
            total_chars += len(tc.id) if tc.id else 0

    # 3. 图像（如果有）
    # 注意：当前 Message 类型可能不包含图像，这里预留
    # if hasattr(message, 'images') and message.images:
    #     total_chars += len(message.images) * IMAGE_TOKEN_ESTIMATE * CHARS_PER_TOKEN

    return max(1, total_chars // CHARS_PER_TOKEN)


def estimate_total_tokens(messages: list[Message]) -> int:
    """
    估算消息列表的总 token 数量。

    Args:
        messages: 消息列表

    Returns:
        估算的总 token 数量
    """
    return sum(estimate_tokens(msg) for msg in messages)


# ============================================================================
# 压缩判断
# ============================================================================


def should_compact(
    messages: list[Message],
    settings: CompactionSettings,
) -> bool:
    """
    判断是否需要触发压缩。

    触发条件：
        total_tokens > context_window - reserve_tokens

    Args:
        messages: 消息列表
        settings: 压缩配置

    Returns:
        是否需要压缩
    """
    if not settings.enabled:
        return False

    total_tokens = estimate_total_tokens(messages)
    return total_tokens > settings.threshold


# ============================================================================
# 切割点查找
# ============================================================================


def find_cut_point(
    messages: list[Message],
    keep_tokens: int,
) -> int:
    """
    找到消息列表的切割点。

    算法：
        1. 从后往前遍历消息
        2. 累加 token 估算值
        3. 当累加值 > keep_tokens 时停止
        4. 找到最近的 user 消息作为切割点（保持 Turn 完整性）

    Args:
        messages: 消息列表
        keep_tokens: 保留的 token 数量

    Returns:
        切割点索引（保留 messages[cut_point:] 的消息）
        返回 0 表示保留所有消息，返回 len(messages) 表示不保留任何消息
    """
    if not messages:
        return 0

    accumulated = 0
    cut_index = len(messages)

    # 从后往前遍历
    for i in range(len(messages) - 1, -1, -1):
        msg_tokens = estimate_tokens(messages[i])
        accumulated += msg_tokens

        if accumulated > keep_tokens:
            # 超过阈值，找到最近的 user 消息作为切割点
            for j in range(i + 1, len(messages)):
                if messages[j].role.value == "user":
                    cut_index = j
                    break
            else:
                # 没找到 user 消息，从当前位置开始
                cut_index = i + 1
            break

    return cut_index


# ============================================================================
# 消息序列化（用于摘要生成）
# ============================================================================


def serialize_messages_for_summary(messages: list[Message]) -> str:
    """
    将消息序列化为文本格式，用于 LLM 摘要生成。

    格式：
        [User]: 用户消息内容
        [Assistant]: 助手回复内容
        [Assistant tool calls]: read(path="..."); bash(command="...")
        [Tool result]: 工具返回结果（截断到 2000 字符）

    Args:
        messages: 消息列表

    Returns:
        序列化后的文本
    """
    lines = []
    TOOL_RESULT_MAX_LENGTH = 2000

    for msg in messages:
        role = msg.role.value

        if role == "user":
            content = msg.content or "(空消息)"
            lines.append(f"[User]: {content}")

        elif role == "assistant":
            # 文本内容
            if msg.content:
                lines.append(f"[Assistant]: {msg.content}")

            # 工具调用
            if msg.tool_calls:
                tool_calls_str = "; ".join(
                    f'{tc.function.name}({tc.function.arguments})'
                    for tc in msg.tool_calls
                )
                lines.append(f"[Assistant tool calls]: {tool_calls_str}")

        elif role == "tool":
            content = msg.content or "(空结果)"
            # 截断长工具结果
            if len(content) > TOOL_RESULT_MAX_LENGTH:
                content = content[:TOOL_RESULT_MAX_LENGTH] + f"... (截断，共 {len(msg.content or '')} 字符)"
            lines.append(f"[Tool result]: {content}")

        elif role == "system":
            # 系统消息通常不需要摘要
            pass

    return "\n".join(lines)


# ============================================================================
# 摘要生成 Prompt
# ============================================================================

SUMMARIZATION_PROMPT = """The messages above are a conversation to summarize. Create a structured context checkpoint summary that another LLM will use to continue the work.

Use this EXACT format (in Chinese):

## 目标
[用户想要完成什么？如果有多个任务可以分点列出]

## 约束与偏好
- [用户提到的任何约束、偏好或要求]
- [如果没有，写 "(无)"]

## 进度
### 已完成
- [x] [已完成的任务/变更]

### 进行中
- [ ] [当前正在做的工作]

### 阻塞
- [阻碍进度的问题，如果有]

## 关键决策
- **[决策名称]**: [简要理由]

## 下一步
1. [按顺序列出接下来应该做什么]

## 关键上下文
- [继续工作所需的任何数据、示例或引用]
- [保留精确的文件路径、函数名、错误消息]
- [如果不适用，写 "(无)"]

Keep each section concise. Preserve exact file paths, function names, and error messages."""


UPDATE_SUMMARIZATION_PROMPT = """The messages above are NEW conversation messages to incorporate into the existing summary provided in <previous-summary> tags.

Update the existing structured summary with new information. RULES:
- PRESERVE all existing information from the previous summary
- ADD new progress, decisions, and context from the new messages
- UPDATE the Progress section: move items from "进行中" to "已完成" when completed
- UPDATE "下一步" based on what was accomplished

Use this EXACT format (in Chinese):

## 目标
[保留现有目标，如果任务扩展则添加新目标]

## 约束与偏好
- [保留现有内容，添加新发现的]

## 进度
### 已完成
- [x] [包含之前已完成的和新增已完成的项目]

### 进行中
- [ ] [根据进度更新当前工作]

### 阻塞
- [当前阻塞项，如果已解决则移除]

## 关键决策
- **[决策]**: [理由] (保留所有之前的，添加新的)

## 下一步
1. [根据当前状态更新]

## 关键上下文
- [保留重要上下文，按需添加新的]

Keep each section concise. Preserve exact file paths, function names, and error messages."""


# ============================================================================
# 摘要生成
# ============================================================================


async def generate_summary(
    messages: list[Message],
    llm: LLMClient,
    previous_summary: str | None = None,
) -> str:
    """
    调用 LLM 生成结构化摘要。

    Args:
        messages: 需要摘要的消息列表
        llm: LLM 客户端
        previous_summary: 之前的摘要（用于增量更新）

    Returns:
        生成的摘要文本
    """
    # 序列化消息
    conversation_text = serialize_messages_for_summary(messages)

    # 构建 prompt
    if previous_summary:
        prompt_text = f"""<conversation>
{conversation_text}
</conversation>

<previous-summary>
{previous_summary}
</previous-summary>

{UPDATE_SUMMARIZATION_PROMPT}"""
    else:
        prompt_text = f"""<conversation>
{conversation_text}
</conversation>

{SUMMARIZATION_PROMPT}"""

    # 调用 LLM
    summary_message = Message.user(prompt_text)
    response = await llm.chat(messages=[summary_message])

    return response.content or "(摘要生成失败)"


# ============================================================================
# 压缩执行
# ============================================================================


async def compact(
    messages: list[Message],
    llm: LLMClient,
    settings: CompactionSettings,
    previous_summary: str | None = None,
    entry_ids: list[str] | None = None,
) -> CompactionResult | None:
    """
    执行上下文压缩。

    流程：
        1. 找到切割点
        2. 分离需要摘要的消息和保留的消息
        3. 生成摘要
        4. 构建压缩结果

    Args:
        messages: 完整消息列表
        llm: LLM 客户端
        settings: 压缩配置
        previous_summary: 之前的摘要（用于增量更新）
        entry_ids: 消息对应的 Entry ID 列表（用于 v2 格式）

    Returns:
        CompactionResult 或 None（如果无需压缩）
    """
    if not messages:
        return None

    # 1. 计算压缩前的 token 数
    tokens_before = estimate_total_tokens(messages)

    # 2. 找到切割点
    cut_point = find_cut_point(messages, settings.keep_recent_tokens)

    # 如果没有需要摘要的消息
    if cut_point == 0:
        return None

    # 3. 分离消息
    messages_to_summarize = messages[:cut_point]
    kept_messages = messages[cut_point:]

    # 4. 生成摘要
    summary = await generate_summary(messages_to_summarize, llm, previous_summary)

    # 5. 构建摘要消息
    summary_content = f"""[上下文摘要]

{summary}

---
*以上是对之前对话的摘要，保留关键信息以便继续工作。*
"""
    summary_message = Message.system(summary_content)

    # 6. 计算压缩后的 token 数
    tokens_after = estimate_tokens(summary_message) + estimate_total_tokens(kept_messages)

    # 7. 获取 first_kept_entry_id（v2 格式支持）
    first_kept_entry_id: str | None = None
    if entry_ids and cut_point < len(entry_ids):
        first_kept_entry_id = entry_ids[cut_point]

    # 8. 构建 CompactionEntry
    entry = CompactionEntry(
        id=str(uuid.uuid4()),
        timestamp=datetime.now().isoformat(),
        summary=summary,
        first_kept_msg_idx=cut_point,
        tokens_before=tokens_before,
        tokens_after=tokens_after,
    )

    return CompactionResult(
        entry=entry,
        summary_message=summary_message,
        kept_messages=kept_messages,
        tokens_saved=tokens_before - tokens_after,
        first_kept_entry_id=first_kept_entry_id,
    )


# ============================================================================
# 便捷函数
# ============================================================================


def get_latest_summary(compactions: list[CompactionEntry]) -> str | None:
    """
    获取最新的摘要。

    Args:
        compactions: 压缩历史列表

    Returns:
        最新摘要或 None
    """
    if not compactions:
        return None
    return compactions[-1].summary
