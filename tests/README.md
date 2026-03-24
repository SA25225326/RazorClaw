# Poiclaw 测试套件

## 测试文件概览

| 文件 | 测试内容 | 类型 |
|------|----------|------|
| `test_core.py` | Agent 核心 ReAct 循环、工具注册、钩子系统 | 单元测试 |
| `test_tools.py` | 内置工具（BashTool, ReadFileTool 等） | 单元测试 |
| `test_llm.py` | LLM 客户端、消息类型、流式响应 | 单元测试 |
| `test_session.py` | 会话持久化、元数据管理 | 单元测试 |
| `test_events.py` | 事件系统、生命周期事件 | 单元测试 |
| `test_compaction.py` | 上下文压缩逻辑 | 单元测试 |
| `test_subagent_parallel.py` | 子 Agent 并行执行 | 集成测试 |
| `test_system_prompt_tokens.py` | 系统提示词 Token 数量验证 | 基准测试 |
| `test_compaction_tokens.py` | 压缩效果 Token 数量验证 | 基准测试 |
| `test_progressive_tokens.py` | 渐进式工具加载 Token 数量验证 | 基准测试 |

## 运行测试

```bash
# 运行所有测试
pytest tests/

# 运行单个测试文件
pytest tests/test_core.py

# 运行带详细输出
pytest tests/ -v

# 运行特定测试函数
pytest tests/test_core.py::test_agent_basic_flow
```

## 测试分类

### 单元测试
- `test_core.py` - Agent 核心逻辑
- `test_tools.py` - 工具实现
- `test_llm.py` - LLM 交互
- `test_session.py` - 会话管理
- `test_events.py` - 事件系统
- `test_compaction.py` - 压缩算法

### 集成测试
- `test_subagent_parallel.py` - 多 Agent 协作

### 基准测试
- `test_system_prompt_tokens.py` - 系统提示词 Token 消耗
- `test_compaction_tokens.py` - 压缩效果
- `test_progressive_tokens.py` - 渐进式加载效果

## 依赖

测试需要以下依赖：
- `pytest` - 测试框架
- `pytest-asyncio` - 异步测试支持
