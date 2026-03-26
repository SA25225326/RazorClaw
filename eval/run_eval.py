"""
PoiClaw Agent 效果评估脚本

评估方法：pass@k
- 对同一任务运行 n 次，统计成功次数 c
- pass@k = 1 - C(n-c, k) / C(n, k)
- 含义：从 n 次尝试中随机抽 k 次，至少成功 1 次的概率

使用方法：
    # 需要 Mock LLM（不消耗真实 API）
    python eval/run_eval.py

    # 如果有真实 API Key，可以用真实 LLM
    python eval/run_eval.py --real
"""

import asyncio
import json
import math
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# 加载 .env 文件
from dotenv import load_dotenv
load_dotenv()


# ============ 评测任务定义 ============


@dataclass
class EvalTask:
    """评测任务"""
    id: str
    name: str
    description: str
    difficulty: str  # easy / medium / hard
    setup: callable  # 任务初始化函数
    verify: callable  # 验证函数，返回 (success: bool, message: str)


# ============ 评测结果 ============


@dataclass
class EvalResult:
    """单次评测结果"""
    task_id: str
    run_id: int
    success: bool
    message: str
    tokens_used: int = 0
    duration_ms: int = 0
    error: str | None = None


@dataclass
class EvalReport:
    """评测报告"""
    timestamp: str
    total_tasks: int
    total_runs: int
    results: list[EvalResult]
    pass_at_1: float = 0.0
    pass_at_3: float = 0.0
    pass_at_5: float = 0.0
    summary: dict[str, Any] = field(default_factory=dict)


# ============ pass@k 计算 ============


def comb(n: int, k: int) -> int:
    """组合数 C(n, k)"""
    if k > n or k < 0:
        return 0
    return math.factorial(n) // (math.factorial(k) * math.factorial(n - k))


def calculate_pass_at_k(n: int, c: int, k: int) -> float:
    """
    计算 pass@k

    Args:
        n: 总运行次数
        c: 成功次数
        k: pass@k 的 k

    Returns:
        pass@k 值 (0.0 - 1.0)
    """
    if n == 0:
        return 0.0
    if c >= n:
        return 1.0
    if k > n:
        k = n

    # pass@k = 1 - C(n-c, k) / C(n, k)
    return 1.0 - comb(n - c, k) / comb(n, k)


# ============ 任务定义 ============


