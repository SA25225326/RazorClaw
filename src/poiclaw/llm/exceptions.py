"""LLM 模块自定义异常"""

from __future__ import annotations


class LLMError(Exception):
    """LLM 调用基础异常"""

    pass


class LLMConnectionError(LLMError):
    """网络连接错误（DNS 解析失败、连接拒绝等）"""

    pass


class LLMTimeoutError(LLMError):
    """请求超时"""

    pass


class LLMAPIError(LLMError):
    """API 返回错误（非 200 状态码）"""

    def __init__(self, status_code: int, message: str) -> None:
        self.status_code = status_code
        self.message = message
        super().__init__(f"API Error [{status_code}]: {message}")


class LLMStreamError(LLMError):
    """流式响应解析错误"""

    pass
