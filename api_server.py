"""
PoiClaw Agent HTTP API 服务器。

提供 HTTP 接口供外部调用 Agent。

使用方式：
    uv run python api_server.py

API 端点：
    POST /chat
    Body: {"message": "用户消息", "session_id": "会话ID（可选）"}
    Response: {"response": "Agent回复"}
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from poiclaw.llm import LLMClient
from poiclaw.core import Agent, AgentConfig, ToolRegistry, HookManager, FileSessionManager
from poiclaw.tools import register_all_tools
from poiclaw.extensions import SandboxExtension

# 加载环境变量
load_dotenv(Path(__file__).parent / ".env")

# 创建 FastAPI 应用
app = FastAPI(title="PoiClaw Agent API", version="1.0.0")


class ChatRequest(BaseModel):
    """聊天请求"""
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    """聊天响应"""
    response: str


def create_agent(session_id: str | None = None) -> Agent:
    """创建 Agent 实例"""
    # 1. 创建 LLM 客户端
    llm = LLMClient(
        base_url=os.environ.get("OPENAI_BASE_URL", ""),
        api_key=os.environ.get("OPENAI_API_KEY", ""),
        model=os.environ.get("OPENAI_MODEL", "glm-4-flash"),
    )

    # 2. 注册工具
    tools = ToolRegistry()
    register_all_tools(tools)

    # 3. 添加安全沙箱
    hooks = HookManager()
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

    # 4. 创建会话管理器
    session_manager = FileSessionManager(
        base_path=os.environ.get("SESSION_BASE_PATH", ".poiclaw")
    )

    # 5. 创建 Agent
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=int(os.environ.get("MAX_STEPS", "10"))),
        session_manager=session_manager,
        session_id=session_id,
    )

    return agent


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    处理聊天请求。

    Args:
        request: 包含 message 和可选的 session_id

    Returns:
        ChatResponse: Agent 的回复
    """
    if not request.message:
        raise HTTPException(status_code=400, detail="message 不能为空")

    try:
        # 创建 Agent
        agent = create_agent(request.session_id)

        # 运行 Agent
        response = await agent.run(request.message)

        return ChatResponse(response=response)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent 运行错误: {str(e)}")


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("API_PORT", "8080"))

    print(f"Starting PoiClaw Agent API on http://0.0.0.0:{port}")
    print(f"API docs: http://0.0.0.0:{port}/docs")

    uvicorn.run(app, host="0.0.0.0", port=port)
