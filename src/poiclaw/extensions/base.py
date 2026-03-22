"""扩展基类 - 所有扩展必须继承此类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Awaitable, Callable

if TYPE_CHECKING:
    from poiclaw.core import HookContext, HookResult


class BaseExtension(ABC):
    """
    扩展抽象基类 - 所有扩展必须继承此类。

    设计理念：
        - 一个扩展专注于一个功能
        - 通过 get_hook() 提供安全拦截能力（AOP 切面）
        - 支持生命周期钩子 on_register/on_unregister

    责任链模式：
        多个扩展可以按顺序注册，形成责任链。
        HookManager 会依次调用每个扩展的钩子，
        任一钩子返回 proceed=False 即终止链条。

    用法：
        class MyExtension(BaseExtension):
            @property
            def name(self) -> str:
                return "my_extension"

            def get_hook(self):
                async def my_hook(ctx: HookContext) -> HookResult:
                    # 检查逻辑...
                    return HookResult(proceed=True)
                return my_hook

        # 使用
        ext = MyExtension()
        hooks.add_before_execute(ext.get_hook())
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        扩展名称（唯一标识）。

        Returns:
            str: 扩展的唯一名称，用于日志和调试
        """
        pass

    @property
    def description(self) -> str:
        """
        扩展描述。

        Returns:
            str: 扩展的功能描述，默认为空字符串
        """
        return ""

    @property
    def version(self) -> str:
        """
        扩展版本。

        Returns:
            str: 版本号，默认为 "1.0.0"
        """
        return "1.0.0"

    @abstractmethod
    def get_hook(self) -> Callable[[HookContext], Awaitable[HookResult]]:
        """
        返回该扩展提供的安全钩子函数。

        钩子签名：
            async def hook(ctx: HookContext) -> HookResult

        钩子会在工具执行前被调用，可以：
        - 检查工具参数
        - 决定是否拦截（proceed=False）
        - 返回拦截原因和假结果

        Returns:
            钩子函数，接收 HookContext，返回 Awaitable[HookResult]
        """
        pass

    async def on_register(self) -> None:
        """
        扩展被注册时调用。

        可以在此执行初始化逻辑，如：
        - 加载配置
        - 建立连接
        - 预热缓存
        """
        pass

    async def on_unregister(self) -> None:
        """
        扩展被注销时调用。

        可以在此执行清理逻辑，如：
        - 释放资源
        - 关闭连接
        - 保存状态
        """
        pass

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r}>"
