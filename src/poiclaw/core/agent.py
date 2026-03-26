"""Agent 核心 - ReAct 循环"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from poiclaw.llm import LLMClient, Message, ToolCall

from .compaction import CompactionSettings, compact, should_compact
from .events import (
    AgentEndEvent,
    AgentStartEvent,
    ContextCompactEvent,
    ErrorEvent,
    MessageUpdateEvent,
    ToolCallEndEvent,
    ToolCallErrorEvent,
    ToolCallStartEvent,
    TurnEndEvent,
    TurnStartEvent,
    EventEmitter,
)
from .hooks import HookContext, HookManager, HookResult
from .session import CompactionEntry, FileSessionManager, UsageStats
from .session_tree import TreeSessionManager
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

    会话管理：
        - 支持会话持久化（通过 session_manager）
        - 内存保护：只在 messages 为空时加载历史
        - 标题保护：保存时 title=None 保留原标题

    事件系统：
        - 通过 event_emitter 订阅和发射事件
        - 支持完整的 Agent 生命周期事件

    用法：
        # 基础用法（无会话持久化）
        agent = Agent(
            llm_client=LLMClient(...),
            tools=ToolRegistry(),
            hooks=HookManager(),
            config=AgentConfig(max_steps=10),
        )

        # 订阅事件
        @agent.event_emitter.on(EventType.AGENT_START)
        async def on_start(event: AgentStartEvent):
            print(f"Agent started: {event.user_input}")

        # 运行
        response = await agent.run("帮我列出当前目录的文件")
    """

    def __init__(
        self,
        llm_client: LLMClient,
        tools: ToolRegistry | None = None,
        hooks: HookManager | None = None,
        config: AgentConfig | None = None,
        # ===== 会话管理参数 =====
        session_manager: FileSessionManager | TreeSessionManager | None = None,
        session_id: str | None = None,
        # ===== 压缩配置 =====
        compaction_settings: CompactionSettings | None = None,
        # ===== 事件系统 =====
        event_emitter: EventEmitter | None = None,
        # ===== 渐进式工具加载 =====
        progressive_tools: bool = False,
    ) -> None:
        self.llm = llm_client
        self.tools = tools or ToolRegistry()
        self.hooks = hooks or HookManager()
        self.config = config or AgentConfig()
        self.messages: list[Message] = []
        self.state = AgentState()

        # ===== 会话管理属性 =====
        self.session_manager = session_manager
        self.session_id = session_id
        self._usage_stats = UsageStats.zero()
        self._session_loaded = False  # 防止重复加载

        # ===== 树形 Session 支持 =====
        self._is_tree_session = isinstance(session_manager, TreeSessionManager)
        self._entry_ids: list[str] = []  # 消息对应的 Entry ID（用于树形 Session）

        # ===== 压缩配置 =====
        self.compaction_settings = compaction_settings or CompactionSettings()
        self._compactions: list[CompactionEntry] = []  # 压缩历史
        self._last_summary: str | None = None  # 最新摘要缓存

        # ===== 事件系统 =====
        self.event_emitter = event_emitter or EventEmitter()

        # ===== 渐进式工具加载 =====
        self.progressive_tools = progressive_tools

    def add_message(self, message: Message) -> None:
        """添加消息到历史"""
        self.messages.append(message)

    def clear_messages(self) -> None:
        """清空对话历史（注意：不会删除持久化的会话文件）"""
        self.messages = []
        self.state = AgentState()
        self._usage_stats = UsageStats.zero()
        self._session_loaded = False

    def set_system_prompt(self, prompt: str) -> None:
        """设置系统提示词"""
        self.config.system_prompt = prompt

    def get_usage_stats(self) -> UsageStats:
        """获取当前的 Token 使用统计"""
        return self._usage_stats

    async def run(self, user_input: str) -> str:
        """
        核心 ReAct 循环。

        Args:
            user_input: 用户输入

        Returns:
            str: Agent 的最终回复
        """
        # ===== 发射 AGENT_START 事件 =====
        await self.event_emitter.emit(
            AgentStartEvent(
                agent_id=self.session_id,
                user_input=user_input,
                config=self.config,
            )
        )

        final_response: str | None = None
        error_message: str | None = None

        try:
            # ===== 内存保护：只在 messages 为空且未加载过时才加载历史 =====
            if (
                self.session_manager
                and self.session_id
                and len(self.messages) == 0
                and not self._session_loaded
            ):
                history = await self.session_manager.load_session(self.session_id)
                if history:
                    self.messages = history
                self._session_loaded = True

            # 重置状态（但不清空 messages）
            self.state = AgentState()

            # 添加用户消息
            user_msg = Message.user(user_input)
            self.add_message(user_msg)

            # ===== 发射 MESSAGE_UPDATE 事件 =====
            await self.event_emitter.emit(
                MessageUpdateEvent(
                    agent_id=self.session_id,
                    message=user_msg,
                    role=user_msg.role.value,
                    content_preview=user_input[:100] if user_input else None,
                )
            )

            # ===== 持久化用户消息 =====
            if self.session_manager and self.session_id:
                await self.session_manager.save_session(
                    session_id=self.session_id,
                    messages=self.messages,
                    title=None,  # title=None 触发标题保护逻辑
                    usage=self._usage_stats,
                )

            # ReAct 循环
            while self.state.step < self.config.max_steps:
                self.state.step += 1

                # ===== 发射 TURN_START 事件 =====
                await self.event_emitter.emit(
                    TurnStartEvent(
                        agent_id=self.session_id,
                        turn_number=self.state.step,
                    )
                )

                # 1. 构建上下文并调用 LLM
                context = await self._build_context()

                # 渐进式工具加载：不注入工具 Schema，让 Agent 用 list_tools 查询
                if self.progressive_tools:
                    llm_tools = None
                else:
                    llm_tools = self.tools.to_llm_tools() if self.tools else None

                response = await self.llm.chat(
                    messages=context,
                    tools=llm_tools if llm_tools else None,
                )

                # ===== 累积 Token 使用统计 =====
                # 注意：当前 LLMClient.chat() 返回的 Message 不包含 usage
                # 如果 LLM API 返回了 usage，需要在这里累积
                # self._usage_stats = self._usage_stats.merge(...)

                # 2. 添加 assistant 消息到历史
                assistant_msg = Message(
                    role=response.role,
                    content=response.content,
                    tool_calls=response.tool_calls,
                )
                self.add_message(assistant_msg)

                # ===== 发射 MESSAGE_UPDATE 事件 =====
                await self.event_emitter.emit(
                    MessageUpdateEvent(
                        agent_id=self.session_id,
                        message=assistant_msg,
                        role=assistant_msg.role.value,
                        content_preview=response.content[:100] if response.content else None,
                    )
                )

                # 3. 检查是否有工具调用
                if not response.tool_calls:
                    # 没有工具调用，返回最终回复
                    self.state.finished = True
                    final_response = response.content or ""

                    # ===== 发射 TURN_END 事件 =====
                    await self.event_emitter.emit(
                        TurnEndEvent(
                            agent_id=self.session_id,
                            turn_number=self.state.step,
                            llm_response=response.content,
                            tool_calls_made=0,
                        )
                    )

                    # ===== 循环结束后保存会话 =====
                    if self.session_manager and self.session_id:
                        await self.session_manager.save_session(
                            session_id=self.session_id,
                            messages=self.messages,
                            title=None,
                            usage=self._usage_stats,
                        )

                    return final_response

                # 4. 执行所有工具调用
                tools_this_turn = 0
                for tool_call in response.tool_calls:
                    self.state.total_tool_calls += 1
                    tool_result = await self._execute_tool(tool_call)
                    self.add_message(tool_result)
                    tools_this_turn += 1

                # ===== 发射 TURN_END 事件 =====
                await self.event_emitter.emit(
                    TurnEndEvent(
                        agent_id=self.session_id,
                        turn_number=self.state.step,
                        llm_response=response.content,
                        tool_calls_made=tools_this_turn,
                    )
                )

                # ===== 每轮循环后保存会话 =====
                if self.session_manager and self.session_id:
                    await self.session_manager.save_session(
                        session_id=self.session_id,
                        messages=self.messages,
                        title=None,
                        usage=self._usage_stats,
                    )

            # 超过最大步数
            self.state.finished = True
            final_response = (
                f"[Agent 达到最大步数限制 ({self.config.max_steps})，任务可能未完成]"
            )

            # ===== 保存会话 =====
            if self.session_manager and self.session_id:
                await self.session_manager.save_session(
                    session_id=self.session_id,
                    messages=self.messages,
                    title=None,
                    usage=self._usage_stats,
                )

            return final_response

        except Exception as e:
            error_message = str(e)
            # ===== 发射 ERROR 事件 =====
            await self.event_emitter.emit(
                ErrorEvent(
                    agent_id=self.session_id,
                    error_type=type(e).__name__,
                    error_message=error_message,
                )
            )
            raise
        finally:
            # ===== 发射 AGENT_END 事件 =====
            await self.event_emitter.emit(
                AgentEndEvent(
                    agent_id=self.session_id,
                    final_response=final_response,
                    state=self.state,
                    error=error_message,
                )
            )

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

        # ===== 发射 TOOL_CALL_START 事件 =====
        await self.event_emitter.emit(
            ToolCallStartEvent(
                agent_id=self.session_id,
                turn_number=self.state.step,
                tool_name=tool_name,
                tool_arguments=arguments,
            )
        )

        start_time = time.time()

        # 1. 查找工具
        tool = self.tools.get(tool_name)
        if tool is None:
            error_msg = f"错误：工具 '{tool_name}' 不存在"
            # ===== 发射 TOOL_CALL_ERROR 事件 =====
            await self.event_emitter.emit(
                ToolCallErrorEvent(
                    agent_id=self.session_id,
                    turn_number=self.state.step,
                    tool_name=tool_name,
                    error_type="ToolNotFound",
                    error_message=error_msg,
                )
            )
            return Message.tool_result(
                tool_call_id=tool_call.id,
                content=error_msg,
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
                duration_ms = int((time.time() - start_time) * 1000)
                # ===== 发射 TOOL_CALL_END 事件（拦截）=====
                await self.event_emitter.emit(
                    ToolCallEndEvent(
                        agent_id=self.session_id,
                        turn_number=self.state.step,
                        tool_name=tool_name,
                        success=False,
                        result_preview=f"[拦截] {reason}",
                        duration_ms=duration_ms,
                    )
                )
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
            error_msg = f"工具执行异常：{e}"
            duration_ms = int((time.time() - start_time) * 1000)
            # ===== 发射 TOOL_CALL_ERROR 事件 =====
            await self.event_emitter.emit(
                ToolCallErrorEvent(
                    agent_id=self.session_id,
                    turn_number=self.state.step,
                    tool_name=tool_name,
                    error_type=type(e).__name__,
                    error_message=error_msg,
                )
            )
            return Message.tool_result(
                tool_call_id=tool_call.id,
                content=error_msg,
            )

        # 4. 返回 tool_result 消息
        duration_ms = int((time.time() - start_time) * 1000)
        # ===== 发射 TOOL_CALL_END 事件 =====
        await self.event_emitter.emit(
            ToolCallEndEvent(
                agent_id=self.session_id,
                turn_number=self.state.step,
                tool_name=tool_name,
                success=True,
                result_preview=content[:100] if content else None,
                duration_ms=duration_ms,
            )
        )
        return Message.tool_result(
            tool_call_id=tool_call.id,
            content=content,
        )

    async def _build_context(self) -> list[Message]:
        """
        构建发送给 LLM 的上下文。

        包括：system prompt（如果有）+ [摘要] + 对话历史

        树形 Session 支持：
            - 如果使用 TreeSessionManager，使用 build_session_context() 构建上下文
            - 自动处理 compaction 路径

        压缩逻辑：
            1. 检查是否需要压缩（should_compact）
            2. 如果需要，执行压缩并更新会话
            3. 返回压缩后的上下文

        渐进式工具加载：
            - 如果 progressive_tools=True，在 system prompt 末尾添加工具简介
        """
        context: list[Message] = []

        # 构建 system prompt
        system_prompt = self.config.system_prompt or ""

        # 渐进式模式：把工具简介加到 system prompt
        if self.progressive_tools and self.tools:
            tools_brief = self.tools.to_brief()
            if system_prompt:
                system_prompt = f"{system_prompt}\n\n{tools_brief}"
            else:
                system_prompt = tools_brief

        # 添加 system prompt
        if system_prompt:
            context.append(Message.system(system_prompt))

        # ===== 树形 Session：使用 build_session_context =====
        if self._is_tree_session and self.session_manager:
            # 树形 Session 的上下文构建由 TreeSessionManager 处理
            # compaction 已经在 get_branch() 路径中处理
            context.extend(self.messages)
            return context

        # ===== 扁平 Session：检查是否需要压缩 =====
        if should_compact(self.messages, self.compaction_settings):
            await self._run_compaction()

        # ===== 添加摘要（如果有）=====
        if self._last_summary:
            summary_content = f"""[上下文摘要]

{self._last_summary}

---
*以上是对之前对话的摘要，保留关键信息以便继续工作。*
"""
            context.append(Message.system(summary_content))

        # 添加对话历史
        context.extend(self.messages)

        return context

    async def _run_compaction(self) -> None:
        """
        执行上下文压缩。

        流程：
            1. 调用 compaction.compact() 生成摘要
            2. 更新压缩历史
            3. 更新消息列表（替换为摘要 + 保留消息）
            4. 持久化压缩条目

        树形 Session 支持：
            - 传递 entry_ids 以生成 first_kept_entry_id
            - 使用 TreeSessionManager.append_compaction() 持久化
        """
        result = await compact(
            messages=self.messages,
            llm=self.llm,
            settings=self.compaction_settings,
            previous_summary=self._last_summary,
            entry_ids=self._entry_ids if self._is_tree_session else None,
        )

        if result is None:
            return  # 无需压缩

        # 更新状态
        self._compactions.append(result.entry)
        self._last_summary = result.entry.summary
        self.messages = result.kept_messages

        # ===== 树形 Session：更新 entry_ids =====
        if self._is_tree_session and result.first_kept_entry_id:
            # 找到 first_kept_entry_id 在 entry_ids 中的索引
            try:
                keep_idx = self._entry_ids.index(result.first_kept_entry_id)
                self._entry_ids = self._entry_ids[keep_idx:]
            except ValueError:
                pass

        # ===== 发射 CONTEXT_COMPACT 事件 =====
        await self.event_emitter.emit(
            ContextCompactEvent(
                agent_id=self.session_id,
                tokens_before=result.entry.tokens_before,
                tokens_after=result.entry.tokens_after,
                tokens_saved=result.tokens_saved,
                summary_preview=result.entry.summary[:100],
            )
        )

        print(
            f"[Agent] 上下文压缩完成："
            f"{result.entry.tokens_before} -> {result.entry.tokens_after} tokens "
            f"(节省 {result.tokens_saved})"
        )

        # 持久化压缩条目
        if self.session_manager and self.session_id:
            if self._is_tree_session:
                # 树形 Session：使用 append_compaction
                tree_manager: TreeSessionManager = self.session_manager  # type: ignore
                tree_manager.append_compaction(
                    summary=result.entry.summary,
                    first_kept_entry_id=result.first_kept_entry_id or "",
                    tokens_before=result.entry.tokens_before,
                    tokens_after=result.entry.tokens_after,
                )
            else:
                # 扁平 Session：使用 add_compaction
                await self.session_manager.add_compaction(self.session_id, result.entry)

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

            context = await self._build_context()

            # 渐进式工具加载：不注入工具 Schema，让 Agent 用 list_tools 查询
            if self.progressive_tools:
                llm_tools = None
            else:
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
