"""
系统提示词构建模块。

参考 pi-mono 的 system-prompt.ts 设计，支持：
- 自定义提示词
- 动态工具列表
- 项目上下文文件
- 灵活的指导原则
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ToolInfo:
    """工具信息，用于系统提示词中的工具描述"""

    name: str
    description: str

    @classmethod
    def from_tool(cls, tool: Any) -> ToolInfo:
        """从 BaseTool 实例创建"""
        return cls(name=tool.name, description=tool.description)


@dataclass
class ContextFile:
    """项目上下文文件"""

    path: str
    content: str


@dataclass
class BuildSystemPromptOptions:
    """
    构建系统提示词的选项。

    Attributes:
        custom_prompt: 自定义系统提示词（完全替换默认）
        selected_tools: 选中的工具名称列表，默认使用所有注册的工具
        tool_snippets: 工具的简短描述（覆盖默认描述）
        prompt_guidelines: 额外的指导原则
        append_system_prompt: 追加到系统提示词末尾的文本
        cwd: 工作目录，默认为当前目录
        context_files: 项目上下文文件（如 CLAUDE.md）
        agent_name: Agent 名称，默认为 "Poiclaw"
    """

    custom_prompt: str | None = None
    selected_tools: list[str] | None = None
    tool_snippets: dict[str, str] | None = None
    prompt_guidelines: list[str] | None = None
    append_system_prompt: str | None = None
    cwd: str | None = None
    context_files: list[ContextFile] | None = None
    agent_name: str = "Poiclaw"


# 工具默认描述（当工具本身没有提供时使用）
DEFAULT_TOOL_DESCRIPTIONS: dict[str, str] = {
    "bash": "执行 bash/shell 命令（ls, grep, find 等）",
    "read": "读取文件内容",
    "write": "创建或覆盖文件",
    "edit": "对文件进行精确编辑（查找并替换文本）",
    "grep": "在文件内容中搜索模式（尊重 .gitignore）",
    "find": "按 glob 模式查找文件（尊重 .gitignore）",
    "ls": "列出目录内容",
    "subagent": "创建子 Agent 并行处理任务（Fork-Join 模式）",
    "list_tools": "查询已注册工具的详细 Schema",
}


def build_system_prompt(
    tools: list[ToolInfo] | None = None,
    options: BuildSystemPromptOptions | None = None,
) -> str:
    """
    构建系统提示词。

    Args:
        tools: 可用工具列表
        options: 构建选项

    Returns:
        str: 完整的系统提示词
    """
    options = options or BuildSystemPromptOptions()
    tools = tools or []

    cwd = options.cwd or str(Path.cwd())
    # 统一路径分隔符为 /
    prompt_cwd = cwd.replace("\\", "/")
    date = datetime.now().strftime("%Y-%m-%d")

    append_section = f"\n\n{options.append_system_prompt}" if options.append_system_prompt else ""
    context_files = options.context_files or []

    # 如果提供了自定义提示词，使用它作为基础
    if options.custom_prompt:
        prompt = options.custom_prompt

        if append_section:
            prompt += append_section

        # 追加项目上下文文件
        if context_files:
            prompt += "\n\n# 项目上下文\n\n"
            prompt += "项目特定的指令和指南：\n\n"
            for cf in context_files:
                prompt += f"## {cf.path}\n\n{cf.content}\n\n"

        # 追加日期和工作目录
        prompt += f"\n当前日期: {date}"
        prompt += f"\n当前工作目录: {prompt_cwd}"

        return prompt

    # ===== 构建默认系统提示词 =====

    # 构建工具列表
    selected_names = options.selected_tools
    if selected_names is None:
        # 使用所有工具
        tool_names = [t.name for t in tools]
    else:
        tool_names = [n for n in selected_names if n in [t.name for t in tools] or n in DEFAULT_TOOL_DESCRIPTIONS]

    tools_list = _build_tools_list(tool_names, options.tool_snippets or {})

    # 构建指导原则
    guidelines = _build_guidelines(tool_names, options.prompt_guidelines or [])

    # 构建基础提示词
    prompt = f"""你是一个在 {options.agent_name} 编码助手框架中运行的专家级编程助手。你通过读取文件、执行命令、编辑代码和编写新文件来帮助用户。

可用工具:
{tools_list}

