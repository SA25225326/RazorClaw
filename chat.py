"""
PoiClaw 本地命令行交互模式。

使用方式：
    uv run python chat.py
"""

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from poiclaw.llm import LLMClient
from poiclaw.core import Agent, AgentConfig, ToolRegistry, HookManager, FileSessionManager
from poiclaw.tools import register_all_tools
from poiclaw.extensions import SandboxExtension


async def main():
    # 加载环境变量
    load_dotenv(Path(__file__).parent / ".env")

    # 检查配置
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    model = os.environ.get("OPENAI_MODEL", "glm-5")

    if not api_key or api_key == "your_api_key_here":
        print("错误：请先在 .env 文件中配置 OPENAI_API_KEY")
        return

    # 创建 LLM 客户端
    llm = LLMClient(
        base_url=base_url,
        api_key=api_key,
        model=model,
    )

    # 注册工具
    tools = ToolRegistry()
    register_all_tools(tools)

    # 添加安全沙箱
    hooks = HookManager()
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

    # 创建会话管理器（支持多轮对话）
    session_manager = FileSessionManager(base_path=".poiclaw")
    session_id = session_manager.generate_id()

    # 创建 Agent
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=10),
        session_manager=session_manager,
        session_id=session_id,
    )

    print("=" * 60)
    print("  PoiClaw 本地交互模式")
    print("  输入 'quit' 或 'exit' 退出")
    print("  输入 'clear' 开始新会话")
    print("=" * 60)
    print()

    while True:
        try:
            # 获取用户输入
            user_input = input("你: ").strip()

            if not user_input:
                continue

            # 退出命令
            if user_input.lower() in ["quit", "exit", "q"]:
                print("\n再见！")
                break

            # 清空会话
            if user_input.lower() == "clear":
                session_id = session_manager.generate_id()
                agent = Agent(
                    llm_client=llm,
                    tools=tools,
                    hooks=hooks,
                    config=AgentConfig(max_steps=10),
                    session_manager=session_manager,
                    session_id=session_id,
                )
                print("已开始新会话\n")
                continue

            # 运行 Agent
            print("\nAgent: ", end="", flush=True)
            response = await agent.run(user_input)
            print(response)
            print()

        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            print(f"\n错误: {e}\n")


if __name__ == "__main__":
    asyncio.run(main())
