# PoiClaw 项目架构分析

> 生成时间: 2026-03-24
> 分析目标: 深入理解 PoiClaw 的架构设计

---

## 项目概览

**PoiClaw** 是一个极简、透明的 Python Coding Agent 框架，核心理念是**极简、透明、可控**。不依赖 LangChain 等重型框架，每一行代码都清晰可读。

### 核心特点
- 🎯 **极简主义**: 6 个核心工具 + 可选扩展
- 🔒 **安全优先**: 多层安全机制（Hooks + Sandbox + Docker）
- 📡 **完整事件流**: 10 种事件类型覆盖全生命周期
- 💾 **会话持久化**: 分离存储 + 断点续传
- 🤝 **多智能体协作**: Tool-based Fork-Join 模式
- 🧠 **上下文压缩**: LLM 摘要压缩 + 智能切割

---

## 整体架构图

```mermaid
graph TB
    subgraph "用户接口层"
        CLI[CLI/API]
        Feishu[飞书机器人<br/>feishu-bot.js]
        APIServer[Python API<br/>api_server.py]
    end

    subgraph "Agent 核心层"
        Agent[Agent<br/>ReAct 循环]
        Events[EventEmitter<br/>事件系统]
        Hooks[HookManager<br/>安全钩子]
        Session[FileSessionManager<br/>会话管理]
        Compaction[Compaction<br/>上下文压缩]
        SystemPrompt[SystemPrompt<br/>提示词构建]
    end

    subgraph "工具层"
        Tools[内置工具<br/>bash/read/write/edit]
        Subagent[SubagentTool<br/>多智能体协作]
        Progressive[ListToolsTool<br/>渐进式加载]
        Skills[Skills<br/>技能系统]
    end

    subgraph "扩展层"
        Extensions[Extensions<br/>扩展机制]
        Sandbox[SandboxExtension<br/>安全沙箱]
        DockerSandbox[DockerSandbox<br/>容器隔离]
    end

    subgraph "LLM 层"
        LLMClient[LLMClient<br/>统一 API]
        Providers[OpenAI 兼容 API<br/>智谱/Kimi/DeepSeek]
    end

    CLI --> Agent
    Feishu --> APIServer
    APIServer --> Agent

    Agent --> Events
    Agent --> Hooks
    Agent --> Session
    Agent --> Compaction
    Agent --> SystemPrompt

    Agent --> Tools
    Agent --> Subagent
    Agent --> Progressive
    Agent --> Skills

    Hooks --> Extensions
    Hooks --> Sandbox

    Tools --> DockerSandbox

    Agent --> LLMClient
    LLMClient --> Providers

    style Agent fill:#f9f,stroke:#333,stroke-width:2px
    style LLMClient fill:#9ff,stroke:#333,stroke-width:1px
    style Events fill:#ff9,stroke:#333,stroke-width:1px
```

---

## 核心模块详解

### 1. Agent 核心 (core/agent.py)

**职责**: ReAct 循环的完整实现

```mermaid
flowchart TD
    A[用户输入] --> B[构建上下文]
    B --> C{需要压缩?}
    C -->|是| D[LLM 摘要压缩]
    C -->|否| E[调用 LLM]
    D --> E
    E --> F{有工具调用?}
    F -->|是| G[运行安全钩子]
    G --> H{被拦截?}
    H -->|是| I[返回拦截消息]
    H -->|否| J[执行工具]
    I --> K[追加结果到消息]
    J --> K
    K --> E
    F -->|否| L[返回最终回复]
```

**关键特性**:
- ✅ **渐进式工具加载**: `progressive_tools=True` 时只注入工具简介
- ✅ **自动上下文压缩**: 超过阈值时自动触发 LLM 摘要
- ✅ **事件发射**: 每个关键节点发射事件
- ✅ **会话持久化**: 每轮循环后自动保存

---

### 2. 事件系统 (core/events.py)

