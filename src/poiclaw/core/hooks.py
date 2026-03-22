"""安全拦截钩子机制"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable

if TYPE_CHECKING:
    from .tools import BaseTool, ToolResult


@dataclass
class HookContext:
    """
    钩子上下文 - 传递给 before_execute 钩子的信息。

    Attributes:
        tool_name: 工具名称
        arguments: 工具参数
        tool: 工具实例
    """

    tool_name: str
    arguments: dict[str, Any]
    tool: "BaseTool"


@dataclass
class HookResult:
    """
    钩子返回结果。

    Attributes:
        proceed: True=继续执行工具, False=拦截
        reason: 拦截原因（用于日志和返回给 LLM）
        fake_result: 拦截时返回的假结果（可选，不提供则使用默认拦截消息）
    """

    proceed: bool
    reason: str | None = None
    fake_result: "ToolResult | None" = None


# 钩子函数签名
BeforeExecuteHook = Callable[[HookContext], Awaitable[HookResult]]


class HookManager:
    """
    钩子管理器。

    用法：
        manager = HookManager()

        # 定义一个安全钩子
        async def block_dangerous_commands(ctx: HookContext) -> HookResult:
            if ctx.tool_name == "bash":
                cmd = ctx.arguments.get("cmd", "")
                if "rm -rf" in cmd:
                    return HookResult(
                        proceed=False,
                        reason="危险命令被拦截：rm -rf"
                    )
            return HookResult(proceed=True)

        # 注册钩子
        manager.add_before_execute(block_dangerous_commands)

        # 在 Agent 中使用
        result = await manager.run_before_execute(ctx)
        if not result.proceed:
            # 拦截
        else:
            # 执行工具
    """

    def __init__(self) -> None:
        self._before_hooks: list[BeforeExecuteHook] = []

    def add_before_execute(self, hook: BeforeExecuteHook) -> None:
        """
        添加 before_execute 钩子。

        钩子按添加顺序执行，任一钩子返回 proceed=False 即拦截。
        """
        self._before_hooks.append(hook)

    def remove_before_execute(self, hook: BeforeExecuteHook) -> bool:
        """移除 before_execute 钩子"""
        if hook in self._before_hooks:
            self._before_hooks.remove(hook)
            return True
        return False

    def clear_hooks(self) -> None:
        """清空所有钩子"""
        self._before_hooks.clear()

    async def run_before_execute(self, ctx: HookContext) -> HookResult:
        """
        运行所有 before_execute 钩子。

        Returns:
            HookResult: 任一钩子拦截则返回拦截结果，否则返回 proceed=True
        """
        for hook in self._before_hooks:
            result = await hook(ctx)
            if not result.proceed:
                return result
        return HookResult(proceed=True)

    @property
    def has_hooks(self) -> bool:
        """是否有注册的钩子"""
        return len(self._before_hooks) > 0


# ============ 内置安全钩子 ============


def create_bash_safety_hook(
    blocked_commands: list[str] | None = None,
) -> BeforeExecuteHook:
    """
    创建 bash 工具的安全钩子。

    Args:
        blocked_commands: 要拦截的危险命令列表，默认为常见的危险命令

    Returns:
        BeforeExecuteHook: 钩子函数

    示例：
        hook = create_bash_safety_hook(["rm -rf", "sudo", "mkfs"])
        manager.add_before_execute(hook)
    """
    if blocked_commands is None:
        blocked_commands = [
            "rm -rf",
            "rm -fr",
            "sudo rm",
            "mkfs",
            "dd if=",
            "> /dev/sd",
            "chmod 777",
            "chown root",
            ":(){ :|:& };:",  # fork bomb
        ]

    async def bash_safety_hook(ctx: HookContext) -> HookResult:
        if ctx.tool_name != "bash":
            return HookResult(proceed=True)

        # 注意：BashTool 使用的参数名是 "command"，不是 "cmd"
        command = ctx.arguments.get("command", "")
        if not isinstance(command, str):
            return HookResult(proceed=True)

        for blocked in blocked_commands:
            if blocked in command:
                return HookResult(
                    proceed=False,
                    reason=f"安全拦截：命令包含危险操作 '{blocked}'",
                )

        return HookResult(proceed=True)

    return bash_safety_hook
