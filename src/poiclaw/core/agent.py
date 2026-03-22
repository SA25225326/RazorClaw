"""Agent 核心 - ReAct 循环"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from poiclaw.llm import LLMClient, Message, ToolCall

from .hooks import HookContext, HookManager, HookResult
from .tools import BaseTool, ToolRegistry, ToolResult


@dataclass
class AgentConfig:
    """
    Agent 配置。

    Attributes:
        max_steps: 最大循环步数，防止死循环
        system_prompt: 系统提示词
    """

    max_steps: int = 10
    system_prompt: str | None = None


@dataclass
class AgentState:
    """
    Agent 运行状态。

    Attributes:
        step: 当前步数
        total_tool_calls: 总工具调用次数
        finished: 是否已完成
    """

    step: int = 0
    total_tool_calls: int = 0
    finished: bool = False


class Agent:
    """
    ReAct 循环 Agent。

    核心流程：
        1. 接收用户输入
        2. 调用 LLM 获取回复
        3. 如果 LLM 返回 tool_calls -> 执行工具 -> 追加结果 -> 回到步骤 2
        4. 如果 LLM 没有返回 tool_calls -> 返回最终回复
        5. 超过 max_steps -> 强制停止

    用法：
        agent = Agent(
            llm_client=LLMClient(...),
            tools=ToolRegistry(),
            hooks=HookManager(),
            config=AgentConfig(max_steps=10),
        )

        # 注册工具
        agent.tools.register(BashTool())

        # 添加安全钩子
        agent.hooks.add_before_execute(block_dangerous_commands)

        # 运行
        response = await agent.run("帮我列出当前目录的文件")
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tools: ToolRegistry | None = None,
        hooks: HookManager | None = None,
        config: AgentConfig | None = None,
    ) -> None:
        self.llm = llm_client
        self.tools = tools or ToolRegistry()
        self.hooks = hooks or HookManager()
        self.config = config or AgentConfig()
        self.messages: list[Message] = []
        self.state = AgentState()

    def add_message(self, message: Message) -> None:
        """添加消息到历史"""
        self.messages.append(message)

    def clear_messages(self) -> None:
        """清空对话历史"""
        self.messages = []
        self.state = AgentState()

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词"""
        self.config.system_prompt = prompt

    async def run(self, user_input: str) -> str:
        """
        核心 ReAct 循环。

        Args:
            user_input: 用户输入

        Returns:
            str: Agent 的最终回复
        """
        # 重置状态
        self.state = AgentState()

        # 添加用户消息
        self.add_message(Message.user(user_input))

        # ReAct 循环
        while self.state.step < self.config.max_steps:
            self.state.step += 1

            # 1. 构建上下文并调用 LLM
            context = self._build_context()
            llm_tools = self.tools.to_llm_tools() if self.tools else None

            response = await self.llm.chat(
                messages=context,
                tools=llm_tools if llm_tools else None,
            )

            # 2. 添加 assistant 消息到历史
            self.add_message(Message(
                role=response.role,
                content=response.content,
                tool_calls=response.tool_calls,
            ))

            # 3. 检查是否有工具调用
            if not response.tool_calls:
                # 没有工具调用，返回最终回复
                self.state.finished = True
                return response.content or ""

            # 4. 执行所有工具调用
            for tool_call in response.tool_calls:
                self.state.total_tool_calls += 1
                tool_result = await self._execute_tool(tool_call)
                self.add_message(tool_result)

        # 超过最大步数
        self.state.finished = True
        return f"[Agent 达到最大步数限制 ({self.config.max_steps})，任务可能未完成]"

    async def _execute_tool(self, tool_call: ToolCall) -> Message:
        """
        执行单个工具调用。

        流程：
            1. 查找工具
            2. 运行 before_execute 钩子
            3. 如果拦截 -> 返回假结果
            4. 如果通过 -> 执行工具
            5. 返回 tool_result 消息

        Args:
            tool_call: 工具调用

        Returns:
            Message: tool_result 消息
        """
        tool_name = tool_call.function.name
        arguments = tool_call.function.parse_arguments()

        # 1. 查找工具
        tool = self.tools.get(tool_name)
        if tool is None:
            return Message.tool_result(
                tool_call_id=tool_call.id,
                content=f"错误：工具 '{tool_name}' 不存在",
            )

        # 2. 运行 before_execute 钩子
        if self.hooks.has_hooks:
            ctx = HookContext(
                tool_name=tool_name,
                arguments=arguments,
                tool=tool,
            )
            hook_result = await self.hooks.run_before_execute(ctx)

            if not hook_result.proceed:
                # 拦截：返回假结果
                reason = hook_result.reason or "工具调用被拦截"
                return Message.tool_result(
                    tool_call_id=tool_call.id,
                    content=f"[拦截] {reason}",
                )

        # 3. 执行工具
        try:
            result: ToolResult = await tool.execute(**arguments)
            content = result.content
            if result.error:
                content = f"错误：{result.error}"
        except Exception as e:
            content = f"工具执行异常：{e}"

        # 4. 返回 tool_result 消息
        return Message.tool_result(
            tool_call_id=tool_call.id,
            content=content,
        )

    def _build_context(self) -> list[Message]:
        """
        构建发送给 LLM 的上下文。

        包括：system prompt（如果有）+ 对话历史
        """
        context: list[Message] = []

        # 添加 system prompt
        if self.config.system_prompt:
            context.append(Message.system(self.config.system_prompt))

        # 添加对话历史
        context.extend(self.messages)

        return context

    # ============ 流式版本（可选） ============

    async def run_stream(self, user_input: str) -> Any:
        """
        流式 ReAct 循环（返回生成器）。

        注意：流式版本在工具调用时会累积完整响应，
        只有在 LLM 输出文本时才真正流式。

        Yields:
            StreamEvent: 流式事件
        """
        from poiclaw.llm import StreamEventType

        self.state = AgentState()
        self.add_message(Message.user(user_input))

        while self.state.step < self.config.max_steps:
            self.state.step += 1

            context = self._build_context()
            llm_tools = self.tools.to_llm_tools() if self.tools else None

            # 流式调用 LLM
            accumulated_content = ""
            accumulated_tool_calls: list[ToolCall] = []

            async for event in self.llm.stream(
                messages=context,
                tools=llm_tools,
            ):
                if event.type == StreamEventType.TEXT_DELTA and event.delta:
                    accumulated_content += event.delta
                    yield event
                elif event.type == StreamEventType.TOOL_CALL and event.tool_call:
                    accumulated_tool_calls.append(event.tool_call)
                elif event.type == StreamEventType.DONE:
                    pass

            # 添加 assistant 消息
            self.add_message(Message(
                role="assistant",
                content=accumulated_content or None,
                tool_calls=accumulated_tool_calls or None,
            ))

            # 没有工具调用，结束
            if not accumulated_tool_calls:
                self.state.finished = True
                return

            # 执行工具
            for tool_call in accumulated_tool_calls:
                self.state.total_tool_calls += 1
                tool_result = await self._execute_tool(tool_call)
                self.add_message(tool_result)

        self.state.finished = True
