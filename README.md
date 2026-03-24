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
| **事件系统** | ✅ | 完整的生命周期事件，支持订阅/发射 |
| 内置工具 | ✅ | bash、read_file、write_file、edit_file、subagent |
| 扩展系统 | ✅ | BaseExtension 抽象基类 + SandboxExtension 安全沙箱 |
| 多智能体协作 | ✅ | SubagentTool (Tool-based Fork-Join 模式) |
| 会话管理 | ✅ | 对话历史持久化、多轮对话断点续传、Token 统计 |
| 上下文压缩 | ✅ | LLM 摘要压缩、智能切割点查找、分级记忆 |
| **系统提示词** | ✅ | 动态构建、工具感知指导原则、项目上下文 |
| **Skills 系统** | ✅ | 渐进式技能加载、Markdown 格式、95% Token 节省 |
| **Docker 沙箱** | ✅ | 容器隔离执行、宿主机保护 |
| IM 接入 | ✅ | 飞书机器人（WebSocket 模式）|
| PM2 部署 | ✅ | 后台长期运行，崩溃自动重启 |

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
│       ├── core/                # ✅ Agent 核心模块
│       │   ├── __init__.py      # 模块入口
│       │   ├── agent.py         # ReAct 循环 Agent
│       │   ├── events.py        # ✅ 事件系统模块
│       │   ├── tools.py         # BaseTool + ToolRegistry
│       │   ├── hooks.py         # 安全拦截钩子
│       │   ├── session.py       # 会话持久化管理
│       │   ├── compaction.py    # ✅ 上下文压缩模块
│       │   └── system_prompt.py # ✅ 系统提示词构建
│       ├── sandbox/             # ✅ Docker 沙箱模块
│       │   ├── __init__.py      # 模块入口
│       │   └── docker_manager.py # DockerSandbox 类
│       ├── skills/              # ✅ Skills 系统
│       │   ├── __init__.py      # 模块入口
│       │   ├── models.py        # Skill 数据模型
│       │   ├── loader.py        # Skill 加载器
│       │   └── registry.py      # Skill 注册表
│       └── tools/               # ✅ 内置工具模块
│           ├── __init__.py      # 统一注册入口
│           ├── bash.py          # BashTool（支持沙箱模式）
│           ├── read_file.py     # ReadFileTool
│           ├── write_file.py    # WriteFileTool
│           ├── edit_file.py     # EditFileTool
│           ├── list_tools.py    # ✅ 渐进式工具查询
│           ├── read_skill.py    # ✅ 技能详情查询
│           └── subagent.py      # SubagentTool (多智能体协作)
│       └── extensions/          # ✅ 扩展模块
│           ├── __init__.py      # 模块入口
│           ├── base.py          # BaseExtension 抽象基类
│           └── sandbox.py       # SandboxExtension 安全沙箱
│       └── server/              # ✅ IM 接入模块
│           ├── __init__.py      # 模块入口
│           └── feishu.py        # 飞书机器人（WebSocket 模式）
├── skills/                      # ✅ 技能定义目录
│   ├── commit.md                # Git 提交技能
│   ├── review-pr.md             # PR 审查技能
│   └── test-runner.md           # 测试运行技能
├── tests/
│   ├── test_llm.py              # LLM 模块测试
│   ├── test_core.py             # Core 模块测试
│   ├── test_compaction.py       # 上下文压缩测试
│   ├── test_events.py           # ✅ 事件系统测试
│   ├── test_system_prompt_tokens.py  # ✅ 系统提示词 Token 测试
│   ├── test_progressive_tokens.py    # ✅ 渐进式工具加载测试
│   ├── test_skills_tokens.py         # ✅ Skills 系统 Token 测试
│   ├── test_docker_sandbox.py        # ✅ Docker 沙箱测试
│   ├── test_subagent_parallel.py     # ✅ Subagent 并行测试
│   └── test_tools.py            # Tools 模块测试
├── feishu-bot.js                # ✅ 飞书机器人（Node.js 版本）
├── api_server.py                # ✅ Python API 服务器
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

