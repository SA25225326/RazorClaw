"""
LLM 模块测试脚本

使用方法:
1. 设置环境变量:
   export OPENAI_BASE_URL=https://api.openai.com/v1
   export OPENAI_API_KEY=sk-xxx

2. 运行测试:
   uv run python tests/test_llm.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from poiclaw.llm import (
    LLMClient,
    LLMAPIError,
    LLMConnectionError,
    Message,
    MessageRole,
    StreamEvent,
    StreamEventType,
    Tool,
)


async def test_basic_chat() -> None:
    """测试基本的非流式调用"""
    print("\n" + "=" * 60)
    print("测试 1: 基本非流式调用")
    print("=" * 60)

    client = LLMClient(
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        model="gpt-4o-mini",  # 或你的模型
    )

    messages = [
        Message.system("你是一个友好的助手，用简短的中文回答问题。"),
        Message.user("用一句话解释什么是 Agent。"),
    ]

    try:
        response = await client.chat(messages)
        print(f"回复: {response.content}")
        print("✅ 测试通过")
    except LLMAPIError as e:
        print(f"❌ API 错误: {e}")
    except LLMConnectionError as e:
        print(f"❌ 连接错误: {e}")


async def test_stream_chat() -> None:
    """测试流式调用"""
    print("\n" + "=" * 60)
    print("测试 2: 流式调用")
    print("=" * 60)

    client = LLMClient(
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        model="gpt-4o-mini",
    )

    messages = [Message.user("用三句话介绍 Python 语言。")]

    try:
        print("回复: ", end="", flush=True)
        async for event in client.stream(messages):
            if event.type == StreamEventType.TEXT_DELTA and event.delta:
                print(event.delta, end="", flush=True)
            elif event.type == StreamEventType.DONE:
                print(f"\n[完成: {event.finish_reason}]")
        print("✅ 测试通过")
    except LLMAPIError as e:
        print(f"\n❌ API 错误: {e}")
    except LLMConnectionError as e:
        print(f"\n❌ 连接错误: {e}")


async def test_tool_call() -> None:
    """测试工具调用"""
    print("\n" + "=" * 60)
    print("测试 3: 工具调用")
    print("=" * 60)

    client = LLMClient(
        base_url=os.environ.get("OPENAI_BASE_URL"),
        api_key=os.environ.get("OPENAI_API_KEY"),
        model="gpt-4o-mini",
    )

    # 定义一个简单的天气查询工具
    tools = [
        Tool.create(
            name="get_weather",
            description="获取指定城市的天气信息",
            parameters={
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "城市名称",
                    }
                },
                "required": ["city"],
            },
        )
    ]

    messages = [Message.user("北京今天天气怎么样？")]

    try:
        response = await client.chat(messages, tools=tools)

        if response.tool_calls:
            print(f"模型请求调用工具:")
            for tc in response.tool_calls:
                args = tc.function.parse_arguments()
                print(f"  - 工具: {tc.function.name}")
                print(f"  - 参数: {args}")
            print("✅ 测试通过")
        else:
            print(f"模型直接回复: {response.content}")
            print("⚠️ 模型没有调用工具（可能不支持或不需要）")
    except LLMAPIError as e:
        print(f"❌ API 错误: {e}")
    except LLMConnectionError as e:
        print(f"❌ 连接错误: {e}")


def check_env() -> bool:
    """检查环境变量是否设置"""
    if not os.environ.get("OPENAI_BASE_URL"):
        print("⚠️ 请设置环境变量 OPENAI_BASE_URL")
        print("   例如: export OPENAI_BASE_URL=https://api.openai.com/v1")
        return False

    if not os.environ.get("OPENAI_API_KEY"):
        print("⚠️ 请设置环境变量 OPENAI_API_KEY")
        print("   例如: export OPENAI_API_KEY=sk-xxx")
        return False

    return True


async def main() -> None:
    """运行所有测试"""
    print("=" * 60)
    print("PoiClaw LLM 模块测试")
    print("=" * 60)

    if not check_env():
        print("\n请先设置环境变量后再运行测试。")
        return

    await test_basic_chat()
    await test_stream_chat()
    await test_tool_call()

    print("\n" + "=" * 60)
    print("所有测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
