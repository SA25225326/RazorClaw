"""测试系统提示词 Token 数量"""

from poiclaw.core import (
    BuildSystemPromptOptions,
    ContextFile,
    ToolInfo,
    ToolRegistry,
    build_system_prompt,
)
from poiclaw.tools import register_all_tools


def count_tokens(text: str) -> int:
    """估算 token 数量（4 字符 ≈ 1 token）"""
    return len(text) // 4


def test_system_prompt_tokens():
    # 1. 准备工具信息
    registry = ToolRegistry()
    register_all_tools(registry)
    tool_infos = [ToolInfo.from_tool(t) for t in registry.get_all_tools()]

    print("=" * 50)
    print("系统提示词 Token 测试")
    print("=" * 50)

    # 2. 最小配置（仅工具，无额外指导）
    options_min = BuildSystemPromptOptions()
    prompt_min = build_system_prompt(tool_infos, options_min)
    tokens_min = count_tokens(prompt_min)

    print(f"\n1. 最小配置（仅工具）")
    print(f"   长度: {len(prompt_min)} 字符")
    print(f"   Token: ~{tokens_min}")

    # 3. 标准配置（工具 + 额外指导原则）
    options_std = BuildSystemPromptOptions(
        prompt_guidelines=[
            "优先使用 Python 类型注解",
            "代码需要完整的错误处理",
        ]
    )
    prompt_std = build_system_prompt(tool_infos, options_std)
    tokens_std = count_tokens(prompt_std)

    print(f"\n2. 标准配置（工具 + 指导原则）")
    print(f"   长度: {len(prompt_std)} 字符")
    print(f"   Token: ~{tokens_std}")

    # 4. 完整配置（工具 + 指导原则 + 项目上下文）
    # 模拟 CLAUDE.md 约 2000 字符
    mock_context = ContextFile(
        path="CLAUDE.md",
        content="# Project Context\n\n" + "x" * 2000,
    )
    options_full = BuildSystemPromptOptions(
        context_files=[mock_context],
        prompt_guidelines=["优先使用 Python 类型注解"],
    )
    prompt_full = build_system_prompt(tool_infos, options_full)
    tokens_full = count_tokens(prompt_full)

    print(f"\n3. 完整配置（工具 + 指导原则 + 上下文）")
    print(f"   长度: {len(prompt_full)} 字符")
    print(f"   Token: ~{tokens_full}")

    print("=" * 50)
    print(f"结论: 基础提示词（无上下文）约 {tokens_std} tokens")
    print("=" * 50)

    # 返回结果便于断言
    return {
        "min": tokens_min,
        "std": tokens_std,
        "full": tokens_full,
    }


if __name__ == "__main__":
    test_system_prompt_tokens()
