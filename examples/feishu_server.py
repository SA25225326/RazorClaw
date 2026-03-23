"""
飞书机器人启动脚本（WebSocket 模式）。

使用 WebSocket 长连接模式，无需内网穿透！

使用方式：
    1. 复制 .env.example 为 .env，填入配置
    2. 运行：uv run python examples/feishu_server.py

环境变量（可在 .env 文件中配置）：
    FEISHU_APP_ID       - 飞书应用 ID
    FEISHU_APP_SECRET   - 飞书应用密钥
    OPENAI_BASE_URL     - LLM API 地址
    OPENAI_API_KEY      - LLM API 密钥
    OPENAI_MODEL        - 模型名称（默认 glm-5）
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from poiclaw.server.feishu import FeishuBot, FeishuConfig

# 加载 .env 文件
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)


def main():
    """启动飞书机器人"""
    # 读取配置
    config = FeishuConfig(
        feishu_app_id=os.environ.get("FEISHU_APP_ID", ""),
        feishu_app_secret=os.environ.get("FEISHU_APP_SECRET", ""),
        llm_base_url=os.environ.get("OPENAI_BASE_URL", ""),
        llm_api_key=os.environ.get("OPENAI_API_KEY", ""),
        llm_model=os.environ.get("OPENAI_MODEL", "glm-5"),
        session_base_path=os.environ.get("SESSION_BASE_PATH", ".poiclaw"),
        max_steps=int(os.environ.get("MAX_STEPS", "10")),
    )

    # 检查必要配置
    if not config.feishu_app_id or not config.feishu_app_secret:
        print("错误：请设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET 环境变量")
        return

    if not config.llm_base_url or not config.llm_api_key:
        print("错误：请设置 OPENAI_BASE_URL 和 OPENAI_API_KEY 环境变量")
        return

    # 创建并启动机器人
    bot = FeishuBot(config)

    try:
        # start() 会阻塞，直到连接断开
        bot.start()
    except KeyboardInterrupt:
        print("\n[Feishu] 收到停止信号，正在退出...")
    except Exception as e:
        print(f"[Feishu] 发生错误: {e}")


if __name__ == "__main__":
    main()
