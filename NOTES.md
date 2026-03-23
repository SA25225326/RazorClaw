# PoiClaw 学习笔记

> 用大白话解释 PoiClaw 每个模块是干嘛的，面试怎么吹。

---

## 一、这个项目是什么？

**PoiClaw = 一个自己手写的 AI Agent 框架**

- 不用 LangChain（太重了，几千行代码都不知道干了啥）
- 每一行代码都是自己写的，面试随便问
- 核心代码 500 行左右，一天能看完

---

## 二、整体架构（一张图看懂）

```
┌─────────────────────────────────────────────────────┐
│                     用户提问                         │
│                 "帮我列出当前目录"                    │
└─────────────────────┬───────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│                    Agent                            │
│                                                     │
│   ┌──────────────────────────────────────────┐     │
│   │         ReAct 循环（核心！）               │     │
│   │                                          │     │
│   │   1. 把问题发给 LLM                       │     │
│   │   2. LLM 说：我要调用 bash 工具           │     │
│   │   3. 检查：这个命令危险吗？（Hook）        │     │
│   │   4. 安全 → 执行工具                      │     │
│   │   5. 把结果发回给 LLM                     │     │
│   │   6. LLM 继续思考...                      │     │
│   │   7. 直到 LLM 说"我回答完了"              │     │
│   │                                          │     │
│   └──────────────────────────────────────────┘     │
│                                                     │
│   ┌─────────┐  ┌─────────┐  ┌─────────┐           │
│   │  LLM    │  │  Tools  │  │  Hooks  │           │
│   │  调用   │  │  工具箱  │  │  安全校验 │           │
│   └─────────┘  └─────────┘  └─────────┘           │
└─────────────────────────────────────────────────────┘
                      ▼
┌─────────────────────────────────────────────────────┐
│                   最终回复                           │
│              "当前目录有 a.py, b.txt..."             │
└─────────────────────────────────────────────────────┘
```

---

## 三、模块详解

### 模块 1：LLM 调用层 (src/poiclaw/llm/)

**一句话解释**：和 AI 大模型对话的"电话机"。

**有什么用？**
- 把你的消息发给 AI（比如智谱 GLM、Kimi、DeepSeek）
- 把 AI 的回复拿回来给你
- 支持"流式输出"（AI 一个字一个字往外蹦，不用等很久）

**核心文件**：

| 文件 | 干嘛的 | 大白话解释 |
|------|--------|-----------|
| `client.py` | LLMClient 类 | 打电话用的，发消息、收消息 |
| `types.py` | 消息类型定义 | 定义"消息"长什么样 |
| `stream.py` | 流式解析 | 处理 AI 一个字一个字往外蹦的情况 |
| `exceptions.py` | 报错用的 | 出错了怎么告诉你 |

**核心类**：

```python
# LLMClient - 打电话用的
class LLMClient:
    def __init__(self, base_url, api_key, model):
        # 初始化：记下 API 地址和密钥

    async def chat(self, messages) -> ChatResponse:
        # 非流式调用：发消息，等 AI 全部说完再返回

    async def stream(self, messages) -> AsyncGenerator:
        # 流式调用：AI 说一个字，返回一个字

# Message - 消息长什么样
class Message:
    role: "user" / "assistant" / "system" / "tool"
    content: "消息内容"
    tool_calls: [...]  # AI 想要调用什么工具

    @staticmethod
    def user(content): ...      # 快速创建用户消息
    @staticmethod
    def tool_result(id, content): ...  # 工具执行结果
```

**怎么用**：

```python
# 创建客户端
client = LLMClient(
    base_url="https://open.bigmodel.cn/api/coding/paas/v4",
    api_key="你的密钥",
    model="glm-5",
)

# 发消息给 AI
response = await client.chat([
    Message.user("你好！")
])

print(response.content)  # AI 的回复
```

---

### 模块 2：Agent 核心 (src/poiclaw/core/)

**一句话解释**：让 AI 能"动手干活"的大脑。

#### 2.1 ReAct 循环是什么？

**ReAct = Reasoning（思考） + Acting（行动）**

举个栗子：

```
用户：帮我看看当前目录有什么文件

第 1 轮：
  Agent 思考：用户要看目录，我需要用 bash 工具执行 ls 命令
  Agent 行动：调用 bash 工具，执行 "ls"
  观察结果：a.py, b.txt, c/

第 2 轮：
  Agent 思考：我已经知道目录内容了，可以回答用户了
  Agent 回复：当前目录有 a.py、b.txt 和文件夹 c

结束！
```

**为什么需要循环？**
- 因为 AI 可能一次干不完
- AI 可能需要调用多个工具
- AI 需要根据上一个工具的结果决定下一步干嘛

#### 2.2 核心类

```python
# Agent - 大脑
class Agent:
    def __init__(self, llm_client, tools, hooks, config):
        # llm_client: 用来调 AI 的
        # tools: 工具箱
        # hooks: 安全校验
        # config: 配置（比如最多循环多少步）

    async def run(self, user_input) -> str:
        # 核心 ReAct 循环
        # 1. 发消息给 LLM
        # 2. 如果 LLM 要调工具 -> 执行工具 -> 把结果发回 LLM
        # 3. 循环直到 LLM 说"我回答完了"
        # 4. 返回最终回复

# AgentConfig - 配置
class AgentConfig:
    max_steps: int = 10        # 最多循环多少步（防止死循环）
    system_prompt: str = None  # 系统提示词

# AgentState - 状态
class AgentState:
    step: int = 0              # 当前第几步
    total_tool_calls: int = 0  # 调用了多少次工具
    finished: bool = False     # 是否完成
```

#### 2.3 工具系统 (tools.py)

**一句话解释**：AI 能使用的"技能"。

```python
# BaseTool - 所有工具的基类（模板）
class BaseTool(ABC):
    @property
    def name(self) -> str:
        "工具名字，比如 'bash'、'read_file'"

    @property
    def description(self) -> str:
        "工具描述，AI 会看这个描述决定要不要用"

    @property
    def parameters_schema(self) -> dict:
        "参数说明，告诉 AI 这个工具需要什么参数"

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        "真正干活的函数"

    def to_llm_tool(self) -> dict:
        "转换成 LLM API 需要的格式"

# ToolResult - 工具执行结果
class ToolResult(BaseModel):
    success: bool      # 成功还是失败
    content: str       # 执行结果
    error: str | None  # 错误信息（如果有）

# ToolRegistry - 工具箱
class ToolRegistry:
    def register(self, tool): ...     # 注册工具
    def get(self, name): ...          # 获取工具
    def to_llm_tools(self): ...       # 转换成 LLM API 格式
```

**怎么定义一个工具？**

```python
class BashTool(BaseTool):
    # 工具名字
    @property
    def name(self) -> str:
        return "bash"

    # 工具描述（AI 会看这个描述决定要不要用）
    @property
    def description(self) -> str:
        return "执行 bash 命令"

    # 参数说明（告诉 AI 这个工具需要什么参数）
    @property
    def parameters_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "cmd": {"type": "string", "description": "要执行的命令"},
            },
            "required": ["cmd"],
        }

    # 真正干活的函数
    async def execute(self, cmd: str) -> ToolResult:
        # 执行命令...
        return ToolResult(success=True, content="命令执行结果")
```

#### 2.4 安全钩子 (hooks.py) ⭐ 重点！

**一句话解释**：在 AI 执行危险操作前拦住它！

**为什么需要这个？**

想象一下：
- AI 说："我要执行 rm -rf /"
- 你："卧槽别！"
- 但你拦不住，因为代码已经执行了
- 电脑没了

**Hook 的作用**：

```
1. AI 决定调用: bash(command="rm -rf /")

2. 引擎找到 bash 工具

3. 引擎不急着执行，而是先问所有 Hook：
   "这个命令能不能执行？"

4. 【安全 Hook】检查发现参数里有 "rm -rf"

5. 【安全 Hook】大喊："不行！这个命令太危险了！"
   返回一个假结果："检测到高危命令，已被拦截"

6. 引擎发现 Hook 拦截了，于是直接跳过真实的 bash.execute()

7. 引擎把那个假结果发回给 AI

8. AI 收到结果："哦，这个命令被拒绝了，我换个安全的命令试试"

✨ 完美闭环！
```

**核心类**：

```python
# HookContext - 传给 Hook 的信息
class HookContext:
    tool_name: str      # 工具名字
    arguments: dict     # 工具参数
    tool: BaseTool      # 工具实例

# HookResult - Hook 返回的结果
class HookResult:
    proceed: bool           # True=放行, False=拦截
    reason: str | None      # 拦截原因
    fake_result: ...        # 假结果（拦截时返回给 AI 的）

# HookManager - 钩子管理器
class HookManager:
    def add_before_execute(self, hook): ...  # 添加钩子
    async def run_before_execute(self, ctx): ...  # 运行所有钩子
```

**怎么写一个 Hook？**

```python
# 这是一个检查 bash 命令是否安全的 Hook
async def bash_safety_hook(ctx: HookContext) -> HookResult:
    # 只检查 bash 工具
    if ctx.tool_name != "bash":
        return HookResult(proceed=True)  # 不是 bash，放行

    # 获取命令
    cmd = ctx.arguments.get("cmd", "")

    # 检查危险命令
    dangerous_commands = ["rm -rf", "sudo", "mkfs"]
    for dangerous in dangerous_commands:
        if dangerous in cmd:
            # 发现危险命令，拦截！
            return HookResult(
                proceed=False,  # 不允许执行
                reason=f"危险命令被拦截：{dangerous}"
            )

    # 没问题，放行
    return HookResult(proceed=True)

# 怎么用
hooks = HookManager()
hooks.add_before_execute(bash_safety_hook)
```

