# PoiClaw 🦀

一个极简、透明的 Python Agent 框架，基于 [pi-mono](https://github.com/badlogic/pi-mono) 架构设计理念。

## 项目简介

PoiClaw 是一个从零开始实现的 Coding Agent 框架，核心理念是**极简、透明、可控**。不依赖 LangChain 等重型框架，每一行代码都清晰可读。

### 为什么叫 PoiClaw？

- **Poi** - 作者的昵称
- **Claw** - 爪子，象征 Agent 抓取和处理任务的能力

## 当前进度

```
✅ 已完成
🚧 进行中
⏳ 待开发
```

| 模块 | 状态 | 说明 |
|------|------|------|
| LLM 调用层 | ✅ 已完成 | 统一的 LLM API 调用，支持 OpenAI 兼容格式 |
| Agent 循环 | ⏳ 待开发 | ReAct 循环，工具调度 |
| 工具系统 | ⏳ 待开发 | bash、read、write、edit 等核心工具 |
| 会话管理 | ⏳ 待开发 | 对话历史持久化 |
| IM 接入 | ⏳ 待开发 | 飞书/钉钉机器人 |
| PM2 部署 | ⏳ 待开发 | 后台长期运行 |

## 项目结构

```
PoiClaw/
├── src/
│   └── poiclaw/
│       ├── __init__.py
│       └── llm/                 # ✅ LLM 调用模块
│           ├── __init__.py      # 模块入口
│           ├── client.py        # LLMClient 类
│           ├── exceptions.py    # 自定义异常
│           ├── stream.py        # SSE 流式解析
│           └── types.py         # pydantic 类型定义
├── tests/
│   └── test_llm.py              # LLM 模块测试
├── pyproject.toml               # 项目配置 (uv)
└── README.md
```

## LLM 模块功能

- ✅ 统一的 LLM 调用接口
- ✅ 支持 OpenAI 兼容 API（OpenAI、智谱、Kimi、DeepSeek 等）
- ✅ 流式输出（SSE）
- ✅ 工具调用（Function Calling）
- ✅ 全异步（async/await）
- ✅ 强类型（pydantic）
- ✅ 自定义异常处理

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/你的用户名/RazorClaw.git
cd RazorClaw

# 安装依赖 (需要先安装 uv)
uv sync
```

### 配置

```bash
# 设置环境变量
export OPENAI_BASE_URL="https://api.openai.com/v1"  # 或其他兼容 API
export OPENAI_API_KEY="your-api-key"
```

### 使用示例

```python
import asyncio
from poiclaw.llm import LLMClient, Message, Tool, StreamEventType

async def main():
    # 初始化客户端
    client = LLMClient(
        base_url="https://api.openai.com/v1",
        api_key="your-api-key",
        model="gpt-4o-mini",
    )

    # 非流式调用
    response = await client.chat([
        Message.user("Hello!")
    ])
    print(response.content)

    # 流式调用
    async for event in client.stream([Message.user("讲个笑话")]):
        if event.type == StreamEventType.TEXT_DELTA:
            print(event.delta, end="", flush=True)

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
