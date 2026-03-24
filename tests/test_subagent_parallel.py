"""测试 Subagent 并行效率

对比 parallel vs chain 模式的执行时间。
使用模拟任务避免真实 LLM 调用成本。
"""

import asyncio
import sys
import time

# 修复 Windows 控制台编码问题
sys.stdout.reconfigure(encoding="utf-8")


async def mock_task(task_id: int, duration: float = 2.0) -> str:
    """模拟一个耗时任务（如 LLM 调用）"""
    await asyncio.sleep(duration)
    return f"任务 {task_id} 完成（耗时 {duration}s）"


async def run_sequential(num_tasks: int, task_duration: float) -> tuple[str, float]:
    """串行执行（模拟 chain 模式）"""
    start = time.time()
    results = []
    for i in range(num_tasks):
        result = await mock_task(i, duration=task_duration)
        results.append(result)
    elapsed = time.time() - start
    return "\n".join(results), elapsed


async def run_parallel(num_tasks: int, task_duration: float) -> tuple[str, float]:
    """并行执行（模拟 parallel 模式）"""
    start = time.time()
    coroutines = [mock_task(i, duration=task_duration) for i in range(num_tasks)]
    results = await asyncio.gather(*coroutines)
    elapsed = time.time() - start
    return "\n".join(results), elapsed


async def test_parallel_efficiency():
    """测试并行效率"""
    num_tasks = 3
    task_duration = 1.5  # 每个任务 1.5 秒

    print("=" * 60)
    print("📊 Subagent 并行效率测试")
    print("=" * 60)
    print(f"任务数量: {num_tasks}")
    print(f"单任务耗时: {task_duration} 秒")
    print("-" * 60)

    # 1. 串行执行（chain 模式）
    print("\n🔄 串行执行中...")
    _, seq_time = await run_sequential(num_tasks, task_duration)
    print(f"   完成: {seq_time:.2f} 秒")

    # 2. 并行执行（parallel 模式）
    print("\n⚡ 并行执行中...")
    _, par_time = await run_parallel(num_tasks, task_duration)
    print(f"   完成: {par_time:.2f} 秒")

    # 3. 计算效率提升
    speedup = seq_time / par_time
    time_saved = seq_time - par_time
    efficiency = (speedup / num_tasks) * 100  # 并行效率

    print("-" * 60)
    print(f"串行耗时: {seq_time:.2f} 秒")
    print(f"并行耗时: {par_time:.2f} 秒")
    print("-" * 60)
    print(f"✅ 效率提升: {speedup:.1f}x")
    print(f"✅ 节省时间: {time_saved:.2f} 秒 ({time_saved / seq_time * 100:.1f}%)")
    print(f"✅ 并行效率: {efficiency:.1f}% (理论最大 {num_tasks * 100}%)")
    print("=" * 60)

    # 验证
    assert speedup > 1.5, f"并行应该有明显加速，实际 {speedup:.1f}x"
    print(f"\n🎉 测试通过！并行模式加速 {speedup:.1f}x")

    return speedup


async def test_different_task_counts():
    """测试不同任务数量的效率"""
    print("\n" + "=" * 60)
    print("📈 不同任务数量对比")
    print("=" * 60)

    task_duration = 1.0
    task_counts = [2, 3, 4, 5]

    print(f"\n单任务耗时: {task_duration} 秒\n")
    print(f"{'任务数':<8} {'串行':>10} {'并行':>10} {'加速比':>10} {'节省':>10}")
    print("-" * 60)

    for n in task_counts:
        _, seq_time = await run_sequential(n, task_duration)
        _, par_time = await run_parallel(n, task_duration)
        speedup = seq_time / par_time
        saved = seq_time - par_time

        print(f"{n:<8} {seq_time:>10.2f}s {par_time:>10.2f}s {speedup:>9.1f}x {saved:>9.2f}s")

    print("=" * 60)


async def test_with_real_subagent_tool():
    """使用真实 SubagentTool 测试（需要 mock LLM）"""
    print("\n" + "=" * 60)
    print("🔧 真实 SubagentTool 测试（Mock LLM）")
    print("=" * 60)

    from unittest.mock import AsyncMock, MagicMock

    from poiclaw.core import Agent, AgentConfig, HookManager, ToolRegistry
    from poiclaw.llm import Message
    from poiclaw.tools.subagent import SubagentMode, SubagentTool

    # 1. 创建 Mock LLM（模拟 1.5 秒延迟）
    async def mock_chat(messages: list[Message], tools=None) -> Message:
        await asyncio.sleep(1.5)
        return Message.assistant("任务完成")

    mock_llm = MagicMock()
    mock_llm.chat = AsyncMock(side_effect=mock_chat)

    # 2. 创建工具和钩子
    tools = ToolRegistry()
    hooks = HookManager()

    # 3. 创建 SubagentTool
    subagent_tool = SubagentTool(
        llm_client=mock_llm,
        base_tools=tools,
        hooks=hooks,
    )

    # 4. 测试 parallel 模式
    print("\n⚡ 测试 parallel 模式（3 个任务）...")
    tasks = [
        {"agent_role": "分析师", "instruction": "分析代码"},
        {"agent_role": "审查员", "instruction": "审查代码"},
        {"agent_role": "测试员", "instruction": "测试代码"},
    ]

    start = time.time()
    result = await subagent_tool.execute(
        mode="parallel",
        tasks=tasks,
        max_steps=1,
    )
    parallel_time = time.time() - start

    print(f"   耗时: {parallel_time:.2f}s")
    print(f"   成功: {result.success}")

    # 5. 测试 chain 模式
    print("\n🔄 测试 chain 模式（3 个任务）...")
    start = time.time()
    result = await subagent_tool.execute(
        mode="chain",
        tasks=tasks,
        max_steps=1,
    )
    chain_time = time.time() - start

    print(f"   耗时: {chain_time:.2f}s")
    print(f"   成功: {result.success}")

    # 6. 对比
    speedup = chain_time / parallel_time
    print("-" * 60)
    print(f"Chain 耗时: {chain_time:.2f}s")
    print(f"Parallel 耗时: {parallel_time:.2f}s")
    print(f"加速比: {speedup:.1f}x")
    print("=" * 60)

    assert speedup > 1.5, f"Parallel 应该更快，实际 {speedup:.1f}x"
    print(f"\n🎉 真实 SubagentTool 测试通过！")


async def test_overhead_analysis():
    """分析并行开销"""
    print("\n" + "=" * 60)
    print("🔬 并行开销分析")
    print("=" * 60)

    # 理论上，asyncio.gather 的开销应该非常小
    # 这里测试非常短的任务，看看开销

    async def tiny_task():
        await asyncio.sleep(0.01)  # 10ms
        return "done"

    # 串行
    start = time.time()
    for _ in range(10):
        await tiny_task()
    seq_time = time.time() - start

    # 并行
    start = time.time()
    await asyncio.gather(*[tiny_task() for _ in range(10)])
    par_time = time.time() - start

    print(f"10 个 10ms 任务:")
    print(f"  串行: {seq_time * 1000:.1f}ms")
    print(f"  并行: {par_time * 1000:.1f}ms")
    print(f"  理论串行: {10 * 10}ms")
    print(f"  理论并行: {10}ms")
    print(f"  并行开销: {(par_time - 0.01) * 1000:.1f}ms")
    print("=" * 60)


if __name__ == "__main__":
    async def main():
        await test_parallel_efficiency()
        await test_different_task_counts()
        await test_with_real_subagent_tool()
        await test_overhead_analysis()
        print("\n✨ 所有测试完成！")

    asyncio.run(main())