#### 2.5 事件系统 (events.py) ⭐ 新增

**一句话解释**：让 Agent "告诉"外面它正在干啥。

**为什么需要事件系统？**

想象一下：
- 你想在 Agent 运行时记录日志
- 你想在工具调用时发通知
- 你想在 Agent 结束后统计耗时
- 你想做 Web UI，需要实时显示 Agent 的执行进度

**没有事件系统**：
```
你：想知道 Agent 调用了哪些工具
代码：我只能把日志写在 Agent 内部
你：但是我想在外面用这些数据
代码：那没办法，你得改 Agent 代码
```

**有事件系统**：
```
你：想知道 Agent 调用了哪些工具
Agent：我调工具时会发射 tool_call_start 事件
你：我订阅这个事件，记录日志
Agent：我还会发射 tool_call_end、turn_start、agent_end 等事件
你：在外面就能监听 Agent 的所有活动，不用改代码
```

**核心类**：

```python
# EventType - 事件类型枚举
class EventType(str, Enum):
    # Agent 生命周期
    AGENT_START = "agent_start"    # Agent 开始运行
    AGENT_END = "agent_end"        # Agent 运行结束

    # Turn 生命周期（一个 LLM 调用 + 工具执行回合）
    TURN_START = "turn_start"      # 新回合开始
    TURN_END = "turn_end"          # 回合结束

    # 消息相关
    MESSAGE_UPDATE = "message_update"  # 新消息添加到上下文

    # 工具调用相关
    TOOL_CALL_START = "tool_call_start"    # 工具调用开始
    TOOL_CALL_END = "tool_call_end"        # 工具调用结束
    TOOL_CALL_ERROR = "tool_call_error"    # 工具调用错误

    # 上下文相关
    CONTEXT_COMPACT = "context_compact"    # 上下文压缩

    # 错误相关
    ERROR = "error"                        # Agent 运行错误

# EventEmitter - 事件发射器
class EventEmitter:
    def on(self, event_type: EventType):
        """装饰器方式订阅事件"""

    def add_handler(self, event_type: EventType, handler):
        """添加事件处理器"""

    def remove_handler(self, event_type: EventType, handler):
        """移除事件处理器"""

    async def emit(self, event):
        """发射事件，通知所有订阅者"""
```

**事件数据类**：

```python
# AgentStartEvent - Agent 开始事件
@dataclass
class AgentStartEvent:
    agent_id: str | None       # Agent 标识
    user_input: str | None     # 用户输入
    config: AgentConfig | None # Agent 配置

# AgentEndEvent - Agent 结束事件
@dataclass
class AgentEndEvent:
    agent_id: str | None       # Agent 标识
    final_response: str | None # 最终回复
    state: AgentState | None   # 最终状态
    error: str | None          # 错误信息（如果有）

# TurnStartEvent - 回合开始事件
@dataclass
class TurnStartEvent:
    agent_id: str | None
    turn_number: int           # 回合编号

# TurnEndEvent - 回合结束事件
@dataclass
class TurnEndEvent:
    agent_id: str | None
    turn_number: int
    llm_response: str | None   # LLM 回复内容
    tool_calls_made: int       # 本回合执行的工具调用数

# ToolCallStartEvent - 工具调用开始事件
@dataclass
class ToolCallStartEvent:
    agent_id: str | None
    turn_number: int
    tool_name: str             # 工具名称
    tool_arguments: dict       # 工具参数

# ToolCallEndEvent - 工具调用结束事件
@dataclass
class ToolCallEndEvent:
    agent_id: str | None
    turn_number: int
    tool_name: str
    success: bool              # 是否成功
    result_preview: str | None # 结果预览
    duration_ms: int | None    # 执行耗时（毫秒）

# ToolCallErrorEvent - 工具调用错误事件
@dataclass
class ToolCallErrorEvent:
    agent_id: str | None
    turn_number: int
    tool_name: str
    error_type: str | None     # 错误类型
    error_message: str | None  # 错误消息
```

#### 2.6 怎么订阅事件？

**方式 1：装饰器**

```python
from poiclaw.core import Agent, EventEmitter, EventType

agent = Agent(...)

# 订阅 Agent 开始事件
@agent.event_emitter.on(EventType.AGENT_START)
async def on_agent_start(event):
    print(f"Agent 开始了！用户输入：{event.user_input}")

# 订阅工具调用事件
@agent.event_emitter.on(EventType.TOOL_CALL_START)
async def on_tool_call(event):
    print(f"工具调用：{event.tool_name}，参数：{event.tool_arguments}")
```

**方式 2：函数式**

```python
async def on_turn_end(event):
    print(f"回合 {event.turn_number} 结束，调用了 {event.tool_calls_made} 个工具")

agent.event_emitter.add_handler(EventType.TURN_END, on_turn_end)
```

#### 2.7 Agent 集成事件

Agent 在执行过程中会自动发射事件：

```python
async def run(self, user_input: str) -> str:
    # 1. 发射 AGENT_START 事件
    await self.event_emitter.emit(AgentStartEvent(...))

    try:
        # ... ReAct 循环 ...

        while self.state.step < self.config.max_steps:
            # 2. 发射 TURN_START 事件
            await self.event_emitter.emit(TurnStartEvent(...))

            # ... 调用 LLM ...

            # 3. 发射 MESSAGE_UPDATE 事件
            await self.event_emitter.emit(MessageUpdateEvent(...))

            # ... 执行工具 ...

            for tool_call in response.tool_calls:
                # 4. 发射 TOOL_CALL_START 事件
                await self.event_emitter.emit(ToolCallStartEvent(...))

                result = await self._execute_tool(tool_call)

                # 5. 发射 TOOL_CALL_END 事件
                await self.event_emitter.emit(ToolCallEndEvent(...))

            # 6. 发射 TURN_END 事件
            await self.event_emitter.emit(TurnEndEvent(...))

    finally:
        # 7. 发射 AGENT_END 事件
        await self.event_emitter.emit(AgentEndEvent(...))
```

#### 2.8 事件系统设计亮点

**1. 解耦**
- Agent 不关心谁在监听
- 监听者不关心 Agent 内部实现
- 通过事件松耦合

**2. 并发执行**
- 多个处理器并发执行
- 不阻塞主流程
- 用 `asyncio.gather(return_exceptions=True)` 保证异常不影响主流程

**3. 灵活订阅**
- 装饰器订阅（代码简洁）
- 函数式订阅（动态添加/移除）
- 可以订阅部分事件，不感兴趣的不订阅

**4. 完整的事件流**
```
agent_start
  ├─ turn_start
  │   ├─ message_update (user)
  │   ├─ message_update (assistant)
  │   ├─ tool_call_start (bash)
  │   ├─ tool_call_end (bash)
  │   ├─ message_update (tool_result)
  │   └─ turn_end
  ├─ turn_start
  │   └─ ...
  └─ agent_end
```

#### 2.9 实际应用场景

**场景 1：日志记录**

```python
@agent.event_emitter.on(EventType.TOOL_CALL_START)
async def log_tool_call(event):
    logger.info(f"工具调用: {event.tool_name} with {event.tool_arguments}")

@agent.event_emitter.on(EventType.TOOL_CALL_END)
async def log_tool_result(event):
    logger.info(f"工具结果: {event.tool_name} -> {event.success}")
```

**场景 2：性能监控**

```python
tool_durations = {}

@agent.event_emitter.on(EventType.TOOL_CALL_END)
async def track_duration(event):
    tool_name = event.tool_name
    duration = event.duration_ms
    if tool_name not in tool_durations:
        tool_durations[tool_name] = []
    tool_durations[tool_name].append(duration)
```

**场景 3：Web UI 实时更新**

```python
# WebSocket 推送事件给前端
@agent.event_emitter.on(EventType.MESSAGE_UPDATE)
async def send_to_frontend(event):
    await websocket.send_json({
        "type": "message_update",
        "role": event.role,
        "content": event.content_preview,
    })
```

---

### 模块 3：内置工具 (src/poiclaw/tools/)

**一句话解释**：Agent 能用的 4 个核心工具。

| 工具 | 文件 | 功能 |
|------|------|------|
| `bash` | `bash.py` | 执行命令 |
| `read_file` | `read_file.py` | 读取文件 |
| `write_file` | `write_file.py` | 写入文件 |
| `edit_file` | `edit_file.py` | 编辑文件 |

#### 3.1 BashTool

**功能**：执行 bash 命令

**参数**：
- `command`: 要执行的命令
- `timeout`: 超时时间（秒），默认 30

**特点**：
- 使用 `asyncio.create_subprocess_shell` 异步执行
- 默认 30 秒超时（防止死循环卡死 Agent）
- 输出截断（30KB / 2000 行，防止爆内存）
- 捕获 stdout 和 stderr

```python
class BashTool(BaseTool):
    MAX_BYTES = 30 * 1024  # 30KB
    MAX_LINES = 2000

    async def execute(self, command: str, timeout: int = 30):
        # 1. 创建子进程
        process = await asyncio.create_subprocess_shell(command, ...)

        # 2. 等待执行（带超时）
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=timeout,
        )

        # 3. 截断输出
        # 4. 返回结果
```

