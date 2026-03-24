"""Skill 数据模型"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Skill:
    """
    技能定义。

    每个 Skill 对应一个 Markdown 文件，包含触发条件、指令和示例。

    Attributes:
        name: 技能名称（文件名去掉 .md）
        trigger_conditions: 触发条件
        instructions: 执行指令
        examples: 示例
        file_path: 文件路径
    """

    name: str
    trigger_conditions: str
    instructions: str
    examples: str
    file_path: Path

    @classmethod
    def from_markdown(cls, content: str, file_path: Path) -> Skill:
        """
        从 Markdown 内容解析 Skill。

        支持的 section 格式：
        - ## 触发条件 / ## Triggers
        - ## 指令 / ## Instructions
        - ## 示例 / ## Examples

        Args:
            content: Markdown 文件内容
            file_path: 文件路径

        Returns:
            Skill: 解析后的技能对象
        """
        name = file_path.stem

        # 简单解析：按 ## 分割
        sections: dict[str, str] = {}
        current_section: str | None = None
        current_content: list[str] = []

        # Section 名称映射（支持中英文）
        section_mapping = {
            "触发条件": "trigger_conditions",
            "triggers": "trigger_conditions",
            "指令": "instructions",
            "instructions": "instructions",
            "示例": "examples",
            "examples": "examples",
        }

        for line in content.split("\n"):
            if line.startswith("## "):
                # 保存上一个 section
                if current_section:
                    sections[current_section] = "\n".join(current_content).strip()
                # 开始新 section
                section_title = line[3:].strip().lower()
                current_section = section_mapping.get(section_title, section_title)
                current_content = []
            else:
                current_content.append(line)

        # 保存最后一个 section
        if current_section:
            sections[current_section] = "\n".join(current_content).strip()

        return cls(
            name=name,
            trigger_conditions=sections.get("trigger_conditions", ""),
            instructions=sections.get("instructions", ""),
            examples=sections.get("examples", ""),
            file_path=file_path,
        )

    def to_brief(self) -> str:
        """
        返回简要描述（用于初始注入 system prompt）。

        只包含技能名称和触发条件的第一行。

        Returns:
            str: 简要描述，格式为 "- {name}: {第一行触发条件}"
        """
        first_line = ""
        if self.trigger_conditions:
            # 取第一行非空内容
            for line in self.trigger_conditions.split("\n"):
                line = line.strip()
                if line and not line.startswith("#"):
                    # 去掉列表符号
                    if line.startswith("- "):
                        line = line[2:]
                    first_line = line
                    break

        if first_line:
            return f"- {self.name}: {first_line}"
        return f"- {self.name}"

    def to_full_prompt(self) -> str:
        """
        返回完整提示词（按需加载时使用）。

        Returns:
            str: 完整的 Skill 内容，包含所有 section
        """
        parts = [f"# Skill: {self.name}"]

        if self.trigger_conditions:
            parts.append("\n## 触发条件")
            parts.append(self.trigger_conditions)

        if self.instructions:
            parts.append("\n## 指令")
            parts.append(self.instructions)

        if self.examples:
            parts.append("\n## 示例")
            parts.append(self.examples)

        return "\n".join(parts)