**职责**: 提供完整的事件流，支持订阅/发射模式

```mermaid
graph LR
    subgraph "Agent 生命周期事件"
        E1[agent_start]
        E2[agent_end]
    end

    subgraph "Turn 事件"
        E3[turn_start]
        E4[turn_end]
    end

    subgraph "工具事件"
        E5[tool_call_start]
        E6[tool_call_end]
        E7[tool_call_error]
    end

    subgraph "其他事件"
        E8[message_update]
        E9[context_compact]
        E10[error]
    end

    E1 --> E3 --> E5 --> E6 --> E4 --> E2
    E5 -.-> E7
    B --> E9
```

**10 种事件类型**:

| 事件 | 触发时机 | 关键数据 |
|------|---------|---------|
| `agent_start` | Agent 开始运行 | user_input, config |
| `agent_end` | Agent 运行结束 | final_response, state, error |
| `turn_start` | 回合开始 | turn_number |
| `turn_end` | 回合结束 | llm_response, tool_calls_made |
| `message_update` | 消息添加到上下文 | role, content_preview |
| `tool_call_start` | 工具调用开始 | tool_name, arguments |
| `tool_call_end` | 工具调用结束 | success, result_preview, duration_ms |
| `tool_call_error` | 工具调用错误 | error_type, error_message |
| `context_compact` | 上下文压缩 | tokens_before, tokens_after |
| `error` | Agent 运行错误 | error_type, error_message |

---

### 3. 安全钩子系统 (core/hooks.py)

**职责**: AOP 切面，在工具执行前拦截

```mermaid
sequenceDiagram
    participant Agent
    participant HookManager
    participant Hook1 as 安全沙箱钩子
    participant Hook2 as 自定义钩子
    participant Tool

    Agent->>HookManager: run_before_execute(ctx)
    HookManager->>Hook1: execute(ctx)
    alt 拦截
        Hook1-->>HookManager: HookResult(proceed=False)
        HookManager-->>Agent: 拦截结果
    else 通过
        Hook1-->>HookManager: HookResult(proceed=True)
        HookManager->>Hook2: execute(ctx)
        alt 拦截
            Hook2-->>HookManager: HookResult(proceed=False)
        else 通过
            Hook2-->>HookManager: HookResult(proceed=True)
            HookManager->>Tool: execute(**args)
            Tool-->>Agent: ToolResult
        end
    end
```

**责任链模式**: 多个钩子按顺序执行，任一返回 `proceed=False` 即终止

---

### 4. 会话管理 (core/session.py)

**职责**: 分离存储方案的会话持久化

```mermaid
graph TB
    subgraph "存储结构"
        A[.poiclaw/sessions/]
        B[metadata/]
        C[data/]
        D["{uuid}.json<br/>轻量元数据"]
        E["{uuid}.json<br/>完整消息"]
    end

    A --> B
    A --> C
    B --> D
    C --> E

    subgraph "SessionMetadata"
        F[id, title]
        G[created_at, last_modified]
        H[message_count]
        I[usage: TokenStats]
        J[preview: 前2KB]
    end

    subgraph "SessionData"
        K[id, title]
        L[messages: 完整列表]
        M[compactions: 压缩历史]
    end

    D --> F
    D --> G
    D --> H
    D --> I
    D --> J

    E --> K
    E --> L
    E --> M
```

**关键特性**:
- ✅ **分离存储**: metadata 用于列表展示，data 存储完整数据
- ✅ **标题保护**: `title=None` 时保留原标题
- ✅ **内存保护**: 只在 messages 为空时加载历史
- ✅ **异步 I/O**: 使用 `asyncio.to_thread` 包装文件操作

---

### 5. 上下文压缩 (core/compaction.py)

**职责**: LLM 摘要压缩，智能切割点查找