#### 3.2 ReadFileTool

**功能**：读取文件内容

**参数**：
- `path`: 文件路径
- `start_line`: 起始行号（可选，从 1 开始）
- `end_line`: 结束行号（可选）

**特点**：
- 使用 `asyncio.to_thread` 包装同步读取（不引入 aiofiles）
- 支持行范围读取
- 自动截断大文件（100KB）
- 文件不存在时返回友好错误

```python
class ReadFileTool(BaseTool):
    MAX_BYTES = 100 * 1024  # 100KB

    async def execute(self, path: str, start_line=None, end_line=None):
        # 1. 检查文件是否存在
        # 2. 使用 asyncio.to_thread 读取
        content = await asyncio.to_thread(file_path.read_text, encoding="utf-8")
        # 3. 按行范围截取
        # 4. 返回结果
```

#### 3.3 WriteFileTool

**功能**：写入文件

**参数**：
- `path`: 文件路径
- `content`: 要写入的内容
- `mode`: "write"（覆盖）或 "append"（追加）

**特点**：
- 支持覆盖和追加两种模式
- 自动创建父目录
- 使用 `asyncio.to_thread` 包装同步写入

```python
class WriteFileTool(BaseTool):
    async def execute(self, path: str, content: str, mode: str = "write"):
        # 1. 自动创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)
        # 2. 使用 asyncio.to_thread 写入
        # 3. 返回结果
```

#### 3.4 EditFileTool

**功能**：编辑文件（精确字符串替换）

**参数**：
- `path`: 文件路径
- `old_text`: 要查找的文本（必须完全匹配且唯一）
- `new_text`: 替换后的文本

**特点**：
- 精确字符串替换（不是复杂的 Diff）
- 要求 old_text 必须唯一匹配（防止改错地方）
- 未找到或多处匹配时返回错误

```python
class EditFileTool(BaseTool):
    async def execute(self, path: str, old_text: str, new_text: str):
        # 1. 读取文件
        content = await asyncio.to_thread(file_path.read_text, ...)

        # 2. 检查 old_text 是否存在
        if old_text not in content:
            return ToolResult(success=False, error="未找到要替换的文本")

        # 3. 检查是否唯一
        if content.count(old_text) > 1:
            return ToolResult(success=False, error="找到多处匹配，请扩大上下文")

        # 4. 执行替换
        new_content = content.replace(old_text, new_text, 1)

        # 5. 写回文件
        await asyncio.to_thread(file_path.write_text, new_content, ...)
```

#### 3.5 统一注册

```python
# __init__.py
def register_all_tools(registry: ToolRegistry) -> None:
    """一键注册所有内置工具"""
    registry.register(BashTool())
    registry.register(ReadFileTool())
    registry.register(WriteFileTool())
    registry.register(EditFileTool())

# 用法
from poiclaw.tools import register_all_tools

tools = ToolRegistry()
register_all_tools(tools)  # 一行搞定
```

---

### 模块 4：扩展系统 (src/poiclaw/extensions/)

**一句话解释**：给 Agent 加"插件"，让 Agent 能力更强、更安全、更可扩展。

#### 4.1 这个模块解决什么问题？

**问题场景**：
- 你想让 AI 不能执行 `rm -rf` 这种危险命令 → 需要拦截
- 你想让 AI 多一个"查天气"的工具 → 需要注册新工具
- 你想输入 `/diff` 查看 git 变更 → 需要斜杠命令
- 你想记录 AI 每次调用了什么工具 → 需要监听事件

**如果把这些逻辑都塞进 Agent 里**：
- Agent 代码越来越臃肿
- 改一个功能可能影响其他功能
- 难以维护和扩展

**扩展系统的解决方案**：
- 把这些功能抽离成独立的"扩展"
- 每个"扩展"专注于一个功能
- 想加功能就写个新扩展，不想用就不注册

#### 4.2 一个生活化的类比

把 Agent 想象成一个**手机**：
- **手机本身** = Agent 核心（ReAct 循环）
- **App** = 扩展（Extension）

| 手机 App | 扩展 | 功能 |
|---------|------|------|
| 杀毒软件 | SandboxExtension | 拦截危险操作 |
| 新安装的工具 App | get_tools() | 给 AI 新能力 |
| 快捷指令 | get_commands() | /diff、/files 斜杠命令 |
| 后台监听 | get_event_handlers() | 记录日志、统计 |

#### 4.3 扩展能做什么？（4 种能力）

```
┌─────────────────────────────────────────────────────┐
│                    BaseExtension                     │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  1. get_hook() → 拦截工具调用                │   │
│   │     "AI 要执行 rm -rf？拦住！"              │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  2. get_tools() → 注册新工具                 │   │
│   │     "给 AI 加一个查天气的工具"              │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  3. get_commands() → 注册斜杠命令            │   │
│   │     "用户输入 /diff，显示 git 变更"         │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  4. get_event_handlers() → 订阅事件          │   │
│   │     "AI 启动时记录日志，工具调用时统计"      │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

**能力 1：拦截工具调用（get_hook）**

```
AI 想执行: bash(command="rm -rf /")
                    ↓
         ┌─────────────────────┐
         │   Hook 检查命令      │
         │   发现 "rm -rf"！    │
         └─────────────────────┘
                    ↓
         返回假结果给 AI："命令太危险，被拦截了"
                    ↓
         AI 换个安全的命令继续
```

**能力 2：注册新工具（get_tools）**

```python
# 比如你想给 AI 加一个"查天气"的能力
class WeatherExtension(BaseExtension):
    def get_tools(self):
        return [WeatherTool()]  # LLM 就能调用这个工具了
```

**能力 3：注册斜杠命令（get_commands）**

```python
# 用户输入 /diff，显示 git 变更
class DiffExtension(BaseExtension):
    def get_commands(self):
        return {
            "diff": ExtensionCommand(
                name="diff",
                description="显示 git 变更",
                handler=self._show_diff,
            )
        }
```

**能力 4：订阅事件（get_event_handlers）**

```python
# 监听 Agent 的生命周期
class LogExtension(BaseExtension):
    def get_event_handlers(self):
        return {
            "agent_start": [self._on_start],   # Agent 启动时
            "tool_call": [self._on_tool],       # 工具调用时
            "agent_end": [self._on_end],        # Agent 结束时
        }
```

#### 4.4 核心文件

| 文件 | 作用 | 大白话解释 |
|------|------|-----------|
| `base.py` | BaseExtension 基类 | 定义"扩展"长什么样，有哪些能力 |
| `manager.py` | ExtensionManager | 管理所有扩展，注册、注销、事件分发 |
| `sandbox.py` | SandboxExtension | 安全沙箱，拦截 rm -rf 等危险命令 |

#### 4.5 SandboxExtension 干了啥？

**场景**：AI 想执行 `rm -rf /`

**没有沙箱**：
```
AI: 我要执行 rm -rf /
Agent: 好的，执行！
电脑: 💀 文件全没了
```

**有沙箱**：
```
AI: 我要执行 rm -rf /
SandboxExtension: 等等！这个命令匹配了危险模式 "rm\s+(-[rf]+\s+"
SandboxExtension: 返回 HookResult(proceed=False, reason="[安全拦截]...")
AI: 收到假结果 "[安全拦截] 命令太危险，请换个安全的命令"
AI: 那我用 ls 看看有什么文件
Agent: 好的，执行 ls
```

**拦截的危险命令**：
- `rm -rf` → 删除一切
- `wget`、`curl -o` → 下载恶意文件
- `sudo` → 提权
- `mkfs` → 格式化磁盘
- `chmod 777` → 危险权限

#### 4.6 怎么用？

**最简单的用法（只用沙箱）**：

```python
from poiclaw.extensions import SandboxExtension
from poiclaw.core import Agent, HookManager

# 创建沙箱
sandbox = SandboxExtension()

# 注册钩子
hooks = HookManager()
hooks.add_before_execute(sandbox.get_hook())

# 创建 Agent
agent = Agent(llm_client=llm, hooks=hooks)
```

**完整用法（用 ExtensionManager）**：

```python
from poiclaw.extensions import ExtensionManager, SandboxExtension

# 创建管理器
manager = ExtensionManager()

# 注册扩展（可以注册多个）
manager.register(SandboxExtension())
# manager.register(LogExtension())      # 再加个日志扩展
# manager.register(DiffExtension())     # 再加个 /diff 命令

# 获取所有钩子
for ext in manager.get_all_extensions():
    hook = ext.get_hook()
    if hook:
        hooks.add_before_execute(hook)
