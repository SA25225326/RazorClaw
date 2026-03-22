"""
扩展模块 - 提供可插拔的 Agent 扩展能力。

设计理念：
- 极简：每个扩展专注于一个功能
- AOP：通过 Hook 在工具执行前/后进行拦截
- 可组合：多个扩展可以组合使用

用法：
    from poiclaw.extensions import BaseExtension, SandboxExtension
    from poiclaw.core import HookManager

    # 创建扩展实例
    sandbox = SandboxExtension()

    # 获取钩子并注册到 HookManager
    hooks = HookManager()
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
            async def my_hook(ctx: HookContext) -> HookResult:
                # 你的拦截逻辑
                return HookResult(proceed=True)
            return my_hook
"""

from .base import BaseExtension
from .sandbox import SandboxExtension

__all__ = [
    "BaseExtension",
    "SandboxExtension",
]
