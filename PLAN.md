# the-harness Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a self-implemented Coding Agent Harness with a feedback loop mechanism that autonomously fixes failing tests through multi-round self-correction.

**Architecture:** Agent main loop orchestrates LLM calls, tool dispatch, guardrails, and a feedback loop (validator → classifier → injector). All mechanisms are deterministic code testable with mock LLM. WebUI provides terminal-style streaming via FastAPI WebSocket.

**Tech Stack:** Python 3.12, FastAPI, pytest, cryptography, openai, SQLite, Docker

---

## Task Dependency Graph

```
Task 1 (Scaffolding)
  └── Task 2 (Data Models)
        ├── Task 3 (LLM Abstraction)      ┐
        ├── Task 4 (Credential Manager)    │
        ├── Task 5 (Guardrail)             │ Parallelizable
        ├── Task 6 (Tool Dispatcher)       │ (after Task 2)
        ├── Task 7 (Test Validator)        │
        ├── Task 10 (Memory Store)         ┘
        │     └── Task 8 (Failure Classifier)
        │           └── Task 9 (Feedback Injector)
        └── Task 11 (Agent Main Loop) — depends on 3,4,5,6,7,8,9,10
              ├── Task 12 (WebUI)
              ├── Task 13 (Demo Script)
              └── Task 14 (Docker + CI) — depends on all
```

**Parallelizable groups:**
- After Task 2: Tasks 3, 4, 5, 6, 7, 10 (separate worktrees)
- After Task 7: Task 8 → Task 9
- After Task 11: Tasks 12, 13 (parallel)

---

## Task 1: Project Scaffolding ✅

**Completed:** 2026-07-10
**Commit:** `240c07b` (merge: `3a4e668`)
**Notes:** TDD RED→GREEN, two-stage code review passed. Fixed build-backend from `setuptools.backends._legacy:_legacy` to `setuptools.build_meta` per reviewer. Commented out `project.scripts` entry point (Task 12 not yet implemented).

**Goal:** Create package structure, pyproject.toml, and base Config dataclass.

**Depends on:** None

**Files:**
- Create: `pyproject.toml`, `the_harness/__init__.py`, `the_harness/config.py`
- Create: `tests/__init__.py`, `tests/conftest.py`
- Test: `tests/test_config.py`

**Implementation points:**
- `pyproject.toml`: project metadata, dependencies (openai, cryptography, fastapi, uvicorn, websockets, pytest), pytest config
- `Config` dataclass: `max_rounds=5`, `llm_provider="openai"`, `model="gpt-4o-mini"`, `workspace="."`, `test_timeout=30`

**Verification (TDD):**
1. Write `tests/test_config.py` — test default config values and custom config
2. Run `pytest tests/test_config.py -v` → FAIL (ModuleNotFoundError)
3. Implement `pyproject.toml` + `the_harness/config.py`
4. Run `pip install -e . && pytest tests/test_config.py -v` → PASS
5. Commit: `feat: project scaffolding with config dataclass`

---

## Task 2: Data Models ✅

**Completed:** 2026-07-13
**Commit:** `aca8b06` (merge: `45088e9`)
**Notes:** TDD RED→GREEN, two-stage code review passed. Added `__test__=False` to TestResult to prevent pytest collection warning. Added GuardrailResult test per reviewer feedback. Added `test_output.txt` to .gitignore.

**Goal:** Define all core data structures used across the harness.

**Depends on:** Task 1

**Files:**
- Create: `the_harness/models.py`
- Test: `tests/test_models.py`

**Implementation points:**
- Enums (use `str, Enum` mixin, values are lowercase strings):
  - `ActionType`: `READ_FILE="read_file"`, `EDIT_FILE="edit_file"`, `WRITE_FILE="write_file"`, `RUN_SHELL="run_shell"`, `RUN_TESTS="run_tests"`, `GIVE_UP="give_up"`
  - `FeedbackType`: `COMPILE_ERROR="compile_error"`, `ASSERTION_FAILURE="assertion_failure"`, `ENVIRONMENT_ERROR="environment_error"`, `TIMEOUT="timeout"`, `PASS="pass"`, `UNKNOWN="unknown_failure"`