```

#### 4.7 设计亮点（面试吹点）

**1. AOP（面向切面编程）**
- 安全检查、日志这些"横切"的逻辑，不写在 Agent 里
- 单独抽成扩展，Agent 核心代码保持干净

**2. 责任链模式**

​	

- 多个扩展排成一队
- 每个扩展都有机会拦截
- 一个拦住了，后面的就不用执行了

**3. 正则表达式匹配**
- 比简单字符串匹配强大
- 能匹配 `rm -rf`、`rm -fr`、`rm -r -f` 等各种变体

**4. 详细的拦截消息**
- 拦截时告诉 AI "为什么被拦" + "建议换什么命令"
- AI 能自我纠错，换一种方式完成任务

**5. 参考了 pi-mono 的设计**
- pi-mono 是 TypeScript 写的，我们是纯 Python
- 用 Python 的类继承风格重写，符合 Python 规范

---

### 模块 5：多智能体协作 (src/poiclaw/tools/subagent.py)

**一句话解释**：让 Agent 能"分身"，派多个子 Agent 并行或串行干活。

#### 5.1 这个模块解决什么问题？

**问题场景**：
- 你想同时分析前端和后端代码 → 需要 2 个 Agent 并行工作
- 你想先设计数据库，再根据设计实现代码 → 需要 Agent 串行协作
- 你想让一个 Agent 专注干一件事 → 需要拆分子任务

**如果只用一个 Agent**：
- 任务太复杂，容易跑偏
- 不能并行，效率低
- 上下文越来越乱

**SubagentTool 的解决方案**：
- 把"派生子 Agent"变成一个**普通工具**
- 主 Agent 可以像调用 `bash` 一样调用 `subagent`
- 子 Agent 有独立的上下文，不污染主 Agent

#### 5.2 三种执行模式

```
┌─────────────────────────────────────────────────────┐
│                  SubagentTool                        │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  mode: "single"                              │   │
│   │  派一个子 Agent 干活                          │   │
│   │  [任务] → [子 Agent] → [结果]                │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  mode: "parallel"（并行）                     │   │
│   │  同时派多个子 Agent，最后聚合结果             │   │
│   │                                              │   │
│   │  [任务1] → [子 Agent 1] → [结果1]            │   │
│   │  [任务2] → [子 Agent 2] → [结果2]  → 聚合    │   │
│   │  [任务3] → [子 Agent 3] → [结果3]            │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
│   ┌─────────────────────────────────────────────┐   │
│   │  mode: "chain"（串行链式）                    │   │
│   │  前一个结果作为下一个的上下文                  │   │
│   │                                              │   │
│   │  [任务1] → [结果1]                           │   │
│   │      ↓                                       │   │
│   │  [任务2 + 结果1] → [结果2]                   │   │
│   │      ↓                                       │   │
│   │  [任务3 + 结果2] → [最终结果]                │   │
│   └─────────────────────────────────────────────┘   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

#### 5.3 核心代码逻辑

**single 模式**：
```python
async def _run_single(self, task, max_steps):
    # 1. 创建隔离的子 Agent
    sub_agent = Agent(
        llm_client=self._llm_client,
        tools=self._base_tools,
        hooks=self._hooks,  # 必须继承 hooks！
        config=AgentConfig(
            max_steps=max_steps,
            system_prompt=f"你是{task.agent_role}"
        )
    )
    # 2. 执行并返回
    result = await sub_agent.run(task.instruction)
    return result
```

**parallel 模式**：
```python
async def _run_parallel(self, tasks, max_steps):
    async def run_one(task):
        sub_agent = self._create_sub_agent(task.agent_role, max_steps)
        return await sub_agent.run(task.instruction)

    # Fork: 并发启动所有子 Agent
    results = await asyncio.gather(*[run_one(t) for t in tasks])

    # Join: 聚合结果（Markdown 格式）
    output = []
    for role, result in results:
        output.append(f"## [{role}]\n\n{result}\n---")
    return "\n".join(output)
```

**chain 模式**：
```python
async def _run_chain(self, tasks, max_steps):
    previous_result = ""

    for task in tasks:
        # 1. 拼接上下文
        if previous_result:
            instruction = f"{task.instruction}\n\n前置上下文：\n{previous_result}"
        else:
            instruction = task.instruction

        # 2. 创建子 Agent 执行
        sub_agent = self._create_sub_agent(task.agent_role, max_steps)
        result = await sub_agent.run(instruction)

        # 3. 保存给下一轮
        previous_result = result

    return previous_result  # 返回最后一个结果
```

#### 5.4 安全设计（极其重要！）

**致命漏洞**：如果子 Agent 不继承 hooks，就会绕过 SandboxExtension！

```python
# ❌ 错误：子 Agent 裸奔
sub_agent = Agent(
    llm_client=self._llm_client,
    tools=self._base_tools,
    hooks=None,  # 危险！没有沙箱保护
)

# ✅ 正确：子 Agent 必须继承 hooks
sub_agent = Agent(
    llm_client=self._llm_client,
    tools=self._base_tools,
    hooks=self._hooks,  # 安全：继承沙箱规则
)
```

**为什么这么重要？**
- 主 Agent 被沙箱保护，不能执行 `rm -rf`
- 但如果子 Agent 不继承 hooks，子 Agent 可以执行任何命令
- 这就是"越权漏洞"

#### 5.5 怎么用？

```python
from poiclaw.tools import register_all_tools, register_subagent_tool

# 1. 注册基础工具
tools = ToolRegistry()
register_all_tools(tools)

# 2. 设置安全沙箱
hooks = HookManager()
sandbox = SandboxExtension()
hooks.add_before_execute(sandbox.get_hook())

# 3. 注册 SubagentTool（必须注入 llm_client 和 hooks！）
register_subagent_tool(tools, llm_client=llm, hooks=hooks)

# 4. 创建主 Agent
agent = Agent(llm_client=llm, tools=tools, hooks=hooks)

# 5. 运行 - LLM 会自动调用 subagent 工具
response = await agent.run("""
用 subagent 工具，parallel 模式并行执行：
- 派一个前端专家分析 UI 组件
- 派一个后端专家分析 API 接口
""")
```

#### 5.6 设计亮点（面试吹点）

**1. Tool-based Fork-Join 模型**
- 多智能体能力作为普通工具挂载
- 不需要修改 Agent 核心代码
- 符合"开闭原则"

**2. 三种执行模式**
- single：单任务
- parallel：并行执行（asyncio.gather）
- chain：串行链式（前一个结果传给下一个）

**3. 安全继承**
- 子 Agent 必须继承 hooks
- 确保 SandboxExtension 在所有子节点生效
- 防止越权漏洞

**4. 状态隔离**
- 每个子 Agent 有独立的 messages
- 不污染主 Agent 的上下文
- 可以无限嵌套（子 Agent 再派孙子 Agent）

**5. 参考 pi-mono 的设计**
- pi-mono 用独立进程实现隔离
- 我们用 Python 内存隔离，更轻量
- 核心思想一致：Tool-based Fork-Join

---

### 模块 6：会话管理 (src/poiclaw/core/session.py)

**一句话解释**：把对话历史保存到硬盘，下次打开还能接着聊。

#### 6.1 这个模块解决什么问题？

**问题场景**：
- 你和 AI 聊了一半，关掉终端，第二天想继续聊 → 历史没了
- 你想让 AI 记住之前的上下文（比如项目背景） → 需要持久化
- 你想知道这次对话花了多少 Token → 需要统计

**如果没有会话管理**：
- 每次重启都是新对话
- AI 记不住之前说的话
- 无法统计 Token 使用量

**FileSessionManager 的解决方案**：
- 把对话历史保存到 `.poiclaw/sessions/` 目录
- 支持"断点续传"：下次加载历史继续聊
- 自动统计 Token 使用量
- 分离存储：metadata（轻量）+ data（完整数据）

#### 6.2 存储结构（大白话）

```
.poiclaw/
└── sessions/
    ├── metadata/
    │   └── {uuid}.json     # 轻量元数据（用于列表展示）
    └── data/
        └── {uuid}.json     # 完整消息列表
```

**为什么要分两个文件？**

想象一下：
- 你有 100 个会话
- 想在 UI 上展示会话列表（标题、预览、时间）
- 如果每个会话都存一个大文件，加载列表时要读 100 个大文件 → 慢！

**分离存储的好处**：
- `metadata/` 存轻量信息（标题、预览、统计）→ 列表展示快
- `data/` 存完整数据（所有消息）→ 需要时才加载

#### 6.3 核心数据模型

```python
# Token 使用统计
class UsageStats:
    input: int = 0          # 输入 Token
    output: int = 0         # 输出 Token
    cache_read: int = 0     # 缓存读取
    cache_write: int = 0    # 缓存写入
    total_tokens: int = 0   # 总计

    def merge(self, other): ...  # 累积统计

# 会话元数据（轻量）
class SessionMetadata:
    id: str                 # UUID
    title: str              # 会话标题
    created_at: str         # 创建时间
    last_modified: str      # 最后修改时间
    message_count: int      # 消息数量
    usage: UsageStats       # Token 统计
    preview: str            # 前 2KB 预览

# 会话完整数据
class SessionData:
    id: str
    title: str
    created_at: str
    last_modified: str
    messages: list[dict]    # 所有消息
    usage: UsageStats
```

#### 6.4 FileSessionManager 核心接口

```python
class FileSessionManager:
    # 保存会话（同时保存 metadata 和 data）
    async def save_session(
        self,
        session_id: str,
        messages: list[Message],
        title: str | None = None,  # None = 保留原标题
        usage: UsageStats | None = None,
    ) -> bool: ...

    # 加载完整消息列表
    async def load_session(self, session_id: str) -> list[Message] | None: ...

    # 获取单个元数据
    async def get_metadata(self, session_id: str) -> SessionMetadata | None: ...

    # 列出所有会话（按最后修改时间降序）
    async def list_sessions(self) -> list[SessionMetadata]: ...

    # 删除会话
    async def delete_session(self, session_id: str) -> bool: ...

    # 更新标题
    async def update_title(self, session_id: str, title: str) -> bool: ...

    # 生成 UUID
    @staticmethod
    def generate_id() -> str: ...
```