### 事件系统模块 ⭐ 新增

- ✅ **完整的事件流** - 覆盖 Agent 生命周期的所有关键节点
- ✅ **10 种事件类型**：
  - `agent_start` / `agent_end` - Agent 开始/结束
  - `turn_start` / `turn_end` - 回合开始/结束
  - `message_update` - 消息添加到上下文
  - `tool_call_start` / `tool_call_end` / `tool_call_error` - 工具调用生命周期
  - `context_compact` - 上下文压缩
  - `error` - 通用错误事件
- ✅ **灵活的订阅方式** - 装饰器 `@emitter.on()` 或 `add_handler()`
- ✅ **并发执行** - 多个处理器并发执行，不阻塞主流程
- ✅ **事件摘要** - `create_event_summary()` 生成可读的事件日志

### 内置工具模块

- ✅ **BashTool** - 执行 bash 命令（异步，30秒超时，输出截断）
- ✅ **ReadFileTool** - 读取文件（支持行范围）
- ✅ **WriteFileTool** - 写入文件（覆盖/追加模式）
- ✅ **EditFileTool** - 编辑文件（精确字符串替换）
- ✅ **SubagentTool** - 多智能体协作（Fork-Join 模式，支持 single/parallel/chain）
- ✅ **ListToolsTool** - 渐进式工具查询（按需获取工具详情）
- ✅ **ReadSkillTool** - 技能详情加载（渐进式披露）
- ✅ **ListSkillsTool** - 列出可用技能
- ✅ **统一注册** - `register_all_tools()` 一键注册

### 多智能体协作模块

- ✅ **Tool-based Fork-Join 模型** - 将多智能体能力作为普通工具挂载到主 Agent
- ✅ **三种执行模式**：
  - `single` - 单任务模式
  - `parallel` - 并行执行（asyncio.gather）
  - `chain` - 串行链式执行（前一个结果作为下一个的上下文）
- ✅ **安全继承** - 子 Agent 必须继承 hooks，确保 SandboxExtension 在所有子节点生效
- ✅ **状态隔离** - 每个 Agent 拥有独立的 messages 上下文

### 扩展模块

- ✅ **BaseExtension** - 抽象基类（类似 Java Interface），支持 4 种扩展能力
- ✅ **SandboxExtension** - 安全沙箱，正则匹配拦截 rm -rf、wget、curl 等高危命令
- ✅ **ExtensionManager** - 扩展管理器，统一管理注册、事件分发、钩子链
- ✅ **4 种扩展能力**：
  - `get_hook()` - 拦截工具调用（AOP 切面）
  - `get_tools()` - 注册新工具给 LLM
  - `get_commands()` - 注册斜杠命令（如 /diff、/files）
  - `get_event_handlers()` - 订阅 Agent 事件（agent_start、tool_call 等）

### 会话管理模块

- ✅ **FileSessionManager** - 基于文件系统的会话持久化管理器
- ✅ **分离存储** - metadata（轻量元数据）+ data（完整消息）
- ✅ **断点续传** - 支持多轮对话历史恢复
- ✅ **Token 统计** - 累积 input/output/cache_read/cache_write/total_tokens
- ✅ **标题保护** - 保存时 title=None 保留原标题
- ✅ **内存保护** - 只在 messages 为空时加载历史，避免重复 I/O
- ✅ **异步 I/O** - 使用 asyncio.to_thread 包装文件操作
- ✅ **容错机制** - 文件不存在返回 None，保存失败打印警告但不中断

### 上下文压缩模块 ⭐ 新增

- ✅ **LLM 摘要压缩** - 当对话超过 context_window - reserve_tokens 时自动触发
- ✅ **Token 估算** - 基于 `len(text) // 4` 的保守估算
- ✅ **智能切割点** - 从后往前遍历，保持 Turn 完整性（在 user 消息处切割）
- ✅ **结构化摘要** - 包含目标、进度、决策、下一步、关键上下文
- ✅ **增量更新** - 支持基于已有摘要的增量更新，避免重复摘要
- ✅ **压缩历史** - 保留多次压缩记录，便于调试和恢复

