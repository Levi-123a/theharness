"""Tests for AgentLoop — the harness kernel that orchestrates all components."""

from the_harness.agent_loop import AgentLoop
from the_harness.config import Config
from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.guardrail.guardrail import Guardrail
from the_harness.llm.mock_provider import MockLLMProvider
from the_harness.memory.store import MemoryStore
from the_harness.models import TestResult, Task
from the_harness.tools.dispatcher import ToolDispatcher


class MockValidator:
    """Mock validator that returns preset TestResults sequentially."""
    __test__ = False

    def __init__(self, results):
        self._results = results
        self._index = 0

    def validate(self, test_path):
        if self._index >= len(self._results):
            return self._results[-1]
        r = self._results[self._index]
        self._index += 1
        return r


def _make_loop(tmp_path, llm_actions, validator_results, max_rounds=5):
    """Helper to create an AgentLoop with mock components."""
    config = Config(max_rounds=max_rounds, workspace=str(tmp_path))
    return AgentLoop(
        config=config,
        llm_provider=MockLLMProvider(llm_actions),
        guardrail=Guardrail(str(tmp_path)),
        tool_dispatcher=ToolDispatcher(str(tmp_path)),
        validator=MockValidator(validator_results),
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(str(tmp_path)),
    )


def test_success_in_2_rounds(tmp_path):
    """Agent succeeds in 2 rounds: first action fails, second passes."""
    actions = [
        {"action": "write_file", "params": {"file_path": "a.py", "content": "x=1"}, "reasoning": "create"},
        {"action": "write_file", "params": {"file_path": "b.py", "content": "y=2"}, "reasoning": "fix"},
    ]
    results = [
        TestResult(exit_code=1, stdout="1 failed", stderr="err", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True
    assert result.rounds == 2


def test_session_summary_generated_and_saved(tmp_path):
    """AgentLoop should generate an AI summary and store it in the session.

    The summary is displayed in the sidebar session list so users can
    tell sessions apart at a glance, instead of seeing just '#5'.
    """
    actions = [
        {"action": "write_file", "params": {"file_path": "a.py", "content": "x=1"}, "reasoning": "创建初始文件"},
        {"action": "write_file", "params": {"file_path": "b.py", "content": "y=2"}, "reasoning": "修复变量赋值"},
    ]
    results = [
        TestResult(exit_code=1, stdout="1 failed", stderr="err", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results)
    loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))

    sessions = loop._memory.get_sessions()
    assert len(sessions) == 1
    assert sessions[0]["summary"] != ""
    # The mock provider's summarize_session uses the last action's reasoning
    assert "修复变量赋值" in sessions[0]["summary"]


def test_freeform_saves_description_and_final_reply(tmp_path):
    """run_freeform() should save the user's description and AI's final reply.

    Bug: when the LLM returns 'done', its reasoning (the AI's actual reply
    text) was NOT saved — only actions that were *executed* get saved.
    So freeform sessions with immediate 'done' had empty actions and no
    AI reply text, making the session detail page show nothing useful.
    """
    actions = [
        {"action": "done", "params": {}, "reasoning": "这是一个Python测试代理项目，用于自动修复失败的测试用例。"},
    ]
    loop = _make_loop(tmp_path, actions, [])
    task = Task(
        test_path="",
        workspace=str(tmp_path),
        description="请读取 README.md 并总结项目用途",
    )
    loop.run_freeform(task)

    sessions = loop._memory.get_sessions()
    assert len(sessions) == 1
    # User's original message must be saved
    assert sessions[0]["description"] == "请读取 README.md 并总结项目用途"
    # AI's final reply text must be saved
    assert sessions[0]["final_reply"] == "这是一个Python测试代理项目，用于自动修复失败的测试用例。"

    # get_session (detail view) must also include these
    detail = loop._memory.get_session(sessions[0]["id"])
    assert detail["description"] == "请读取 README.md 并总结项目用途"
    assert detail["final_reply"] == "这是一个Python测试代理项目，用于自动修复失败的测试用例。"


def test_freeform_with_history_continues_conversation(tmp_path):
    """run_freeform() should include conversation history in LLM context.

    When the user sends a follow-up message, the previous Q&A pairs are
    passed as 'history' so the LLM has conversation context.
    """
    # The mock provider records the messages it receives
    actions = [
        {"action": "done", "params": {}, "reasoning": "好的，我知道了。"},
    ]
    loop = _make_loop(tmp_path, actions, [])

    history = [
        {"role": "user", "content": "项目用什么语言？"},
        {"role": "assistant", "content": "项目使用 Python。"},
    ]
    task = Task(
        test_path="",
        workspace=str(tmp_path),
        description="那它的测试框架是什么？",
    )
    loop.run_freeform(task, history=history)

    # Verify the session was saved with the user's follow-up question
    sessions = loop._memory.get_sessions()
    assert len(sessions) == 1
    assert sessions[0]["description"] == "那它的测试框架是什么？"
    assert sessions[0]["final_reply"] == "好的，我知道了。"


def test_give_up(tmp_path):
    """Agent stops when LLM returns give_up action."""
    actions = [{"action": "give_up", "params": {}, "reasoning": "can't fix"}]
    results = [TestResult(exit_code=1, stdout="fail", stderr="", passed=False)]
    loop = _make_loop(tmp_path, actions, results)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is False
    assert "gave up" in result.reason.lower()


def test_max_rounds_exceeded(tmp_path):
    """Agent stops after max_rounds without success."""
    actions = [
        {"action": "write_file", "params": {"file_path": f"f{i}.py", "content": str(i)}, "reasoning": f"attempt {i}"}
        for i in range(6)
    ]
    results = [TestResult(exit_code=1, stdout="fail", stderr="", passed=False)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=3)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is False
    assert "max rounds" in result.reason.lower()


def test_repeated_action(tmp_path):
    """Agent stops when it repeats the same action twice."""
    action_dict = {"action": "write_file", "params": {"file_path": "same.py", "content": "x=1"}, "reasoning": "same"}
    actions = [action_dict, action_dict]
    results = [TestResult(exit_code=1, stdout="fail", stderr="", passed=False)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=5)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is False
    assert "stuck" in result.reason.lower() or "repeated" in result.reason.lower()


def test_guardrail_blocks(tmp_path):
    """Guardrail blocks dangerous action, agent continues with safe action."""
    actions = [
        {"action": "run_shell", "params": {"command": "rm -rf /"}, "reasoning": "dangerous"},
        {"action": "write_file", "params": {"file_path": "safe.py", "content": "x=1"}, "reasoning": "safe"},
    ]
    results = [
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results, max_rounds=5)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True


def test_feedback_drives_correction(tmp_path):
    """Feedback loop: first action causes compile error, second fixes it."""
    actions = [
        {"action": "write_file", "params": {"file_path": "bad.py", "content": "def (:"}, "reasoning": "bad edit"},
        {"action": "write_file", "params": {"file_path": "good.py", "content": "x = 1"}, "reasoning": "good edit"},
    ]
    results = [
        TestResult(exit_code=1, stdout="SyntaxError: invalid syntax", stderr="", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results, max_rounds=5)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True
    assert result.rounds == 2


# ── Bug1: 非生产性迭代不应消耗轮数 ────────────────────────────


def test_parse_error_does_not_consume_round(tmp_path):
    """A parse error should not count against max_rounds.

    Bug: with max_rounds=1, if the LLM first returns an invalid action
    (parse error) and then a valid passing action, the task should
    succeed because the parse error is a retry, not a consumed round.
    """
    actions = [
        {"action": "invalid_action", "params": {}, "reasoning": "typo"},
        {"action": "write_file", "params": {"file_path": "a.py", "content": "x=1"}, "reasoning": "fix"},
    ]
    results = [TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=1)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True


def test_execution_failure_does_not_consume_round(tmp_path):
    """An execution failure should not count against max_rounds.

    Bug: with max_rounds=1, if the first action fails to execute (e.g.
    editing a nonexistent file) and the second action succeeds and passes,
    the task should succeed because the failed execution is a retry.
    """
    actions = [
        {"action": "edit_file", "params": {"file_path": "nonexistent.py", "old_text": "x", "new_text": "y"}, "reasoning": "edit missing file"},
        {"action": "write_file", "params": {"file_path": "good.py", "content": "x=1"}, "reasoning": "create file"},
    ]
    results = [TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=1)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True


def test_guardrail_block_does_not_consume_round(tmp_path):
    """A guardrail-blocked action should not count against max_rounds.

    Bug: with max_rounds=1, if the first action is blocked by guardrail
    (e.g. rm -rf /) and the second action is safe and passes, the task
    should succeed because the blocked action is a retry.
    """
    actions = [
        {"action": "run_shell", "params": {"command": "rm -rf /"}, "reasoning": "dangerous"},
        {"action": "write_file", "params": {"file_path": "safe.py", "content": "x=1"}, "reasoning": "safe"},
    ]
    results = [TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True)]
    loop = _make_loop(tmp_path, actions, results, max_rounds=1)
    result = loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))
    assert result.success is True