#### 6.5 三个关键保护机制

**1. 标题保护**

```python
# 问题：如果每次保存都传 title=None，标题会被覆盖为空吗？
# 解决：在 save_session 中检查

async def save_session(self, session_id, messages, title=None, usage=None):
    # 如果 title 为 None，读取现有 metadata 保留原标题
    if title is None:
        existing = await self.get_metadata(session_id)
        if existing:
            title = existing.title  # 保留原标题
        else:
            title = self._generate_title(messages)  # 新会话，自动生成
```

**2. 内存保护**

```python
# 问题：如果在 Agent.run() 中每次都加载历史，会发生什么？
# - 重复 I/O 浪费
# - 可能覆盖当前内存中的消息

# 解决：只在 messages 为空时加载
class Agent:
    async def run(self, user_input: str) -> str:
        # 内存保护：只在 messages 为空且未加载过时才加载历史
        if (
            self.session_manager
            and self.session_id
            and len(self.messages) == 0
            and not self._session_loaded
        ):
            history = await self.session_manager.load_session(self.session_id)
            if history:
                self.messages = history
            self._session_loaded = True

        # ... 后续逻辑
```

**3. 异步 I/O**

```python
# 问题：文件操作是同步的，会阻塞事件循环
# 解决：用 asyncio.to_thread 包装

async def _read_json_async(self, path: Path) -> dict | None:
    def _read() -> str | None:
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    # 把同步操作扔到线程池执行
    content = await asyncio.to_thread(_read)
    return json.loads(content) if content else None
```

#### 6.6 完整使用示例

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

    # 5. 第一次对话（自动保存）
    response1 = await agent.run("帮我分析当前项目结构")
    print(response1)

    # 6. 第二次对话（自动加载历史）
    response2 = await agent.run("继续，帮我写一个 README")
    print(response2)

    # 7. 查看 Token 统计
    stats = agent.get_usage_stats()
    print(f"总 Token: {stats.total_tokens}")

    # 8. 列出所有会话
    sessions = await session_manager.list_sessions()
    for s in sessions:
        print(f"[{s.id[:8]}] {s.title}")
        print(f"  消息数: {s.message_count}, Token: {s.usage.total_tokens}")

asyncio.run(main())
```

#### 6.7 Agent 集成要点

```python
class Agent:
    def __init__(
        self,
        llm_client: LLMClient,
        tools: ToolRegistry | None = None,
        hooks: HookManager | None = None,
        config: AgentConfig | None = None,
        # ===== 新增参数 =====
        session_manager: FileSessionManager | None = None,
        session_id: str | None = None,
    ):
        # ...
        self.session_manager = session_manager
        self.session_id = session_id
        self._usage_stats = UsageStats.zero()
        self._session_loaded = False

    async def run(self, user_input: str) -> str:
        # 1. 内存保护：只在 messages 为空时加载历史
        if self.session_manager and self.session_id and len(self.messages) == 0:
            history = await self.session_manager.load_session(self.session_id)
            if history:
                self.messages = history
            self._session_loaded = True

        # 2. 添加用户消息
        user_msg = Message.user(user_input)
        self.add_message(user_msg)

        # 3. 持久化用户消息
        if self.session_manager and self.session_id:
            await self.session_manager.save_session(
                session_id=self.session_id,
                messages=self.messages,
                title=None,  # 触发标题保护
                usage=self._usage_stats,
            )

        # 4. ReAct 循环
        while ...:
            # ... 调用 LLM，执行工具 ...

            # 每轮循环后保存
            if self.session_manager and self.session_id:
                await self.session_manager.save_session(...)

        return response
```

#### 6.8 设计亮点（面试吹点）

**1. 分离存储**
- metadata 轻量，列表展示快
- data 完整，需要时才加载
- 参考 pi-mono 的惰性元数据构建

**2. 三个保护机制**
- 标题保护：title=None 时保留原标题
- 内存保护：只在 messages 为空时加载
- 异步 I/O：asyncio.to_thread 不阻塞

**3. 容错设计**
- 文件不存在返回 None
- JSON 解析失败打印警告但不中断
- 保存失败不抛异常

**4. Token 统计**
- 每次保存时累积统计
- 支持 merge 操作合并多个 UsageStats

**5. Pydantic 序列化**
- model_dump() 序列化
- model_validate() 反序列化
- 强类型保证


### 模块 7：上下文压缩 (src/poiclaw/core/compaction.py) ⭐ 新增

**一句话解释**：当对话太长超出 LLM 上下文窗口时，自动用 LLM 把旧消息总结成摘要，节省 Token。

#### 7.1 这个模块解决什么问题？

**问题场景**：

- 长对话会积累几百条消息，直接发给 LLM 会超出上下文限制（比如 128k tokens）
- 简单粗暴地删掉旧消息会丢失关键信息（用户目标、已完成的工作、重要决策）
- LLM 按输入 Token 计费，发一堆重复的历史消息很浪费钱

**解决方案**：

- **Token 估算**：用 `len(text) // 4` 快速估算消息占用的 Token 数
- **智能切割**：从后往前遍历，找到合适的切割点，保持对话轮次（Turn）完整性
- **LLM 摘要**：调用 LLM 把旧消息总结成结构化摘要（目标、进度、决策、下一步）
- **增量更新**：支持基于已有摘要的增量更新，避免重复总结

#### 7.2 核心数据结构

```python
# 压缩配置
class CompactionSettings(BaseModel):
    enabled: bool = True                       # 是否启用压缩
    context_window: int = 128000               # 模型上下文窗口大小
    reserve_tokens: int = 16384                # 保留缓冲区（给回复留空间）
    keep_recent_tokens: int = 20000            # 保留最近多少 tokens 不压缩

    @property
    def threshold(self) -> int:
        # 触发压缩的阈值 = 窗口大小 - 保留缓冲区
        return self.context_window - self.reserve_tokens

# 压缩条目（存储在 SessionData 中）
class CompactionEntry(BaseModel):
    id: str                                    # 压缩记录的唯一 ID
    timestamp: str                             # 压缩时间（ISO 8601）
    summary: str                               # LLM 生成的摘要
    first_kept_msg_idx: int                    # 第一个保留的消息索引
    tokens_before: int                         # 压缩前的 token 数
    tokens_after: int                          # 压缩后的 token 数
```

#### 7.3 核心算法

**1. Token 估算**

```python
def estimate_tokens(message: Message) -> int:
    """估算单条消息的 Token 数"""
    count = 0

    # 文本内容：len // 4（保守估算）
    if message.content:
        count += len(message.content) // 4

    # 工具调用：name + arguments
    if message.tool_calls:
        for tc in message.tool_calls:
            count += len(tc.function.name) // 4
            count += len(tc.function.arguments) // 4

    return max(1, count)  # 至少 1 个 token
```

**2. 智能切割点查找**

```python
def find_cut_point(messages: list[Message], keep_tokens: int) -> int:
    """
    从后往前遍历，找到切割点。

    关键：保持 Turn 完整性 — 在 user 消息处切割，
    这样每个 user → assistant 的轮次都是完整的。
    """
    accumulated = 0

    # 从后往前遍历
    for i in range(len(messages) - 1, -1, -1):
        msg = messages[i]
        accumulated += estimate_tokens(msg)

        # 超过保留额度，开始找切割点
        if accumulated >= keep_tokens:
            # 找到最近的 user 消息（保持 Turn 完整性）
            for j in range(i, len(messages)):
                if messages[j].role == MessageRole.USER:
                    return j  # 在这里切割

    return len(messages)  # 不需要切割
```

**3. 摘要生成 Prompt**

参考 pi-mono 的结构化摘要格式：

```python
COMPACT_PROMPT = """你是一个智能助手，需要把以下对话历史总结成简洁的摘要。

对话历史：
{messages}

{previous_prompt}

请按以下格式输出摘要：

## Goal
[用户想要完成什么]

## Progress
### Done
- [x] 已完成的任务 1
- [x] 已完成的任务 2

### In Progress
- [ ] 当前正在做的任务

### Blocked
- [ ] 被阻塞的任务（如有）

## Key Decisions
- **[决策点]**: [为什么这样决定]

## Next Steps
1. [下一步应该做什么]

## Critical Context
[继续工作所需的关键信息，比如文件路径、重要变量名等]
"""
```

**4. 主压缩函数**

```python
async def compact(
    messages: list[Message],
    llm: LLMClient,
    settings: CompactionSettings,
    previous_summary: str | None = None,
) -> CompactionResult:
    """
    执行压缩：
    1. 找到切割点
    2. 序列化旧消息
    3. 调用 LLM 生成摘要
    4. 返回摘要和新的消息列表
    """
    # 1. 检查是否需要压缩
    if not should_compact(messages, settings):
        return CompactionResult(summary=None, messages=messages)

    # 2. 找到切割点
    cut_idx = find_cut_point(messages, settings.keep_recent_tokens)

    if cut_idx == 0:
        return CompactionResult(summary=None, messages=messages)

    # 3. 分离旧消息和新消息
    old_messages = messages[:cut_idx]
    new_messages = messages[cut_idx:]

    # 4. 序列化旧消息
    serialized = serialize_messages_for_summary(old_messages)

    # 5. 调用 LLM 生成摘要
    summary = await generate_summary(
        messages=old_messages,
        llm=llm,
        previous_summary=previous_summary,
    )

    return CompactionResult(
        summary=summary,
        messages=new_messages,  # 返回保留的消息
    )
```