### 系统提示词构建模块 ⭐ 新增

- ✅ **动态构建** - 根据工具列表自动生成指导原则
- ✅ **自定义提示词** - 支持完全替换默认提示词
- ✅ **项目上下文** - 支持加载 CLAUDE.md 等上下文文件
- ✅ **工具感知指导** - 根据可用工具自动添加使用建议（如优先用 grep 而非 bash）
- ✅ **工作目录注入** - 自动注入当前工作目录和日期
- ✅ **灵活扩展** - `append_system_prompt` 追加额外内容

### 渐进式工具加载 ⭐ 新增

- ✅ **Token 节省** - 初始只注入工具简介，按需查询详情
- ✅ **ListToolsTool** - 让 Agent 查询工具的完整 Schema
- ✅ **ToolRegistry.to_brief()** - 生成工具简要描述列表
- ✅ **Agent 配置** - `progressive_tools=True` 启用模式

### Docker 沙箱模块 ⭐ 新增

- ✅ **容器隔离** - 命令在 Docker 容器内执行，保护宿主机
- ✅ **工作目录挂载** - 项目目录自动挂载到 `/workspace`
- ✅ **生命周期管理** - `start()` / `stop()` / `remove()` 完整控制
- ✅ **超时控制** - 支持命令执行超时
- ✅ **流式输出** - `exec_with_stream()` 支持实时输出

### 飞书接入模块 (server/feishu.py) ✅

- ✅ **WebSocket 长连接** - 使用飞书官方 SDK，无需内网穿透
- ✅ **消息接收** - 监听 `im.message.receive_v1` 事件
- ✅ **Agent 集成** - 每个用户独立会话，支持多轮对话
- ✅ **消息回复** - 通过飞书 API 回复消息
- ✅ **Node.js 版本** - 独立的 Node.js 飞书机器人（feishu-bot.js）

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

#### Agent + 内置工具 + 安全钩子

```python
import asyncio
from poiclaw.llm import LLMClient
from poiclaw.core import (
    Agent, AgentConfig,
    ToolRegistry, HookManager,
)
from poiclaw.tools import register_all_tools
from poiclaw.extensions import SandboxExtension

async def main():
    # 设置 LLM
    llm = LLMClient(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key="your-api-key",
        model="glm-5",
    )

    # 注册所有内置工具
    tools = ToolRegistry()
    register_all_tools(tools)  # 一键注册 bash, read_file, write_file, edit_file

    # 添加安全沙箱扩展
    hooks = HookManager()
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

    # 创建 Agent
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=10),
    )

    # 运行
    response = await agent.run("帮我列出当前目录的文件")
    print(response)

asyncio.run(main())
```

#### 自定义工具

```python
from poiclaw.core import BaseTool, ToolResult

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

# 注册自定义工具
tools.register(EchoTool())
```

#### 自定义扩展

```python
from poiclaw.extensions import (
    BaseExtension,
    ExtensionCommand,
    ExtensionContext,
    ExtensionManager,
    ToolCallEvent,
)
from poiclaw.core import HookContext, HookResult

class MyExtension(BaseExtension):
    @property
    def name(self) -> str:
        return "my_extension"

    @property
    def description(self) -> str:
        return "我的自定义扩展"

    # 1. 拦截工具调用
    def get_hook(self):
        async def my_hook(ctx: HookContext) -> HookResult:
            if ctx.tool_name == "bash":
                command = ctx.arguments.get("command", "")
                if "dangerous" in command:
                    return HookResult(
                        proceed=False,
                        reason="[拦截] 不允许执行危险命令",
                    )
            return HookResult(proceed=True)
        return my_hook

    # 2. 注册斜杠命令
    def get_commands(self):
        return {
            "hello": ExtensionCommand(
                name="hello",
                description="打招呼",
                handler=self._handle_hello,
            )
        }

    async def _handle_hello(self, args: list[str], ctx: ExtensionContext):
        print(f"Hello! Args: {args}")

    # 3. 订阅事件
    def get_event_handlers(self):
        return {
            "agent_start": [self._on_agent_start],
            "tool_call": [self._on_tool_call],
        }

    async def _on_agent_start(self, event, ctx):
        print(f"Agent started: {event.user_input}")

    async def _on_tool_call(self, event: ToolCallEvent, ctx):
        print(f"Tool called: {event.tool_name}")

# 使用 ExtensionManager 管理
manager = ExtensionManager()
manager.register(MyExtension())

# 获取所有钩子，注册到 Agent
for ext in manager.get_all_extensions():
    hook = ext.get_hook()
    if hook:
        hooks.add_before_execute(hook)
```

