# commit

## 触发条件
- 用户要求提交代码
- 用户说 "commit" 或 "提交" 或 "帮我提交"

## 指令
1. 运行 `git status` 查看所有变更文件
2. 运行 `git diff` 查看具体改动内容
3. 根据改动生成符合 Conventional Commits 规范的 commit message
4. 询问用户确认 commit message
5. 用户确认后执行 `git commit`

## 示例
用户：帮我提交代码
助手：我来帮你提交。先看看有哪些改动...
[运行 git status]
发现有 3 个文件改动：
- src/agent.py
- src/tools.py
- tests/test_agent.py

改动内容：
[展示 git diff 摘要]

建议的 commit message:
```
feat(agent): add progressive tool loading support

- Add to_brief() method to ToolRegistry
- Add ListToolsTool for on-demand schema query
- Reduce initial tool injection from 373 to 25 tokens
```

确认提交吗？
