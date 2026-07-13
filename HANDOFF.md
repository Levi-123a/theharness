# HANDOFF PROMPT — the-harness 项目继续执行

> 将此提示词完整提供给新的智能体，它应能从当前状态继续推进项目。

---

## 你是谁，你要做什么

你是一个编码智能体，正在完成 AI4SE 期末项目 **Coding Agent Harness（the-harness）**。这个项目要求你**自己编码实现**一个 coding agent 的 harness 内核（主循环、工具分发、治理护栏、反馈闭环、记忆存储），而不是在现成框架上做配置。

项目工作目录：`d:\001\the harness`

## 工作流要求（必须严格遵守）

1. **git worktrees 隔离**：每个 task 开一个 worktree（`.worktrees/task-N-xxx`），对应一个 feature 分支
2. **TDD 强制**：红→绿→重构。先写失败测试，确认 RED，再写最少实现使其变绿，再重构。不允许先写实现再补测试
3. **两阶段评审**：每个 task 完成后，派发 `code-reviewer` subagent 做 (1) spec 合规检查 (2) 代码质量检查。Critical issue 必须修复才能进入下一 task
4. **完成分支**：`git merge --no-ff` 合并回 main，然后 `git worktree remove --force` 清理
5. **文档同步**：每完成一个 task，更新 `PLAN.md`（标记 ✅ + commit hash）和 `AGENT_LOG.md`（时间戳 + 过程 + 教训）

### TDD 具体步骤（每个 task）

```
1. git worktree add .worktrees/task-N-xxx -b feature/task-N-xxx
2. cd .worktrees/task-N-xxx && py -m pip install -e . -q
3. 编写 tests/test_xxx.py（失败测试）
4. py -m pytest tests/test_xxx.py -v  → 确认 RED（ModuleNotFoundError）
5. 实现 the_harness/xxx.py
6. py -m pytest tests/test_xxx.py -v  → 确认 GREEN
7. py -m pytest -v  → 全量测试无回归
8. git add -A && git commit -m "feat: ..."
9. 派发 code-reviewer subagent 两阶段评审
10. 修复 Critical issue → git commit --amend
11. cd .. && git merge feature/task-N-xxx --no-ff -m "merge: Task N — ..."
12. git worktree remove .worktrees/task-N-xxx --force
13. 更新 PLAN.md + AGENT_LOG.md → git commit -m "docs: ..."
```

## 环境信息

- **OS**: Windows (win32)
- **Shell**: PowerShell
- **Python**: 3.13.5（用 `py` 命令启动，不是 `python`）
- **pip**: 用 `py -m pip`，不是 `pip`
- **PowerShell CLIXML 问题**：PowerShell 命令输出可能被 CLIXML 编码包裹。用以下方式捕获输出：
  ```powershell
  py -c "import subprocess; r = subprocess.run(['py', '-m', 'pytest', '-v'], capture_output=True, text=True, cwd=r'd:\001\the harness\.worktrees\task-N-xxx'); print(r.stdout[-2000:]); print('RC:', r.returncode)"
  ```
- **pytest 配置**：`pyproject.toml` 中已配置 `testpaths = ["tests"]`

## 当前状态

### 已完成 Tasks 1-10（main 分支，68 tests passing）

| Task | 模块 | Merge Commit | 测试数 |
|------|------|-------------|--------|
| 1 | Project Scaffolding | (early) | 2 |
| 2 | Data Models (`models.py`) | `aca8b06` | 9 |
| 3 | LLM Abstraction (`llm/`) | `5b97ddc` | 3 |
| 4 | Credential Manager (`credentials/`) | `be3dcd3` | 6 |
| 5 | Guardrail (`guardrail/`) | `91fcf98` | 12 |
| 6 | Tool Dispatcher (`tools/`) | `780e1f1` | 8 |
| 7 | Test Validator (`feedback/validator.py`) | `c535bb5` | 5 |
| 8 | Failure Classifier (`feedback/classifier.py`) | `a8f88cc` | 10 |
| 9 | Feedback Injector (`feedback/injector.py`) | `c451b3c` | 7 |
| 10 | Memory Store (`memory/store.py`) | `3289958` | 6 |

**main 分支 HEAD**: `1e2b0e3` (docs: update PLAN.md and AGENT_LOG.md for Task 10)

### Task 11 (Agent Main Loop) — 进行中

