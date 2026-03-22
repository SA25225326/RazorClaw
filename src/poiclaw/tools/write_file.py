"""文件写入工具"""

from __future__ import annotations

import asyncio
from pathlib import Path

from poiclaw.core import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    """
    文件写入工具。

    支持覆盖写入和追加写入两种模式。
    自动创建父目录。
    """

    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "写入文件。可以创建新文件或覆盖/追加到现有文件。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "文件路径",
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容",
                },
                "mode": {
                    "type": "string",
                    "enum": ["write", "append"],
                    "description": "写入模式：write（覆盖）或 append（追加）",
                    "default": "write",
                },
            },
            "required": ["path", "content"],
        }

    async def execute(
        self,
        path: str,
        content: str,
        mode: str = "write",
    ) -> ToolResult:
        """
        写入文件。

        Args:
            path: 文件路径
            content: 要写入的内容
            mode: 写入模式（write 或 append）

        Returns:
            ToolResult: 包含写入结果或错误信息
        """
        try:
            file_path = Path(path).expanduser().resolve()

            # 自动创建父目录
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # 确定写入模式
            if mode == "append":
                write_mode = "a"
                action = "追加"
            else:
                write_mode = "w"
                action = "写入"

            # 使用 asyncio.to_thread 写入文件
            def _write():
                with open(file_path, write_mode, encoding="utf-8") as f:
                    f.write(content)
                return len(content)

            bytes_written = await asyncio.to_thread(_write)

            return ToolResult(
                success=True,
                content=f"成功{action} {bytes_written} 字节到 {path}",
            )

        except PermissionError:
            return ToolResult(success=False, content="", error=f"没有权限写入文件：{path}")
        except IsADirectoryError:
            return ToolResult(success=False, content="", error=f"路径是目录，不是文件：{path}")
        except Exception as e:
            return ToolResult(success=False, content="", error=f"写入文件时发生错误：{e}")
