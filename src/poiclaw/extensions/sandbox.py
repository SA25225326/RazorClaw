"""安全沙箱扩展 - 使用正则表达式拦截高危 bash 命令"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from .base import BaseExtension

if TYPE_CHECKING:
    from poiclaw.core import HookContext, HookResult


class SandboxExtension(BaseExtension):
    """
    安全沙箱扩展。

    使用正则表达式检查 bash 工具的 command 参数，
    一旦发现 rm -rf、wget、curl 等高危敏感词，直接阻断执行，
    并向 LLM 返回详细的拦截消息，高详细的报错提示能帮助 LLM 在
    ReAct 循环中进行更好的自我纠错。

    用法：
        from poiclaw.extensions import SandboxExtension
        from poiclaw.core import HookManager

        sandbox = SandboxExtension()
        hooks = HookManager()
        hooks.add_before_execute(sandbox.get_hook())

    自定义危险模式：
        sandbox = SandboxExtension(
            patterns=[
                r"rm\\s+(-[rf]+\\s+|.*\\s+-[rf]+)",
                r"sudo\\s+",
            ],
            custom_message="自定义拦截消息",
        )
    """

    # 默认高危命令正则模式
    DEFAULT_PATTERNS: list[str] = [
        # rm -rf 变体（包括 rm -rf, rm -fr, rm -r -f 等）
        r"rm\s+(-[rf]+\s+|.*\s+-[rf]+)",
        r"rm\s+-[a-z]*r[a-z]*f",
        # 下载工具
        r"wget\s+",
        r"curl\s+.*(-o|--output)\s",
        # 提权
        r"sudo\s+",
        # 磁盘操作
        r"mkfs",
        r"dd\s+.*of=/dev/",
        r">\s*/dev/sd",
        r">\s*/dev/hd",
        # 危险权限
        r"chmod\s+(-R\s+)?777",
        r"chown\s+.*root",
        # Fork bomb
        r":\(\)\s*\{\s*:\|:&\s*\}\s*;:",
    ]

    def __init__(
        self,
        patterns: list[str] | None = None,
        custom_message: str | None = None,
    ) -> None:
        """
        初始化安全沙箱扩展。

        Args:
            patterns: 自定义危险模式列表，默认使用 DEFAULT_PATTERNS
            custom_message: 自定义拦截消息模板，可用 {command} 和 {pattern} 占位符
        """
        self._patterns = patterns if patterns is not None else self.DEFAULT_PATTERNS
        self._custom_message = custom_message
        # 预编译正则表达式以提高性能
        self._compiled_patterns: list[re.Pattern] = [
            re.compile(p, re.IGNORECASE) for p in self._patterns
        ]

    @property
    def name(self) -> str:
        return "sandbox"

    @property
    def description(self) -> str:
        return "安全沙箱：使用正则表达式拦截 rm -rf、wget、curl 等高危命令"

    def get_hook(self):
        """
        返回安全沙箱钩子函数。

        Returns:
            异步钩子函数，签名：(ctx: HookContext) -> Awaitable[HookResult]
        """
        compiled_patterns = self._compiled_patterns
        custom_message = self._custom_message

        async def sandbox_hook(ctx: "HookContext") -> "HookResult":
            # 导入放在函数内部避免循环导入
            from poiclaw.core import HookResult

            # 只检查 bash 工具
            if ctx.tool_name != "bash":
                return HookResult(proceed=True)

            # 获取命令参数（注意：BashTool 使用的参数名是 command）
            command = ctx.arguments.get("command", "")
            if not isinstance(command, str) or not command:
                return HookResult(proceed=True)

            # 使用正则表达式匹配危险模式
            for pattern in compiled_patterns:
                match = pattern.search(command)
                if match:
                    # 构建详细的拦截消息
                    if custom_message:
                        reason = custom_message.format(
                            command=command,
                            pattern=pattern.pattern,
                        )
                    else:
                        reason = (
                            f"[安全拦截] 命令 '{command}' 匹配危险模式 "
                            f"'{pattern.pattern}'，已被沙箱拒绝执行。"
                            f"请思考并使用其他安全的命令重试。"
                        )
                    return HookResult(
                        proceed=False,
                        reason=reason,
                    )

            # 未匹配任何危险模式，放行
            return HookResult(proceed=True)

        return sandbox_hook