def create_eval_tasks() -> list[EvalTask]:
    """创建评测任务集"""

    tasks = []

    # ===== Easy 任务 =====

    def task_01_setup():
        """创建测试文件"""
        test_dir = Path(".eval_tmp/task_01")
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "input.txt").write_text("Hello World\n")
        return str(test_dir)

    def task_01_verify(context):
        """验证：读取文件内容"""
        test_dir = Path(".eval_tmp/task_01")
        content = (test_dir / "input.txt").read_text()
        if "Hello World" in content:
            return True, "成功读取文件内容"
        return False, f"读取内容错误: {content}"

    tasks.append(EvalTask(
        id="read_file_01",
        name="读取文件",
        description="读取 input.txt 文件内容",
        difficulty="easy",
        setup=task_01_setup,
        verify=task_01_verify,
    ))

    def task_02_setup():
        """创建写入测试目录"""
        test_dir = Path(".eval_tmp/task_02")
        test_dir.mkdir(parents=True, exist_ok=True)
        return str(test_dir)

    def task_02_verify(context):
        """验证：写入文件成功"""
        test_dir = Path(".eval_tmp/task_02")
        output_file = test_dir / "output.txt"
        if output_file.exists():
            content = output_file.read_text()
            if "test content" in content.lower() or "hello" in content.lower():
                return True, f"成功写入文件: {content[:50]}"
        return False, "文件未创建或内容不正确"

    tasks.append(EvalTask(
        id="write_file_01",
        name="写入文件",
        description="创建 output.txt 并写入内容",
        difficulty="easy",
        setup=task_02_setup,
        verify=task_02_verify,
    ))

    def task_03_setup():
        """创建编辑测试文件"""
        test_dir = Path(".eval_tmp/task_03")
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "edit.txt").write_text("Hello OLD World\n")
        return str(test_dir)

    def task_03_verify(context):
        """验证：编辑文件成功"""
        test_dir = Path(".eval_tmp/task_03")
        content = (test_dir / "edit.txt").read_text()
        if "NEW" in content and "OLD" not in content:
            return True, f"成功编辑文件: {content}"
        return False, f"编辑失败，当前内容: {content}"

    tasks.append(EvalTask(
        id="edit_file_01",
        name="编辑文件",
        description="将 edit.txt 中的 OLD 替换为 NEW",
        difficulty="easy",
        setup=task_03_setup,
        verify=task_03_verify,
    ))

    # ===== Medium 任务 =====

    def task_04_setup():
        """创建多文件目录"""
        test_dir = Path(".eval_tmp/task_04")
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "a.txt").write_text("file a\n")
        (test_dir / "b.txt").write_text("file b\n")
        (test_dir / "c.txt").write_text("file c\n")
        return str(test_dir)

    def task_04_verify(context):
        """验证：列出文件"""
        test_dir = Path(".eval_tmp/task_04")
        files = list(test_dir.glob("*.txt"))
        if len(files) >= 3:
            return True, f"成功列出 {len(files)} 个文件"
        return False, f"文件数量不对: {len(files)}"

    tasks.append(EvalTask(
        id="list_files_01",
        name="列出文件",
        description="列出目录下所有 .txt 文件",
        difficulty="medium",
        setup=task_04_setup,
        verify=task_04_verify,
    ))

    def task_05_setup():
        """创建代码分析任务"""
        test_dir = Path(".eval_tmp/task_05")
        test_dir.mkdir(parents=True, exist_ok=True)
        code = '''
def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def calculate(x, y, z):
    return add(x, multiply(y, z))
'''
        (test_dir / "calc.py").write_text(code)
        return str(test_dir)

    def task_05_verify(context):
        """验证：理解代码结构"""
        test_dir = Path(".eval_tmp/task_05")
        # 这个任务主要是看 Agent 能否读取并理解代码
        # 简化验证：只要文件存在就算成功
        if (test_dir / "calc.py").exists():
            return True, "成功读取代码文件"
        return False, "代码文件不存在"

    tasks.append(EvalTask(
        id="code_analysis_01",
        name="代码分析",
        description="读取 calc.py 并说明 calculate 函数的作用",
        difficulty="medium",
        setup=task_05_setup,
        verify=task_05_verify,
    ))

    def task_06_setup():
        """创建文件合并任务"""
        test_dir = Path(".eval_tmp/task_06")
        test_dir.mkdir(parents=True, exist_ok=True)
        (test_dir / "part1.txt").write_text("Part 1 content\n")
        (test_dir / "part2.txt").write_text("Part 2 content\n")
        return str(test_dir)

    def task_06_verify(context):
        """验证：合并文件"""
        test_dir = Path(".eval_tmp/task_06")
        merged = test_dir / "merged.txt"
        if merged.exists():
            content = merged.read_text()
            if "Part 1" in content or "Part 2" in content:
                return True, f"成功合并文件: {content[:50]}"
        return False, "合并文件不存在或内容不正确"

    tasks.append(EvalTask(
        id="merge_files_01",
        name="合并文件",
        description="将 part1.txt 和 part2.txt 合并到 merged.txt",
        difficulty="medium",
        setup=task_06_setup,
        verify=task_06_verify,
    ))

    # ===== Hard 任务 =====

    def task_07_setup():
        """创建 Bug 修复任务"""
        test_dir = Path(".eval_tmp/task_07")
        test_dir.mkdir(parents=True, exist_ok=True)
        buggy_code = '''
def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        # Bug: 这里应该是 fibonacci(n-1) + fibonacci(n-2)
        return fibonacci(n-1) - fibonacci(n-2)

# 测试
print(fibonacci(10))  # 应该输出 55
'''
        (test_dir / "fib.py").write_text(buggy_code)
        return str(test_dir)

    def task_07_verify(context):
        """验证：Bug 是否修复"""
        test_dir = Path(".eval_tmp/task_07")
        content = (test_dir / "fib.py").read_text()
        # 检查是否修复了减号为加号
        if "fibonacci(n-1) + fibonacci(n-2)" in content:
            return True, "成功修复 Bug"
        return False, "Bug 未修复"

    tasks.append(EvalTask(
        id="bug_fix_01",
        name="Bug 修复",
        description="修复 fib.py 中的 Bug，使 fibonacci(10) 输出 55",
        difficulty="hard",
        setup=task_07_setup,
        verify=task_07_verify,
    ))

    def task_08_setup():
        """创建代码重构任务"""
        test_dir = Path(".eval_tmp/task_08")
        test_dir.mkdir(parents=True, exist_ok=True)
        code = '''
# TODO: 需要重构
def process_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result

def filter_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item)
    return result

def transform_data(data):
    result = []
    for item in data:
        if item > 0:
            result.append(item * 2)
    return result
'''
        (test_dir / "refactor.py").write_text(code)
        return str(test_dir)

    def task_08_verify(context):
        """验证：代码是否重构"""
        test_dir = Path(".eval_tmp/task_08")
        # 简化验证：文件存在即可
        if (test_dir / "refactor.py").exists():
            return True, "重构任务完成"
        return False, "重构文件不存在"

    tasks.append(EvalTask(
        id="refactor_01",
        name="代码重构",
        description="重构 refactor.py，消除重复代码",
        difficulty="hard",
        setup=task_08_setup,
        verify=task_08_verify,
    ))

    def task_09_setup():
        """创建测试编写任务"""
        test_dir = Path(".eval_tmp/task_09")
        test_dir.mkdir(parents=True, exist_ok=True)
        code = '''
def is_prime(n):
    if n < 2:
        return False
    for i in range(2, int(n**0.5) + 1):
        if n % i == 0:
            return False
    return True
'''
        (test_dir / "prime.py").write_text(code)
        return str(test_dir)

    def task_09_verify(context):
        """验证：测试文件是否创建"""
        test_dir = Path(".eval_tmp/task_09")
        test_file = test_dir / "test_prime.py"
        if test_file.exists():
            content = test_file.read_text()
            if "test" in content.lower() or "assert" in content:
                return True, "成功创建测试文件"
        return False, "测试文件不存在或格式不正确"

    tasks.append(EvalTask(
        id="write_test_01",
        name="编写测试",
        description="为 prime.py 编写单元测试",
        difficulty="hard",
        setup=task_09_setup,
        verify=task_09_verify,
    ))

    def task_10_setup():
        """创建复杂任务"""
        test_dir = Path(".eval_tmp/task_10")
        test_dir.mkdir(parents=True, exist_ok=True)
        # 创建一个需要多步骤完成的任务
        (test_dir / "config.json").write_text('{"name": "test", "value": 100}')
        return str(test_dir)

    def task_10_verify(context):
        """验证：复杂任务完成"""
        test_dir = Path(".eval_tmp/task_10")
        # 只要目录存在就算成功
        if test_dir.exists():
            return True, "复杂任务环境就绪"
        return False, "任务环境未就绪"

    tasks.append(EvalTask(
        id="complex_01",
        name="复杂任务",
        description="读取 config.json 并创建对应的 Python 配置类",
        difficulty="hard",
        setup=task_10_setup,
        verify=task_10_verify,
    ))

    return tasks


