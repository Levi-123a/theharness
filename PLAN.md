# the-harness 实现计划

> **给 Claude：** 必须使用 superpowers:executing-plans 技能逐个 task 实现本计划。

**目标：** 构建一个自研的 Coding Agent Harness，具备反馈闭环机制，能自主修复失败的测试，通过多轮自我修正完成。

**架构：** Agent 主循环编排 LLM 调用、工具分发、护栏和反馈闭环（校验器 → 分类器 → 回灌器）。所有机制均为确定性代码，可用 mock LLM 测试。WebUI 通过 FastAPI WebSocket 提供终端风格流式输出。

**技术栈：** Python 3.12, FastAPI, pytest, cryptography, openai, SQLite, Docker

---

## Task 依赖图

```
Task 1 (项目脚手架)
  └── Task 2 (数据模型)
        ├── Task 3 (LLM 抽象层)         ┐
        ├── Task 4 (凭据管理器)          │
        ├── Task 5 (护栏)                │ 可并行
        ├── Task 6 (工具分发器)          │（Task 2 之后）
        ├── Task 7 (测试校验器)          │
        ├── Task 10 (记忆存储)           ┘
        │     └── Task 8 (失败分类器)
        │           └── Task 9 (反馈回灌器)
        └── Task 11 (Agent 主循环) — 依赖 3,4,5,6,7,8,9,10
              ├── Task 12 (WebUI)
              ├── Task 13 (演示脚本)
              └── Task 14 (Docker + CI) — 依赖全部
```

**可并行组：**
- Task 2 之后：Task 3, 4, 5, 6, 7, 10（独立 worktree）
- Task 7 之后：Task 8 → Task 9
- Task 11 之后：Task 12, 13（可并行）

---

## Task 1: 项目脚手架 ✅

**完成日期：** 2026-07-10
**Commit：** `240c07b`（合并：`3a4e668`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。根据 reviewer 建议将构建后端从 `setuptools.backends._legacy:_legacy` 修正为 `setuptools.build_meta`。注释掉了 `project.scripts` 入口点（Task 12 尚未实现）。

**目标：** 创建包结构、pyproject.toml 和基础 Config 数据类。

**依赖：** 无

**文件：**
- 创建：`pyproject.toml`、`the_harness/__init__.py`、`the_harness/config.py`
- 创建：`tests/__init__.py`、`tests/conftest.py`
- 测试：`tests/test_config.py`

**实现要点：**
- `pyproject.toml`：项目元信息、依赖（openai, cryptography, fastapi, uvicorn, websockets, pytest）、pytest 配置
- `Config` 数据类：`max_rounds=5`、`llm_provider="openai"`、`model="gpt-4o-mini"`、`workspace="."`、`test_timeout=30`

**验证（TDD）：**
1. 编写 `tests/test_config.py` — 测试默认配置值和自定义配置
2. 运行 `pytest tests/test_config.py -v` → 失败（ModuleNotFoundError）
3. 实现 `pyproject.toml` + `the_harness/config.py`
4. 运行 `pip install -e . && pytest tests/test_config.py -v` → 通过
5. 提交：`feat: project scaffolding with config dataclass`

---

## Task 2: 数据模型 ✅

**完成日期：** 2026-07-13
**Commit：** `aca8b06`（合并：`45088e9`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。为 TestResult 添加 `__test__=False` 防止 pytest 收集警告。根据 reviewer 反馈添加了 GuardrailResult 测试。将 `test_output.txt` 加入 .gitignore。

**目标：** 定义 harness 中使用的所有核心数据结构。

**依赖：** Task 1

**文件：**
- 创建：`the_harness/models.py`
- 测试：`tests/test_models.py`