#### 7.4 Agent 集成

```python
# Agent._build_context() 中自动触发压缩
async def _build_context(self) -> list[Message]:
    context = [self._system_prompt]

    # 检查是否需要压缩
    if should_compact(self.messages, self.compaction_settings):
        await self._run_compaction()

    # 如果有摘要，作为 system message 添加
    if self._last_summary:
        context.append(Message.system(
            "<previous_conversation_summary>\n"
            f"{self._last_summary}\n"
            "</previous_conversation_summary>"
        ))

    # 添加最近的消息
    context.extend(self.messages)
    return context
```

#### 7.5 使用示例

```python
from poiclaw.core import Agent, CompactionSettings

# 创建 Agent 并配置压缩
agent = Agent(
    llm_client=llm,
    tools=tools,
    compaction_settings=CompactionSettings(
        enabled=True,
        context_window=128000,      # 智谱 GLM-5 的上下文窗口
        reserve_tokens=16384,       # 保留 16k 给回复
        keep_recent_tokens=20000,   # 保留最近 20k tokens
    ),
)

# 长对话会自动触发压缩
for i in range(100):
    await agent.run(f"任务 {i}：" + "内容..." * 1000)
    # 当 Token 数超过 128k - 16k = 112k 时，
    # 自动把旧消息总结成摘要

# 查看压缩历史
session = await agent.session_manager.load_session(agent.session_id)
for entry in session.compactions:
    print(f"压缩时间: {entry.timestamp}")
    print(f"压缩前: {entry.tokens_before} tokens")
    print(f"压缩后: {entry.tokens_after} tokens")
    print(f"摘要: {entry.summary[:100]}...")
```

#### 7.6 设计亮点（面试吹点）

**1. 分级记忆机制**

- **短期记忆**：最近 20k tokens 的完整对话
- **长期记忆**：LLM 生成的结构化摘要
- 优点：既保留上下文完整性，又控制成本

**2. Turn 完整性保证**

- 切割点选择在 user 消息，确保每个 user → assistant 轮次完整
- 避免把同一个轮次的消息拆开，导致上下文混乱

**3. 增量摘要更新**

- 支持基于已有摘要的增量更新
- 避免每次都从头总结，提高效率

**4. 结构化摘要格式**

- Goal / Progress / Decisions / Next Steps / Critical Context
- 比 "纯文本摘要" 更容易让 LLM 理解和利用

**5. 压缩历史可追溯**

- 每次压缩都保存 CompactionEntry
- 可以回溯查看压缩历史，方便调试和恢复

**6. 保守的 Token 估算**

- 用 `len // 4` 保守估算，确保不会真的超出限制
- 相比实际 Token 计数（需要调用 tokenizer），速度更快

#### 7.7 测试覆盖

```python
# tests/test_compaction.py

class TestEstimateTokens:
    def test_estimate_text_only(self)    # 纯文本
    def test_estimate_with_tool_calls(self)  # 带工具调用
    def test_estimate_tool_result(self)  # 工具结果

class TestShouldCompact:
    def test_disabled(self)              # 禁用压缩
    def test_below_threshold(self)       # 低于阈值
    def test_above_threshold(self)       # 超过阈值

class TestFindCutPoint:
    def test_keep_all(self)              # 不需要切割
    def test_cut_middle(self)            # 中间切割
    def test_cut_at_user_message(self)   # 在 user 消息处切割

# ... 共 21 个测试用例
```


### 模块 8：飞书接入 (src/poiclaw/server/feishu.py) 🚧

**一句话解释**：让你的 Agent 在飞书里跑，用户可以通过飞书私聊和 Agent 对话。

#### 7.1 这个模块解决什么问题？

**问题场景**：

- 你写了一个很厉害的 Agent，但只能在终端里用
- 想让同事也能用，但让他们装 Python 环境太麻烦
- 飞书是企业常用 IM，把 Agent 接进去最方便

**解决方案**：

- 用飞书官方 SDK 的 WebSocket 长连接
- 用户在飞书里发消息 → Agent 收到 → 处理 → 回复

#### 7.2 两种连接模式对比

| 模式                 | 原理                 | 优点                      | 缺点                   |
| -------------------- | -------------------- | ------------------------- | ---------------------- |
| **WebSocket 长连接** | 你的服务器主动连飞书 | 无需公网 IP、无需内网穿透 | 配置稍复杂             |
| **Webhook**          | 飞书主动连你的服务器 | 配置简单                  | 需要公网 IP 或内网穿透 |

**本项目选择 WebSocket 模式**，因为：

- 本地开发不需要内网穿透工具
- 部署更简单，只要有网就行

#### 7.3 架构图

```
┌─────────────────────────────────────────────────────────┐
│                      飞书客户端                           │
│                   （用户发消息）                          │
└─────────────────────────┬───────────────────────────────┘
                          ▼
┌─────────────────────────────────────────────────────────┐
│                    飞书服务器                             │
│              （事件订阅，推送消息）                        │
└─────────────────────────┬───────────────────────────────┘
                          ▼ WebSocket 长连接
                          （你的服务器主动连飞书）
┌─────────────────────────────────────────────────────────┐
│                   PoiClaw FeishuBot                      │
│                                                         │
│   1. 收到消息事件                                         │
│   2. 提取文本内容                                         │
│   3. 调用 Agent 处理（每个用户独立会话）                    │
│   4. 获取 Agent 回复                                      │
│   5. 通过飞书 API 回复消息                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 7.4 核心类

```python
# FeishuConfig - 配置类
class FeishuConfig(BaseModel):
    feishu_app_id: str       # 飞书应用 ID
    feishu_app_secret: str   # 飞书应用密钥
    llm_base_url: str        # LLM API 地址
    llm_api_key: str         # LLM API 密钥
    llm_model: str           # 模型名称
    session_base_path: str   # 会话存储路径
    max_steps: int           # Agent 最大步数

# FeishuBot - 机器人类
class FeishuBot:
    def __init__(self, config: FeishuConfig):
        # 初始化配置

    def start(self):
        # 1. 创建飞书 API 客户端（用于发送消息）
        # 2. 创建事件处理器（监听消息事件）
        # 3. 创建 WebSocket 客户端（接收飞书推送）
        # 4. 启动连接（阻塞运行）

    def _on_message(self, data):
        # 收到消息时的回调
        # 1. 提取消息内容
        # 2. 获取发送者 ID（作为会话 ID）
        # 3. 运行 Agent
        # 4. 回复消息
```

#### 7.5 飞书开放平台配置步骤

1. **创建应用**

   - 访问 https://open.feishu.cn/
   - 创建「企业自建应用」
   - 获取 App ID 和 App Secret

2. **配置权限**

   ```
   im:message              # 接收消息
   im:message:send_as_bot  # 以机器人身份发消息
   im:chat:read            # 读取聊天信息
   ```

3. **配置事件订阅**

   - 订阅方式：选择「使用长连接接收事件」
   - 添加事件：`im.message.receive_v1`

4. **启用机器人**

   - 应用功能 → 机器人 → 启用
   - 设置机器人名称和头像

5. **发布版本**

   - 版本管理 → 发布版本
   - 只有发布后配置才会生效！

#### 7.6 使用示例

**启动脚本** (`examples/feishu_server.py`)：

```python
from poiclaw.server.feishu import FeishuBot, FeishuConfig

config = FeishuConfig(
    feishu_app_id="cli_xxx",
    feishu_app_secret="xxx",
    llm_base_url="https://open.bigmodel.cn/api/paas/v4",
    llm_api_key="xxx",
    llm_model="glm-5",
)

bot = FeishuBot(config)
bot.start()  # 阻塞运行
```

**环境变量配置** (`.env`)：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4
OPENAI_API_KEY=xxx
OPENAI_MODEL=glm-5
```

**运行**：

```bash
uv run python examples/feishu_server.py
```

#### 7.7 消息处理流程

```
用户在飞书发消息 "你好"
        ↓
飞书服务器推送事件到 WebSocket
        ↓
FeishuBot._on_message() 被调用
        ↓
提取消息：
  - open_id: "ou_xxx" (用户唯一标识)
  - text: "你好"
  - message_id: "om_xxx" (用于回复)
        ↓
以 open_id 作为 session_id 运行 Agent
（每个用户有独立的对话历史）
        ↓
Agent 返回回复 "你好！有什么可以帮助你的吗？"
        ↓
调用飞书 API 回复消息
```

#### 7.8 并发安全设计

**问题**：同一用户快速连发多条消息，可能导致文件损坏

**解决**：使用 `asyncio.Lock` 保护每个用户的会话

```python
# 全局锁字典
session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

async def _handle_message_async(self, open_id, text, message_id):
    # 获取用户锁，防止并发写入
    async with session_locks[open_id]:
        response = await self._run_agent(open_id, text)
        await self._reply_message(message_id, response)
```

#### 7.9 当前状态 🚧

**已实现**：

- ✅ WebSocket 长连接
- ✅ 消息接收和解析
- ✅ Agent 集成（每个用户独立会话）
- ✅ 消息回复
- ✅ 并发安全锁