除了上述工具外，你可能还能访问其他自定义工具，具体取决于项目配置。

指导原则:
{guidelines}

在处理任务时：
1. 先理解用户的真实需求，不要假设用户知道确切要做什么
2. 使用第一性原理思考：质疑假设，理解"为什么"
3. 如果动机/目标/约束不清楚，先询问澄清
4. 走简单直接的路径，不要过度设计
5. 保持简洁的回复，展示文件路径时要清晰"""

    if append_section:
        prompt += append_section

    # 追加项目上下文文件
    if context_files:
        prompt += "\n\n# 项目上下文\n\n"
        prompt += "项目特定的指令和指南：\n\n"
        for cf in context_files:
            prompt += f"## {cf.path}\n\n{cf.content}\n\n"

    # 追加日期和工作目录
    prompt += f"\n当前日期: {date}"
    prompt += f"\n当前工作目录: {prompt_cwd}"

    return prompt


def _build_tools_list(
    tool_names: list[str],
    tool_snippets: dict[str, str],
) -> str:
    """构建工具列表描述"""
    if not tool_names:
        return "(无)"

    lines = []
    for name in tool_names:
        # 优先使用自定义 snippet，然后是默认描述，最后用名称
        snippet = tool_snippets.get(name) or DEFAULT_TOOL_DESCRIPTIONS.get(name, name)
        lines.append(f"- {name}: {snippet}")

    return "\n".join(lines)


def _build_guidelines(
    tool_names: list[str],
    extra_guidelines: list[str],
) -> str:
    """构建指导原则列表"""
    guidelines: list[str] = []
    seen: set[str] = set()

    def add(g: str) -> None:
        if g not in seen:
            seen.add(g)
            guidelines.append(g)

    has_bash = "bash" in tool_names
    has_read = "read" in tool_names
    has_edit = "edit" in tool_names
    has_write = "write" in tool_names
    has_grep = "grep" in tool_names
    has_find = "find" in tool_names
    has_ls = "ls" in tool_names
    has_subagent = "subagent" in tool_names

    # 文件探索指导
    if has_bash and not has_grep and not has_find and not has_ls:
        add("使用 bash 进行文件操作（如 ls, rg, find）")
    elif has_bash and (has_grep or has_find or has_ls):
        add("文件探索优先使用 grep/find/ls 工具而非 bash（更快，且尊重 .gitignore）")

    # 读取文件指导
    if has_read and has_edit:
        add("编辑前先使用 read 查看文件内容，不要用 bash 的 cat 或 sed")

    # 编辑指导
    if has_edit:
        add("使用 edit 进行精确修改（旧文本必须完全匹配）")

    # 写入指导
    if has_write:
        add("write 仅用于创建新文件或完全重写")

    # 输出指导
    if has_edit or has_write:
        add("总结操作时直接输出文本，不要用 cat 或 bash 展示你做了什么")

    # 子 Agent 指导
    if has_subagent:
        add("复杂任务可以使用 subagent 创建子 Agent 并行处理")
        add("子 Agent 适合独立、可并行的子任务，不适合有依赖关系的任务")

    # 添加额外指导
    for g in extra_guidelines:
        normalized = g.strip()
        if normalized:
            add(normalized)

    # 总是包含的指导
    add("回复要简洁")
    add("操作文件时清晰展示文件路径")

    return "\n".join(f"- {g}" for g in guidelines)


def load_context_file(file_path: str | Path) -> ContextFile | None:
    """
    加载项目上下文文件。

    Args:
        file_path: 文件路径

    Returns:
        ContextFile 或 None（如果文件不存在）
    """
    path = Path(file_path)
    if not path.exists():
        return None

    try:
        content = path.read_text(encoding="utf-8")
        return ContextFile(path=str(path), content=content)
    except Exception:
        return None


def build_default_system_prompt(
    cwd: str | None = None,
    agent_name: str = "Poiclaw",
) -> str:
    """
    构建默认系统提示词（便捷函数）。

    用于不需要工具信息的简单场景。

    Args:
        cwd: 工作目录
        agent_name: Agent 名称

    Returns:
        str: 默认系统提示词
    """
    return build_system_prompt(
        tools=[],
        options=BuildSystemPromptOptions(
            cwd=cwd,
            agent_name=agent_name,
        ),
    )