```mermaid
flowchart TD
    A[检查是否需要压缩] --> B{tokens > threshold?}
    B -->|否| C[返回原消息]
    B -->|是| D[从后往前遍历]
    D --> E[找到切割点<br/>user 消息处]
    E --> F[构建摘要请求]
    F --> G[LLM 生成结构化摘要]
    G --> H[返回摘要 + 保留消息]
    H --> I[发射 context_compact 事件]
```

**压缩流程**:
1. 估算当前 token 数（`len(text) // 4`）
2. 如果超过 `context_window - reserve_tokens`，触发压缩
3. 从后往前遍历，在 user 消息处切割（保持 Turn 完整性）
4. 调用 LLM 生成结构化摘要（目标、进度、决策、下一步）
5. 替换压缩部分为摘要

---

### 6. 系统提示词构建 (core/system_prompt.py)

**职责**: 动态构建系统提示词

```mermaid
graph LR
    A[工具列表] --> B[生成工具描述]
    C[自定义提示词] --> D[合并基础提示词]
    E[项目上下文文件] --> F[追加 CLAUDE.md]
    G[指导原则] --> H[工具感知指导]

    B --> I[build_system_prompt]
    D --> I
    F --> I
    H --> I

    I --> J[最终 System Prompt]
```

**工具感知指导**:
- 如果有 `bash` 但没有 `grep`/`find` → "使用 bash 进行文件操作"
- 如果有 `read` + `edit` → "编辑前先使用 read 查看文件内容"
- 如果有 `subagent` → "复杂任务可以使用 subagent 创建子 Agent"

---

### 7. 工具系统

#### 7.1 BaseTool 抽象类

```mermaid
classDiagram
    class BaseTool {
        <<abstract>>
        +name: str
        +description: str
        +parameters_schema: dict
        +execute(**kwargs) ToolResult
        +to_llm_tool() dict
    }

    class BashTool {
        +name: "bash"
        +description: "执行命令"
        +execute(command, timeout)
    }

    class ReadFileTool {
        +name: "read_file"
        +description: "读取文件"
        +execute(path, start_line, end_line)
    }

    class WriteFileTool {
        +name: "write_file"
        +description: "写入文件"
        +execute(path, content, mode)
    }

    class EditFileTool {
        +name: "edit_file"
        +description: "编辑文件"
        +execute(path, old_text, new_text)
    }

    class SubagentTool {
        +name: "subagent"
        +description: "多智能体协作"
        +execute(mode, tasks, max_steps)
    }

    class ListToolsTool {
        +name: "list_tools"
        +description: "查询工具详情"
        +execute(tool_name)
    }

    BaseTool <|-- BashTool
    BaseTool <|-- ReadFileTool
    BaseTool <|-- WriteFileTool
    BaseTool <|-- EditFileTool
    BaseTool <|-- SubagentTool
    BaseTool <|-- ListToolsTool
```

#### 7.2 ToolRegistry

```mermaid
graph LR
    A[ToolRegistry] --> B[register]
    A --> C[unregister]
    A --> D[get]
    A --> E[to_llm_tools]
    A --> F[to_brief]

    B --> G["添加工具到 _tools dict"]
    C --> H["从 dict 移除"]
    D --> I["按名称获取"]
    E --> J["转换为 LLM API 格式"]
    F --> K["生成简要描述列表"]
```

---

### 8. SubagentTool 多智能体协作

**职责**: Tool-based Fork-Join 模式

```mermaid
graph TB
    subgraph "Single 模式"
        S1[主 Agent] --> S2[子 Agent]
        S2 --> S3[返回结果]
    end

    subgraph "Parallel 模式"
        P1[主 Agent] --> P2[子 Agent 1]
        P1 --> P3[子 Agent 2]
        P1 --> P4[子 Agent 3]
        P2 --> P5[gather 聚合]
        P3 --> P5
        P4 --> P5
        P5 --> P6[Markdown 结果]
    end

    subgraph "Chain 模式"
        C1[主 Agent] --> C2[子 Agent 1]
        C2 --> C3[结果作为上下文]
        C3 --> C4[子 Agent 2]
        C4 --> C5[结果作为上下文]
        C5 --> C6[子 Agent 3]
        C6 --> C7[最终结果]
    end
```