**实现要点：**
- 枚举（使用 `str, Enum` 混入，值为小写字符串）：
  - `ActionType`: `READ_FILE="read_file"`, `EDIT_FILE="edit_file"`, `WRITE_FILE="write_file"`, `RUN_SHELL="run_shell"`, `RUN_TESTS="run_tests"`, `GIVE_UP="give_up"`
  - `FeedbackType`: `COMPILE_ERROR="compile_error"`, `ASSERTION_FAILURE="assertion_failure"`, `ENVIRONMENT_ERROR="environment_error"`, `TIMEOUT="timeout"`, `PASS="pass"`, `UNKNOWN="unknown_failure"`
- 数据类（带默认值）：
  - `Task(test_path: str, workspace: str)` — 无默认值
  - `Action(type: ActionType, params: dict[str, Any], reasoning: str = "")`
  - `ActionResult(success: bool, output: str = "", error: str | None = None)`
  - `TestResult(exit_code: int, stdout: str, stderr: str, passed: bool)` — 无默认值
  - `ClassifiedFeedback(type: FeedbackType, location: str | None = None, message: str | None = None, expected: str | None = None, actual: str | None = None, strategy_hint: str = "")`
  - `Result(success: bool, rounds: int, reason: str, action_history: list[Action] = field(default_factory=list))`
  - `GuardrailResult(blocked: bool, reason: str = "")`
- 注意：Config 传入 AgentLoop 构造函数，不内嵌于 Task

**验证（TDD）：**
1. 编写 `tests/test_models.py` — 7 个测试：创建每个数据类，验证字段和枚举值
2. 运行 `pytest tests/test_models.py -v` → 失败
3. 实现 `the_harness/models.py`
4. 运行 `pytest tests/test_models.py -v` → 通过（7 个测试）
5. 提交：`feat: add core data models`

---

## Task 3: LLM 抽象层 ✅

**完成日期：** 2026-07-13
**Commit：** `5b97ddc`（合并：`86add89`）
**备注：** TDD RED→GREEN，两阶段代码评审通过（spec 合规通过，代码质量通过）。无关键问题。

**目标：** 创建 LLMProvider 接口和 MockLLMProvider 用于确定性测试。

**依赖：** Task 2

**文件：**
- 创建：`the_harness/llm/__init__.py`、`the_harness/llm/base.py`、`the_harness/llm/mock_provider.py`
- 测试：`tests/test_mock_provider.py`

**实现要点：**
- `LLMProvider`（ABC）：抽象方法 `complete(messages) -> dict`，返回 `{"action", "params", "reasoning"}`
- `MockLLMProvider`：接收预设动作列表，按顺序返回，耗尽时抛出 `IndexError`，`reset()` 重新开始

**验证（TDD）：**
1. 编写 `tests/test_mock_provider.py` — 3 个测试：按顺序返回预设动作、耗尽时抛出 IndexError、reset 可重置
2. 运行 → 失败
3. 实现 `base.py` + `mock_provider.py`
4. 运行 → 通过（3 个测试）
5. 提交：`feat: add LLM abstraction layer with mock provider`

---

## Task 4: 凭据管理器 ✅

**完成日期：** 2026-07-13
**Commit：** `f54e36f`（合并：`be3dcd3`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。修复了 `unlock()` 在尝试前清除状态的问题。根据 reviewer 移除了未使用的导入。

**目标：** 实现 AES-256 加密的凭据存储，使用主密码（PBKDF2 密钥派生）。

**依赖：** Task 2

**文件：**
- 创建：`the_harness/credentials/__init__.py`、`the_harness/credentials/manager.py`
- 测试：`tests/test_credential_manager.py`

**实现要点：**
- `CredentialManager`：AES-GCM 加密，PBKDF2 密钥派生（10 万次迭代，16 字节 salt）
- 方法：`setup(master_password)`、`unlock(master_password)`、`lock()`、`store(provider, key)`、`get(provider)`、`status()`（不回显明文）、`delete(provider)`
- 文件格式：salt(16) + nonce(12) + 密文，文件权限 600