**待解决**：

- 🚧 事件推送未生效（可能是飞书开放平台配置问题）
- 🚧 需要进一步调试 Python SDK 的 WebSocket 实现

#### 7.10 设计亮点（面试吹点）

**1. WebSocket 长连接**

- 无需公网 IP，无需内网穿透
- 本地开发友好

**2. 会话隔离**

- 每个用户（open_id）独立会话
- 复用 FileSessionManager，支持多轮对话

**3. 并发安全**

- asyncio.Lock 防止同用户并发写入
- 防止文件损坏

**4. 配置分离**

- 敏感信息（App Secret、API Key）放 .env
- .env 在 .gitignore 中，不会泄露到 GitHub



### 模块 8：PM2 部署 (main.py + ecosystem.config.js)

**一句话解释**：让 Agent 7x24 小时在线，后台运行，崩溃自动重启。

#### 8.1 这个模块解决什么问题？

**问题场景**：

- 你在终端运行 `python main.py`，关闭终端后程序就停了
- 程序崩溃了，没人知道，机器人就"失联"了
- 想看日志，但终端输出太多，找不到错误

**解决方案**：

- 用 PM2 守护进程
- 后台运行，关闭终端也不影响
- 崩溃自动重启
- 日志持久化存储

#### 8.2 核心文件

| 文件                  | 作用                             |
| --------------------- | -------------------------------- |
| `main.py`             | 统一启动入口，信号处理，优雅退出 |
| `ecosystem.config.js` | PM2 配置文件                     |
| `logs/`               | 日志存储目录                     |

#### 8.3 main.py 设计要点

```python
# 1. 信号处理 - 捕获 SIGINT 和 SIGTERM
def signal_handler(signum, frame):
    print(f"收到信号 {signal.Signals(signum).name}")
    bot.stop()  # 优雅退出
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# 2. 配置加载 - 从 .env 读取
config = load_config()

# 3. 启动机器人（阻塞）
bot = FeishuBot(config)
bot.start()
```

**为什么需要信号处理？**

- PM2 停止进程时发送 SIGTERM
- 用户按 Ctrl+C 时发送 SIGINT
- 捕获这些信号，可以优雅退出（断开 WebSocket 连接）

#### 8.4 PM2 配置详解

```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: "poiclaw-agent",           // 进程名称
    script: "main.py",               // 启动脚本
    interpreter: ".venv/bin/python", // Python 解释器

    // 自动重启配置
    autorestart: true,               // 崩溃自动重启
    restart_delay: 3000,             // 重启延迟 3 秒（防止飞书限流）
    max_restarts: 5,                 // 1 分钟内最多重启 5 次
    min_uptime: "10s",               // 10 秒内退出视为异常

    // 日志配置
    error_file: "logs/error.log",    // 错误日志
    out_file: "logs/out.log",        // 标准输出日志
    merge_logs: true,                // 合并日志
  }]
};
```

**关键配置解释**：

| 配置                         | 作用          | 为什么这样设置                          |
| ---------------------------- | ------------- | --------------------------------------- |
| `restart_delay: 3000`        | 重启延迟 3 秒 | 飞书 WebSocket 断线后立即重连可能被限流 |
| `max_restarts: 5`            | 最大重启次数  | 防止配置错误导致无限重启                |
| `min_uptime: "10s"`          | 最小运行时间  | 如果 10 秒内退出，说明启动失败          |
| `max_memory_restart: "500M"` | 内存超限重启  | 防止内存泄漏                            |

#### 8.5 常用命令

```bash
# 启动
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 查看日志（实时）
pm2 logs poiclaw-agent

# 查看最近 100 行日志
pm2 logs poiclaw-agent --lines 100

# 停止
pm2 stop poiclaw-agent

# 重启
pm2 restart poiclaw-agent

# 删除
pm2 delete poiclaw-agent

# 监控面板
pm2 monit

# 保存进程列表
pm2 save

# 开机自启动
pm2 startup
```

#### 8.6 日志管理

**日志文件位置**：

```
logs/
├── error.log    # 错误日志
└── out.log      # 标准输出日志
```

**日志轮转**（防止日志文件太大）：

安装 pm2-logrotate：

```bash
pm2 install pm2-logrotate
```

配置：

```bash
pm2 set pm2-logrotate:max_size 10M      # 单文件最大 10MB
pm2 set pm2-logrotate:retain 7          # 保留 7 天
```

#### 8.7 设计亮点（面试吹点）

**1. 优雅退出**

- 捕获 SIGTERM 和 SIGINT 信号
- 先断开 WebSocket 连接，再退出进程
- 防止突然断开导致用户收不到回复

**2. 防止无限重启**

- `restart_delay: 3000` 延迟重启
- `max_restarts: 5` 限制重启次数
- `min_uptime: "10s"` 检测启动失败

**3. 日志持久化**

- 所有输出写入文件
- 支持 pm2-logrotate 自动轮转
- 方便排查问题

**4. 开机自启动**

- `pm2 save` 保存进程列表
- `pm2 startup` 生成启动脚本

---

## 四、面试怎么吹？

### Q1：你这个框架和 LangChain 有什么区别？

**答**：

| LangChain | 我的框架 |
|-----------|---------|
| 几千行代码，很多层抽象 | 核心 500 行，一目了然 |
| 出了 bug 不知道哪出问题 | 每一行都是自己写的，随便调试 |
| 依赖很多第三方库 | 只依赖 httpx 和 pydantic |
| 面试问到底层答不上来 | 随便问，每一行都能解释 |

### Q2：什么是 ReAct 循环？

**答**：

ReAct = Reasoning（思考）+ Acting（行动）

就是让 AI 不只是"说"，还能"做"：
1. AI 思考下一步干嘛
2. AI 决定调用什么工具
3. 执行工具，拿到结果
4. AI 根据结果继续思考
5. 循环直到任务完成

比如用户问"北京天气怎么样"：
- AI 思考：需要查天气
- AI 调用：weather_tool(city="北京")
- 获得结果：25度，晴
- AI 回复：北京今天25度，天气晴朗

### Q3：你的安全钩子是怎么实现的？

**答**：

这是我的核心设计！面试官最爱听这个。

问题：AI 可能执行危险命令，比如 rm -rf /

解决：
1. 在工具执行前，先经过所有注册的 Hook
2. Hook 检查参数，发现危险就返回"拦截"
3. 拦截后不执行真实工具，返回假结果给 AI
4. AI 以为执行了，实际上被拦截了

好处：
- AI 不会"发疯"删库
- 可以自定义拦截规则
- AI 会自动换个安全的命令

### Q4：你的工具是怎么实现的？

**答**：

我实现了 5 个核心工具：

1. **BashTool**：执行命令，用 `asyncio.create_subprocess_shell` 异步执行，30 秒超时，输出截断

2. **ReadFileTool**：读取文件，支持行范围，用 `asyncio.to_thread` 包装同步读取

3. **WriteFileTool**：写入文件，支持覆盖/追加，自动创建父目录

4. **EditFileTool**：精确字符串替换，要求 old_text 唯一匹配

5. **SubagentTool**：多智能体协作，支持 single/parallel/chain 三种模式

所有工具都继承 BaseTool，有统一的接口。错误不抛异常，而是返回错误信息让 AI 自己处理。

### Q5：你的扩展系统是怎么设计的？

**答**：

这是我的 AOP（面向切面编程）设计！参考了 pi-mono 的 extension 机制。

设计理念：
1. **BaseExtension 抽象基类**：类似 Java 的 Interface，定义了 `name`、`description`、`get_hook()` 等必须实现的方法
2. **责任链模式**：多个扩展按顺序执行，任一扩展拦截就终止
3. **正则表达式匹配**：比简单字符串匹配更强大，能匹配各种变体

SandboxExtension 实现：
- 用预编译的正则表达式检查 bash 命令
- 匹配 rm -rf、wget、curl、sudo、mkfs 等高危命令
- 返回详细的拦截消息，引导 LLM 自我纠错

好处：
- 核心代码干净，扩展功能可插拔
- 可以轻松添加新扩展（日志、权限检查等）
- 符合开闭原则：对扩展开放，对修改关闭

### Q6：你的多智能体协作是怎么实现的？

**答**：

这是我的 Tool-based Fork-Join 设计！参考了 pi-mono 的 subagent 机制。

设计理念：
1. **SubagentTool 作为普通工具**：不修改 Agent 核心代码，只是注册了一个新工具
2. **三种执行模式**：
   - single：单任务
   - parallel：asyncio.gather 并行执行
   - chain：串行链式，前一个结果作为下一个的上下文
3. **安全继承**：子 Agent 必须继承 hooks，确保 SandboxExtension 在所有子节点生效

安全设计（关键！）：
- 如果子 Agent 不继承 hooks，就会绕过沙箱保护
- 这相当于子 Agent 可以执行 rm -rf 等危险命令
- 所以 SubagentTool 初始化时必须接收 hooks 参数

好处：
- 符合开闭原则：不修改 Agent 核心代码
- 状态隔离：每个子 Agent 有独立的 messages
- 可以无限嵌套：子 Agent 可以再派孙子 Agent

### Q7：你的会话管理是怎么实现的？

**答**：

这是我的持久化设计！支持多轮对话的断点续传。

