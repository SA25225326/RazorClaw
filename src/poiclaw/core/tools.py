"""工具抽象基类和注册器"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    pass


class ToolResult(BaseModel):
    """工具执行结果"""

    success: bool
    content: str
    error: str | None = None


class BaseTool(ABC):
    """
    工具基类 - 所有工具必须继承此类。

    实现一个工具只需要：
    1. 定义 name, description, parameters_schema
    2. 实现 async execute() 方法
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称（唯一标识）"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述（给 LLM 看的，描述工具的功能）"""
        pass

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """
        参数 JSON Schema。

        示例：
        {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "要执行的命令"}
            },
            "required": ["cmd"]
        }
        """
        return {}

    @abstractmethod
    async def execute(self, **kwargs: Any) -> ToolResult:
        """
        执行工具。

        Args:
            **kwargs: 工具参数

        Returns:
            ToolResult: 执行结果
        """
        pass

    def to_llm_tool(self) -> dict[str, Any]:
        """转换为 LLM API 需要的工具格式"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }


class ToolRegistry:
    """
    工具注册器。

    用法：
        registry = ToolRegistry()
        registry.register(BashTool())
        registry.register(ReadTool())

        # 获取工具
        tool = registry.get("bash")

        # 转换为 LLM API 格式
        tools = registry.to_llm_tools()
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            return True
        return False

    def get(self, name: str) -> BaseTool | None:
        """获取工具"""
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        """检查工具是否存在"""
        return name in self._tools

    def get_all_tools(self) -> list[BaseTool]:
        """获取所有工具"""
        return list(self._tools.values())

    def get_all_names(self) -> list[str]:
        """获取所有工具名称"""
        return list(self._tools.keys())

    def to_llm_tools(self) -> list[dict[str, Any]]:
        """转换为 LLM API 需要的工具列表格式"""
        return [tool.to_llm_tool() for tool in self._tools.values()]

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return name in self._tools