def test_freeform_parse_error_does_not_consume_round(tmp_path):
    """In freeform mode, a parse error should not count against max_rounds."""
    actions = [
        {"action": "invalid_action", "params": {}, "reasoning": "typo"},
        {"action": "done", "params": {}, "reasoning": "done"},
    ]
    loop = _make_loop(tmp_path, actions, [], max_rounds=1)
    task = Task(test_path="", workspace=str(tmp_path), description="test")
    result = loop.run_freeform(task)
    assert result.success is True


def test_freeform_execution_failure_does_not_consume_round(tmp_path):
    """In freeform mode, an execution failure should not count against max_rounds."""
    actions = [
        {"action": "read_file", "params": {"file_path": "nonexistent.py"}, "reasoning": "read missing"},
        {"action": "done", "params": {}, "reasoning": "done"},
    ]
    loop = _make_loop(tmp_path, actions, [], max_rounds=1)
    task = Task(test_path="", workspace=str(tmp_path), description="test")
    result = loop.run_freeform(task)
    assert result.success is True


# ── Bug3 后端: actions 应保存执行结果 ────────────────────────


def test_session_actions_include_execution_results(tmp_path):
    """Saved session actions should include execution output for each action.

    Bug: when viewing a past session, action results (execution output)
    were not saved — only action type/params/reasoning. So old sessions
    showed action names but no results, making it impossible to see what
    actually happened in each round.
    """
    actions = [
        {"action": "write_file", "params": {"file_path": "a.py", "content": "x=1"}, "reasoning": "create"},
        {"action": "write_file", "params": {"file_path": "b.py", "content": "y=2"}, "reasoning": "fix"},
    ]
    results = [
        TestResult(exit_code=1, stdout="1 failed", stderr="err", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]
    loop = _make_loop(tmp_path, actions, results)
    loop.run(Task(test_path="tests/test_foo.py", workspace=str(tmp_path)))

    sessions = loop._memory.get_sessions()
    assert len(sessions) == 1
    detail = loop._memory.get_session(sessions[0]["id"])
    assert len(detail["actions"]) == 2
    # Each action should have a non-empty result (execution output)
    assert detail["actions"][0]["result"] != ""
    assert detail["actions"][1]["result"] != ""


# ── Bug4: 同会话多次提问应归并到一个会话 ────────────────────


def test_freeform_with_session_id_appends_to_existing(tmp_path):
    """run_freeform with session_id should append to existing session.

    Bug: each follow-up question in a freeform conversation created a new
    session, cluttering the sidebar. With session_id, follow-up actions
    are appended to the original session.
    """
    # First question creates a session
    actions1 = [{"action": "done", "params": {}, "reasoning": "第一个回答"}]
    loop1 = _make_loop(tmp_path, actions1, [])
    task1 = Task(test_path="", workspace=str(tmp_path), description="第一个问题")
    loop1.run_freeform(task1)

    sessions = loop1._memory.get_sessions()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]

    # Second question should append to the same session
    actions2 = [{"action": "done", "params": {}, "reasoning": "第二个回答"}]
    loop2 = _make_loop(tmp_path, actions2, [])
    task2 = Task(test_path="", workspace=str(tmp_path), description="第二个问题")
    loop2.run_freeform(task2, session_id=session_id)

    sessions = loop2._memory.get_sessions()
    assert len(sessions) == 1  # still only 1 session!
    detail = loop2._memory.get_session(session_id)
    assert len(detail["actions"]) == 2
    # final_reply should be updated to the latest
    assert detail["final_reply"] == "第二个回答"