**安全设计**:
- 子 Agent **必须**继承 hooks，确保安全沙箱规则生效
- 子 Agent 拥有独立的 messages 上下文，不污染主 Agent

---

### 9. 扩展系统 (extensions/)

**职责**: 提供可插拔的扩展能力

```mermaid
classDiagram
    class BaseExtension {
        <<abstract>>
        +name: str
        +description: str
        +version: str
        +get_hook() HookFunction
        +get_tools() list~ExtensionTool~
        +get_commands() dict
        +get_event_handlers() dict
        +on_register(ctx)
        +on_unregister()
    }

    class SandboxExtension {
        +name: "sandbox"
        +get_hook() 拦截危险命令
    }

    class MyExtension {
        +name: "my_extension"
        +get_hook() 自定义拦截
        +get_commands() 斜杠命令
        +get_event_handlers() 事件订阅
    }

    BaseExtension <|-- SandboxExtension
    BaseExtension <|-- MyExtension
```

**4 种扩展能力**:
1. `get_hook()` - 拦截工具调用（AOP 切面）
2. `get_tools()` - 注册新工具
3. `get_commands()` - 注册斜杠命令
4. `get_event_handlers()` - 订阅 Agent 事件

---

### 10. Docker 沙箱 (sandbox/docker_manager.py)

**职责**: 容器隔离执行命令

```mermaid
sequenceDiagram
    participant User
    participant BashTool
    participant DockerSandbox
    participant Container as Docker Container

    User->>BashTool: 执行命令
    BashTool->>DockerSandbox: exec(command)
    DockerSandbox->>Container: docker exec bash -c "command"
    Container-->>DockerSandbox: exit_code, output
    DockerSandbox-->>BashTool: (exit_code, output)
    BashTool-->>User: ToolResult
```

**关键特性**:
- ✅ **工作目录挂载**: 项目目录自动挂载到 `/workspace`
- ✅ **生命周期管理**: `start()` / `stop()` / `remove()`
- ✅ **超时控制**: 支持命令执行超时
- ✅ **流式输出**: `exec_with_stream()` 实时输出

---

### 11. Skills 系统 (skills/)

**职责**: 渐进式技能加载

```mermaid
flowchart LR
    A[Agent 启动] --> B[注入 Skill 简介到 System Prompt]
    B --> C[Agent 决定使用 Skill]
    C --> D[调用 read_skill 工具]
    D --> E[加载完整 Skill 内容]
    E --> F[Agent 按照指导执行]

    subgraph "Skill 文件格式"
        G[frontmatter<br/>name, description, triggers]
        H[Markdown 内容<br/>指令、示例、注意事项]
    end
```

**Token 节省**: 初始只注入简介（~50 tokens），按需加载完整内容（~500 tokens）

---

### 12. LLM 客户端 (llm/client.py)

**职责**: 统一的 LLM API 调用

```mermaid
graph TB
    subgraph "LLMClient"
        A[chat<br/>非流式调用]
        B[stream<br/>流式调用]
        C[collect_stream<br/>流收集器]
    end

    subgraph "支持的服务商"
        D[OpenAI]
        E[智谱 AI]
        F[Kimi]
        G[DeepSeek]
        H[其他 OpenAI 兼容 API]
    end

    A --> D
    B --> E
    C --> F
```

**关键特性**:
- ✅ **统一接口**: 一个 API 调用所有服务商
- ✅ **流式响应**: SSE（Server-Sent Events）
- ✅ **工具调用**: Function Calling
- ✅ **全异步**: async/await
- ✅ **强类型**: Pydantic

---

## 数据流图