## 内置工具说明

| 工具 | 功能 | 参数 |
|------|------|------|
| `bash` | 执行命令 | `command`, `timeout`(可选, 默认30秒) |
| `read_file` | 读取文件 | `path`, `start_line`(可选), `end_line`(可选) |
| `write_file` | 写入文件 | `path`, `content`, `mode`("write"/"append") |
| `edit_file` | 编辑文件 | `path`, `old_text`, `new_text` |
| `subagent` | 多智能体协作 | `mode`("single"/"parallel"/"chain"), `tasks`, `max_steps`(可选) |
| `list_tools` | 查询工具详情 | `tool_name`(可选，不填返回所有工具简介) |
| `list_skills` | 列出可用技能 | 无参数 |
| `read_skill` | 读取技能详情 | `skill_name` |

## 会话管理使用示例

### 基础用法：带会话持久化的 Agent

```python
import asyncio
from poiclaw.llm import LLMClient
from poiclaw.core import (
    Agent, AgentConfig,
    ToolRegistry, HookManager,
    FileSessionManager,
)
from poiclaw.tools import register_all_tools
from poiclaw.extensions import SandboxExtension

async def main():
    # 1. 设置 LLM
    llm = LLMClient(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key="your-api-key",
        model="glm-5",
    )

    # 2. 注册工具和钩子
    tools = ToolRegistry()
    register_all_tools(tools)

    hooks = HookManager()
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

    # 3. 创建会话管理器
    session_manager = FileSessionManager(base_path=".poiclaw")
    session_id = session_manager.generate_id()

    # 4. 创建带会话持久化的 Agent
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=10),
        session_manager=session_manager,
        session_id=session_id,
    )

    # 5. 第一次对话
    response1 = await agent.run("帮我分析当前项目的结构")
    print(response1)

    # 6. 第二次对话（自动加载历史）
    response2 = await agent.run("继续，帮我写一个 README")
    print(response2)

    # 7. 查看会话统计
    stats = agent.get_usage_stats()
    print(f"总 Token: {stats.total_tokens}")

asyncio.run(main())
```

### 会话列表和恢复

```python
import asyncio
from poiclaw.core import FileSessionManager

async def main():
    session_manager = FileSessionManager(base_path=".poiclaw")

    # 列出所有会话
    sessions = await session_manager.list_sessions()
    for s in sessions:
        print(f"[{s.id[:8]}] {s.title}")
        print(f"  消息数: {s.message_count}, Token: {s.usage.total_tokens}")
        print(f"  预览: {s.preview[:100]}...")

    # 恢复指定会话
    if sessions:
        session_id = sessions[0].id
        messages = await session_manager.load_session(session_id)
        print(f"恢复了 {len(messages)} 条消息")

    # 更新会话标题
    await session_manager.update_title(session_id, "新标题")

    # 删除会话
    await session_manager.delete_session(session_id)

asyncio.run(main())
```

### 存储结构

```
.poiclaw/
└── sessions/
    ├── metadata/
    │   └── {uuid}.json     # 轻量元数据（用于列表展示）
    └── data/
        └── {uuid}.json     # 完整消息列表
```

