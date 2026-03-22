"""
内置工具模块。

提供 4 个核心编程工具：
- BashTool: 执行 bash 命令
- ReadFileTool: 读取文件
- WriteFileTool: 写入文件
- EditFileTool: 编辑文件（字符串替换）
"""

from __future__ import annotations

from poiclaw.core import ToolRegistry

from .bash import BashTool
from .edit_file import EditFileTool
from .read_file import ReadFileTool
from .write_file import WriteFileTool

__all__ = [
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "register_all_tools",
]


def register_all_tools(registry: ToolRegistry) -> None:
    """
    注册所有内置工具到 ToolRegistry。

    用法：
        from poiclaw.core import ToolRegistry
        from poiclaw.tools import register_all_tools

        registry = ToolRegistry()
        register_all_tools(registry)
    """
    registry.register(BashTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())