- Dataclasses with defaults:
  - `Task(test_path: str, workspace: str)` — no defaults
  - `Action(type: ActionType, params: dict[str, Any], reasoning: str = "")`
  - `ActionResult(success: bool, output: str = "", error: str | None = None)`
  - `TestResult(exit_code: int, stdout: str, stderr: str, passed: bool)` — no defaults
  - `ClassifiedFeedback(type: FeedbackType, location: str | None = None, message: str | None = None, expected: str | None = None, actual: str | None = None, strategy_hint: str = "")`
  - `Result(success: bool, rounds: int, reason: str, action_history: list[Action] = field(default_factory=list))`
  - `GuardrailResult(blocked: bool, reason: str = "")`
- Note: Config is passed to AgentLoop constructor, not embedded in Task

**Verification (TDD):**
1. Write `tests/test_models.py` — 7 tests: create each dataclass, verify fields and enum values
2. Run `pytest tests/test_models.py -v` → FAIL
3. Implement `the_harness/models.py`
4. Run `pytest tests/test_models.py -v` → PASS (7 tests)
5. Commit: `feat: add core data models`

---

## Task 3: LLM Abstraction Layer ✅

**Completed:** 2026-07-13
**Commit:** `5b97ddc` (merge: `86add89`)
**Notes:** TDD RED→GREEN, two-stage code review passed (spec compliance PASS, code quality PASS). No critical issues.

**Goal:** Create LLMProvider interface and MockLLMProvider for deterministic testing.

**Depends on:** Task 2

**Files:**
- Create: `the_harness/llm/__init__.py`, `the_harness/llm/base.py`, `the_harness/llm/mock_provider.py`
- Test: `tests/test_mock_provider.py`

**Implementation points:**
- `LLMProvider` (ABC): abstract method `complete(messages) -> dict` returning `{"action", "params", "reasoning"}`
- `MockLLMProvider`: takes preset action list, returns sequentially, raises `IndexError` when exhausted, `reset()` to restart

**Verification (TDD):**
1. Write `tests/test_mock_provider.py` — 3 tests: returns preset actions in order, raises IndexError when exhausted, reset works
2. Run → FAIL
3. Implement `base.py` + `mock_provider.py`
4. Run → PASS (3 tests)
5. Commit: `feat: add LLM abstraction layer with mock provider`

---

## Task 4: Credential Manager ✅

**Completed:** 2026-07-13
**Commit:** `f54e36f` (merge: `be3dcd3`)
**Notes:** TDD RED→GREEN, two-stage code review passed. Fixed unlock() to clear state before attempting. Removed unused imports per reviewer.

**Goal:** Implement AES-256 encrypted credential storage with master password (PBKDF2 key derivation).

**Depends on:** Task 2

**Files:**
- Create: `the_harness/credentials/__init__.py`, `the_harness/credentials/manager.py`
- Test: `tests/test_credential_manager.py`

**Implementation points:**
- `CredentialManager`: AES-GCM encryption, PBKDF2 key derivation (100k iterations, 16-byte salt)
- Methods: `setup(master_password)`, `unlock(master_password)`, `lock()`, `store(provider, key)`, `get(provider)`, `status()` (no plaintext), `delete(provider)`
- File format: salt(16) + nonce(12) + ciphertext, file permission 600

**Verification (TDD):**
1. Write `tests/test_credential_manager.py` — 6 tests: setup creates file, store+get roundtrip, status no plaintext, delete, wrong password fails, update key
2. Run → FAIL
3. Implement `manager.py` using `cryptography` library
4. Run → PASS (6 tests)
5. Commit: `feat: add AES-256 encrypted credential manager`

---

## Task 5: Guardrail ✅

**Completed:** 2026-07-13
**Commit:** `4d01088` (merge: `91fcf98`)
**Notes:** TDD RED→GREEN, two-stage code review passed (spec compliance PASS, code quality PASS). No critical issues.

**Goal:** Implement dangerous action interception with regex patterns and workspace path checking.

**Depends on:** Task 2

**Files:**
- Create: `the_harness/guardrail/__init__.py`, `the_harness/guardrail/guardrail.py`
- Test: `tests/test_guardrail.py`