**SessionMetadata 结构**：
```json
{
  "id": "uuid",
  "title": "会话标题",
  "created_at": "2024-01-01T00:00:00",
  "last_modified": "2024-01-01T00:05:00",
  "message_count": 10,
  "usage": {
    "input": 1000,
    "output": 500,
    "cache_read": 200,
    "cache_write": 100,
    "total_tokens": 1800
  },
  "preview": "前 2KB 预览..."
}
```

## SubagentTool 使用示例

```python
import asyncio
from poiclaw.llm import LLMClient
from poiclaw.core import Agent, AgentConfig, ToolRegistry, HookManager
from poiclaw.tools import register_all_tools, register_subagent_tool
from poiclaw.extensions import SandboxExtension

async def main():
    # 1. 设置 LLM
    llm = LLMClient(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key="your-api-key",
        model="glm-5",
    )

    # 2. 注册工具
    tools = ToolRegistry()
    register_all_tools(tools)

    # 3. 设置安全沙箱
    hooks = HookManager()
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

    # 4. 注册 SubagentTool（必须注入 llm_client 和 hooks）
    register_subagent_tool(tools, llm_client=llm, hooks=hooks)

    # 5. 创建主 Agent
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=10),
    )

    # 6. 运行 - LLM 可以调用 subagent 工具
    response = await agent.run("""
    请使用 subagent 工具，以 parallel 模式并行执行：
    - 派一个前端专家分析 src/ui/ 目录的组件结构
    - 派一个后端专家分析 src/api/ 目录的接口设计
    """)
    print(response)

asyncio.run(main())
```

**LLM 调用 subagent 工具的参数示例**：

```json
{
    "mode": "parallel",
    "tasks": [
        {"agent_role": "前端专家", "instruction": "分析 src/ui/ 目录的组件结构"},
        {"agent_role": "后端专家", "instruction": "分析 src/api/ 目录的接口设计"}
    ],
    "max_steps": 5
}
```

## 系统提示词构建

```python
from poiclaw.core import build_system_prompt, BuildSystemPromptOptions, ToolInfo
from poiclaw.core import load_context_file

# 构建基础系统提示词
prompt = build_system_prompt(
    tools=[
        ToolInfo(name="bash", description="执行 shell 命令"),
        ToolInfo(name="read", description="读取文件内容"),
        ToolInfo(name="edit", description="编辑文件"),
    ],
    options=BuildSystemPromptOptions(
        cwd="/path/to/project",
        agent_name="Poiclaw",
    ),
)

# 加载项目上下文文件（如 CLAUDE.md）
context = load_context_file("CLAUDE.md")
if context:
    prompt = build_system_prompt(
        tools=[...],
        options=BuildSystemPromptOptions(
            context_files=[context],
            append_system_prompt="额外指令：保持回复简洁",
        ),
    )
```

## 渐进式工具加载

当工具很多时，初始注入所有工具 Schema 会消耗大量 Token。渐进式加载让 Agent 按需查询：

```python
import asyncio
from poiclaw.llm import LLMClient
from poiclaw.core import Agent, AgentConfig, ToolRegistry, HookManager
from poiclaw.tools import register_all_tools, register_progressive_tools
from poiclaw.extensions import SandboxExtension

async def main():
    llm = LLMClient(
        base_url="https://open.bigmodel.cn/api/coding/paas/v4",
        api_key="your-api-key",
        model="glm-5",
    )

    # 注册工具
    tools = ToolRegistry()
    register_all_tools(tools)
    register_progressive_tools(tools)  # 注册 ListToolsTool

    # 安全钩子
    hooks = HookManager()
    sandbox = SandboxExtension()
    hooks.add_before_execute(sandbox.get_hook())

    # 创建 Agent（启用渐进式加载）
    agent = Agent(
        llm_client=llm,
        tools=tools,
        hooks=hooks,
        config=AgentConfig(max_steps=10),
        progressive_tools=True,  # 关键：启用渐进式加载
    )

    # Agent 初始只获得工具简介，可通过 list_tools 查询详情
    response = await agent.run("帮我分析项目结构")
    print(response)

asyncio.run(main())
```