# ── Bug5: done action 的 result 不应重复 reasoning ────────────────


def test_freeform_done_action_result_not_duplicate_reasoning(tmp_path):
    """done action 的 result 字段不应等于 reasoning。

    Bug: run_freeform 中 done action 的 action_results 存了 action.reasoning，
    导致 _save_session 中 result = reasoning。前端 loadSessionDetail 同时显示
    headline（reasoning）和 detail（result），造成回复在大框和小框各显示一次。

    Fix: done/give_up action 的 result 应为空或简短状态，不应等于 reasoning。
    """
    actions = [
        {"action": "done", "params": {}, "reasoning": "你好！我是编程助手。"},
    ]
    loop = _make_loop(tmp_path, actions, [])
    task = Task(test_path="", workspace=str(tmp_path), description="介绍自己")
    loop.run_freeform(task)

    sessions = loop._memory.get_sessions()
    detail = loop._memory.get_session(sessions[0]["id"])
    done_action = detail["actions"][0]
    # result should NOT duplicate reasoning
    assert done_action["reasoning"] == "你好！我是编程助手。"
    assert done_action["result"] != done_action["reasoning"], (
        f"result should not duplicate reasoning, got result={done_action['result']!r}"
    )


# ── Bug6: 会话详情应返回 query_index 以正确交替显示问答 ──────────