**Implementation points:**
- `Guardrail(workspace)`: 14 dangerous regex patterns (rm -rf, del /s, git push --force, git reset --hard, git push origin, curl|sh, wget|sh, scp, rsync, sudo, chmod 777, git clean -fd, rm -r, rmdir /s)
- System path check: `/etc/`, `C:\Windows\`, `/sys/`, `/proc/`
- Workspace boundary: resolve path, check `relative_to(workspace)`, block if outside
- `check(action) -> GuardrailResult(blocked, reason)`

**Verification (TDD):**
1. Write `tests/test_guardrail.py` — 12 tests: safe read allowed, rm -rf blocked, git push --force blocked, git reset --hard blocked, sudo blocked, curl|sh blocked, path traversal blocked, write outside blocked, safe shell allowed, pytest allowed, chmod 777 blocked, del /s blocked
2. Run → FAIL
3. Implement `guardrail.py`
4. Run → PASS (12 tests)
5. Commit: `feat: add guardrail with 5-category dangerous action interception`

---

## Task 6: Tool Dispatcher ✅

**Completed:** 2026-07-13
**Commit:** `e4d4a12` (merge: `780e1f1`)
**Notes:** TDD RED→GREEN, two-stage code review passed. Fixed `py` to `python` for CI portability per reviewer.

**Goal:** Implement file operations (read/write/edit) and shell execution with workspace isolation.

**Depends on:** Task 2

**Files:**
- Create: `the_harness/tools/__init__.py`, `the_harness/tools/dispatcher.py`
- Test: `tests/test_tool_dispatcher.py`

**Implementation points:**
- `ToolDispatcher(workspace)`: resolves all paths relative to workspace
- `_read_file`: read file content, return error if not found
- `_write_file`: create/overwrite file, create parent dirs
- `_edit_file`: exact string replacement (old_text → new_text), error if old_text not found
- `_run_shell`: `subprocess.run(shell=True, cwd=workspace, timeout=30)`, return stdout/stderr
- `give_up`: return success with "gave up"

**Verification (TDD):**
1. Write `tests/test_tool_dispatcher.py` — 8 tests: read file, write file, edit file, edit text not found, shell success, shell failure, read nonexistent, give up
2. Run → FAIL
3. Implement `dispatcher.py`
4. Run → PASS (8 tests)
5. Commit: `feat: add tool dispatcher with file ops and shell execution`

---

## Task 7: Test Validator ✅

**Completed:** 2026-07-13
**Commit:** `c535bb5` (merge: `7eeb976`)
**Notes:** TDD RED→GREEN→REFACTOR, two-stage code review passed (spec compliance PASS, code quality PASS). Added `__test__=False` to prevent pytest collection warning. Added 5th test `test_validate_pytest_not_found` per reviewer suggestion. Simplified timeout assertion.

**Goal:** Implement deterministic test validator that runs pytest and captures output.

**Depends on:** Task 2

**Files:**
- Create: `the_harness/feedback/__init__.py`, `the_harness/feedback/validator.py`
- Test: `tests/test_validator.py`

**Implementation points:**
- `TestValidator(workspace, timeout=30)`: runs `pytest --tb=short -v`
- `validate(test_path) -> TestResult`: captures exit_code, stdout, stderr; `passed = exit_code == 0`
- Handles: TimeoutExpired → TestResult(passed=False, stderr="timed out"), FileNotFoundError → "pytest not found"
- Pure deterministic: mock `subprocess.run` in tests

**Verification (TDD):**
1. Write `tests/test_validator.py` — 4 tests: validate pass (mock exit_code=0), validate fail (mock exit_code=1), syntax error in output, timeout
2. Run → FAIL
3. Implement `validator.py`
4. Run → PASS (4 tests)
5. Commit: `feat: add deterministic test validator`

---

## Task 8: Failure Classifier ✅

**Completed:** 2026-07-13
**Commit:** `a8f88cc` (merge: `1818fd1`)
**Notes:** TDD RED→GREEN, two-stage code review passed. Fixed critical issue: "timed out" → also check "timeout" per spec. Added `test_classify_timeout_by_stderr_only` test. Split `_RE_SYNTAX` into two patterns for correct location extraction.

**Goal:** Implement failure classifier that categorizes TestResult into 5 types using regex. This is the core of the feedback loop.

**Depends on:** Task 7

**Files:**
- Create: `the_harness/feedback/classifier.py`
- Test: `tests/test_classifier.py`

**Implementation points:**
- `FailureClassifier`: pure regex matching on `TestResult.stdout + stderr`
- Classification rules (in priority order):
  1. `passed == True` → `FeedbackType.PASS`
  2. `SyntaxError|IndentationError` → `COMPILE_ERROR` (extract location, message)
  3. `AssertionError|assert` → `ASSERTION_FAILURE` (extract expected, actual)
  4. `ModuleNotFoundError|ImportError|FileNotFoundError` → `ENVIRONMENT_ERROR` (extract missing module)
  5. `exit_code == -1` or "timeout" in stderr → `TIMEOUT` (extract timeout_limit)
  6. fallback → `UNKNOWN`
- Each type has a `strategy_hint` string
- Pure deterministic: same input → same output, every time

**Verification (TDD):**
1. Write `tests/test_classifier.py` — 9 tests: classify pass, syntax error (check location), assertion failure (check expected/actual), import error, file not found, timeout, unknown, deterministic same-input-same-output, strategy_hint present
2. Run → FAIL
3. Implement `classifier.py` with regex patterns
4. Run → PASS (9 tests)
5. Commit: `feat: add failure classifier with 5-type regex classification`

---

## Task 9: Feedback Injector ✅

**Completed:** 2026-07-13
**Commit:** `c451b3c` (merge: `5ef6151`)
**Notes:** TDD RED→GREEN, two-stage code review passed. Fixed TIMEOUT format redundancy per reviewer. Added `test_inject_includes_strategy_hint` test per reviewer.

**Goal:** Implement feedback injector that converts ClassifiedFeedback into structured prompt fragments for the next LLM round.

**Depends on:** Task 8

**Files:**
- Create: `the_harness/feedback/injector.py`
- Test: `tests/test_injector.py`

**Implementation points:**
- `FeedbackInjector`: converts `ClassifiedFeedback` → structured text prompt fragment
- Different types produce different injection content:
  - `COMPILE_ERROR`: "Syntax error at {location}: {message}. Fix the syntax error."
  - `ASSERTION_FAILURE`: "Test failed: expected {expected}, got {actual}. Check the logic."
  - `ENVIRONMENT_ERROR`: "Missing dependency: {missing_module}. Check if dependencies are installed."
  - `TIMEOUT`: "Test timed out after {timeout_limit}s. Check for infinite loops or performance issues."
  - `UNKNOWN`: "Test failed with unknown error: {message}."
  - `PASS`: "All tests passed."
- Each injection includes the `strategy_hint`
- Only injects current round's feedback summary, not full history

**Verification (TDD):**
1. Write `tests/test_injector.py` — 6 tests: inject compile_error (check location in output), inject assertion_failure (check expected/actual in output), inject environment_error (check missing module in output), inject timeout (check timeout info in output), inject unknown, inject pass (check "passed" in output)
2. Run → FAIL
3. Implement `injector.py`
4. Run → PASS (6 tests)
5. Commit: `feat: add feedback injector with type-specific strategy routing`

---

## Task 10: Memory Store

**Goal:** Implement memory store with project context, session history (SQLite), and failure patterns.

**Depends on:** Task 2

**Files:**
- Create: `the_harness/memory/__init__.py`, `the_harness/memory/store.py`
- Test: `tests/test_memory_store.py`

**Implementation points:**
- `MemoryStore(workspace)`:
  - `scan_project() -> dict`: scan for test framework, language, directory structure → save to `project_context.json`
  - `save_session(session_data)`: insert into SQLite `sessions` and `actions` tables
  - `get_sessions() -> list`: query past sessions
  - `save_failure_pattern(failure_type, strategy)`: update `failure_patterns.json`
  - `get_failure_pattern(failure_type) -> str|None`: lookup successful strategy for failure type
  - `build_context(task) -> str`: assemble relevant context fragments (project info + relevant failure patterns)
- SQLite schema: `sessions(id, test_path, success, rounds, created_at, reason)`, `actions(id, session_id, round, action_type, action_params, result)`

**Verification (TDD):**
1. Write `tests/test_memory_store.py` — 6 tests: scan project (mock directory), save and get session, save and get failure pattern, build context includes project info, build context includes relevant failure pattern, empty store returns minimal context
2. Run → FAIL
3. Implement `store.py` using `sqlite3` and `json`
4. Run → PASS (6 tests)
5. Commit: `feat: add memory store with SQLite session history and failure patterns`

---

## Task 11: Agent Main Loop

**Goal:** Implement the agent main loop that orchestrates all components. This is the harness kernel.

**Depends on:** Tasks 3, 4, 5, 6, 7, 8, 9, 10

**Files:**
- Create: `the_harness/agent_loop.py`
- Test: `tests/test_agent_loop.py`

**Implementation points:**
- `AgentLoop(config, llm_provider, guardrail, tool_dispatcher, validator, classifier, injector, memory_store)`
- `run(task) -> Result`:
  1. `context = memory.build_context(task)`
  2. Loop `max_rounds` times:
     a. `response = llm.complete(context)` — call LLM
     b. `action = parse_action(response)` — parse JSON to Action
     c. If `action.type == GIVE_UP` → stop (reason="LLM gave up")
     d. `gr = guardrail.check(action)` — guardrail check
     e. If `gr.blocked` → HITL approval; if rejected → append "rejected" to context, continue
     f. `result = tool_dispatcher.execute(action)` — execute
     g. `test_result = validator.validate(task.test_path)` — run tests
     h. `feedback = classifier.classify(test_result)` — classify
     i. If `feedback.type == PASS` → stop (success=True)
     j. If `is_repeated(action, history)` → stop (reason="stuck in loop")
     k. `injection = injector.inject(feedback)` — generate feedback prompt
     l. `context.append(injection)` — inject feedback
     m. `memory.update(task, action, feedback)` — update memory
  3. If loop exhausted → stop (reason="max rounds exceeded")
- `parse_action(response)`: parse JSON `{"action", "params", "reasoning"}` → Action object; on parse failure, append "please return valid JSON" to context
- `is_repeated(action, history)`: check if last 2 actions are identical

**Verification (TDD):**
1. Write `tests/test_agent_loop.py` — 6 tests using MockLLMProvider:
   - `test_success_in_2_rounds`: mock returns edit_file then run_tests, validator returns pass on 2nd → success
   - `test_give_up`: mock returns give_up → stops with reason
   - `test_max_rounds_exceeded`: mock returns non-fixing actions 5 times → stops
   - `test_repeated_action`: mock returns identical edit_file twice → stops with "stuck"
   - `test_guardrail_blocks`: mock returns rm -rf → guardrail blocks → next action safe
   - `test_feedback_drives_correction`: mock returns bad edit (compile_error) then good edit → success
2. Run → FAIL
3. Implement `agent_loop.py`
4. Run → PASS (6 tests)
5. Commit: `feat: add agent main loop with 5 stopping conditions`

---

## Task 12: WebUI

**Goal:** Implement FastAPI WebUI with terminal-style streaming output and session history sidebar.

**Depends on:** Task 11

**Files:**
- Create: `the_harness/webui/__init__.py`, `the_harness/webui/app.py`
- Create: `the_harness/webui/static/index.html`, `the_harness/webui/static/style.css`, `the_harness/webui/static/app.js`
- Test: `tests/test_webui.py`

**Implementation points:**
- `app.py`: FastAPI with WebSocket endpoint `/ws/fix` and REST endpoints
  - `POST /api/fix` — start fix task (test_path, workspace) → returns session_id
  - `WS /ws/fix/{session_id}` — stream agent output events in real-time
  - `GET /api/sessions` — list past sessions
  - `GET /api/sessions/{id}` — get session detail
  - Static file serving for `index.html`
- `index.html`: left sidebar (session history list), right main area (terminal-style streaming output), bottom input bar (test path input + start button)
- `app.js`: WebSocket client, render streaming events as terminal output, fetch session history
- Events: `{"type": "action", "data": {...}}`, `{"type": "feedback", "data": {...}}`, `{"type": "result", "data": {...}}`

**Verification (TDD):**
1. Write `tests/test_webui.py` — 5 tests using FastAPI TestClient:
   - `test_post_fix_returns_session_id`: POST /api/fix returns session_id
   - `test_get_sessions_returns_list`: GET /api/sessions returns list
   - `test_websocket_connect`: WS connection establishes
   - `test_websocket_receives_events`: WS receives action/feedback/result events (using mock LLM)
   - `test_static_index_served`: GET / returns HTML
2. Run → FAIL
3. Implement `app.py` + frontend files
4. Run → PASS (5 tests)
5. Commit: `feat: add WebUI with terminal streaming and session history`

---

## Task 13: Mechanism Demo Script

**Goal:** Create `demo.py` that deterministically reproduces 3 mechanism behaviors under mock LLM (§A.6 requirement).

**Depends on:** Task 11

**Files:**
- Create: `demo.py`
- Test: `tests/test_demo.py`

**Implementation points:**
- `demo.py` runs 3 demonstrations, all using MockLLMProvider (no network/real LLM):
  1. **Guardrail intercepts dangerous action**: MockLLM returns `run_shell("rm -rf /")` → guardrail blocks → next mock action is safe → verify blocked=True then safe execution
  2. **Feedback loop drives self-correction**: MockLLM returns edit_file (introduces syntax error) → validator returns compile_error → injector generates feedback → 2nd mock action fixes → validator returns pass → verify 2 rounds, success=True
  3. **Failure classification + strategy routing**: Construct 4 different TestResults → classifier produces 4 different types → injector produces 4 different strategy hints → verify each path
- Output: print each demonstration's result with assertion checks
- Exit code 0 if all demonstrations pass

**Verification (TDD):**
1. Write `tests/test_demo.py` — 3 tests: demo_guardrail_interception, demo_feedback_self_correction, demo_failure_classification_routing
2. Run → FAIL
3. Implement `demo.py`
4. Run `python demo.py` → all 3 demos pass; `pytest tests/test_demo.py -v` → PASS
5. Commit: `feat: add mechanism demo script with 3 deterministic demonstrations`

---

## Task 14: Docker + CI/CD

**Goal:** Create Dockerfile, GitHub Actions CI config, and deployment setup.

**Depends on:** All previous tasks

**Files:**
- Create: `Dockerfile`
- Create: `.github/workflows/ci.yml`
- Create: `Makefile`
- Modify: `README.md` (ensure distribution instructions are complete)

**Implementation points:**
- `Dockerfile`:
  - Base: `python:3.12-slim`
  - Install dependencies: `pip install -e .`
  - Expose port 8000
  - CMD: `uvicorn the_harness.webui:app --host 0.0.0.0 --port 8000`
- `.github/workflows/ci.yml`:
  - Job `unit-test` (required name per §五.6): checkout → setup Python 3.12 → pip install -e .[dev] → pytest
  - Job `docker-build` (depends on unit-test): docker build → docker push (on main)
- `Makefile`: `test: pytest`, `run: uvicorn ...`, `docker-build: docker build ...`, `demo: python demo.py`

**Verification:**
1. Run `make test` → all tests pass
2. Run `docker build -t the-harness .` → image builds successfully
3. Run `docker run -p 8000:8000 the-harness` → server starts, WebUI accessible at localhost:8000
4. Push to GitHub → CI `unit-test` job passes
5. Commit: `feat: add Dockerfile, CI config, and Makefile`

---

## Summary

| Task | Module | Tests | Depends on | Parallelizable |
|------|--------|-------|------------|----------------|
| 1 | Scaffolding | 2 | — | — |
| 2 | Data Models | 7 | 1 | — |
| 3 | LLM Abstraction | 3 | 2 | Yes (with 4,5,6,7,10) |
| 4 | Credential Manager | 6 | 2 | Yes (with 3,5,6,7,10) |
| 5 | Guardrail | 12 | 2 | Yes (with 3,4,6,7,10) |
| 6 | Tool Dispatcher | 8 | 2 | Yes (with 3,4,5,7,10) |
| 7 | Test Validator | 4 | 2 | Yes (with 3,4,5,6,10) |
| 8 | Failure Classifier | 9 | 7 | — |
| 9 | Feedback Injector | 6 | 8 | — |
| 10 | Memory Store | 6 | 2 | Yes (with 3,4,5,6,7) |
| 11 | Agent Main Loop | 6 | 3,4,5,6,7,8,9,10 | — |
| 12 | WebUI | 5 | 11 | Yes (with 13) |
| 13 | Demo Script | 3 | 11 | Yes (with 12) |
| 14 | Docker + CI | — | All | — |

**Total: 14 tasks, 77 tests**

---

## PLAN.md Update Protocol

Per §4.7: "PLAN.md 持续更新：每完成一个 task 即标记完成并附 commit hash"

After completing each task, update the corresponding task entry:

```markdown
## Task N: [Name] ✅
**Completed:** 2026-07-XX
**Commit:** `abc1234`
**Notes:** [any deviations or learnings]
```

