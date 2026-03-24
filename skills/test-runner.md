# test-runner

## 触发条件
- 用户要求运行测试
- 用户说 "test" 或 "测试" 或 "跑一下测试"
- 代码修改后需要验证

## 指令
1. 检测项目使用的测试框架（pytest、jest、vitest 等）
2. 运行相关测试文件或测试用例
3. 分析测试结果：
   - 通过的测试
   - 失败的测试（含错误信息）
   - 覆盖率（如果可用）
4. 对于失败的测试，分析原因并给出修复建议

## 示例
用户：跑一下测试
助手：检测到项目使用 pytest，开始运行测试...

```
==================== test session starts ====================
collected 15 items

tests/test_agent.py ..........                           [66%]
tests/test_tools.py ....                                 [93%]
tests/test_session.py F                                  [100%]

==================== FAILURES ====================
tests/test_session.py::test_save_session
AssertionError: Expected session file to exist

==================== 14 passed, 1 failed in 2.3s ====================
```

### 分析
- 14 个测试通过
- 1 个测试失败：`test_save_session`

### 失败原因
`test_session.py:45` 期望会话文件被创建，但文件未生成。
可能是 `save_session()` 方法中的路径问题。

### 建议
检查 `FileSessionManager._get_session_path()` 是否正确处理了路径。