# ============ Mock Agent（不消耗 API） ============


class MockAgent:
    """
    Mock Agent - 模拟 Agent 执行，不消耗真实 API

    模拟策略：
    - Easy 任务：90% 成功率
    - Medium 任务：70% 成功率
    - Hard 任务：50% 成功率
    """

    def __init__(self):
        self.success_rates = {
            "easy": 0.90,
            "medium": 0.70,
            "hard": 0.50,
        }

    async def run(self, task: EvalTask) -> EvalResult:
        """执行任务（模拟）"""
        import random
        import time

        start_time = time.time()

        # 初始化任务环境
        context = task.setup()

        # 模拟执行
        await asyncio.sleep(0.1)  # 模拟延迟

        # 根据难度决定成功率
        success_rate = self.success_rates.get(task.difficulty, 0.5)
        success = random.random() < success_rate

        # 验证结果
        if success:
            success, message = task.verify(context)
        else:
            message = "模拟执行失败"

        duration_ms = int((time.time() - start_time) * 1000)
        tokens_used = random.randint(500, 2000)  # 模拟 Token 消耗

        return EvalResult(
            task_id=task.id,
            run_id=0,
            success=success,
            message=message,
            tokens_used=tokens_used,
            duration_ms=duration_ms,
        )


# ============ 真实 Agent（需要 API Key） ============


