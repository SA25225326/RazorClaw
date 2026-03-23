"""
飞书 IM 接入模块（WebSocket 长连接模式）。

使用飞书官方 SDK 的 WebSocket 长连接接收事件，无需内网穿透。

使用方式：
    from poiclaw.server.feishu import FeishuBot, FeishuConfig

    config = FeishuConfig(
        feishu_app_id="...",
        feishu_app_secret="...",
        llm_base_url="...",
        llm_api_key="...",
    )

    bot = FeishuBot(config)
    bot.start()  # 阻塞运行
"""

from __future__ import annotations

import asyncio
import collections
import json
from typing import TYPE_CHECKING

import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    P2ImMessageReceiveV1,
)
from pydantic import BaseModel, Field

from poiclaw.core import Agent, AgentConfig, FileSessionManager, HookManager, ToolRegistry
from poiclaw.extensions import SandboxExtension
from poiclaw.llm import LLMClient
from poiclaw.tools import register_all_tools

if TYPE_CHECKING:
    pass


# ============================================================================
# 全局并发锁（防止同一用户快速连发消息导致文件损坏）
# ============================================================================

session_locks: dict[str, asyncio.Lock] = collections.defaultdict(asyncio.Lock)


# ============================================================================
# 配置模型
# ============================================================================


class FeishuConfig(BaseModel):
    """飞书 + LLM 配置"""

    # 飞书配置
    feishu_app_id: str = Field(..., description="飞书应用 ID")
    feishu_app_secret: str = Field(..., description="飞书应用密钥")

    # LLM 配置
    llm_base_url: str = Field(..., description="LLM API 地址")
    llm_api_key: str = Field(..., description="LLM API 密钥")
    llm_model: str = Field(default="glm-5", description="模型名称")

    # 会话配置
    session_base_path: str = Field(default=".poiclaw", description="会话存储路径")

    # Agent 配置
    max_steps: int = Field(default=10, description="Agent 最大步数")


# ============================================================================
# 辅助函数
# ============================================================================


def extract_text_from_content(content: str) -> str | None:
    """
    从飞书消息 content 中提取文本。

    Args:
        content: JSON 字符串，如 '{"text":"你好"}'

    Returns:
        提取的文本，解析失败返回 None
    """
    try:
        data = json.loads(content)
        return data.get("text")
    except (json.JSONDecodeError, TypeError):
        return None


# ============================================================================
# 飞书 WebSocket 机器人
# ============================================================================


