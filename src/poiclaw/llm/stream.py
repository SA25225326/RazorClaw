"""SSE 流式响应解析器"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from .exceptions import LLMStreamError
from .types import FunctionCall, StreamEvent, StreamEventType, ToolCall


async def parse_sse_stream(
    response: httpx.Response,
) -> AsyncGenerator[StreamEvent, None]:
    """
    解析 OpenAI 兼容的 SSE 流式响应。

    SSE 格式示例：
        data: {"id":"chatcmpl-xxx","choices":[{"delta":{"content":"Hello"},"finish_reason":null}]}
        data: {"id":"chatcmpl-xxx","choices":[{"delta":{},"finish_reason":"stop"}]}
        data: [DONE]

    Args:
        response: httpx 流式响应对象

    Yields:
        StreamEvent: 流式事件
    """
    buffer = ""  # 用于累积不完整的行

    async for chunk in response.aiter_text():
        buffer += chunk

        # 按行分割处理
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.strip()

            # 跳过空行和注释
            if not line or line.startswith(":"):
                continue

            # 处理 data: 开头的行
            if line.startswith("data: "):
                data_str = line[6:]  # 去掉 "data: " 前缀

                # 检查是否是结束标记
                if data_str == "[DONE]":
                    yield StreamEvent(type=StreamEventType.DONE, finish_reason="stop")
                    return

                # 解析 JSON
                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError as e:
                    yield StreamEvent(
                        type=StreamEventType.ERROR,
                        error=f"JSON 解析错误: {e}",
                    )
                    continue

                # 解析 OpenAI 格式的响应
                async for event in _parse_openai_chunk(data):
                    yield event


async def _parse_openai_chunk(data: dict[str, Any]) -> AsyncGenerator[StreamEvent, None]:
    """解析 OpenAI 格式的 chunk"""
    choices = data.get("choices", [])
    if not choices:
        return

    choice = choices[0]
    delta = choice.get("delta", {})
    finish_reason = choice.get("finish_reason")

    # 处理文本增量
    if "content" in delta and delta["content"]:
        yield StreamEvent(
            type=StreamEventType.TEXT_DELTA,
            delta=delta["content"],
        )

    # 处理工具调用
    if "tool_calls" in delta:
        for tool_call_delta in delta["tool_calls"]:
            # 注意：流式响应中 tool_calls 是增量的，需要累积
            # 这里简化处理，假设完整的 tool_call 在一个 chunk 中
            if "function" in tool_call_delta:
                tc_id = tool_call_delta.get("id", "")
                function = tool_call_delta["function"]

                if "name" in function and "arguments" in function:
                    yield StreamEvent(
                        type=StreamEventType.TOOL_CALL,
                        tool_call=ToolCall(
                            id=tc_id,
                            type="function",
                            function=FunctionCall(
                                name=function["name"],
                                arguments=function["arguments"],
                            ),
                        ),
                    )

    # 处理结束原因
    if finish_reason:
        yield StreamEvent(
            type=StreamEventType.DONE,
            finish_reason=finish_reason,
        )
