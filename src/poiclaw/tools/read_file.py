"""文件读取工具"""

from __future__ import annotations

import asyncio
from pathlib import Path

from poiclaw.core import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    """
    文件读取工具。

    支持读取整个文件或指定行范围。
    使用 asyncio.to_thread 包装同步 I/O，保持极简（不引入 aiofiles）。
    """

    # 最大读取字节数
    MAX_BYTES = 100 * 1024  # 100KB

    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "读取文件内容。可以读取整个文件或指定行范围。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "start_line": {
                    "type": "integer",
                    "description": "起始行号（从 1 开始），可选",
                },
                "end_line": {
                    "type": "integer",
                    "description": "结束行号，可选",
                },
            },
            "required": ["path"],
        }

    async def execute(
        self,
        path: str,
        start_line: int | None = None,
        end_line: int | None = None,
    ) -> ToolResult:
        """
        读取文件内容。

        Args:
            path: 文件路径
            start_line: 起始行号（从 1 开始）
            end_line: 结束行号

        Returns:
            ToolResult: 包含文件内容或错误信息
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

            # 检查是否是文件
            if not file_path.is_file():
                return ToolResult(
                    success=False,
                    content="",
                    error=f"路径不是文件：{path}",
                )

            # 使用 asyncio.to_thread 读取文件
            content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")

            # 按行处理
            lines = content.split("\n")
            total_lines = len(lines)

            # 行号范围处理
            if start_line is not None or end_line is not None:
                start = (start_line or 1) - 1  # 转为 0-indexed
                end = end_line or total_lines
                lines = lines[start:end]
                content = "\n".join(lines)
                header = f"[文件 {path}，第 {start + 1}-{min(end, total_lines)} 行，共 {total_lines} 行]\n"
            else:
                header = f"[文件 {path}，共 {total_lines} 行]\n"

            # 截断处理
            if len(content.encode("utf-8")) > self.MAX_BYTES:
                content_bytes = content.encode("utf-8")
                truncated = content_bytes[: self.MAX_BYTES].decode(
                    "utf-8", errors="ignore"
                )
                content = truncated + f"\n... [文件过大，仅显示前 {self.MAX_BYTES // 1024}KB]"

            return ToolResult(success=True, content=header + content)

        except PermissionError:
            return ToolResult(success=False, content="", error=f"没有权限读取文件：{path}")
        except UnicodeDecodeError:
            return ToolResult(success=False, content="", error=f"文件编码无法识别（可能不是文本文件）：{path}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"读取文件时发生错误：{e}")