- **Worktree**: `.worktrees/task-11-agent-loop`（分支 `feature/task-11-agent-loop`，commit `6555d69`）
- **TDD 状态**: RED→GREEN 完成，6 tests passed，74 total passed
- **代码评审**: 已完成，发现 **2 个 Critical issue**：
  1. `credential_manager` 参数是死代码且打乱了构造函数位置参数顺序（规范中没有此参数）
  2. `tool_dispatcher.execute(action)` 返回值被丢弃，执行失败被静默忽略

### Task 11 需要的修复

在 worktree `d:\001\the harness\.worktrees\task-11-agent-loop` 中修改 `the_harness/agent_loop.py`：

1. **移除 `credential_manager` 参数**：从构造函数中删除 `credential_manager` 参数和 `self._creds = credential_manager` 赋值。同时删除 `from the_harness.credentials.manager import CredentialManager` 导入。更新测试文件 `tests/test_agent_loop.py` 中的 `_make_loop` 函数，删除 `credential_manager=None` 参数。

2. **捕获执行结果**：将 `self._dispatcher.execute(action)` 改为：
   ```python
   exec_result = self._dispatcher.execute(action)
   if not exec_result.success:
       context_parts.append(f"Action execution failed: {exec_result.error}")
       continue
   ```

3. **可选改进**（reviewer 建议但非必须）：
   - `_parse_action` 的 except 增加 `AttributeError, TypeError`
   - `_is_repeated` 移除冗余的 `action` 参数或改用 `action` 比较
   - 在 `run()` 结束时调用 `self._memory.save_session()` 保存会话

修复后：
```powershell
# 验证测试通过
py -c "import subprocess; r = subprocess.run(['py', '-m', 'pytest', 'tests/test_agent_loop.py', '-v'], capture_output=True, text=True, cwd=r'd:\001\the harness\.worktrees\task-11-agent-loop'); print(r.stdout[-1500:]); print('RC:', r.returncode)"

# amend 提交
cd "d:\001\the harness\.worktrees\task-11-agent-loop" && git add -A && git commit --amend -m "feat: add agent main loop with 5 stopping conditions"

# 合并回 main
cd "d:\001\the harness" && git merge feature/task-11-agent-loop --no-ff -m "merge: Task 11 — agent main loop with 5 stopping conditions"

# 清理 worktree
git worktree remove .worktrees/task-11-agent-loop --force

# 更新文档（PLAN.md + AGENT_LOG.md）后提交
git add -A && git commit -m "docs: update PLAN.md and AGENT_LOG.md for Task 11"
```

## 待完成 Tasks 12-14 + 收尾

### Task 12: WebUI

**依赖**: Task 11
**文件**: `the_harness/webui/__init__.py`, `the_harness/webui/app.py`, `the_harness/webui/static/index.html`, `the_harness/webui/static/style.css`, `the_harness/webui/static/app.js`
**测试**: `tests/test_webui.py`（5 tests）

**实现要点**:
- FastAPI + WebSocket
- `POST /api/fix` — 启动修复任务 (test_path, workspace) → 返回 session_id
- `WS /ws/fix/{session_id}` — 实时流式输出 agent 事件
- `GET /api/sessions` — 列出历史会话
- `GET /api/sessions/{id}` — 会话详情
- 静态文件服务 `index.html`
- 事件格式: `{"type": "action", "data": {...}}`, `{"type": "feedback", "data": {...}}`, `{"type": "result", "data": {...}}`
- 前端: 左侧会话历史列表，右侧终端风格流式输出，底部输入栏

**测试**（用 FastAPI TestClient）:
1. `test_post_fix_returns_session_id`: POST /api/fix 返回 session_id
2. `test_get_sessions_returns_list`: GET /api/sessions 返回列表
3. `test_websocket_connect`: WS 连接建立
4. `test_websocket_receives_events`: WS 接收 action/feedback/result 事件（用 mock LLM）
5. `test_static_index_served`: GET / 返回 HTML

**注意**: 需要在 `pyproject.toml` 中确认 `fastapi`, `uvicorn`, `websockets` 已在 dependencies 中。TestClient 需要 `httpx`。

### Task 13: 机制演示脚本

**依赖**: Task 11
**文件**: `demo.py`, `tests/test_demo.py`（3 tests）

**实现要点**:
- 3 个确定性演示，全部使用 MockLLMProvider（无网络/真实 LLM）:
  1. **护栏拦截危险动作**: MockLLM 返回 `run_shell("rm -rf /")` → guardrail 拦截 → 下一个 mock action 安全 → 验证 blocked=True 然后安全执行
  2. **反馈闭环驱动自我修正**: MockLLM 返回 edit_file（引入语法错误）→ validator 返回 compile_error → injector 生成反馈 → 第 2 个 mock action 修复 → validator 返回 pass → 验证 2 rounds, success=True
  3. **失败分类 + 策略路由**: 构造 4 个不同 TestResult → classifier 产生 4 种类型 → injector 产生 4 种 strategy hint → 验证每条路径