```mermaid
sequenceDiagram
    participant User as 用户
    participant Agent as Agent
    participant Hooks as HookManager
    participant Tools as 工具
    participant LLM as LLMClient
    participant Session as SessionManager

    User->>Agent: 输入消息
    Agent->>Agent: 发射 agent_start 事件
    Agent->>Session: 加载历史会话（如果有）

    loop ReAct 循环
        Agent->>Agent: 构建上下文
        Agent->>Agent: 检查是否需要压缩
        Agent->>LLM: 调用 LLM
        LLM-->>Agent: 返回响应

        alt 有工具调用
            Agent->>Agent: 发射 tool_call_start 事件
            Agent->>Hooks: 运行 before_execute 钩子

            alt 被拦截
                Hooks-->>Agent: 返回拦截结果
            else 通过
                Agent->>Tools: 执行工具
                Tools-->>Agent: 返回结果
            end

            Agent->>Agent: 发射 tool_call_end 事件
            Agent->>Session: 保存会话
        else 无工具调用
            Agent-->>User: 返回最终回复
        end
    end

    Agent->>Agent: 发射 agent_end 事件
```

---

## 设计哲学

### 1. 极简主义
- 核心只有 6 个工具
- 不依赖 LangChain 等重型框架
- 每行代码清晰可读

### 2. 安全优先
- **三层安全**: Hooks → SandboxExtension → DockerSandbox
- **责任链模式**: 多个钩子按顺序拦截
- **强制继承**: 子 Agent 必须继承安全钩子

### 3. 事件驱动
- 完整的生命周期事件
- 并发执行处理器
- 易于构建响应式 UI

### 4. 可扩展性
- BaseExtension 抽象基类
- 4 种扩展能力（钩子、工具、命令、事件）
- Skills 系统支持自定义技能

### 5. 渐进式加载
- 工具按需查询（`list_tools`）
- 技能按需加载（`read_skill`）
- 大幅节省 Token

---

## 项目结构

```
PoiClaw/
├── src/poiclaw/
│   ├── llm/                    # LLM 调用层
│   │   ├── client.py           # 统一 API 客户端
│   │   ├── stream.py           # SSE 流式解析
│   │   ├── types.py            # Pydantic 类型
│   │   └── exceptions.py       # 自定义异常
│   ├── core/                   # Agent 核心层
│   │   ├── agent.py            # ReAct 循环
│   │   ├── events.py           # 事件系统
│   │   ├── tools.py            # BaseTool + ToolRegistry
│   │   ├── hooks.py            # 安全钩子
│   │   ├── session.py          # 会话管理
│   │   ├── compaction.py       # 上下文压缩
│   │   └── system_prompt.py    # 系统提示词构建
│   ├── tools/                  # 内置工具
│   │   ├── bash.py             # BashTool
│   │   ├── read_file.py        # ReadFileTool
│   │   ├── write_file.py       # WriteFileTool
│   │   ├── edit_file.py        # EditFileTool
│   │   ├── subagent.py         # SubagentTool
│   │   ├── list_tools.py       # ListToolsTool
│   │   └── read_skill.py       # ReadSkillTool
│   ├── extensions/             # 扩展系统
│   │   ├── base.py             # BaseExtension
│   │   ├── manager.py          # ExtensionManager
│   │   └── sandbox.py          # SandboxExtension
│   ├── skills/                 # Skills 系统
│   │   ├── models.py           # Skill 数据模型
│   │   ├── loader.py           # Skill 加载器
│   │   └── registry.py         # Skill 注册表
│   ├── sandbox/                # Docker 沙箱
│   │   └── docker_manager.py   # DockerSandbox
│   └── server/                 # IM 接入
│       └── feishu.py           # 飞书机器人
├── skills/                     # 技能定义
│   ├── commit.md
│   ├── review-pr.md
│   └── test-runner.md
└── tests/                      # 测试文件
```

---

**生成者**: Claude AI
**分析日期**: 2026-03-24