class FeishuBot:
    """
    飞书 WebSocket 机器人。

    使用飞书官方 SDK 的 WebSocket 长连接接收事件，无需内网穿透。

    用法：
        config = FeishuConfig(...)
        bot = FeishuBot(config)
        await bot.start()  # 阻塞运行
    """

    def __init__(self, config: FeishuConfig) -> None:
        self.config = config
        self._client: lark.Client | None = None
        self._ws_client: lark.ws.Client | None = None

    def start(self) -> None:
        """
        启动 WebSocket 连接并监听消息。

        此方法会阻塞，直到连接断开或发生错误。
        注意：lark-oapi SDK 的 ws.Client.start() 是同步方法。
        """
        # 1. 创建飞书 API 客户端（用于发送消息）
        self._client = lark.Client.builder() \
            .app_id(self.config.feishu_app_id) \
            .app_secret(self.config.feishu_app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        # 2. 创建事件处理器
        event_handler = lark.EventDispatcherHandler.builder(
            "", "", lark.LogLevel.INFO
        ) \
            .register_p2_im_message_receive_v1(self._on_message) \
            .build()

        # 3. 创建 WebSocket 客户端
        self._ws_client = lark.ws.Client(
            app_id=self.config.feishu_app_id,
            app_secret=self.config.feishu_app_secret,
            log_level=lark.LogLevel.DEBUG,
            event_handler=event_handler,
            auto_reconnect=True,
        )

        print(f"""
╔════════════════════════════════════════════════════════════╗
║                    PoiClaw Feishu Bot                        ║
╠════════════════════════════════════════════════════════════╣
║  模式: WebSocket 长连接（无需内网穿透）
║  状态: 正在连接...
╚════════════════════════════════════════════════════════════╝
        """)

        # 4. 启动 WebSocket 连接（阻塞）
        self._ws_client.start()

    def stop(self) -> None:
        """
        停止 WebSocket 连接。

        注意：lark-oapi SDK 的 ws.Client 没有提供 stop() 方法，
        但设置 _ws_client 为 None 后，主进程退出时会自动清理连接。
        """
        print("[Feishu] 正在停止...")
        self._ws_client = None
        print("[Feishu] 已断开连接")

    def _on_message(self, data: P2ImMessageReceiveV1) -> None:
        """
        处理收到的消息（同步回调，由 SDK 调用）。

        Args:
            data: 飞书消息事件数据
        """
        try:
            # 提取消息信息
            message = data.event.message
            sender = data.event.sender

            # 过滤非文本消息
            if message.message_type != "text":
                print(f"[Feishu] 忽略非文本消息: type={message.message_type}")
                return

            # 提取文本内容
            text = extract_text_from_content(message.content)
            if not text:
                print(f"[Feishu] 无法提取文本内容: content={message.content[:100]}")
                return

            # 获取发送者 open_id
            open_id = sender.sender_id.open_id
            message_id = message.message_id

            print(f"[Feishu] 收到消息: open_id={open_id}, text={text[:50]}...")

            # 在新的事件循环中运行异步任务
            # （因为 SDK 的回调是同步的，但我们的处理逻辑是异步的）
            asyncio.create_task(
                self._handle_message_async(open_id, text, message_id)
            )

        except Exception as e:
            print(f"[Feishu] 处理消息异常: {e}")

    async def _handle_message_async(
        self,
        open_id: str,
        text: str,
        message_id: str,
    ) -> None:
        """
        异步处理消息：运行 Agent 并回复。

        Args:
            open_id: 用户 ID
            text: 消息文本
            message_id: 消息 ID（用于回复）
        """
        # 获取用户锁，防止并发写入
        async with session_locks[open_id]:
            try:
                # 运行 Agent
                response = await self._run_agent(open_id, text)
                print(f"[Feishu] Agent 运行完成: open_id={open_id}")

                # 回复消息
                success = await self._reply_message(message_id, response)
                if success:
                    print(f"[Feishu] 消息回复成功: open_id={open_id}")
                else:
                    print(f"[Feishu] 消息回复失败: open_id={open_id}")

            except Exception as e:
                print(f"[Feishu] Agent 运行异常: {e}")
                # 尝试发送错误消息
                try:
                    await self._reply_message(
                        message_id,
                        f"抱歉，处理您的请求时发生错误：{e}",
                    )
                except Exception:
                    pass

    async def _run_agent(self, open_id: str, text: str) -> str:
        """
        运行 Agent 处理消息。

        Args:
            open_id: 用户 ID（作为 session_id）
            text: 用户输入文本

        Returns:
            str: Agent 的回复
        """
        # 1. 实例化 LLMClient
        llm = LLMClient(
            base_url=self.config.llm_base_url,
            api_key=self.config.llm_api_key,
            model=self.config.llm_model,
        )

        # 2. 注册工具
        tools = ToolRegistry()
        register_all_tools(tools)

        # 3. 添加安全钩子
        hooks = HookManager()
        sandbox = SandboxExtension()
        hooks.add_before_execute(sandbox.get_hook())

        # 4. 实例化会话管理器
        session_manager = FileSessionManager(base_path=self.config.session_base_path)

        # 5. 创建 Agent（以 open_id 为 session_id）
        agent = Agent(
            llm_client=llm,
            tools=tools,
            hooks=hooks,
            config=AgentConfig(max_steps=self.config.max_steps),
            session_manager=session_manager,
            session_id=open_id,
        )

        # 6. 运行 Agent
        print(f"[Feishu] Agent 开始运行: open_id={open_id}, text={text[:50]}...")
        response = await agent.run(text)

        return response

    def _reply_message(self, message_id: str, content: str) -> bool:
        """
        回复消息给用户。

        Args:
            message_id: 父消息 ID
            content: 回复内容

        Returns:
            bool: 是否成功
        """
        # 构建请求
        request = CreateMessageRequest.builder() \
            .receive_id_type("open_id") \
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(message_id)
                .msg_type("text")
                .content(json.dumps({"text": content}, ensure_ascii=False))
                .build()
            ) \
            .build()

        # 发送回复
        response = self._client.im.v1.message.create(request)

        if not response.success():
            print(f"[Feishu] 发送消息失败: code={response.code}, msg={response.msg}")
            return False

        return True
