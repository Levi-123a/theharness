"""Tests for WebUI -- FastAPI with WebSocket streaming and session history."""

from fastapi.testclient import TestClient

from the_harness.webui.app import app
from the_harness.models import TestResult


class _MockValidator:
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


def _install_mock_factory(tmp_path):
    """Override the agent-loop factory to use mock components.

    Returns the original factory for restoration.
    """
    import importlib

    webui_mod = importlib.import_module("the_harness.webui.app")
    original = webui_mod._agent_loop_factory

    actions = [
        {"action": "write_file", "params": {"file_path": "a.py", "content": "x=1"}, "reasoning": "create"},
        {"action": "write_file", "params": {"file_path": "b.py", "content": "y=2"}, "reasoning": "fix"},
    ]
    results = [
        TestResult(exit_code=1, stdout="1 failed", stderr="err", passed=False),
        TestResult(exit_code=0, stdout="1 passed", stderr="", passed=True),
    ]

    def mock_factory(workspace, event_queue=None):
        from the_harness.agent_loop import AgentLoop
        from the_harness.config import Config
        from the_harness.feedback.classifier import FailureClassifier
        from the_harness.feedback.injector import FeedbackInjector
        from the_harness.guardrail.guardrail import Guardrail
        from the_harness.llm.mock_provider import MockLLMProvider
        from the_harness.memory.store import MemoryStore
        from the_harness.tools.dispatcher import ToolDispatcher
        from the_harness.webui.app import _EmittingLLM, _EmittingValidator

        llm = MockLLMProvider(actions)
        validator = _MockValidator(results)

        if event_queue is not None:
            llm = _EmittingLLM(llm, event_queue)
            validator = _EmittingValidator(validator, event_queue)

        return AgentLoop(
            config=Config(max_rounds=5, workspace=workspace),
            llm_provider=llm,
            guardrail=Guardrail(workspace),
            tool_dispatcher=ToolDispatcher(workspace),
            validator=validator,
            classifier=FailureClassifier(),
            injector=FeedbackInjector(),
            memory_store=MemoryStore(workspace),
        )

    webui_mod._agent_loop_factory = mock_factory
    return original


def _restore_factory(original):
    import importlib

    webui_mod = importlib.import_module("the_harness.webui.app")
    webui_mod._agent_loop_factory = original


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


def test_post_fix_returns_session_id(tmp_path):
    """POST /api/fix returns a session_id."""
    original = _install_mock_factory(tmp_path)
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/fix",
            json={"test_path": "tests/test_foo.py", "workspace": str(tmp_path)},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert isinstance(data["session_id"], str)
    finally:
        _restore_factory(original)


def test_get_sessions_returns_list(tmp_path):
    """GET /api/sessions returns a list."""
    client = TestClient(app)
    resp = client.get("/api/sessions", params={"workspace": str(tmp_path)})
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_websocket_connect(tmp_path):
    """WebSocket connection establishes."""
    original = _install_mock_factory(tmp_path)
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/fix",
            json={"test_path": "tests/test_foo.py", "workspace": str(tmp_path)},
        )
        session_id = resp.json()["session_id"]

        with client.websocket_connect(f"/ws/fix/{session_id}") as ws:
            # Just verify the connection is open by receiving at least one event
            msg = ws.receive_json()
            assert "type" in msg
    finally:
        _restore_factory(original)


def test_websocket_receives_events(tmp_path):
    """WebSocket receives action/feedback/result events (using mock LLM)."""
    original = _install_mock_factory(tmp_path)
    try:
        client = TestClient(app)
        resp = client.post(
            "/api/fix",
            json={"test_path": "tests/test_foo.py", "workspace": str(tmp_path)},
        )
        session_id = resp.json()["session_id"]

        events = []
        with client.websocket_connect(f"/ws/fix/{session_id}") as ws:
            while True:
                msg = ws.receive_json()
                events.append(msg)
                if msg.get("type") == "result":
                    break

        types = [e["type"] for e in events]
        assert "action" in types
        assert "feedback" in types
        assert "result" in types
        result_event = [e for e in events if e["type"] == "result"][0]
        assert result_event["data"]["success"] is True
    finally:
        _restore_factory(original)


def test_static_index_served():
    """GET / returns HTML."""
    client = TestClient(app)
    resp = client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers.get("content-type", "")
    assert "<html" in resp.text.lower()
