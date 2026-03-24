"""测试上下文压缩的 Token 节省

模拟长对话场景，计算压缩前后的 Token 对比。
"""

import sys

# 修复 Windows 控制台编码问题
sys.stdout.reconfigure(encoding="utf-8")

from poiclaw.core.compaction import (
    estimate_tokens,
    estimate_total_tokens,
    find_cut_point,
    serialize_messages_for_summary,
)
from poiclaw.core.session import CompactionSettings
from poiclaw.llm import FunctionCall, Message, ToolCall


def create_mock_conversation(turns: int = 20, msg_length: int = 500) -> list[Message]:
    """创建模拟对话，每轮包含 user + assistant + tool 消息"""
    messages = []
    for i in range(turns):
        # User 消息
        messages.append(
            Message.user(f"第 {i+1} 轮：请帮我分析这段代码，找出潜在的问题..." + "x" * msg_length)
        )
        # Assistant 消息（包含思考内容和工具调用）
        messages.append(
            Message(
                role="assistant",
                content=f"好的，我来分析一下这段代码。首先需要读取文件内容..." + "y" * msg_length,
                tool_calls=[
                    ToolCall(
                        id=f"call_read_{i}",
                        function=FunctionCall(
                            name="read_file",
                            arguments=f'{{"path": "/src/module_{i}.py"}}',
                        ),
                    )
                ],
            )
        )
        # Tool 结果
        messages.append(
            Message.tool_result(
                tool_call_id=f"call_read_{i}",
                content=f"文件内容：def process_data(data):\\n    result = []\\n    for item in data:\\n        result.append(transform(item))\\n    return result\\n..."
                + "z" * msg_length,
            )
        )
    return messages


