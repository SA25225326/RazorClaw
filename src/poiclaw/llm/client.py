"""LLM 统一调用客户端"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from typing import Any

import httpx

from .exceptions import LLMAPIError, LLMConnectionError, LLMTimeoutError
from .stream import parse_sse_stream
from .types import Message, StreamEvent, Tool, Usage


class LLMClient:
    """
    统一的 LLM 调用客户端。

    支持 OpenAI 兼容格式的 API：
    - OpenAI
    - 智谱 AI (GLM-4)
    - Kimi (月之暗面)
    - DeepSeek
    - 其他 OpenAI 兼容 API

    Example:
        client = LLMClient(
            base_url="https://api.openai.com/v1",
            api_key="sk-xxx",
            model="gpt-4o-mini",
        )

        # 非流式调用
        response = await client.chat([Message(role="user", content="Hello")])

        # 流式调用
        async for event in client.stream([Message(role="user", content="Hello")]):
            if event.delta:
                print(event.delta, end="", flush=True)
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ) -> None:
        """
        初始化 LLM 客户端。

        Args:
            base_url: API 基础地址，默认从环境变量 OPENAI_BASE_URL 读取
                     OpenAI: https://api.openai.com/v1
                     智谱: https://open.bigmodel.cn/api/paas/v4
                     Kimi: https://api.moonshot.cn/v1
                     DeepSeek: https://api.deepseek.com/v1
            api_key: API 密钥，默认从环境变量 OPENAI_API_KEY 读取
            model: 模型名称
            timeout: 请求超时时间（秒）
        """
        self.base_url = (base_url or os.environ.get("OPENAI_BASE_URL", "")).rstrip("/")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.model = model
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("base_url 或环境变量 OPENAI_BASE_URL 必须设置")
        if not self.api_key:
            raise ValueError("api_key 或环境变量 OPENAI_API_KEY 必须设置")

    def _get_headers(self) -> dict[str, str]:
        """获取请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _build_payload(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """构建请求体"""
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [msg.to_api_format() for msg in messages],
            "temperature": temperature,
            "stream": stream,
        }

        if max_tokens:
            payload["max_tokens"] = max_tokens

        if tools:
            # tools 可能是 dict 或 Pydantic 模型
            payload["tools"] = [
                tool.model_dump() if hasattr(tool, "model_dump") else tool
                for tool in tools
            ]
            payload["tool_choice"] = tool_choice

        return payload

    async def chat(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> Message:
        """
        非流式调用，返回完整的助手消息。

        Args:
            messages: 对话消息列表
            tools: 可用工具列表
            tool_choice: 工具选择策略 ("auto", "none", "required")
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Returns:
            Message: 助手的完整回复消息
        """
        payload = self._build_payload(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=False,
        )

        response_data = await self._request(payload, stream=False)
        return self._parse_response(response_data)

    async def stream(
        self,
        messages: list[Message],
        tools: list[Tool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> AsyncGenerator[StreamEvent, None]:
        """
        流式调用，返回事件流。

        Args:
            messages: 对话消息列表
            tools: 可用工具列表
            tool_choice: 工具选择策略
            temperature: 温度参数
            max_tokens: 最大生成 token 数

        Yields:
            StreamEvent: 流式事件（文本增量、工具调用、完成等）
        """
        payload = self._build_payload(
            messages=messages,
            tools=tools,
            tool_choice=tool_choice,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        raise LLMAPIError(
                            response.status_code,
                            error_text.decode("utf-8", errors="replace"),
                        )

                    async for event in parse_sse_stream(response):
                        yield event

            except httpx.TimeoutException as e:
                raise LLMTimeoutError(f"请求超时: {e}") from e
            except httpx.ConnectError as e:
                raise LLMConnectionError(f"连接失败: {e}") from e

    async def _request(self, payload: dict[str, Any], stream: bool) -> dict[str, Any]:
        """发送 HTTP 请求"""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )

                if response.status_code != 200:
                    raise LLMAPIError(
                        response.status_code,
                        response.text,
                    )

                return response.json()

            except httpx.TimeoutException as e:
                raise LLMTimeoutError(f"请求超时: {e}") from e
            except httpx.ConnectError as e:
                raise LLMConnectionError(f"连接失败: {e}") from e

    def _parse_response(self, data: dict[str, Any]) -> Message:
        """解析非流式响应"""
        from .types import FunctionCall, MessageRole, ToolCall

        choice = data.get("choices", [{}])[0]
        message_data = choice.get("message", {})

        content = message_data.get("content")
        tool_calls_data = message_data.get("tool_calls", [])

        tool_calls = None
        if tool_calls_data:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=FunctionCall(
                        name=tc["function"]["name"],
                        arguments=tc["function"]["arguments"],
                    ),
                )
                for tc in tool_calls_data
            ]

        return Message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
        )

    def collect_stream(self, events: AsyncGenerator[StreamEvent, None]) -> "StreamCollector":
        """
        创建流收集器，用于累积流式事件并获取最终结果。

        Example:
            collector = client.collect_stream(client.stream(messages))
            async for event in collector.events():
                print(event.delta, end="")
            result = await collector.result()
        """
        return StreamCollector(events)


class StreamCollector:
    """流式事件收集器，累积文本和工具调用"""

    def __init__(self, events: AsyncGenerator[StreamEvent, None]) -> None:
        self._events = events
        self._content = ""
        self._tool_calls: list[ToolCall] = []
        self._finish_reason: str | None = None
        self._usage: Usage | None = None

    @property
    def content(self) -> str:
        """已累积的文本内容"""
        return self._content

    @property
    def tool_calls(self) -> list[ToolCall]:
        """已收集的工具调用"""
        return self._tool_calls

    async def events(self) -> AsyncGenerator[StreamEvent, None]:
        """迭代事件并累积"""
        from .types import ToolCall

        current_tool_call: dict[str, Any] | None = None
        current_args = ""

        async for event in self._events:
            yield event

            if event.type.value == "text_delta" and event.delta:
                self._content += event.delta

            elif event.type.value == "tool_call" and event.tool_call:
                self._tool_calls.append(event.tool_call)

            elif event.type.value == "done":
                self._finish_reason = event.finish_reason

        # 如果有未完成的工具调用，添加到列表
        if current_tool_call:
            from .types import FunctionCall

            self._tool_calls.append(
                ToolCall(
                    id=current_tool_call.get("id", ""),
                    type="function",
                    function=FunctionCall(
                        name=current_tool_call.get("function", {}).get("name", ""),
                        arguments=current_args,
                    ),
                )
            )

    async def result(self) -> Message:
        """获取最终的 Message 结果"""
        from .types import MessageRole

        return Message(
            role=MessageRole.ASSISTANT,
            content=self._content or None,
            tool_calls=self._tool_calls or None,
        )
