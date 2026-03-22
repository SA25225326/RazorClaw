"""
扩展模块 - 提供可插拔的 Agent 扩展能力。

设计理念（参考 pi-mono 的 extension 系统）：
- 极简：每个扩展专注于一个功能
- AOP：通过 Hook 在工具执行前/后进行拦截
- 可组合：多个扩展可以组合使用

扩展能力：
1. 拦截工具调用（get_hook）
2. 注册新工具（get_tools）
3. 注册斜杠命令（get_commands）
4. 订阅 Agent 事件（get_event_handlers）

用法：
    from poiclaw.extensions import (
        BaseExtension,
        SandboxExtension,
        ExtensionManager,
        ExtensionCommand,
        ExtensionContext,
    )

    # 方式1：使用 ExtensionManager（推荐）
    manager = ExtensionManager()
    manager.register(SandboxExtension())

    # 获取所有钩子，注册到 Agent
    hooks = HookManager()
    for ext in manager.get_all_extensions():
        hook = ext.get_hook()
        if hook:
            hooks.add_before_execute(hook)

    # 方式2：直接使用钩子
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

自定义扩展：
    class MyExtension(BaseExtension):
        @property
        def name(self) -> str:
            return "my_extension"

        @property
        def description(self) -> str:
            return "我的自定义扩展"

        def get_hook(self):
            async def my_hook(ctx) -> HookResult:
                # 你的拦截逻辑
                return HookResult(proceed=True)
            return my_hook

        def get_commands(self):
            return {
                "hello": ExtensionCommand(
                    name="hello",
                    description="打招呼",
                    handler=self._handle_hello,
                )
            }

        async def _handle_hello(self, args, ctx):
            print(f"Hello, {args}!")
"""

from .base import (
    AgentEndEvent,
    AgentEvent,
    AgentEventType,
    AgentStartEvent,
    BaseExtension,
    ExtensionCommand,
    ExtensionContext,
    ExtensionTool,
    HookFunction,
    StepEndEvent,
    StepStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from .manager import ExtensionManager, HookContext, HookResult
from .sandbox import SandboxExtension

__all__ = [
    # 基类
    "BaseExtension",
    # 内置扩展
    "SandboxExtension",
    # 管理器
    "ExtensionManager",
    # 类型定义
    "ExtensionTool",
    "ExtensionCommand",
    "ExtensionContext",
    "HookFunction",
    "HookContext",
    "HookResult",
    # 事件类型
    "AgentEventType",
    "AgentEvent",
    "AgentStartEvent",
    "AgentEndEvent",
    "ToolCallEvent",
    "ToolResultEvent",
    "StepStartEvent",
    "StepEndEvent",
]
