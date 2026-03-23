"""
PoiClaw 飞书机器人启动入口（PM2 部署）。

使用 WebSocket 长连接模式，无需内网穿透。

使用方式：
    # 开发环境
    uv run python main.py

    # PM2 部署
    pm2 start ecosystem.config.js
    pm2 logs poiclaw-agent
    pm2 stop poiclaw-agent

环境变量（可在 .env 文件中配置）：
    FEISHU_APP_ID       - 飞书应用 ID
    FEISHU_APP_SECRET   - 飞书应用密钥
    OPENAI_BASE_URL     - LLM API 地址
    OPENAI_API_KEY      - LLM API 密钥
    OPENAI_MODEL        - 模型名称（默认 glm-5）
    MAX_STEPS           - Agent 最大步数（默认 10）
    SESSION_BASE_PATH   - 会话存储路径（默认 .poiclaw）
"""

from __future__ import annotations

import os
import signal
import sys
from pathlib import Path

from dotenv import load_dotenv

from poiclaw.server.feishu import FeishuBot, FeishuConfig

# 全局变量，用于信号处理
_bot: FeishuBot | None = None


def load_config() -> FeishuConfig:
    """从环境变量加载配置"""
    # 加载 .env 文件
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)

    return FeishuConfig(
        feishu_app_id=os.environ.get("FEISHU_APP_ID", ""),
        feishu_app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
        llm_base_url=os.environ.get("OPENAI_BASE_URL", ""),
        llm_api_key=os.environ.get("OPENAI_API_KEY", ""),
        llm_model=os.environ.get("OPENAI_MODEL", "glm-5"),
        session_base_path=os.environ.get("SESSION_BASE_PATH", ".poiclaw"),
        max_steps=int(os.environ.get("MAX_STEPS", "10")),
    )


def signal_handler(signum: int, frame) -> None:
    """处理终止信号，优雅退出"""
    global _bot

    signal_name = signal.Signals(signum).name
    print(f"\n[Main] 收到信号 {signal_name}，正在优雅退出...")

    if _bot:
        _bot.stop()

    # 给 SDK 一点时间清理连接
    import time
    time.sleep(1)

    print("[Main] 退出完成")
    sys.exit(0)


def main() -> None:
    """启动飞书机器人"""
    global _bot

    # 1. 加载配置
    config = load_config()

    # 2. 检查必要配置
    if not config.feishu_app_id or not config.feishu_app_secret:
        print("错误：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
        print("提示：复制 .env.example 为 .env，填入你的配置")
        sys.exit(1)

    if not config.llm_base_url or not config.llm_api_key:
        print("错误：请设置 OPENAI_BASE_URL 和 OPENAI_API_KEY 环境变量")
        sys.exit(1)

    # 3. 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 4. 创建并启动机器人
    _bot = FeishuBot(config)

    try:
        # start() 会阻塞，直到连接断开或收到停止信号
        _bot.start()
    except KeyboardInterrupt:
        print("\n[Main] 收到键盘中断，正在退出...")
    except Exception as e:
        print(f"[Main] 发生错误: {e}")
        sys.exit(1)
    finally:
        if _bot:
            _bot.stop()


if __name__ == "__main__":
    main()