## Docker 沙箱使用

```python
import asyncio
from poiclaw.sandbox import DockerSandbox

async def main():
    # 创建沙箱
    sandbox = DockerSandbox(
        container_name="my-sandbox",
        workspace="/path/to/project",  # 挂载到容器的 /workspace
        image="python:3.11-slim",
    )

    # 启动容器
    await sandbox.start()

    try:
        # 在容器内执行命令
        exit_code, output = await sandbox.exec("ls -la", timeout=30)
        print(f"Exit code: {exit_code}")
        print(output)

        # 流式输出
        async for line in sandbox.exec_with_stream("pip install requests"):
            print(line, end="")

    finally:
        # 清理容器
        await sandbox.remove()

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

## 飞书机器人接入 ✅

PoiClaw 支持通过飞书官方 SDK 的 WebSocket 长连接模式接入飞书，**无需内网穿透**。

### 架构

```
飞书消息 → Node.js (feishu-bot.js) → HTTP → Python Agent (api_server.py) → 工具执行
```

- **Node.js**：负责飞书 WebSocket 连接，接收和发送消息
- **Python Agent**：负责 LLM 调用和工具执行

### 启动方式

**需要开两个终端**：

**终端 1 - 启动 Python API**：
```bash
uv run python api_server.py
```

**终端 2 - 启动飞书机器人**：
```bash
npm install  # 首次运行需要安装依赖
node feishu-bot.js
```

### 功能

飞书机器人支持：
- ✅ 执行命令（bash）
- ✅ 读取文件（read_file）
- ✅ 写入文件（write_file）
- ✅ 编辑文件（edit_file）
- ✅ 多轮对话（有上下文记忆）

### PM2 后台运行

```bash
# 启动 Python API
pm2 start "uv run python api_server.py" --name poiclaw-api

# 启动飞书机器人
pm2 start feishu-bot.js --name poiclaw-feishu

# 查看日志
pm2 logs

# 停止
pm2 stop poiclaw-api poiclaw-feishu
```

### 配置步骤

1. **在飞书开放平台创建应用**
   - 获取 App ID 和 App Secret
   - 启用机器人能力
   - 添加权限：`im:message`、`im:message:send_as_bot`
   - 事件订阅 → 选择「使用长连接接收事件」
   - 添加事件：`im.message.receive_v1`
   - **发布版本**

2. **配置环境变量**（`.env` 文件）
   ```bash
   FEISHU_APP_ID=cli_xxx
   FEISHU_APP_SECRET=xxx
   OPENAI_BASE_URL=https://open.bigmodel.cn/api/coding/paas/v4
   OPENAI_API_KEY=xxx
   OPENAI_MODEL=glm-4-flash
   ```

3. **常见问题**

   如果收不到消息事件，尝试：
   - 重置 App Secret
   - 重新添加 `im.message.receive_v1` 事件
   - 重新发布版本
   - 等待 1-2 分钟

## PM2 部署

使用 PM2 实现后台长期运行、崩溃自动重启。

### 安装 PM2

```bash
npm install -g pm2
```

### 启动机器人

```bash
# 开发环境（前台运行）
uv run python main.py

# PM2 部署（后台运行）
pm2 start ecosystem.config.js

# 查看日志
pm2 logs poiclaw-agent

# 查看状态
pm2 status

# 停止
pm2 stop poiclaw-agent

# 重启
pm2 restart poiclaw-agent
```

### PM2 配置说明

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: "poiclaw-agent",
    script: "main.py",
    interpreter: ".venv/Scripts/python.exe",  // Windows
    // interpreter: ".venv/bin/python",        // Linux/Mac
    autorestart: true,
    restart_delay: 3000,  // 断线重连缓冲
    max_restarts: 5,      // 最大重启次数
    error_file: "logs/error.log",
    out_file: "logs/out.log",
  }]
};
```

### 开机自启动

```bash
# 保存当前进程列表
pm2 save

# 生成开机启动脚本
pm2 startup
```

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