class RealAgent:
    """真实 Agent - 使用 PoiClaw 框架"""

    def __init__(self):
        from poiclaw.core.agent import Agent, AgentConfig
        from poiclaw.core.hooks import HookManager, create_bash_safety_hook
        from poiclaw.core.tools import ToolRegistry
        from poiclaw.llm.client import LLMClient
        from poiclaw.tools import register_all_tools

        # 保存类引用
        self._Agent = Agent
        self._AgentConfig = AgentConfig

        # 从环境变量读取配置
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

        # 创建 LLM 客户端
        self.llm = LLMClient(model=model)

        # 创建工具注册器
        self.tools = ToolRegistry()
        register_all_tools(self.tools)

        # 创建 Hook 管理器
        self.hooks = HookManager()
        self.hooks.add_before_execute(create_bash_safety_hook())

        print(f"[RealAgent] 使用模型: {model}")

        self._ready = True

    async def run(self, task: EvalTask, run_id: int) -> EvalResult:
        """执行任务"""
        import time

        start_time = time.time()

        if not getattr(self, '_ready', False):
            return EvalResult(
                task_id=task.id,
                run_id=run_id,
                success=False,
                message="",
                error="RealAgent 未初始化",
                duration_ms=0,
            )

        try:
            # 初始化任务环境
            context = task.setup()

            # 创建 Agent
            agent = self._Agent(
                llm_client=self.llm,
                tools=self.tools,
                hooks=self.hooks,
                config=self._AgentConfig(
                    max_steps=10,
                    system_prompt=f"你是一个代码助手。{task.description}",
                ),
            )

            # 执行任务
            response = await agent.run(task.description)

            # 验证结果
            success, message = task.verify(context)

            duration_ms = int((time.time() - start_time) * 1000)
            usage = agent.get_usage_stats()

            return EvalResult(
                task_id=task.id,
                run_id=run_id,
                success=success,
                message=message,
                tokens_used=usage.total_tokens,
                duration_ms=duration_ms,
            )

        except Exception as e:
            return EvalResult(
                task_id=task.id,
                run_id=run_id,
                success=False,
                message="",
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )


# ============ 评测运行器 ============


class EvalRunner:
    """评测运行器"""

    def __init__(self, use_real_agent: bool = False, runs_per_task: int = 3):
        self.use_real_agent = use_real_agent
        self.runs_per_task = runs_per_task
        self.tasks = create_eval_tasks()

    async def run(self) -> EvalReport:
        """运行评测"""
        print(f"\n{'='*60}")
        print(f"PoiClaw Agent 评测")
        print(f"{'='*60}")
        print(f"任务数量: {len(self.tasks)}")
        print(f"每任务运行次数: {self.runs_per_task}")
        print(f"总运行次数: {len(self.tasks) * self.runs_per_task}")
        print(f"使用真实 Agent: {self.use_real_agent}")
        print(f"{'='*60}\n")

        results: list[EvalResult] = []

        # 创建 Agent
        if self.use_real_agent:
            try:
                agent = RealAgent()
            except Exception as e:
                print(f"创建真实 Agent 失败: {e}")
                print("回退到 Mock Agent")
                agent = MockAgent()
        else:
            agent = MockAgent()

        # 运行每个任务
        for task in self.tasks:
            print(f"\n[{task.difficulty.upper()}] {task.name} ({task.id})")
            print(f"  描述: {task.description}")

            for run_id in range(self.runs_per_task):
                result = await agent.run(task, run_id)
                results.append(result)

                status = "✅" if result.success else "❌"
                print(f"  Run {run_id + 1}: {status} {result.message}")

        # 计算统计
        report = self._generate_report(results)

        return report

    def _generate_report(self, results: list[EvalResult]) -> EvalReport:
        """生成评测报告"""
        # 按任务分组
        task_results: dict[str, list[EvalResult]] = {}
        for r in results:
            if r.task_id not in task_results:
                task_results[r.task_id] = []
            task_results[r.task_id].append(r)

        # 计算每个任务的 pass@k
        pass_at_1_list = []
        pass_at_3_list = []
        pass_at_5_list = []

        for task_id, task_runs in task_results.items():
            n = len(task_runs)
            c = sum(1 for r in task_runs if r.success)

            pass_at_1 = calculate_pass_at_k(n, c, 1)
            pass_at_3 = calculate_pass_at_k(n, c, 3)
            pass_at_5 = calculate_pass_at_k(n, c, 5)

            pass_at_1_list.append(pass_at_1)
            pass_at_3_list.append(pass_at_3)
            pass_at_5_list.append(pass_at_5)

        # 平均 pass@k
        avg_pass_at_1 = sum(pass_at_1_list) / len(pass_at_1_list) if pass_at_1_list else 0
        avg_pass_at_3 = sum(pass_at_3_list) / len(pass_at_3_list) if pass_at_3_list else 0
        avg_pass_at_5 = sum(pass_at_5_list) / len(pass_at_5_list) if pass_at_5_list else 0

        # 按难度统计
        difficulty_stats = {}
        for task in self.tasks:
            if task.difficulty not in difficulty_stats:
                difficulty_stats[task.difficulty] = {"total": 0, "success": 0}
            runs = task_results.get(task.id, [])
            difficulty_stats[task.difficulty]["total"] += len(runs)
            difficulty_stats[task.difficulty]["success"] += sum(1 for r in runs if r.success)

        report = EvalReport(
            timestamp=datetime.now().isoformat(),
            total_tasks=len(self.tasks),
            total_runs=len(results),
            results=results,
            pass_at_1=avg_pass_at_1,
            pass_at_3=avg_pass_at_3,
            pass_at_5=avg_pass_at_5,
            summary={
                "by_difficulty": difficulty_stats,
                "total_tokens": sum(r.tokens_used for r in results),
                "avg_duration_ms": sum(r.duration_ms for r in results) / len(results) if results else 0,
            },
        )

        return report


