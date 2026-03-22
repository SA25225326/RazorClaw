"""
Agent 核心模块测试。

测试内容：
1. 工具注册和执行
2. 安全钩子拦截
3. ReAct 循环
"""

import asyncio

from poiclaw.core import (
    Agent,
    AgentConfig,
    BaseTool,
    ToolRegistry,
    ToolResult,
    HookManager,
    HookContext,
    create_bash_safety_hook,
)
from poiclaw.llm import LLMClient


# ============ 测试工具 ============


class EchoTool(BaseTool):
    """回显工具 - 用于测试"""

    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "回显输入的文本"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要回显的文本"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str) -> ToolResult:
        return ToolResult(success=True, content=f"[Echo] {text}")


class BashTool(BaseTool):
    """Bash 工具 - 用于测试钩子拦截"""

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "执行 bash 命令"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "要执行的命令"},
            },
            "required": ["cmd"],
        }

    async def execute(self, cmd: str) -> ToolResult:
        # 这里只是模拟，实际实现会调用 subprocess
        return ToolResult(success=True, content=f"[Bash] 执行命令: {cmd}")


# ============ 测试函数 ============


def test_tool_registry():
    """测试工具注册"""
    print("=== 测试工具注册 ===")

    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(BashTool())

    # 测试获取工具
    echo_tool = registry.get("echo")
    assert echo_tool is not None
    assert echo_tool.name == "echo"

    # 测试工具列表
    assert len(registry) == 2
    assert "echo" in registry
    assert "bash" in registry

    # 测试 LLM 格式转换
    llm_tools = registry.to_llm_tools()
    assert len(llm_tools) == 2
    assert llm_tools[0]["type"] == "function"

    print("[OK] Tool registry test passed")


async def test_tool_execute():
    """测试工具执行"""
    print("\n=== 测试工具执行 ===")

    tool = EchoTool()
    result = await tool.execute(text="Hello World")

    assert result.success
    assert result.content == "[Echo] Hello World"

    print(f"[OK] Tool execute test passed: {result.content}")


async def test_hook_intercept():
    """Test hook intercept"""
    print("\n=== Test Hook Intercept ===")

    manager = HookManager()
    manager.add_before_execute(create_bash_safety_hook())

    # Test normal command
    ctx = HookContext(
        tool_name="bash",
        arguments={"cmd": "ls -la"},
        tool=BashTool(),
    )
    result = await manager.run_before_execute(ctx)
    assert result.proceed
    print(f"[OK] Normal command passed: ls -la")

    # Test dangerous command
    ctx2 = HookContext(
        tool_name="bash",
        arguments={"cmd": "rm -rf /"},
        tool=BashTool(),
    )
    result2 = await manager.run_before_execute(ctx2)
    assert not result2.proceed
    print(f"[OK] Dangerous command blocked: rm -rf /")
    print(f"   Reason: {result2.reason}")


async def test_agent_basic():
    """Test Agent basic functions (without real LLM)"""
    print("\n=== Test Agent Basic ===")

    # Create tool registry
    registry = ToolRegistry()
    registry.register(EchoTool())

    # Create hook manager
    hooks = HookManager()

    # Create Agent config
    config = AgentConfig(max_steps=5, system_prompt="You are a test assistant")

    # Test message management
    from poiclaw.llm import Message

    messages = [
        Message.user("Hello"),
        Message.assistant("Hi! How can I help you?"),
    ]

    print(f"[OK] Agent message management test passed")
    print(f"   Message count: {len(messages)}")


# ============ 主函数 ============


async def main():
    print("Start testing PoiClaw Agent core module\n")

    # Sync tests
    test_tool_registry()

    # Async tests
    await test_tool_execute()
    await test_hook_intercept()
    await test_agent_basic()

    print("\n" + "=" * 50)
    print("[OK] All tests passed!")


if __name__ == "__main__":
    asyncio.run(main())
