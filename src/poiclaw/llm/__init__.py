"""
PoiClaw LLM 模块 - 统一的 LLM 调用层

支持 OpenAI 兼容格式的 API：
- OpenAI
- 智谱 AI (GLM-4)
- Kimi (月之暗面)
- DeepSeek
- 其他 OpenAI 兼容 API

使用示例:
    from poiclaw.llm import LLMClient, Message, Tool

    # 初始化客户端
    client = LLMClient(
        base_url="https://api.openai.com/v1",
        api_key="sk-xxx",
        model="gpt-4o-mini",
    )

    # 非流式调用
    response = await client.chat([
        Message.user("Hello!")
    ])
    print(response.content)

    # 流式调用
    async for event in client.stream([Message.user("Hello!")]):
        if event.delta:
            print(event.delta, end="", flush=True)
"""

from .client import LLMClient, StreamCollector
from .exceptions import (
    LLMAPIError,
    LLMConnectionError,
    LLMError,
    LLMStreamError,
    LLMTimeoutError,
)
from .types import (
    FunctionCall,
    FunctionDef,
    Message,
    MessageRole,
    StreamEvent,
    StreamEventType,
    Tool,
    ToolCall,
    Usage,
)

__all__ = [
    # 客户端
    "LLMClient",
    "StreamCollector",
    # 类型
    "Message",
    "MessageRole",
    "Tool",
    "ToolCall",
    "FunctionCall",
    "FunctionDef",
    "StreamEvent",
    "StreamEventType",
    "Usage",
    # 异常
    "LLMError",
    "LLMAPIError",
    "LLMConnectionError",
    "LLMTimeoutError",
    "LLMStreamError",
]
