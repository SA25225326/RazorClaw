"""Bash 命令执行工具"""

from __future__ import annotations

import asyncio

from poiclaw.core import BaseTool, ToolResult


class BashTool(BaseTool):
    """
    Bash 命令执行工具。

    使用 asyncio.create_subprocess_shell 异步执行命令，
    支持超时控制，捕获 stdout 和 stderr。
    """

    # 输出截断限制
    MAX_BYTES = 30 * 1024  # 30KB
    MAX_LINES = 2000

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "执行 bash 命令。可以运行 shell 命令，如 ls、cat、grep 等。"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "要执行的 bash 命令",
                },
                "timeout": {
                    "type": "integer",
                    "description": "超时时间（秒），默认 30 秒",
                    "default": 30,
                },
            },
            "required": ["command"],
        }

    async def execute(self, command: str, timeout: int = 30) -> ToolResult:
        """
        执行 bash 命令。

        Args:
            command: 要执行的命令
            timeout: 超时时间（秒）

        Returns:
            ToolResult: 包含执行结果或错误信息
        """
        try:
            # 创建子进程
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                shell=True,
            )

            # 等待执行完成（带超时）
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # 超时，杀死进程
                process.kill()
                await process.wait()
                return ToolResult(
                    success=False,
                    content="",
                    error=f"命令执行超时（{timeout} 秒），已终止",
                )

            # 解码输出
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            # 合并输出
            output = stdout
            if stderr:
                output = f"{output}\n[stderr]\n{stderr}" if output else stderr

            # 截断输出（行数）
            lines = output.split("\n")
            if len(lines) > self.MAX_LINES:
                lines = lines[-self.MAX_LINES :]
                output = "\n".join(lines)
                output = f"[输出被截断，仅显示最后 {self.MAX_LINES} 行]\n{output}"

            # 截断输出（字节数）
            if len(output.encode("utf-8")) > self.MAX_BYTES:
                output_bytes = output.encode("utf-8")
                output = output_bytes[-self.MAX_BYTES :].decode(
                    "utf-8", errors="ignore"
                )
                output = f"[输出被截断，仅显示最后 {self.MAX_BYTES // 1024}KB]\n{output}"

            # 判断成功与否
            if process.returncode == 0:
                return ToolResult(success=True, content=output or "命令执行成功（无输出）")
            else:
                return ToolResult(
                    success=False,
                    content=output,
                    error=f"命令退出码：{process.returncode}",
                )

        except Exception as e:
            return ToolResult(success=False, content="", error=f"执行命令时发生错误：{e}")
