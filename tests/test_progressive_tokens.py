"""测试渐进式加载的 Token 节省"""

import json
import sys

# 修复 Windows 控制台编码问题
sys.stdout.reconfigure(encoding='utf-8')

from poiclaw.core import ToolRegistry
from poiclaw.tools import register_all_tools


def test_token_savings():
    """测试渐进式加载能节省多少 Token"""
    tools = ToolRegistry()
    register_all_tools(tools)

    # 全量注入
    full_schema = tools.to_llm_tools()
    full_chars = len(json.dumps(full_schema, ensure_ascii=False))
    full_tokens = full_chars // 4  # 粗略估算（中文约 1.5-2 字符/token，英文约 4 字符/token）

    # 渐进式注入
    brief = tools.to_brief()
    brief_tokens = len(brief) // 4

    # 计算
    saved = (full_tokens - brief_tokens) / full_tokens * 100

    print(f"全量注入: {full_tokens} tokens ({full_chars} chars)")
    print(f"渐进注入: {brief_tokens} tokens ({len(brief)} chars)")
    print(f"节省: {saved:.1f}%")

    assert saved > 50, f"应该节省超过 50%，实际节省 {saved:.1f}%"
    print("\n✅ 测试通过：渐进式加载节省超过 50% Token")


def test_get_tool_schema():
    """测试按需获取单个工具 Schema"""
    tools = ToolRegistry()
    register_all_tools(tools)

    # 获取 bash 工具的 Schema
    schema = tools.get_tool_schema("bash")
    assert schema is not None
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "bash"
    assert "parameters" in schema["function"]

    # 获取不存在的工具
    schema = tools.get_tool_schema("not_exist")
    assert schema is None

    print("✅ 测试通过：get_tool_schema 工作正常")


def test_brief_format():
    """测试 to_brief() 输出格式"""
    tools = ToolRegistry()
    register_all_tools(tools)

    brief = tools.to_brief()

    # 检查格式
    assert "可用工具" in brief
    assert "list_tools" in brief  # 提示使用 list_tools 查询详情

    # 每个工具应该是一行
    lines = brief.strip().split("\n")
    assert len(lines) > 1
    assert lines[0].startswith("可用工具")

    print("✅ 测试通过：to_brief() 格式正确")


if __name__ == "__main__":
    test_token_savings()
    test_get_tool_schema()
    test_brief_format()
    print("\n🎉 所有测试通过！")
