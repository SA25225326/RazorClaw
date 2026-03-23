"""LLM 模块类型定义（使用 pydantic）"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


# ============ 消息角色 ============
class MessageRole(str, Enum):
    """消息角色"""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


# ============ 工具调用相关 ============
class FunctionCall(BaseModel):
    """函数调用"""

    name: str
    arguments: str  # JSON 字符串

    def parse_arguments(self) -> dict[str, Any]:
        """解析 arguments JSON 字符串为字典"""
        try:
            return json.loads(self.arguments)
        except json.JSONDecodeError:
            return {}


class ToolCall(BaseModel):
    """工具调用"""

    id: str
    type: Literal["function"] = "function"
    function: FunctionCall


# ============ 工具定义 ============
class FunctionDef(BaseModel):
    """函数定义"""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)  # JSON Schema


class Tool(BaseModel):
    """工具定义"""

    type: Literal["function"] = "function"
    function: FunctionDef

    @classmethod
    def create(
        cls,
        name: str,
        description: str,
        parameters: dict[str, Any] | None = None,
    ) -> "Tool":
        """快捷创建工具"""
        return cls(
            type="function",
            function=FunctionDef(
                name=name,
                description=description,
                parameters=parameters or {},
            ),
        )


# ============ 消息 ============
class Message(BaseModel):
    """聊天消息"""

    role: MessageRole
    content: str | None = None
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None  # 仅用于 tool 角色的消息
    usage: Usage | None = None  # Token 使用量（仅 assistant 消息可能有）

    def to_api_format(self) -> dict[str, Any]:
        """转换为 OpenAI API 格式"""
        result: dict[str, Any] = {"role": self.role.value}

        if self.content is not None:
            result["content"] = self.content

        if self.tool_calls is not None:
            result["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in self.tool_calls
            ]

        if self.tool_call_id is not None:
            result["tool_call_id"] = self.tool_call_id

        return result

    @classmethod
    def user(cls, content: str) -> "Message":
        """快捷创建用户消息"""
        return cls(role=MessageRole.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        """快捷创建助手消息"""
        return cls(role=MessageRole.ASSISTANT, content=content)

    @classmethod
    def system(cls, content: str) -> "Message":
        """快捷创建系统消息"""
        return cls(role=MessageRole.SYSTEM, content=content)

    @classmethod
    def tool_result(cls, tool_call_id: str, content: str) -> "Message":
        """快捷创建工具结果消息"""
        return cls(role=MessageRole.TOOL, tool_call_id=tool_call_id, content=content)


# ============ 流式事件 ============
class StreamEventType(str, Enum):
    """流式事件类型"""

    TEXT_DELTA = "text_delta"
    TOOL_CALL = "tool_call"
    DONE = "done"
    ERROR = "error"


class StreamEvent(BaseModel):
    """流式事件"""

    type: StreamEventType
    delta: str | None = None  # TEXT_DELTA 时使用
    tool_call: ToolCall | None = None  # TOOL_CALL 时使用
    error: str | None = None  # ERROR 时使用
    finish_reason: str | None = None  # DONE 时使用


# ============ 使用量统计 ============
class Usage(BaseModel):
    """Token 使用量"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
