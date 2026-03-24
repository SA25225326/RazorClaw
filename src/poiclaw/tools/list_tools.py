"""工具查询工具 - 用于渐进式加载"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from poiclaw.core import BaseTool, ToolResult

if TYPE_CHECKING:
    from poiclaw.core import ToolRegistry


class ListToolsTool(BaseTool):
    """查询工具详情 - 让 Agent 按需获取完整 Schema"""

    def __init__(self, registry: ToolRegistry) -> None:
        self.registry = registry

    @property
    def name(self) -> str:
        return "list_tools"

    @property
    def description(self) -> str:
        return "查询工具的详细信息。当你需要了解某个工具的完整参数和用法时调用。"

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tool_name": {
                    "type": "string",
                    "description": "要查询的工具名称，不填则返回所有工具简介",
                }
            },
        }

    async def execute(self, tool_name: str | None = None) -> ToolResult:
        if tool_name:
            schema = self.registry.get_tool_schema(tool_name)
            if schema:
                return ToolResult(
                    success=True,
                    content=json.dumps(schema, ensure_ascii=False, indent=2),
                )
            return ToolResult(success=False, error=f"工具 '{tool_name}' 不存在")
        else:
            return ToolResult(success=True, content=self.registry.to_brief())
