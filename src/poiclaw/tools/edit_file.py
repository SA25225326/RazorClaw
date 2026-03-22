"""文件编辑工具 - 精确文本替换"""

from __future__ import annotations

import asyncio
from pathlib import Path

from poiclaw.core import BaseTool, ToolResult


class EditFileTool(BaseTool):
    """
    文件编辑工具。

    使用精确字符串替换方式编辑文件。
    要求 old_text 在文件中必须唯一匹配。
    """

    @property
    def name(self) -> str:
        return "edit_file"

    @property
    def description(self) -> str:
        return (
            "编辑文件。用 new_text 替换文件中的 old_text。"
            "old_text 必须完全匹配且唯一，否则会失败。"
        )

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "old_text": {
                    "type": "string",
                    "description": "要查找的文本（必须完全匹配）",
                },
                "new_text": {
                    "type": "string",
                    "description": "替换后的文本",
                },
            },
            "required": ["path", "old_text", "new_text"],
        }

    async def execute(
        self,
        path: str,
        old_text: str,
        new_text: str,
    ) -> ToolResult:
        """
        编辑文件，用 new_text 替换 old_text。

        Args:
            path: 文件路径
            old_text: 要查找的文本（必须完全匹配且唯一）
            new_text: 替换后的文本

        Returns:
            ToolResult: 包含编辑结果或错误信息
        """
        try:
            file_path = Path(path).expanduser().resolve()

            # 检查文件是否存在
            if not file_path.exists():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"文件不存在：{path}",
                )

            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"路径不是文件：{path}",
                )

            # 使用 asyncio.to_thread 读取文件
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")

            # 检查 old_text 是否存在
            if old_text not in content:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"未找到要替换的文本。请确保 old_text 与文件内容完全匹配。",
                )

            # 检查是否唯一
            occurrences = content.count(old_text)
            if occurrences > 1:
                return ToolResult(
                    success=False,
                    content="",
                    error=f"找到 {occurrences} 处匹配。old_text 必须唯一，请扩大上下文使其唯一。",
                )

            # 执行替换
            new_content = content.replace(old_text, new_text, 1)

            # 检查是否有变化
            if content == new_content:
                return ToolResult(
                    success=False,
                    content="",
                    error="替换后内容未变化。",
                )

            # 写入文件
            await asyncio.to_thread(file_path.write_text, new_content, encoding="utf-8")

            # 计算变更位置
            old_lines = content.split("\n")
            first_changed_line = None
            for i, line in enumerate(old_lines):
                if old_text.split("\n")[0] in line:
                    first_changed_line = i + 1
                    break

            location_info = f"第 {first_changed_line} 行附近" if first_changed_line else ""
            return ToolResult(
                success=True,
                content=f"成功替换 {path} 中的文本（{location_info}）",
            )

        except PermissionError:
            return ToolResult(success=False, content="", error=f"没有权限编辑文件：{path}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"编辑文件时发生错误：{e}")