- 输出: 打印每个演示结果 + 断言检查
- 退出码 0 表示全部通过

### Task 14: Docker + CI/CD

**依赖**: 所有前序 task
**文件**: `Dockerfile`, `.github/workflows/ci.yml`, `Makefile`, 修改 `README.md`

**实现要点**:
- `Dockerfile`: 基于 `python:3.12-slim`，`pip install -e .`，暴露 8000 端口，CMD `uvicorn the_harness.webui:app --host 0.0.0.0 --port 8000`
- `.github/workflows/ci.yml`: 
  - Job `unit-test`（必须叫这个名字）: checkout → setup Python 3.12 → `pip install -e .[dev]` → `pytest`
  - Job `docker-build`（depends on unit-test）: docker build → docker push (on main)
- `Makefile`: `test: pytest`, `run: uvicorn ...`, `docker-build: docker build ...`, `demo: python demo.py`

### 收尾工作

1. **最终代码评审**: 派发 code-reviewer 对整个项目做最终评审
2. **REFLECTION.md**: 1500-2500 字反思报告，至少回答:
   - 哪些 Superpowers 技能发挥了最大作用、哪些"形式大于实质"？
   - TDD 强制在 AI 协作下是阻碍还是放大器？
   - subagent-driven 工作流让智能体能自主运行多久而不偏离主题？
   - 什么样的 task 颗粒度最优？
   - SPEC/PLAN 质量如何影响实现质量（举一个具体案例）？
   - 最有效的 prompt/context 策略是什么？
   - 凭据与分发迫使你想清楚了哪些原本会忽略的问题？
   - 如果重做会改变什么？
   - 对 Superpowers 方法论的批判——它假设了什么，这些假设成立吗？
3. **线上部署**: 提供可访问的公网 WebUI URL（可用 Render/Railway/Fly.io 等免费额度）
4. **README.md**: 确保包含项目简介、安装、运行、分发命令、目录结构、安全边界说明

## 关键技术接口速查

### 数据模型 (`the_harness/models.py`)

```python
class ActionType(str, Enum):
    READ_FILE = "read_file"
    EDIT_FILE = "edit_file"
    WRITE_FILE = "write_file"
    RUN_SHELL = "run_shell"
    RUN_TESTS = "run_tests"
    GIVE_UP = "give_up"

class FeedbackType(str, Enum):
    COMPILE_ERROR = "compile_error"
    ASSERTION_FAILURE = "assertion_failure"
    ENVIRONMENT_ERROR = "environment_error"
    TIMEOUT = "timeout"
    PASS = "pass"
    UNKNOWN = "unknown_failure"

@dataclass
class Task:
    test_path: str
    workspace: str

@dataclass
class Action:
    type: ActionType
    params: dict[str, Any]
    reasoning: str = ""

@dataclass
class ActionResult:
    success: bool
    output: str = ""
    error: str | None = None

@dataclass
class TestResult:
    __test__ = False  # 防止 pytest 收集
    exit_code: int
    stdout: str
    stderr: str
    passed: bool

@dataclass
class ClassifiedFeedback:
    type: FeedbackType
    location: str | None = None
    message: str | None = None
    expected: str | None = None
    actual: str | None = None
    strategy_hint: str = ""

@dataclass
class Result:
    success: bool
    rounds: int
    reason: str
    action_history: list[Action] = field(default_factory=list)

@dataclass
class GuardrailResult:
    blocked: bool
    reason: str = ""
```

### 组件接口

```python
# LLM
class LLMProvider(ABC):
    @abstractmethod
    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]: ...

class MockLLMProvider(LLMProvider):
    def __init__(self, actions: list[dict[str, Any]]) -> None: ...
    def complete(self, messages) -> dict[str, Any]: ...  # 返回 {"action", "params", "reasoning"}
    def reset(self) -> None: ...

# Guardrail
class Guardrail:
    def __init__(self, workspace: str) -> None: ...
    def check(self, action: Action) -> GuardrailResult: ...

# ToolDispatcher
class ToolDispatcher:
    def __init__(self, workspace: str) -> None: ...
    def execute(self, action: Action) -> ActionResult: ...

# TestValidator
class TestValidator:
    __test__ = False
    def __init__(self, workspace: str, timeout: int = 30) -> None: ...
    def validate(self, test_path: str) -> TestResult: ...

# FailureClassifier
class FailureClassifier:
    def classify(self, result: TestResult) -> ClassifiedFeedback: ...

# FeedbackInjector
class FeedbackInjector:
    def inject(self, feedback: ClassifiedFeedback) -> str: ...

# MemoryStore
class MemoryStore:
    def __init__(self, workspace: str) -> None: ...
    def scan_project(self) -> dict: ...
    def save_session(self, session_data: dict) -> int: ...
    def get_sessions(self) -> list[dict]: ...
    def save_failure_pattern(self, failure_type: str, strategy: str) -> None: ...
    def get_failure_pattern(self, failure_type: str) -> str | None: ...
    def build_context(self, task: Task) -> str: ...

# AgentLoop (Task 11, 修复后)
class AgentLoop:
    def __init__(self, config, llm_provider, guardrail, tool_dispatcher, validator, classifier, injector, memory_store, hitl_callback=None): ...
    def run(self, task: Task) -> Result: ...
```