核心设计：
1. **分离存储**：metadata（轻量元数据）+ data（完整消息）
   - 列表展示时只读 metadata，快！
   - 需要详细内容时才加载 data

2. **三个保护机制**：
   - 标题保护：title=None 时保留原标题，不会覆盖为空
   
     - ### 标题保护

       ```python
       # 保存时不传标题
       await manager.save_session(session_id, messages, title=None)
       
       # 结果：保留原来的标题，不会变成空
       ```
   
       新会话 → 自动从首条用户消息生成标题
   - 内存保护：只在 messages 为空时加载历史，避免重复 I/O
   
     - ### 内存保护
   
       **什么时候从文件加载历史？**
   
       ```
       只在 messages 为空 + 第一次运行 时加载
       
       第1轮对话：内存空 → 从文件加载
       第2轮对话：内存有内容 → 不加载，直接用内存里的
       第3轮对话：内存有内容 → 不加载
       ```
   - 异步 I/O：用 asyncio.to_thread 包装文件操作，不阻塞事件循环
   
     - ### 异步 I/O
   
       ```python
       # 读写文件不阻塞程序
       content = await asyncio.to_thread(file.read)
       ```
   
       读写文件时，程序可以同时做其他事，不会卡住。
   
3. **Token 统计**：
   - 每次保存累积统计 input/output/cache_read/cache_write
   - 支持 merge 操作合并多个统计

4. **容错设计**：
   - 文件不存在返回 None
   - 解析失败打印警告但不中断主程序

存储结构：
```
.poiclaw/
└── sessions/
    ├── metadata/{uuid}.json  # 标题、预览、统计
    └── data/{uuid}.json      # 完整消息列表
```

### Q8：你的飞书接入是怎么实现的？

**答**：

这是我的 IM 接入设计！让用户通过飞书和 Agent 对话。

**最终架构：Node.js + Python 混合模式**

```
飞书消息 → Node.js (feishu-bot.js) → HTTP → Python Agent (api_server.py) → 工具执行
```

**为什么这样设计？**

1. **Node.js 负责飞书连接**：
   - Python SDK（lark-oapi）的 WebSocket 有问题，收不到消息事件
   - Node.js SDK（@larksuiteoapi/node-sdk）稳定可靠
   - 只需要接收消息、发送消息，逻辑简单

2. **Python 负责核心 Agent 逻辑**：
   - 复用 PoiClaw 的完整 Agent 实现
   - 支持所有工具（bash、read_file、write_file、edit_file）
   - 支持会话管理（多轮对话）
   - 通过 FastAPI 暴露 HTTP 接口

**核心代码**：

```python
# api_server.py - Python Agent HTTP API
@app.post("/chat")
async def chat(request: ChatRequest):
    agent = create_agent(request.session_id)
    response = await agent.run(request.message)
    return ChatResponse(response=response)
```

```javascript
// feishu-bot.js - Node.js 飞书机器人
eventDispatcher.register({
  'im.message.receive_v1': async (data) => {
    // 调用 Python Agent API
    const response = await fetch('http://127.0.0.1:8080/chat', {
      method: 'POST',
      body: JSON.stringify({ message: text, session_id: openId }),
    });
    // 回复飞书消息
    await sendMessage(openId, response.response);
  },
});
```

**启动方式**：

```bash
# 终端 1：启动 Python API
uv run python api_server.py

# 终端 2：启动飞书机器人
node feishu-bot.js
```

**会话隔离**：
- 每个用户（open_id）有独立的会话
- 使用 FileSessionManager 持久化
- 支持多轮对话

**踩坑记录**：

飞书开放平台配置如果收不到事件，尝试：
1. 重置 App Secret
2. 重新添加 `im.message.receive_v1` 事件
3. 重新发布版本
4. 等待 1-2 分钟

**设计亮点**：
- 语言分离：各取所长（Node.js WebSocket 稳定，Python Agent 功能完整）
- 解耦设计：可以独立升级 Node.js 或 Python 部分
- 复用代码：完全复用 PoiClaw Python Agent 的所有功能

### Q9：你的 PM2 部署是怎么做的？

**答**：

这是我的生产环境部署设计！让 Agent 7x24 小时在线。

核心设计：
1. **main.py 统一入口**：
   - 从 .env 加载配置
   - 捕获 SIGINT/SIGTERM 信号
   - 实现优雅退出（先断开 WebSocket，再退出进程）

2. **PM2 守护进程**：
   - 后台运行，关闭终端也不影响
   - 崩溃自动重启
   - 日志持久化存储

3. **防无限重启机制**：
   - `restart_delay: 3000` - 延迟 3 秒重启（防止飞书限流）
   - `max_restarts: 5` - 1 分钟内最多重启 5 次
   - `min_uptime: "10s"` - 10 秒内退出视为启动失败

4. **日志管理**：
   - 日志写入 `logs/` 目录
   - 可配合 pm2-logrotate 实现自动轮转

常用命令：
- `pm2 start ecosystem.config.js` - 启动
- `pm2 logs poiclaw-agent` - 查看日志
- `pm2 monit` - 监控面板
- `pm2 save` + `pm2 startup` - 开机自启动

---

- 

---

## 五、代码文件对应表

| 文件 | 干嘛的 | 重要程度 |
|------|--------|---------|
| `llm/client.py` | 调 AI API | ⭐⭐⭐ |
| `llm/types.py` | 消息类型定义 | ⭐⭐ |
| `llm/stream.py` | 流式输出解析 | ⭐⭐ |
| `core/agent.py` | ReAct 循环 | ⭐⭐⭐⭐⭐ |
| `core/tools.py` | 工具基类 + 注册器 | ⭐⭐⭐ |
| `core/hooks.py` | 安全钩子 | ⭐⭐⭐⭐⭐ |
| `core/session.py` | 会话持久化管理 | ⭐⭐⭐⭐ |
| `tools/bash.py` | 执行命令 | ⭐⭐⭐ |
| `tools/read_file.py` | 读取文件 | ⭐⭐ |
| `tools/write_file.py` | 写入文件 | ⭐⭐ |
| `tools/edit_file.py` | 编辑文件 | ⭐⭐ |
| `tools/subagent.py` | 多智能体协作 | ⭐⭐⭐⭐⭐ |
| `extensions/base.py` | 扩展抽象基类 | ⭐⭐⭐⭐ |
| `extensions/manager.py` | 扩展管理器 | ⭐⭐⭐⭐ |
| `extensions/sandbox.py` | 安全沙箱扩展 | ⭐⭐⭐⭐ |
| `server/feishu.py` | 飞书机器人接入（Python，有bug） | ⭐⭐⭐ |
| `feishu-bot.js` | 飞书机器人（Node.js，推荐） | ⭐⭐⭐⭐ |
| `api_server.py` | Python Agent HTTP API | ⭐⭐⭐⭐ |
| `chat.py` | 本地交互模式 | ⭐⭐⭐ |
| `main.py` | PM2 启动入口 | ⭐⭐⭐ |
| `ecosystem.config.js` | PM2 配置 | ⭐⭐⭐ |

---



---

## 六、下一步要干嘛？

1. **会话管理**：✅ 已完成！支持断点续传、Token 统计
2. **IM 接入**：✅ 已完成！飞书 WebSocket 模式（Node.js 版本）
3. **PM2 部署**：✅ 已完成！支持后台运行、崩溃自动重启、日志持久化

**🎉 项目全部完成！**

---

*Last updated: 2026-03-23*

---

## 附录：面试吹牛模板

> "我手写了一个极简的 Agent 框架，核心代码只有 500 行。它实现了 ReAct 循环，让 AI 能通过工具和外部世界交互。最重要的是，我设计了扩展系统、多智能体协作、会话管理、IM 接入和 PM2 部署：
>
> 1. **扩展系统**：基于 AOP（面向切面编程）思想，通过 BaseExtension 抽象基类和责任链模式，在工具执行前拦截危险操作。比如 AI 想执行 rm -rf / 的时候，SandboxExtension 会用正则表达式匹配并拦截，返回详细的引导消息让 AI 自我纠错。
>
> 2. **多智能体协作**：基于 Tool-based Fork-Join 模型，把派生子 Agent 变成一个普通工具。支持三种模式：single（单任务）、parallel（asyncio.gather 并行）、chain（串行链式）。关键设计是子 Agent 必须继承 hooks，确保沙箱规则在所有子节点生效，防止越权漏洞。
>
> 3. **会话管理**：基于分离存储设计，metadata（轻量元数据）+ data（完整消息）。实现了三个保护机制：标题保护（title=None 保留原标题）、内存保护（只在 messages 为空时加载历史）、异步 I/O（asyncio.to_thread 不阻塞）。支持 Token 统计和断点续传。
>
> 4. **飞书接入**：使用飞书官方 SDK 的 WebSocket 长连接模式，无需内网穿透。每个用户（open_id）有独立的会话，复用 FileSessionManager 支持多轮对话。使用 asyncio.Lock 防止同用户并发写入导致文件损坏。
>
> 5. **PM2 部署**：实现了优雅退出（捕获 SIGTERM/SIGINT 信号）、防无限重启机制（restart_delay、max_restarts、min_uptime）、日志持久化。支持开机自启动和崩溃自动恢复，确保 Agent 7x24 小时在线。
>
> 整个框架只依赖 httpx 和 pydantic，没有用 LangChain 那种重型框架，所以每一行代码我都清楚它是干嘛的。"