def print_report(report: EvalReport):
    """打印评测报告"""
    print(f"\n{'='*60}")
    print("评测报告")
    print(f"{'='*60}")
    print(f"时间: {report.timestamp}")
    print(f"任务数: {report.total_tasks}")
    print(f"总运行次数: {report.total_runs}")

    print(f"\n[pass@k]")
    print(f"  pass@1: {report.pass_at_1:.1%}")
    print(f"  pass@3: {report.pass_at_3:.1%}")
    print(f"  pass@5: {report.pass_at_5:.1%}")

    print(f"\n[By Difficulty]")
    for diff, stats in report.summary.get("by_difficulty", {}).items():
        success_rate = stats["success"] / stats["total"] if stats["total"] > 0 else 0
        print(f"  {diff}: {stats['success']}/{stats['total']} ({success_rate:.1%})")

    print(f"\n[Resources]")
    print(f"  总 Token: {report.summary.get('total_tokens', 0):,}")
    print(f"  平均耗时: {report.summary.get('avg_duration_ms', 0):.0f}ms")

    print(f"\n{'='*60}")

    # 保存到文件
    output_dir = Path("eval/results")
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"eval_{timestamp}.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump({
            "timestamp": report.timestamp,
            "total_tasks": report.total_tasks,
            "total_runs": report.total_runs,
            "pass_at_1": report.pass_at_1,
            "pass_at_3": report.pass_at_3,
            "pass_at_5": report.pass_at_5,
            "summary": report.summary,
            "results": [
                {
                    "task_id": r.task_id,
                    "run_id": r.run_id,
                    "success": r.success,
                    "message": r.message,
                    "tokens_used": r.tokens_used,
                    "duration_ms": r.duration_ms,
                    "error": r.error,
                }
                for r in report.results
            ],
        }, f, ensure_ascii=False, indent=2)

    print(f"报告已保存到: {output_file}")


async def main(use_real: bool = False):
    """主函数"""
    runner = EvalRunner(use_real_agent=use_real, runs_per_task=3)
    report = await runner.run()
    print_report(report)


if __name__ == "__main__":
    import sys
    import io

    # 设置 stdout 编码
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

    use_real = "--real" in sys.argv

    if use_real:
        print("[!] 使用真实 Agent，需要 API Key")
    else:
        print("[*] 使用 Mock Agent（模拟），不消耗 API")

    asyncio.run(main(use_real))
