"""
SubagentTool - 多智能体协作工具 (Tool-based Fork-Join 模式)

派生子智能体执行任务，支持三种模式：
- single: 单任务
- parallel: 并行执行多个任务
- chain: 串行链式执行（前一个结果作为下一个的上下文）

安全设计：子 Agent 必须继承 hooks，确保 SandboxExtension 在所有子节点生效。
"""

from __future__ import annotations

import asyncio
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from poiclaw.core import Agent, AgentConfig, BaseTool, ToolResult

if TYPE_CHECKING:
    from poiclaw.core import HookManager, LLMClient, ToolRegistry


class SubagentMode(str, Enum):
    """子智能体执行模式"""

    SINGLE = "single"
    PARALLEL = "parallel"
    CHAIN = "chain"


class SubagentTask(BaseModel):
    """单个子任务定义"""

    agent_role: str  # 子 Agent 角色设定（如 "代码审查员"、"测试工程师"）
    instruction: str  # 具体任务指令


class SubagentParams(BaseModel):
    """SubagentTool 的完整参数 Schema"""

    mode: SubagentMode  # 执行模式
    tasks: list[SubagentTask]  # 子任务列表
    max_steps: int = 5  # 每个子 Agent 最大步数


class SubagentTool(BaseTool):
    """
    多智能体协作工具 - Fork-Join 模式。

    核心特性：
    - 子 Agent 拥有独立的上下文（messages），不污染主 Agent
    - 子 Agent 必须继承 hooks，确保安全沙箱规则生效
    - 支持 single/parallel/chain 三种执行模式
    - 完善的异常处理，不会导致主程序崩溃

    用法：
        # 在创建 Agent 时注册
        tools = ToolRegistry()
        register_all_tools(tools)

        # SubagentTool 需要额外注入依赖
        subagent_tool = SubagentTool(
            llm_client=llm,
            base_tools=tools,
            hooks=hooks,  # 必须传递，确保安全沙箱继承
        )
        tools.register(subagent_tool)

    LLM 调用示例：
        {
            "mode": "parallel",
            "tasks": [
                {"agent_role": "前端专家", "instruction": "分析 UI 组件结构"},
                {"agent_role": "后端专家", "instruction": "分析 API 接口设计"}
            ]
        }
    """

    def __init__(
        self,
        llm_client: LLMClient,
        base_tools: ToolRegistry,
        hooks: HookManager,
    ):
        """
        初始化 SubagentTool。

        Args:
            llm_client: LLM 客户端（用于创建子 Agent）
            base_tools: 基础工具集（子 Agent 复用）
            hooks: 钩子管理器（必须传递，确保安全沙箱继承）
        """
        self._llm_client = llm_client
        self._base_tools = base_tools
        self._hooks = hooks  # 安全：必须继承 hooks

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def description(self) -> str:
        return """派生子智能体执行任务，支持三种模式：
- single: 单任务 (mode="single", tasks=[一个任务])
- parallel: 并行执行多个任务 (mode="parallel", tasks=[多个任务])
- chain: 串行链式执行，前一个结果作为下一个的上下文 (mode="chain", tasks=[多个任务])

参数说明：
- agent_role: 子 Agent 的角色设定
- instruction: 具体任务指令
- max_steps: 每个子 Agent 最大执行步数（默认 5）"""

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["single", "parallel", "chain"],
                    "description": "执行模式：single(单任务)、parallel(并行)、chain(串行链式)",
                },
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_role": {
                                "type": "string",
                                "description": "子 Agent 的角色设定（如 '代码审查员'、'测试工程师'）",
                            },
                            "instruction": {
                                "type": "string",
                                "description": "具体任务指令",
                            },
                        },
                        "required": ["agent_role", "instruction"],
                    },
                    "description": "子任务列表",
                },
                "max_steps": {
                    "type": "integer",
                    "description": "每个子 Agent 最大执行步数（默认 5）",
                    "default": 5,
                },
            },
            "required": ["mode", "tasks"],
        }

    async def execute(
        self,
        mode: str,
        tasks: list[dict[str, str]],
        max_steps: int = 5,
    ) -> ToolResult:
        """
        执行子智能体任务。

        Args:
            mode: 执行模式 (single/parallel/chain)
            tasks: 子任务列表，每个包含 agent_role 和 instruction
            max_steps: 每个子 Agent 最大步数

        Returns:
            ToolResult: 聚合后的执行结果
        """
        try:
            # 1. 参数校验
            validated_tasks = [SubagentTask(**t) for t in tasks]
            validated_mode = SubagentMode(mode)
            params = SubagentParams(
                mode=validated_mode,
                tasks=validated_tasks,
                max_steps=max_steps,
            )

            # 2. 根据模式分发
            if params.mode == SubagentMode.SINGLE:
                if len(params.tasks) != 1:
                    return ToolResult(
                        success=False,
                        content="",
                        error="single 模式需要且仅需要一个任务",
                    )
                result = await self._run_single(params.tasks[0], params.max_steps)

            elif params.mode == SubagentMode.PARALLEL:
                if len(params.tasks) < 2:
                    return ToolResult(
                        success=False,
                        content="",
                        error="parallel 模式需要至少 2 个任务",
                    )
                result = await self._run_parallel(params.tasks, params.max_steps)

            elif params.mode == SubagentMode.CHAIN:
                if len(params.tasks) < 2:
                    return ToolResult(
                        success=False,
                        content="",
                        error="chain 模式需要至少 2 个任务",
                    )
                result = await self._run_chain(params.tasks, params.max_steps)

            return ToolResult(success=True, content=result)

        except ValueError as e:
            return ToolResult(success=False, content="", error=f"参数错误: {e}")
        except Exception as e:
            # 容错：任何异常都不崩溃主程序
            return ToolResult(
                success=False,
                content="",
                error=f"SubagentTool 执行失败: {type(e).__name__}: {e}",
            )

    # ============ 私有方法：三种执行模式 ============

    async def _run_single(
        self,
        task: SubagentTask,
        max_steps: int,
    ) -> str:
        """
        单任务模式：创建一个隔离的子 Agent 执行。

        安全：子 Agent 必须继承 hooks，确保沙箱规则生效。
        """
        sub_agent = self._create_sub_agent(task.agent_role, max_steps)
        result = await sub_agent.run(task.instruction)
        return result

    async def _run_parallel(
        self,
        tasks: list[SubagentTask],
        max_steps: int,
    ) -> str:
        """
        并行模式：asyncio.gather 并发运行多个子 Agent。

        Fork: 并发启动所有子 Agent
        Join: 聚合结果（Markdown 格式）
        """

        async def run_one(task: SubagentTask) -> tuple[str, str, bool]:
            """封装单个任务，返回 (agent_role, result, success)"""
            try:
                sub_agent = self._create_sub_agent(task.agent_role, max_steps)
                result = await sub_agent.run(task.instruction)
                return (task.agent_role, result, True)
            except Exception as e:
                return (task.agent_role, f"执行失败: {e}", False)

        # Fork: 并发启动所有子 Agent
        results = await asyncio.gather(*[run_one(t) for t in tasks])

        # Join: 聚合结果（Markdown 格式）
        output_parts = ["# 并行执行结果\n"]
        success_count = sum(1 for _, _, success in results if success)

        for i, (role, result, success) in enumerate(results, 1):
            status = "✅" if success else "❌"
            output_parts.append(f"## {status} [{role}] (任务 {i})\n")
            output_parts.append(f"{result}\n")
            output_parts.append("---\n")

        output_parts.append(f"\n**统计**: {success_count}/{len(results)} 成功")
        return "\n".join(output_parts)

    async def _run_chain(
        self,
        tasks: list[SubagentTask],
        max_steps: int,
    ) -> str:
        """
        串行链式模式：前一个结果作为下一个的上下文。

        流程：Task1 → result1 → Task2(result1) → result2 → ...
        """
        previous_result = ""
        all_results = []

        for i, task in enumerate(tasks, 1):
            # 1. 拼接上下文到 instruction
            if previous_result:
                enhanced_instruction = f"""{task.instruction}

---
**前置上下文（上一阶段输出）**：
{previous_result}
"""
            else:
                enhanced_instruction = task.instruction

            # 2. 创建子 Agent 执行
            sub_agent = self._create_sub_agent(task.agent_role, max_steps)

            try:
                result = await sub_agent.run(enhanced_instruction)
                all_results.append((task.agent_role, result, True))
                previous_result = result
            except Exception as e:
                all_results.append((task.agent_role, str(e), False))
                # 链式模式：遇到错误停止
                break

        # 3. 聚合结果
        output_parts = ["# 链式执行结果\n"]
        for i, (role, result, success) in enumerate(all_results, 1):
            status = "✅" if success else "❌"
            output_parts.append(f"## {status} Step {i}: [{role}]\n")
            output_parts.append(f"{result}\n")
            output_parts.append("---\n")

        if len(all_results) < len(tasks):
            output_parts.append(
                f"\n⚠️ **链式执行在第 {len(all_results)} 步中断**"
            )

        return "\n".join(output_parts)

    # ============ 辅助方法 ============

    def _create_sub_agent(self, agent_role: str, max_steps: int) -> Agent:
        """
        创建一个隔离的子 Agent。

        关键安全设计：
        - 复用主 Agent 的 LLM 客户端
        - 复用主 Agent 的工具集
        - 【必须】继承 hooks，确保 SandboxExtension 生效
        - 独立的 messages 上下文（不污染主 Agent）
        """
        return Agent(
            llm_client=self._llm_client,
            tools=self._base_tools,
            hooks=self._hooks,  # 【安全】必须继承 hooks
            config=AgentConfig(
                max_steps=max_steps,
                system_prompt=self._build_system_prompt(agent_role),
            ),
        )

    def _build_system_prompt(self, agent_role: str) -> str:
        """根据角色生成系统提示词"""
        return f"""你是一个专门的子智能体，角色是：{agent_role}

你的任务：
1. 专注于你被分配的具体任务
2. 高效完成，不要过度扩展
3. 输出简洁清晰的结果

记住：你是 {agent_role}，请扮演好这个角色。
"""