**验证（TDD）：**
1. 编写 `tests/test_credential_manager.py` — 6 个测试：setup 创建文件、store+get 往返、status 不回显明文、delete、错误密码失败、更新密钥
2. 运行 → 失败
3. 使用 `cryptography` 库实现 `manager.py`
4. 运行 → 通过（6 个测试）
5. 提交：`feat: add AES-256 encrypted credential manager`

---

## Task 5: 护栏 ✅

**完成日期：** 2026-07-13
**Commit：** `4d01088`（合并：`91fcf98`）
**备注：** TDD RED→GREEN，两阶段代码评审通过（spec 合规通过，代码质量通过）。无关键问题。

**目标：** 实现危险动作拦截，使用正则模式和工作目录路径检查。

**依赖：** Task 2

**文件：**
- 创建：`the_harness/guardrail/__init__.py`、`the_harness/guardrail/guardrail.py`
- 测试：`tests/test_guardrail.py`

**实现要点：**
- `Guardrail(workspace)`：14 个危险正则模式（rm -rf, del /s, git push --force, git reset --hard, git push origin, curl|sh, wget|sh, scp, rsync, sudo, chmod 777, git clean -fd, rm -r, rmdir /s）
- 系统路径检查：`/etc/`、`C:\Windows\`、`/sys/`、`/proc/`
- 工作目录边界：解析路径，检查 `relative_to(workspace)`，超出则拦截
- `check(action) -> GuardrailResult(blocked, reason)`

**验证（TDD）：**
1. 编写 `tests/test_guardrail.py` — 12 个测试：安全读取放行、rm -rf 拦截、git push --force 拦截、git reset --hard 拦截、sudo 拦截、curl|sh 拦截、路径遍历拦截、工作目录外写入拦截、安全 shell 放行、pytest 放行、chmod 777 拦截、del /s 拦截
2. 运行 → 失败
3. 实现 `guardrail.py`
4. 运行 → 通过（12 个测试）
5. 提交：`feat: add guardrail with 5-category dangerous action interception`

---

## Task 6: 工具分发器 ✅

**完成日期：** 2026-07-13
**Commit：** `e4d4a12`（合并：`780e1f1`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。根据 reviewer 将 `py` 改为 `python` 以保证 CI 可移植性。

**目标：** 实现文件操作（读/写/编辑）和 shell 执行，带工作目录隔离。

**依赖：** Task 2

**文件：**
- 创建：`the_harness/tools/__init__.py`、`the_harness/tools/dispatcher.py`
- 测试：`tests/test_tool_dispatcher.py`

**实现要点：**
- `ToolDispatcher(workspace)`：所有路径相对于工作目录解析
- `_read_file`：读取文件内容，不存在则返回错误
- `_write_file`：创建/覆盖文件，自动创建父目录
- `_edit_file`：精确字符串替换（old_text → new_text），未找到 old_text 则报错
- `_run_shell`：`subprocess.run(shell=True, cwd=workspace, timeout=30)`，返回 stdout/stderr
- `give_up`：返回成功并附带"gave up"

**验证（TDD）：**
1. 编写 `tests/test_tool_dispatcher.py` — 8 个测试：读取文件、写入文件、编辑文件、编辑文本未找到、shell 成功、shell 失败、读取不存在文件、give up
2. 运行 → 失败
3. 实现 `dispatcher.py`
4. 运行 → 通过（8 个测试）
5. 提交：`feat: add tool dispatcher with file ops and shell execution`

---

## Task 7: 测试校验器 ✅

**完成日期：** 2026-07-13
**Commit：** `c535bb5`（合并：`7eeb976`）
**备注：** TDD RED→GREEN→REFACTOR，两阶段代码评审通过（spec 合规通过，代码质量通过）。添加 `__test__=False` 防止 pytest 收集警告。根据 reviewer 建议添加第 5 个测试 `test_validate_pytest_not_found`。简化超时断言。

**目标：** 实现确定性测试校验器，运行 pytest 并捕获输出。

**依赖：** Task 2

**文件：**
- 创建：`the_harness/feedback/__init__.py`、`the_harness/feedback/validator.py`
- 测试：`tests/test_validator.py`

**实现要点：**
- `TestValidator(workspace, timeout=30)`：运行 `pytest --tb=short -v`
- `validate(test_path) -> TestResult`：捕获 exit_code、stdout、stderr；`passed = exit_code == 0`
- 处理：TimeoutExpired → TestResult(passed=False, stderr="timed out")，FileNotFoundError → "pytest not found"
- 纯确定性：测试中 mock `subprocess.run`

**验证（TDD）：**
1. 编写 `tests/test_validator.py` — 4 个测试：校验通过（mock exit_code=0）、校验失败（mock exit_code=1）、输出中的语法错误、超时
2. 运行 → 失败
3. 实现 `validator.py`
4. 运行 → 通过（4 个测试）
5. 提交：`feat: add deterministic test validator`

---

## Task 8: 失败分类器 ✅

**完成日期：** 2026-07-13
**Commit：** `a8f88cc`（合并：`1818fd1`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。修复关键问题：`"timed out"` → 同时检查 `"timeout"`（规范要求）。新增 `test_classify_timeout_by_stderr_only` 测试。将 `_RE_SYNTAX` 拆分为两个独立正则以正确提取 location。

**目标：** 实现失败分类器，使用正则将 TestResult 分类为 5 种类型。这是反馈闭环的核心。

**依赖：** Task 7

**文件：**
- 创建：`the_harness/feedback/classifier.py`
- 测试：`tests/test_classifier.py`

**实现要点：**
- `FailureClassifier`：对 `TestResult.stdout + stderr` 进行纯正则匹配
- 分类规则（按优先级）：
  1. `passed == True` → `FeedbackType.PASS`
  2. `SyntaxError|IndentationError` → `COMPILE_ERROR`（提取 location, message）
  3. `AssertionError|assert` → `ASSERTION_FAILURE`（提取 expected, actual）
  4. `ModuleNotFoundError|ImportError|FileNotFoundError` → `ENVIRONMENT_ERROR`（提取 missing_module）
  5. `exit_code == -1` 或 stderr 中含 "timeout" → `TIMEOUT`（提取 timeout_limit）
  6. 兜底 → `UNKNOWN`
- 每种类型有对应的 `strategy_hint` 字符串
- 纯确定性：相同输入 → 相同输出

**验证（TDD）：**
1. 编写 `tests/test_classifier.py` — 9 个测试：分类通过、语法错误（检查 location）、断言失败（检查 expected/actual）、导入错误、文件未找到、超时、未知、确定性验证（同输入同输出）、strategy_hint 存在
2. 运行 → 失败
3. 实现带正则模式的 `classifier.py`
4. 运行 → 通过（9 个测试）
5. 提交：`feat: add failure classifier with 5-type regex classification`

---

## Task 9: 反馈回灌器 ✅

**完成日期：** 2026-07-13
**Commit：** `c451b3c`（合并：`5ef6151`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。根据 reviewer 修复 TIMEOUT 格式冗余。根据 reviewer 新增 `test_inject_includes_strategy_hint` 测试。

**目标：** 实现反馈回灌器，将 ClassifiedFeedback 转换为结构化 prompt 片段，用于下一轮 LLM 调用。

**依赖：** Task 8

**文件：**
- 创建：`the_harness/feedback/injector.py`
- 测试：`tests/test_injector.py`

**实现要点：**
- `FeedbackInjector`：将 `ClassifiedFeedback` → 结构化文本 prompt 片段
- 不同类型产生不同的注入内容：
  - `COMPILE_ERROR`："Syntax error at {location}: {message}. Fix the syntax error."
  - `ASSERTION_FAILURE`："Test failed: expected {expected}, got {actual}. Check the logic."
  - `ENVIRONMENT_ERROR`："Missing dependency: {missing_module}. Check if dependencies are installed."
  - `TIMEOUT`："Test timed out after {timeout_limit}s. Check for infinite loops or performance issues."
  - `UNKNOWN`："Test failed with unknown error: {message}."
  - `PASS`："All tests passed."
- 每次注入包含 `strategy_hint`
- 只注入当前轮次的反馈摘要，不保留完整历史

**验证（TDD）：**
1. 编写 `tests/test_injector.py` — 6 个测试：注入 compile_error（检查 location）、注入 assertion_failure（检查 expected/actual）、注入 environment_error（检查 missing_module）、注入 timeout（检查 timeout 信息）、注入 unknown、注入 pass（检查 "passed"）
2. 运行 → 失败
3. 实现 `injector.py`
4. 运行 → 通过（6 个测试）
5. 提交：`feat: add feedback injector with type-specific strategy routing`

---

## Task 10: 记忆存储 ✅

**完成日期：** 2026-07-13
**Commit：** `3289958`（合并：`9f104a4`）
**备注：** TDD RED→GREEN，两阶段代码评审通过。根据 reviewer 添加 `__init__.py` 导出、JSON 错误处理、显式 SQLite 连接关闭、PRAGMA foreign_keys。移除意外提交的 `pytest_out.txt`。

**目标：** 实现记忆存储，包含项目上下文、会话历史（SQLite）和失败模式。

**依赖：** Task 2

**文件：**
- 创建：`the_harness/memory/__init__.py`、`the_harness/memory/store.py`
- 测试：`tests/test_memory_store.py`

**实现要点：**
- `MemoryStore(workspace)`：
  - `scan_project() -> dict`：扫描测试框架、语言、目录结构 → 保存到 `project_context.json`
  - `save_session(session_data)`：插入 SQLite `sessions` 和 `actions` 表
  - `get_sessions() -> list`：查询历史会话
  - `save_failure_pattern(failure_type, strategy)`：更新 `failure_patterns.json`
  - `get_failure_pattern(failure_type) -> str|None`：查找失败类型的成功策略
  - `build_context(task) -> str`：组装相关上下文片段（项目信息 + 相关失败模式）
- SQLite 表结构：`sessions(id, test_path, success, rounds, created_at, reason)`、`actions(id, session_id, round, action_type, action_params, result)`

**验证（TDD）：**
1. 编写 `tests/test_memory_store.py` — 6 个测试：扫描项目（mock 目录）、保存并获取会话、保存并获取失败模式、构建上下文包含项目信息、构建上下文包含相关失败模式、空存储返回最小上下文
2. 运行 → 失败
3. 使用 `sqlite3` 和 `json` 实现 `store.py`
4. 运行 → 通过（6 个测试）
5. 提交：`feat: add memory store with SQLite session history and failure patterns`

---

## Task 11: Agent 主循环 ✅

**完成日期：** 2026-07-13
**Commit：** `876f41a`（合并：`HEAD`）
**备注：** TDD RED→GREEN，两阶段代码评审发现 2 个关键问题：(1) `credential_manager` 参数是不在 spec 中的死代码 — 已移除；(2) `tool_dispatcher.execute()` 返回值被丢弃，执行失败被静默忽略 — 现已捕获并检查 `exec_result.success`。还采纳了可选改进：拓宽 `_parse_action` 异常处理、简化 `_is_repeated` 签名、在 max-rounds 退出时添加 `save_session()` 调用。

**目标：** 实现 agent 主循环，编排所有组件。这是 harness 内核。

**依赖：** Task 3, 4, 5, 6, 7, 8, 9, 10

**文件：**
- 创建：`the_harness/agent_loop.py`
- 测试：`tests/test_agent_loop.py`

**实现要点：**
- `AgentLoop(config, llm_provider, guardrail, tool_dispatcher, validator, classifier, injector, memory_store)`
- `run(task) -> Result`：
  1. `context = memory.build_context(task)`
  2. 循环 `max_rounds` 次：
     a. `response = llm.complete(context)` — 调用 LLM
     b. `action = parse_action(response)` — 解析 JSON 为 Action
     c. 如果 `action.type == GIVE_UP` → 停机（reason="LLM gave up"）
     d. `gr = guardrail.check(action)` — 护栏检查
     e. 如果 `gr.blocked` → HITL 审批；如果拒绝 → 追加 "rejected" 到上下文，继续
     f. `result = tool_dispatcher.execute(action)` — 执行
     g. `test_result = validator.validate(task.test_path)` — 运行测试
     h. `feedback = classifier.classify(test_result)` — 分类
     i. 如果 `feedback.type == PASS` → 停机（success=True）
     j. 如果 `is_repeated(action, history)` → 停机（reason="stuck in loop"）
     k. `injection = injector.inject(feedback)` — 生成反馈 prompt
     l. `context.append(injection)` — 注入反馈
     m. `memory.update(task, action, feedback)` — 更新记忆
  3. 循环耗尽 → 停机（reason="max rounds exceeded"）
- `parse_action(response)`：解析 JSON `{"action", "params", "reasoning"}` → Action 对象；解析失败时追加"请返回规范 JSON"到上下文
- `is_repeated(action, history)`：检查最近 2 个动作是否相同

**验证（TDD）：**
1. 编写 `tests/test_agent_loop.py` — 6 个测试（使用 MockLLMProvider）：
   - `test_success_in_2_rounds`：mock 返回 edit_file 然后 run_tests，第二次 validator 返回 pass → 成功
   - `test_give_up`：mock 返回 give_up → 以 reason 停机
   - `test_max_rounds_exceeded`：mock 返回非修复动作 5 次 → 停机
   - `test_repeated_action`：mock 返回相同的 edit_file 两次 → 以"stuck"停机
   - `test_guardrail_blocks`：mock 返回 rm -rf → 护栏拦截 → 下一个动作安全
   - `test_feedback_drives_correction`：mock 返回错误 edit（compile_error）然后正确 edit → 成功
2. 运行 → 失败
3. 实现 `agent_loop.py`
4. 运行 → 通过（6 个测试）
5. 提交：`feat: add agent main loop with 5 stopping conditions`

---

## Task 12: WebUI ✅

**完成日期：** 2026-07-13
**Commit：** `c00f251`（合并：`HEAD`）
**备注：** TDD RED→GREEN，两阶段代码评审发现 2 个关键问题：(1) WebSocket 不是实时流式输出（事件在循环结束后批量发送）— 使用线程安全的 `queue.Queue` 修复以实现真正的实时事件传递；(2) 直接访问 AgentLoop 私有属性 — 修复为在构造前用 emitting 装饰器包装 LLM/validator。还添加了工作目录路径遍历防护、测试中的 feedback 事件断言、WebSocket 关闭时的会话清理。

**目标：** 实现 FastAPI WebUI，提供终端风格流式输出和会话历史侧边栏。

**依赖：** Task 11

**文件：**
- 创建：`the_harness/webui/__init__.py`、`the_harness/webui/app.py`
- 创建：`the_harness/webui/static/index.html`、`the_harness/webui/static/style.css`、`the_harness/webui/static/app.js`
- 测试：`tests/test_webui.py`

**实现要点：**
- `app.py`：FastAPI，含 WebSocket 端点 `/ws/fix` 和 REST 端点
  - `POST /api/fix` — 启动修复任务（test_path, workspace）→ 返回 session_id
  - `WS /ws/fix/{session_id}` — 实时流式推送 agent 输出事件
  - `GET /api/sessions` — 列出历史会话
  - `GET /api/sessions/{id}` — 获取会话详情
  - 静态文件服务 `index.html`
- `index.html`：左侧栏（会话历史列表），右侧主区域（终端风格流式输出），底部输入栏（测试路径输入 + 开始按钮）
- `app.js`：WebSocket 客户端，渲染流式事件为终端输出，获取会话历史
- 事件格式：`{"type": "action", "data": {...}}`、`{"type": "feedback", "data": {...}}`、`{"type": "result", "data": {...}}`

**验证（TDD）：**
1. 编写 `tests/test_webui.py` — 5 个测试（使用 FastAPI TestClient）：
   - `test_post_fix_returns_session_id`：POST /api/fix 返回 session_id
   - `test_get_sessions_returns_list`：GET /api/sessions 返回列表
   - `test_websocket_connect`：WS 连接建立
   - `test_websocket_receives_events`：WS 接收 action/feedback/result 事件（使用 mock LLM）
   - `test_static_index_served`：GET / 返回 HTML
2. 运行 → 失败
3. 实现 `app.py` + 前端文件
4. 运行 → 通过（5 个测试）
5. 提交：`feat: add WebUI with terminal streaming and session history`

---

## Task 13: 机制演示脚本 ✅

**完成日期：** 2026-07-13
**Commit：** `4b3a8a2`（合并：`HEAD`）
**备注：** TDD RED→GREEN，3 个测试 + demo.py 实现 3 个确定性演示（护栏拦截、反馈自我修正、失败分类路由）。全部使用 MockLLMProvider，退出码 0。修复了 assertion_failure 测试数据以匹配分类器的 `assert X == Y` 正则模式。

**目标：** 创建 `demo.py`，在 mock LLM 下确定性复现 3 种机制行为（§A.6 要求）。

**依赖：** Task 11

**文件：**
- 创建：`demo.py`
- 测试：`tests/test_demo.py`

**实现要点：**
- `demo.py` 运行 3 个演示，全部使用 MockLLMProvider（无网络/真实 LLM）：
  1. **护栏拦截危险动作**：MockLLM 返回 `run_shell("rm -rf /")` → 护栏拦截 → 下一个 mock 动作安全 → 验证 blocked=True 然后安全执行
  2. **反馈闭环驱动自我修正**：MockLLM 返回 edit_file（引入语法错误）→ validator 返回 compile_error → injector 生成反馈 → 第 2 个 mock 动作修复 → validator 返回 pass → 验证 2 轮，success=True
  3. **失败分类 + 策略路由**：构造 4 个不同的 TestResult → classifier 产生 4 种类型 → injector 产生 4 种策略提示 → 验证每条路径
- 输出：打印每个演示结果并附断言检查
- 退出码 0 表示全部通过

**验证（TDD）：**
1. 编写 `tests/test_demo.py` — 3 个测试：demo_guardrail_interception、demo_feedback_self_correction、demo_failure_classification_routing
2. 运行 → 失败
3. 实现 `demo.py`
4. 运行 `python demo.py` → 3 个演示全部通过；`pytest tests/test_demo.py -v` → 通过
5. 提交：`feat: add mechanism demo script with 3 deterministic demonstrations`

---

## Task 14: Docker + CI/CD ✅

**完成日期：** 2026-07-13
**Commit：** `47f11ce`（合并：`HEAD`）
**备注：** 创建 Dockerfile（python:3.12-slim, pip install -e ., 暴露 8000, CMD uvicorn）、GitHub Actions CI（unit-test + docker-build 两个 job）、Makefile（test/run/docker-build/demo/install 目标）。更新 README 添加分发命令表。取消注释 pyproject.toml 入口点。

**评审后修复（2026-07-13）：** 修复最终代码评审发现的 5 个问题：
1. `save_session` 字段名不匹配（`type`→`action_type`，`params`→`action_params`）— 数据丢失 bug
2. `save_session` 仅在 max-rounds 退出时调用 — 添加到全部 4 个退出路径（give_up, pass, repeated, max_rounds）
3. `pyproject.toml` 入口点指向 ASGI 对象 — 添加 `main()` 可调用函数
4. 缺少真实 LLM Provider — 创建 `OpenAILLMProvider`（`the_harness/llm/openai_provider.py`）
5. ToolDispatcher 缺少工作目录边界第二层检查 — 在 `_resolve_path` 中添加 `PermissionError`

**合规修复（2026-07-13）：** 修复 TASK.md 合规检查发现的 3 项缺失：
1. 创建 `.gitlab-ci.yml` — GitLab CI 配置，含 `unit-test` job（§五.6 要求）
2. 创建 `the_harness/cli.py` — 交互式首次运行凭据设置 CLI，使用 `getpass` 隐藏输入（§3.1 要求）
3. 更新 `README.md` — 添加部署架构图、CI/CD 管道表、凭据 CLI 命令（§4.11 要求）
4. 在 `pyproject.toml` 添加 `the-harness-creds` 入口点
5. 添加 17 个 CLI 测试（`tests/test_cli.py`）— 共 99 个测试通过

**目标：** 创建 Dockerfile、GitHub Actions CI 配置和部署设置。

**依赖：** 所有前序 task

**文件：**
- 创建：`Dockerfile`
- 创建：`.github/workflows/ci.yml`
- 创建：`Makefile`
- 修改：`README.md`（确保分发说明完整）

**实现要点：**
- `Dockerfile`：
  - 基础镜像：`python:3.12-slim`
  - 安装依赖：`pip install -e .`
  - 暴露端口 8000
  - CMD：`uvicorn the_harness.webui:app --host 0.0.0.0 --port 8000`
- `.github/workflows/ci.yml`：
  - Job `unit-test`（§五.6 要求的名称）：checkout → setup Python 3.12 → pip install -e .[dev] → pytest
  - Job `docker-build`（depends on unit-test）：docker build → docker push（仅 main 分支）
- `Makefile`：`test: pytest`、`run: uvicorn ...`、`docker-build: docker build ...`、`demo: python demo.py`

**验证：**
1. 运行 `make test` → 全部测试通过
2. 运行 `docker build -t the-harness .` → 镜像构建成功
3. 运行 `docker run -p 8000:8000 the-harness` → 服务启动，WebUI 可在 localhost:8000 访问
4. 推送到 GitHub → CI `unit-test` job 通过
5. 提交：`feat: add Dockerfile, CI config, and Makefile`

---

## 总结

| Task | 模块 | 测试数 | 依赖 | 可并行 |
|------|------|--------|------|--------|
| 1 | 项目脚手架 | 2 | — | — |
| 2 | 数据模型 | 7 | 1 | — |
| 3 | LLM 抽象层 | 3 | 2 | 是（与 4,5,6,7,10） |
| 4 | 凭据管理器 | 6 | 2 | 是（与 3,5,6,7,10） |
| 5 | 护栏 | 12 | 2 | 是（与 3,4,6,7,10） |
| 6 | 工具分发器 | 8 | 2 | 是（与 3,4,5,7,10） |
| 7 | 测试校验器 | 4 | 2 | 是（与 3,4,5,6,10） |
| 8 | 失败分类器 | 9 | 7 | — |
| 9 | 反馈回灌器 | 6 | 8 | — |
| 10 | 记忆存储 | 6 | 2 | 是（与 3,4,5,6,7） |
| 11 | Agent 主循环 | 6 | 3,4,5,6,7,8,9,10 | — |
| 12 | WebUI | 5 | 11 | 是（与 13） |
| 13 | 演示脚本 | 3 | 11 | 是（与 12） |
| 14 | Docker + CI | — | 全部 | — |

**总计：14 个 task，99 个测试**（82 原有 + 17 CLI）

---

## PLAN.md 更新协议

根据 §4.7："PLAN.md 持续更新：每完成一个 task 即标记完成并附 commit hash"

每完成一个 task 后，更新对应的 task 条目：

```markdown
## Task N: [名称] ✅
**完成日期：** 2026-07-XX
**Commit：** `abc1234`
**备注：** [任何偏离或教训]
```