### Config (`the_harness/config.py`)

```python
@dataclass
class Config:
    max_rounds: int = 5
    llm_provider: str = "openai"
    model: str = "gpt-4o-mini"
    workspace: str = "."
    test_timeout: int = 30
```

## 已知坑和教训

1. **`__test__ = False`**: 类名以 "Test" 开头的类（如 `TestResult`, `TestValidator`）需要加 `__test__ = False` 防止 pytest 误收集
2. **PowerShell CLIXML**: 直接运行 PowerShell 命令输出会被 CLIXML 编码，用 `py -c "import subprocess; ..."` 包装
3. **`py` vs `python`**: 测试中用 `python` 而非 `py` 以保证 CI 可移植性
4. **意外提交测试输出文件**: `pytest_out.txt`、`test_output.txt` 已加入 `.gitignore`，但仍需注意 `git add -A` 前检查
5. **SQLite `with` 上下文管理器**: 只负责 commit/rollback，不关闭连接。需用 `try/finally + conn.close()`
6. **正则非贪婪匹配 + 可选组**: `.+?` 与 `(?:...)?` 组合时引擎取最短匹配导致可选组被跳过——拆分为独立正则
7. **规范字符串匹配**: `"timeout"` 和 `"timed out"` 是不同子串，需同时覆盖
8. **code-reviewer subagent 限流**: 如果 dispatch 失败提示 "Request rate increased too quickly"，等待 10 秒重试

## 项目目录结构

```
d:\001\the harness\
├── PLAN.md              # 实现计划（14 tasks，依赖图，完成标记）
├── AGENT_LOG.md         # 开发过程日志
├── SPEC.md              # 设计文档
├── SPEC_PROCESS.md      # 规约过程文档
├── TASK.md              # 项目要求原文
├── README.md            # 项目说明
├── pyproject.toml       # 项目配置 + 依赖
├── .gitignore           # 包含 .worktrees/, *.db, *.enc, test_output.txt, pytest_out.txt
├── tests/
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_mock_provider.py
│   ├── test_credential_manager.py
│   ├── test_guardrail.py
│   ├── test_tool_dispatcher.py
│   ├── test_validator.py
│   ├── test_classifier.py
│   ├── test_injector.py
│   ├── test_memory_store.py
│   └── test_agent_loop.py  # Task 11（在 worktree 中）
├── the_harness/
│   ├── __init__.py
│   ├── config.py
│   ├── models.py
│   ├── agent_loop.py     # Task 11（在 worktree 中）
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   └── mock_provider.py
│   ├── credentials/
│   │   ├── __init__.py
│   │   └── manager.py
│   ├── guardrail/
│   │   ├── __init__.py
│   │   └── guardrail.py
│   ├── tools/
│   │   ├── __init__.py
│   │   └── dispatcher.py
│   ├── feedback/
│   │   ├── __init__.py
│   │   ├── validator.py
│   │   ├── classifier.py
│   │   └── injector.py
│   ├── memory/
│   │   ├── __init__.py
│   │   └── store.py
│   └── webui/            # Task 12（待创建）
└── .worktrees/           # gitignored
    └── task-11-agent-loop/  # 当前活跃 worktree
```

## 立即行动

1. 先 `cd "d:\001\the harness\.worktrees\task-11-agent-loop"` 进入 Task 11 worktree
2. 读取 `the_harness/agent_loop.py` 和 `tests/test_agent_loop.py` 了解当前状态
3. 修复 2 个 Critical issue（移除 credential_manager + 捕获执行结果）
4. 验证测试通过 → amend → 合并 → 清理 worktree → 更新文档
5. 继续 Task 12 (WebUI) → Task 13 (Demo) → Task 14 (Docker+CI) → 收尾
