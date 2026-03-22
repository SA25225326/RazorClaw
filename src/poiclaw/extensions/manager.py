"""扩展管理器 - 管理扩展的注册、注销和事件分发"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from .base import (
    AgentEndEvent,
    AgentEvent,
    AgentEventType,
    AgentStartEvent,
    ExtensionCommand,
    ExtensionContext,
    ExtensionTool,
    HookFunction,
    StepEndEvent,
    StepStartEvent,
    ToolCallEvent,
    ToolResultEvent,
)

if TYPE_CHECKING:
    from poiclaw.core import HookContext, HookResult
    from poiclaw.extensions import BaseExtension


@dataclass
class HookContext:
    """
    钩子上下文 - 传递给扩展钩子的信息。

    Attributes:
        tool_name: 工具名称
        arguments: 工具参数
        tool: 工具实例
    """

    tool_name: str
    arguments: dict[str, Any]
    tool: Any  # BaseTool 类型

    # 扩展字段（可被钩子修改）
    modified_arguments: dict[str, Any] | None = None


@dataclass
class HookResult:
    """
    钩子返回结果。

    Attributes:
        proceed: True=继续执行工具, False=拦截
        reason: 拦截原因（用于日志和返回给 LLM）
        modified_arguments: 修改后的参数（可选）
    """

    proceed: bool = True
    reason: str | None = None
    modified_arguments: dict[str, Any] | None = None


class ExtensionManager:
    """
    扩展管理器 - 管理扩展的生命周期和能力注册。

    核心功能：
        1. 扩展注册/注销
        2. 工具注册/获取
        3. 命令注册/获取
        4. 事件分发
        5. 钩子链执行

    用法：
        manager = ExtensionManager()
        manager.register(SandboxExtension())

        # 获取所有工具
        tools = manager.get_all_tools()

        # 获取所有命令
        commands = manager.get_all_commands()

        # 分发事件
        await manager.emit("agent_start", event, ctx)

        # 执行钩子链
        result = await manager.run_hooks(hook_ctx)
    """

    def __init__(self) -> None:
        self._extensions: dict[str, BaseExtension] = {}
        self._tools: dict[str, ExtensionTool] = {}
        self._commands: dict[str, ExtensionCommand] = {}
        self._event_handlers: dict[AgentEventType, list[Callable]] = {}
        self._hooks: list[HookFunction] = []
        self._context: ExtensionContext | None = None

    def register(
        self,
        extension: BaseExtension,
        ctx: ExtensionContext | None = None,
    ) -> bool:
        """
        注册扩展。

        Args:
            extension: 扩展实例
            ctx: 扩展上下文（可选）

        Returns:
            bool: 是否注册成功（同名扩展会覆盖）
        """
        name = extension.name

        # 如果已存在同名扩展，先注销
        if name in self._extensions:
            self.unregister(name)

        # 注册扩展
        self._extensions[name] = extension

        # 注册工具
        for tool in extension.get_tools():
            self._tools[tool.definition.name] = tool

        # 注册命令
        for cmd_name, cmd in extension.get_commands().items():
            cmd.extension_path = name
            self._commands[cmd_name] = cmd

        # 注册事件处理器
        for event_type, handlers in extension.get_event_handlers().items():
            if event_type not in self._event_handlers:
                self._event_handlers[event_type] = []
            self._event_handlers[event_type].extend(handlers)

        # 注册钩子
        hook = extension.get_hook()
        if hook is not None:
            self._hooks.append(hook)

        # 调用生命周期钩子
        if ctx is not None:
            import asyncio

            asyncio.create_task(extension.on_register(ctx))

        return True

    def unregister(self, name: str) -> bool:
        """
        注销扩展。

        Args:
            name: 扩展名称

        Returns:
            bool: 是否注销成功
        """
        if name not in self._extensions:
            return False

        extension = self._extensions[name]

        # 调用生命周期钩子
        import asyncio

        asyncio.create_task(extension.on_unregister())

        # 移除工具（需要遍历查找）
        tools_to_remove = [
            tool_name
            for tool_name, tool in self._tools.items()
            if tool.extension_path == name
        ]
        for tool_name in tools_to_remove:
            del self._tools[tool_name]

        # 移除命令
        commands_to_remove = [
            cmd_name
            for cmd_name, cmd in self._commands.items()
            if cmd.extension_path == name
        ]
        for cmd_name in commands_to_remove:
            del self._commands[cmd_name]

        # 移除钩子
        hook = extension.get_hook()
        if hook is not None and hook in self._hooks:
            self._hooks.remove(hook)

        # 移除扩展
        del self._extensions[name]

        return True

    def get_extension(self, name: str) -> BaseExtension | None:
        """获取扩展实例"""
        return self._extensions.get(name)

    def get_all_extensions(self) -> list[BaseExtension]:
        """获取所有扩展"""
        return list(self._extensions.values())

    def get_extension_names(self) -> list[str]:
        """获取所有扩展名称"""
        return list(self._extensions.keys())

    # ============ 工具管理 ============

    def get_all_tools(self) -> list[ExtensionTool]:
        """获取所有注册的工具"""
        return list(self._tools.values())

    def get_tool(self, name: str) -> ExtensionTool | None:
        """获取指定工具"""
        return self._tools.get(name)

    def has_tool(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    # ============ 命令管理 ============

    def get_all_commands(self) -> dict[str, ExtensionCommand]:
        """获取所有注册的命令"""
        return self._commands.copy()

    def get_command(self, name: str) -> ExtensionCommand | None:
        """获取指定命令"""
        return self._commands.get(name)

    def has_command(self, name: str) -> bool:
        """检查命令是否存在"""
        return name in self._commands

    # ============ 事件分发 ============

    def has_handlers(self, event_type: AgentEventType) -> bool:
        """检查是否有事件处理器"""
        return event_type in self._event_handlers and len(self._event_handlers[event_type]) > 0

    async def emit(
        self,
        event_type: AgentEventType,
        event: AgentEvent,
        ctx: ExtensionContext,
    ) -> list[Any]:
        """
        分发事件给所有处理器。

        Args:
            event_type: 事件类型
            event: 事件对象
            ctx: 扩展上下文

        Returns:
            list: 所有处理器的返回值
        """
        results = []
        handlers = self._event_handlers.get(event_type, [])

        for handler in handlers:
            try:
                result = await handler(event, ctx)
                results.append(result)
            except Exception as e:
                # 记录错误但不中断
                print(f"[ExtensionManager] Event handler error: {e}")

        return results

    # ============ 钩子链执行 ============

    @property
    def has_hooks(self) -> bool:
        """是否有注册的钩子"""
        return len(self._hooks) > 0

    async def run_hooks(self, ctx: HookContext) -> HookResult:
        """
        执行所有钩子（责任链模式）。

        任一钩子返回 proceed=False 即终止链条。

        Args:
            ctx: 钩子上下文

        Returns:
            HookResult: 最终结果
        """
        for hook in self._hooks:
            try:
                result = await hook(ctx)
                if not result.proceed:
                    return result
                # 如果钩子修改了参数，更新上下文
                if result.modified_arguments is not None:
                    ctx.modified_arguments = result.modified_arguments
            except Exception as e:
                # 钩子出错时记录但不中断
                print(f"[ExtensionManager] Hook error: {e}")

        return HookResult(proceed=True)

    # ============ 便捷方法 ============

    def create_context(self, agent: Any, cwd: str = ".") -> ExtensionContext:
        """
        创建扩展上下文。

        Args:
            agent: Agent 实例
            cwd: 当前工作目录

        Returns:
            ExtensionContext: 扩展上下文
        """
        return ExtensionContext(agent=agent, cwd=cwd)

    def __len__(self) -> int:
        return len(self._extensions)

    def __contains__(self, name: str) -> bool:
        return name in self._extensions

    def __repr__(self) -> str:
        return f"<ExtensionManager extensions={list(self._extensions.keys())}>"
