# PoiClaw

一个极简、透明的 Python Agent 框架，基于 [pi-mono](https://github.com/badlogic/pi-mono) 架构设计理念。

## 项目简介

PoiClaw 是一个从零开始实现的 Coding Agent 框架，核心理念是**极简、透明、可控**。不依赖 LangChain 等重型框架，每一行代码都清晰可读。

## 当前进度

```
✅ 已完成    🚧 进行中    ⏳ 待开发
```

| 模块 | 状态 | 说明 |
|------|------|------|
| LLM 调用层 | ✅ | 统一的 LLM API 调用，支持 OpenAI 兼容格式 |
| Agent 核心 | ✅ | ReAct 循环，工具调度，安全钩子 |
| 内置工具 | ⏳ | bash、read、write、edit |
| 会话管理 | ⏳ | 对话历史持久化 |
| IM 接入 | ⏳ | 飞书/钉钉机器人 |
| PM2 部署 | ⏳ | 后台长期运行 |

## 项目结构

```
PoiClaw/
├── src/
│   └── poiclaw/
│       ├── __init__.py
│       ├── llm/                 # ✅ LLM 调用模块
│       │   ├── __init__.py      # 模块入口
│       │   ├── client.py        # LLMClient 类
│       │   ├── exceptions.py    # 自定义异常
│       │   ├── stream.py        # SSE 流式解析
│       │   └── types.py         # Pydantic 类型定义
│       └── core/                # ✅ Agent 核心模块
│           ├── __init__.py      # 模块入口
│           ├── agent.py         # ReAct 循环 Agent
│           ├── tools.py         # BaseTool + ToolRegistry
│           └── hooks.py         # 安全拦截钩子
├── tests/
│   ├── test_llm.py              # LLM 模块测试
│   └── test_core.py             # Core 模块测试
├── pyproject.toml               # 项目配置 (uv)
└── README.md
```

## 功能特性

### LLM 模块

- ✅ 统一的 LLM 调用接口
- ✅ 支持 OpenAI 兼容 API（OpenAI、智谱、Kimi、DeepSeek 等）
- ✅ 流式输出（SSE）
- ✅ 工具调用（Function Calling）
- ✅ 全异步（async/await）
- ✅ 强类型（Pydantic）
- ✅ 自定义异常处理

### Agent 核心模块

- ✅ **ReAct 循环** - 推理 -> 行动 -> 观察 的循环
- ✅ **工具系统** - BaseTool 抽象类 + ToolRegistry 注册器
- ✅ **安全钩子** - 执行前拦截危险命令 ⭐ 核心特色
- ✅ **状态管理** - 消息历史、步数计数器

## 快速开始

### 安装

```bash
git clone https://github.com/SA25225326/RazorClaw.git
cd RazorClaw
uv sync
```

### 配置

```bash
# 设置环境变量
export OPENAI_BASE_URL="https://api.openai.com/v1"
export OPENAI_API_KEY="your-api-key"
```

### 使用示例

#### LLM 客户端

```python
import asyncio
from poiclaw.llm import LLMClient, Message, StreamEventType

async def main():
    client = LLMClient(
        base_url="https://api.openai.com/v1",
        api_key="your-api-key",
        model="gpt-4o-mini",
    )

    # 非流式调用
    response = await client.chat([Message.user("你好！")])
    print(response.content)

    # 流式调用
    async for event in client.stream([Message.user("讲个笑话")]):
        if event.type == StreamEventType.TEXT_DELTA:
            print(event.delta, end="", flush=True)

asyncio.run(main())
```

#### Agent + 工具 + 安全钩子

```python
import asyncio
from poiclaw.llm import LLMClient
from poiclaw.core import (
    Agent, AgentConfig,
    BaseTool, ToolRegistry, ToolResult,
    HookManager, create_bash_safety_hook,
)

# 定义自定义工具
class EchoTool(BaseTool):
    @property
    def name(self) -> str:
        return "echo"

    @property
    def description(self) -> str:
        return "回显输入的文本"

    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "要回显的文本"},
            },
            "required": ["text"],
        }

    async def execute(self, text: str) -> ToolResult:
        return ToolResult(success=True, content=f"[Echo] {text}")

async def main():
    # 设置 LLM
    llm = LLMClient(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key="your-api-key",
        model="glm-5",
    )

    # 注册工具
    tools = ToolRegistry()
    tools.register(EchoTool())

    # 添加安全钩子
    hooks = HookManager()
    hooks.add_before_execute(create_bash_safety_hook())

    # 创建 Agent
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=10),
    )

    # 运行
    response = await agent.run("你好！")
    print(response)

asyncio.run(main())
```

## 支持的 API

| API | Base URL |
|-----|----------|
| OpenAI | `https://api.openai.com/v1` |
| 智谱 AI (GLM) | `https://open.bigmodel.cn/api/paas/v4` |
| 智谱 CodingPlan | `https://open.bigmodel.cn/api/coding/paas/v4` |
| Kimi | `https://api.moonshot.cn/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |

## 技术栈

- **Python 3.12+**
- **httpx** - HTTP 请求
- **pydantic** - 数据校验
- **uv** - 包管理

## 参考资料

- [pi-mono](https://github.com/badlogic/pi-mono) - 极简 coding agent 参考
- [Learn-OpenClaw](https://github.com/poi-agent/Learn-OpenClaw) - Agent 学习教程

## License

MIT

---

**注意**：本项目为学习目的开发，代码全部手写，不依赖 LangChain 等重型框架。