def test_compaction_token_savings():
    """测试压缩的 Token 节省效果"""
    # 1. 创建模拟对话（更多轮次，更长的消息）
    turns = 30
    msg_length = 600
    messages = create_mock_conversation(turns=turns, msg_length=msg_length)

    # 2. 压缩前 token 数
    tokens_before = estimate_total_tokens(messages)

    # 3. 配置压缩参数（保留较少的最近消息以展示效果）
    settings = CompactionSettings(
        enabled=True,
        context_window=128000,
        reserve_tokens=16384,
        keep_recent_tokens=3000,  # 只保留约 3000 tokens
    )

    # 4. 找到切割点
    cut_point = find_cut_point(messages, settings.keep_recent_tokens)

    # 5. 分离消息
    messages_to_summarize = messages[:cut_point]
    kept_messages = messages[cut_point:]

    # 6. 估算摘要 token
    # 摘要通常为原文的 5-10%，这里保守估计 8%
    original_text = serialize_messages_for_summary(messages_to_summarize)
    original_tokens = estimate_total_tokens(messages_to_summarize)
    summary_tokens = max(200, original_tokens // 12)  # 约 8% 压缩率

    # 7. 压缩后 token 数
    kept_tokens = estimate_total_tokens(kept_messages)
    tokens_after = summary_tokens + kept_tokens

    # 8. 计算节省
    tokens_saved = tokens_before - tokens_after
    saved_percent = (tokens_saved / tokens_before) * 100

    # 输出结果
    print("=" * 60)
    print("📊 上下文压缩 Token 节省测试")
    print("=" * 60)
    print(f"对话轮数: {turns} 轮 ({len(messages)} 条消息)")
    print(f"每条消息长度: ~{msg_length} 字符")
    print(f"保留最近: {settings.keep_recent_tokens} tokens ({len(kept_messages)} 条消息)")
    print(f"需要摘要: {len(messages_to_summarize)} 条消息")
    print("-" * 60)
    print(f"🔹 压缩前: {tokens_before:,} tokens")
    print(f"🔹 压缩后: {tokens_after:,} tokens")
    print(f"   - 摘要: {summary_tokens:,} tokens (原文 {original_tokens:,} 的 ~8%)")
    print(f"   - 保留: {kept_tokens:,} tokens")
    print("-" * 60)
    print(f"✅ 节省: {saved_percent:.1f}% ({tokens_saved:,} tokens)")
    print("=" * 60)

    # 验证节省效果
    assert tokens_saved > 0, "压缩应该节省 tokens"
    assert saved_percent > 50, f"节省比例应超过 50%，实际 {saved_percent:.1f}%"

    print(f"\n🎉 测试通过！压缩节省了 {saved_percent:.1f}% 的 tokens")

    return saved_percent


def test_progressive_compaction():
    """测试多次压缩的渐进效果"""
    print("\n" + "=" * 60)
    print("📈 渐进式压缩测试（模拟多次压缩）")
    print("=" * 60)

    # 初始对话
    messages = create_mock_conversation(turns=40, msg_length=400)
    initial_tokens = estimate_total_tokens(messages)

    print(f"初始对话: {len(messages)} 条消息, {initial_tokens:,} tokens\n")

    # 模拟三次压缩
    settings = CompactionSettings(
        enabled=True,
        context_window=128000,
        reserve_tokens=16384,
        keep_recent_tokens=4000,
    )

    results = []
    current_messages = messages.copy()
    cumulative_summary_tokens = 0

    for i in range(3):
        cut_point = find_cut_point(current_messages, settings.keep_recent_tokens)
        if cut_point == 0:
            break

        to_summarize = current_messages[:cut_point]
        kept = current_messages[cut_point:]

        # 模拟摘要（每次压缩摘要累积增长约 300 tokens）
        cumulative_summary_tokens += 300
        total_after = cumulative_summary_tokens + estimate_total_tokens(kept)

        results.append(
            {
                "round": i + 1,
                "before": estimate_total_tokens(current_messages),
                "after": total_after,
                "summarized_count": len(to_summarize),
                "kept_count": len(kept),
            }
        )

        # 下一轮从保留的消息继续
        current_messages = kept

    # 输出结果
    print(f"{'轮次':<6} {'压缩前':>12} {'压缩后':>12} {'节省':>10} {'摘要消息':>10} {'保留消息':>10}")
    print("-" * 60)
    for r in results:
        saved = r["before"] - r["after"]
        print(
            f"{r['round']:<6} {r['before']:>12,} {r['after']:>12,} {saved:>10,} {r['summarized_count']:>10} {r['kept_count']:>10}"
        )

    total_saved = initial_tokens - results[-1]["after"]
    print("-" * 60)
    print(
        f"从初始到最终节省: {total_saved:,} tokens ({total_saved / initial_tokens * 100:.1f}%)"
    )
    print("=" * 60)


def test_different_keep_settings():
    """测试不同 keep_recent_tokens 设置的效果"""
    print("\n" + "=" * 60)
    print("🔧 不同保留策略对比")
    print("=" * 60)

    messages = create_mock_conversation(turns=30, msg_length=500)
    total_tokens = estimate_total_tokens(messages)

    keep_settings = [2000, 4000, 8000, 15000]

    print(f"总消息: {len(messages)} 条, 总 tokens: {total_tokens:,}\n")
    print(f"{'保留设置':>12} {'保留消息':>10} {'压缩后':>12} {'节省':>10} {'节省比例':>10}")
    print("-" * 60)

    for keep_tokens in keep_settings:
        cut_point = find_cut_point(messages, keep_tokens)
        kept = messages[cut_point:]
        kept_tokens = estimate_total_tokens(kept)

        # 摘要约为被压缩内容的 8%
        summarized_tokens = estimate_total_tokens(messages[:cut_point])
        summary_tokens = max(100, summarized_tokens // 12)

        tokens_after = summary_tokens + kept_tokens
        saved = total_tokens - tokens_after
        saved_pct = saved / total_tokens * 100

        print(
            f"{keep_tokens:>12,} {len(kept):>10} {tokens_after:>12,} {saved:>10,} {saved_pct:>9.1f}%"
        )

    print("=" * 60)


if __name__ == "__main__":
    test_compaction_token_savings()
    test_progressive_compaction()
    test_different_keep_settings()
    print("\n✨ 所有测试完成！")
