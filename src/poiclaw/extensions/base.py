"""扩展基类 - 所有扩展必须继承此类"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Literal

if TYPE_CHECKING:
    from poiclaw.core import BaseTool, HookContext, HookResult


@dataclass
class ExtensionTool:
    """扩展注册的工具信息"""

    definition: Any  # ToolDefinition
    extension_path: str = "<builtin>"


@dataclass
class ExtensionCommand:
    """扩展注册的命令信息"""

    name: str
    description: str
    handler: Callable[[list[str], "ExtensionContext"], Awaitable[None]]
    extension_path: str = "<builtin>"


@dataclass
class ExtensionContext:
    """
    扩展上下文 - 传递给事件处理器和命令处理器。

    Attributes:
        agent: Agent 实例（只读访问）
        cwd: 当前工作目录
        has_ui: 是否有 UI（目前始终为 False）
    """

    agent: Any  # Agent 类型，避免循环导入
    cwd: str
    has_ui: bool = False

    def get_tools(self) -> list[str]:
        """获取当前所有工具名称"""
        return self.agent.tools.get_all_names()

    def register_tool(self, tool: "BaseTool") -> None:
        """动态注册工具"""
        self.agent.tools.register(tool)

    def unregister_tool(self, name: str) -> bool:
        """注销工具"""
        return self.agent.tools.unregister(name)

    def add_message(self, role: str, content: str) -> None:
        """添加消息到对话历史"""
        from poiclaw.llm import Message

        if role == "user":
            self.agent.add_message(Message.user(content))
        elif role == "assistant":
            self.agent.add_message(Message.assistant(content))
        elif role == "system":
            self.agent.add_message(Message.system(content))

    def get_state(self) -> dict[str, Any]:
        """获取 Agent 当前状态"""
        return {
            "step": self.agent.state.step,
            "total_tool_calls": self.agent.state.total_tool_calls,
            "finished": self.agent.state.finished,
        }


# 事件类型定义
AgentEventType = Literal[
    "agent_start",
    "agent_end",
    "tool_call",
    "tool_result",
    "step_start",
    "step_end",
]


@dataclass
class AgentEvent:
    """Agent 事件基类"""

    type: AgentEventType


@dataclass
class AgentStartEvent(AgentEvent):
    """Agent 开始运行时触发"""

    type: AgentEventType = "agent_start"
    user_input: str = ""


@dataclass
class AgentEndEvent(AgentEvent):
    """Agent 结束运行时触发"""

    type: AgentEventType = "agent_end"
    final_response: str = ""
    total_steps: int = 0
    total_tool_calls: int = 0


@dataclass
class ToolCallEvent(AgentEvent):
    """工具调用前触发（可拦截）"""

    type: AgentEventType = "tool_call"
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str = ""


@dataclass
class ToolResultEvent(AgentEvent):
    """工具执行后触发（可修改结果）"""

    type: AgentEventType = "tool_result"
    tool_name: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)
    result_content: str = ""
    result_error: str | None = None
    tool_call_id: str = ""


@dataclass
class StepStartEvent(AgentEvent):
    """每一步开始时触发"""

    type: AgentEventType = "step_start"
    step: int = 0


@dataclass
class StepEndEvent(AgentEvent):
    """每一步结束时触发"""

    type: AgentEventType = "step_end"
    step: int = 0
    had_tool_calls: bool = False


# 事件处理器签名
EventHandler = Callable[[AgentEvent, ExtensionContext], Awaitable[None | dict[str, Any]]]

# 钩子函数签名
HookFunction = Callable[["HookContext"], Awaitable["HookResult"]]


class BaseExtension(ABC):
    """
    扩展抽象基类 - 所有扩展必须继承此类。

    设计理念（参考 pi-mono 的 extension 系统）：
        - 一个扩展专注于一个功能
        - 可注册工具、命令、事件处理器
        - 通过 get_hook() 提供安全拦截能力（AOP 切面）
        - 支持生命周期钩子 on_register/on_unregister

    扩展能力：
        1. 拦截工具调用（get_hook）
        2. 注册新工具（get_tools）
        3. 注册斜杠命令（get_commands）
        4. 订阅 Agent 事件（get_event_handlers）

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
                    # 拦截逻辑...
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

            async def _handle_hello(self, args: list[str], ctx: ExtensionContext):
                ctx.add_message("user", "你好！")
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

    # ============ 核心能力（可选择性实现） ============

    def get_hook(self) -> HookFunction | None:
        """
        返回该扩展提供的安全钩子函数。

        钩子签名：
            async def hook(ctx: HookContext) -> HookResult

        钩子会在工具执行前被调用，可以：
        - 检查工具参数
        - 决定是否拦截（proceed=False）
        - 返回拦截原因和假结果

        Returns:
            钩子函数，或 None（如果不提供拦截能力）
        """
        return None

    def get_tools(self) -> list[ExtensionTool]:
        """
        返回该扩展注册的工具列表。

        Returns:
            list[ExtensionTool]: 工具列表，默认为空
        """
        return []

    def get_commands(self) -> dict[str, ExtensionCommand]:
        """
        返回该扩展注册的命令字典。

        Returns:
            dict[str, ExtensionCommand]: 命令字典，key 为命令名（不含 /）
        """
        return {}

    def get_event_handlers(self) -> dict[AgentEventType, list[EventHandler]]:
        """
        返回该扩展订阅的事件处理器。

        Returns:
            dict: key 为事件类型，value 为处理器列表
        """
        return {}

    # ============ 生命周期钩子 ============

    async def on_register(self, ctx: ExtensionContext) -> None:
        """
        扩展被注册时调用。

        Args:
            ctx: 扩展上下文

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
        return f"<{self.__class__.__name__} name={self.name!r} version={self.version!r}>"