def test_get_session_returns_query_index_for_interleaving(tmp_path):
    """get_session 应返回每个 action 的 query_index，使前端能按提问顺序交替显示。

    Bug: description 存所有提问（Q1\\nQ2\\nQ3），actions 按全局 round 编号。
    loadSessionDetail 先渲染所有用户消息再渲染所有 actions，导致语序变成
    Q1 Q2 Q3 A1 A2 A3 而非正确的 Q1 A1 Q2 A2 Q3 A3。

    Fix: actions 表新增 query_index 列，第一次提问的 actions query_index=0，
    追加提问的 actions query_index 递增。前端据此交替渲染。
    """
    # First question creates a session
    actions1 = [{"action": "done", "params": {}, "reasoning": "第一个回答"}]
    loop1 = _make_loop(tmp_path, actions1, [])
    task1 = Task(test_path="", workspace=str(tmp_path), description="第一个问题")
    loop1.run_freeform(task1)

    sessions = loop1._memory.get_sessions()
    session_id = sessions[0]["id"]

    # Second question appends to the same session
    actions2 = [{"action": "done", "params": {}, "reasoning": "第二个回答"}]
    loop2 = _make_loop(tmp_path, actions2, [])
    task2 = Task(test_path="", workspace=str(tmp_path), description="第二个问题")
    loop2.run_freeform(task2, session_id=session_id)

    detail = loop2._memory.get_session(session_id)
    assert len(detail["actions"]) == 2
    # Each action must have a query_index field
    assert "query_index" in detail["actions"][0], "actions must have query_index field"
    # First query's actions should have query_index = 0
    assert detail["actions"][0]["query_index"] == 0
    # Second query's actions should have query_index = 1
    assert detail["actions"][1]["query_index"] == 1
