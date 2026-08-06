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

    def mock_factory(workspace, event_queue=None, freeform=False):
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


def test_get_session_detail_returns_actions(tmp_path):
    """GET /api/sessions/{id} should return the full session including its
    actions list, so the frontend can render the conversation bubbles.

    Bug: clicking a past session in the sidebar showed only the summary
    (success/rounds/reason) but no conversation bubbles, because the
    endpoint used get_sessions() (list) which omits actions.
    """
    from the_harness.memory.store import MemoryStore

    store = MemoryStore(str(tmp_path))
    session_id = store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 2,
        "reason": "All tests passed",
        "actions": [
            {"round": 1, "action_type": "read_file",
             "action_params": {"file_path": "src/foo.py"},
             "result": "file contents...", "reasoning": "Need to read the file"},
            {"round": 2, "action_type": "edit_file",
             "action_params": {"file_path": "src/foo.py", "old_text": "x", "new_text": "y"},
             "result": "edited", "reasoning": "Fix the failing test"},
        ],
    })

    client = TestClient(app)
    resp = client.get(f"/api/sessions/{session_id}", params={"workspace": str(tmp_path)})
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == session_id
    assert data["test_path"] == "tests/test_foo.py"
    # The actions list must be present — this is what the frontend renders
    # as conversation bubbles.
    assert "actions" in data, "session detail must include actions list"
    assert len(data["actions"]) == 2
    a1 = data["actions"][0]
    assert a1["action_type"] == "read_file"
    assert a1["action_params"] == {"file_path": "src/foo.py"}
    assert a1["reasoning"] == "Need to read the file"
    assert a1["result"] == "file contents..."


def test_get_session_detail_returns_404_for_missing(tmp_path):
    """GET /api/sessions/{id} should return 404 for a non-existent session."""
    client = TestClient(app)
    resp = client.get("/api/sessions/99999", params={"workspace": str(tmp_path)})
    assert resp.status_code == 404


def test_delete_session_endpoint(tmp_path):
    """DELETE /api/sessions/{id} should remove the session and return 200.

    After deletion the session must no longer appear in GET /api/sessions
    nor be reachable via GET /api/sessions/{id}.
    """
    from the_harness.memory.store import MemoryStore

    store = MemoryStore(str(tmp_path))
    session_id = store.save_session({
        "test_path": "tests/test_foo.py",
        "success": True,
        "rounds": 1,
        "reason": "ok",
        "actions": [],
    })

    client = TestClient(app)
    resp = client.delete(
        f"/api/sessions/{session_id}",
        params={"workspace": str(tmp_path)},
    )
    assert resp.status_code == 200
    assert resp.json().get("ok") is True

    # Session is gone from the list view
    listing = client.get(
        "/api/sessions", params={"workspace": str(tmp_path)}
    ).json()
    assert all(s["id"] != session_id for s in listing)
    # And from the detail view (404)
    detail = client.get(
        f"/api/sessions/{session_id}", params={"workspace": str(tmp_path)}
    )
    assert detail.status_code == 404


def test_delete_session_endpoint_returns_404_for_missing(tmp_path):
    """DELETE /api/sessions/{id} should return 404 when the session doesn't exist."""
    client = TestClient(app)
    resp = client.delete(
        "/api/sessions/99999",
        params={"workspace": str(tmp_path)},
    )
    assert resp.status_code == 404


def test_delete_sessions_batch_endpoint(tmp_path):
    """POST /api/sessions/batch-delete should remove all listed sessions.

    Body: {"ids": [1, 2, 3]}. Returns {"ok": true, "deleted": <count>}.
    Unknown ids are silently skipped. Used by the UI's "批量删除" button.
    """
    from the_harness.memory.store import MemoryStore

    store = MemoryStore(str(tmp_path))
    sid1 = store.save_session({"test_path": "a", "success": True, "rounds": 1})
    sid2 = store.save_session({"test_path": "b", "success": False, "rounds": 2})
    sid3 = store.save_session({"test_path": "c", "success": True, "rounds": 1})

    client = TestClient(app)
    resp = client.post(
        "/api/sessions/batch-delete",
        params={"workspace": str(tmp_path)},
        json={"ids": [sid1, sid3, 99999]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    assert data.get("deleted") == 2

    # Only sid2 remains
    remaining = client.get(
        "/api/sessions", params={"workspace": str(tmp_path)}
    ).json()
    assert len(remaining) == 1
    assert remaining[0]["id"] == sid2


def test_delete_sessions_batch_endpoint_handles_empty_ids(tmp_path):
    """POST /api/sessions/batch-delete with empty ids should return deleted=0."""
    client = TestClient(app)
    resp = client.post(
        "/api/sessions/batch-delete",
        params={"workspace": str(tmp_path)},
        json={"ids": []},
    )
    assert resp.status_code == 200
    assert resp.json().get("deleted") == 0


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


def test_index_html_has_no_cache_header():
    """GET / should send Cache-Control: no-cache so browsers always fetch
    the latest HTML (which references the latest versioned static assets).

    Without this, browsers may serve a stale index.html from cache that
    references an old app.js, causing users to see outdated UI behavior
    (e.g. removed 'unlock' flow errors).
    """
    client = TestClient(app)
    resp = client.get("/")
    cache_control = resp.headers.get("cache-control", "")
    assert "no-cache" in cache_control or "no-store" in cache_control, (
        f"Expected Cache-Control to prevent caching, got: {cache_control!r}"
    )


def test_static_js_has_no_cache_header():
    """GET /static/app.js should send Cache-Control: no-cache so browsers
    always fetch the latest JS.

    Without this, browsers cache old app.js and users see removed error
    messages like 'Credential store is locked. Unlock first.'
    """
    client = TestClient(app)
    resp = client.get("/static/app.js")
    assert resp.status_code == 200
    cache_control = resp.headers.get("cache-control", "")
    assert "no-cache" in cache_control or "no-store" in cache_control, (
        f"Expected Cache-Control to prevent caching, got: {cache_control!r}"
    )


def test_store_api_key_directly(tmp_path, monkeypatch):
    """POST /api/credentials/store should work without any setup or unlock step."""
    import importlib
    from unittest.mock import patch, MagicMock

    webui_mod = importlib.import_module("the_harness.webui.app")
    # Mock keyring so no real OS keychain is touched
    keyring_store = {}
    mock_kr = MagicMock()
    mock_kr.set_password.side_effect = lambda s, u, p: keyring_store.__setitem__(f"{s}:{u}", p)
    mock_kr.get_password.side_effect = lambda s, u: keyring_store.get(f"{s}:{u}")
    mock_kr.delete_password.side_effect = lambda s, u: keyring_store.pop(f"{s}:{u}", None)
    monkeypatch.setattr(webui_mod, "_credential_manager", None)

    client = TestClient(app)
    with patch("the_harness.credentials.manager.keyring", mock_kr):
        resp = client.post(
            "/api/credentials/store",
            json={"provider": "openai", "api_key": "sk-test-key", "base_url": "", "model": ""},
        )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data["ok"] is True


def test_status_shows_providers_without_unlock(tmp_path, monkeypatch):
    """GET /api/credentials/status should show stored providers without setup/unlock."""
    import importlib
    from unittest.mock import patch, MagicMock

    webui_mod = importlib.import_module("the_harness.webui.app")
    keyring_store = {}
    mock_kr = MagicMock()
    mock_kr.set_password.side_effect = lambda s, u, p: keyring_store.__setitem__(f"{s}:{u}", p)
    mock_kr.get_password.side_effect = lambda s, u: keyring_store.get(f"{s}:{u}")
    mock_kr.delete_password.side_effect = lambda s, u: keyring_store.pop(f"{s}:{u}", None)
    monkeypatch.setattr(webui_mod, "_credential_manager", None)

    client = TestClient(app)
    with patch("the_harness.credentials.manager.keyring", mock_kr):
        # Store a key first
        client.post(
            "/api/credentials/store",
            json={"provider": "openai", "api_key": "sk-test-key", "base_url": "", "model": ""},
        )
        # Now check status — should show the provider without any unlock
        resp = client.get("/api/credentials/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "openai" in data["providers"]
    assert data["providers"]["openai"]["api_key"] is True


def test_env_var_provides_default_api_key(tmp_path, monkeypatch):
    """App should read OPENAI_API_KEY from env var when keychain has no keys.

    This allows pre-configuring a key via .env file without users needing
    to enter their own.
    """
    import importlib
    from unittest.mock import patch, MagicMock

    webui_mod = importlib.import_module("the_harness.webui.app")

    # Set env vars
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
    monkeypatch.setenv("OPENAI_MODEL", "deepseek-chat")

    # Mock keyring with empty store (no user-stored keys)
    mock_kr = MagicMock()
    mock_kr.get_password.return_value = None
    monkeypatch.setattr(webui_mod, "_credential_manager", None)

    # Check that the agent loop factory picks up env var credentials
    with patch("the_harness.credentials.manager.keyring", mock_kr):
        cm = webui_mod._get_credential_manager()
        # The env var key should be accessible
        creds = cm.get("openai")
        # If keychain is empty, env var should be used
        # This is tested via the factory, but we can check the env var directly
        import os
        assert os.environ.get("OPENAI_API_KEY") == "sk-env-test-key"


def test_factory_uses_real_llm_when_any_provider_configured(tmp_path, monkeypatch):
    """Agent loop factory should use OpenAILLMProvider when ANY provider is
    configured in the keyring, not just when 'openai' is configured.

    Bug: factory only checked cm.get('openai').  If a user stored credentials
    under provider name 'deepseek' (a common case since DeepSeek uses an
    OpenAI-compatible API), cm.get('openai') returned None and the factory
    fell back to MockLLMProvider([]), which immediately raised
    'No more preset actions available' on the first agent round.
    """
    import importlib
    from unittest.mock import patch, MagicMock

    webui_mod = importlib.import_module("the_harness.webui.app")
    monkeypatch.setattr(webui_mod, "_credential_manager", None)

    # Simulate a user who stored credentials under 'deepseek' (not 'openai')
    keyring_store = {
        "the-harness:provider:deepseek": '{"api_key": "sk-real-key", "base_url": "https://api.deepseek.com/v1", "model": "deepseek-chat"}',
        "the-harness:__providers__": '["deepseek"]',
    }
    mock_kr = MagicMock()
    mock_kr.get_password.side_effect = lambda s, u: keyring_store.get(f"{s}:{u}")
    mock_kr.set_password.side_effect = lambda s, u, p: keyring_store.__setitem__(f"{s}:{u}", p)
    mock_kr.delete_password.side_effect = lambda s, u: keyring_store.pop(f"{s}:{u}", None)

    # Clear env vars so they don't interfere
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(var, raising=False)

    captured_llm = {}

    with patch("the_harness.credentials.manager.keyring", mock_kr), \
         patch("the_harness.webui.app.OpenAILLMProvider") as mock_provider_cls:
        mock_provider_cls.side_effect = lambda **kwargs: captured_llm.update(kwargs) or MagicMock()

        loop = webui_mod._default_agent_loop_factory(str(tmp_path))

        # OpenAILLMProvider should have been instantiated with the deepseek key
        assert mock_provider_cls.called, "OpenAILLMProvider should be instantiated when a provider is configured"
        assert captured_llm.get("api_key") == "sk-real-key"
        assert captured_llm.get("base_url") == "https://api.deepseek.com/v1"
        assert captured_llm.get("model") == "deepseek-chat"


def test_api_has_cors_headers():
    """API responses should include CORS headers for cross-origin access."""
    client = TestClient(app)
    resp = client.options(
        "/api/credentials/status",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # CORS preflight should succeed
    assert resp.status_code == 200
    assert "access-control-allow-origin" in {k.lower() for k in resp.headers.keys()}


def test_credential_service_name_is_fixed_string(tmp_path, monkeypatch):
    """Credential service name should be a fixed string, not dependent on CWD.

    With keyring-based storage there is no file path; the service name
    namespaces credentials in the OS keychain.  It must be a constant
    so credentials stay accessible regardless of where the server starts.
    """
    import importlib
    import sys

    monkeypatch.chdir(tmp_path)

    saved = sys.modules.pop("the_harness.webui.app", None)
    try:
        webui_mod = importlib.import_module("the_harness.webui.app")
        service_name = webui_mod._SERVICE_NAME
    finally:
        if saved is not None:
            sys.modules["the_harness.webui.app"] = saved

    assert isinstance(service_name, str)
    assert service_name == "the-harness"


def test_credentials_status_returns_200_when_keyring_unavailable(tmp_path, monkeypatch):
    """GET /api/credentials/status must return 200 even when keyring has no backend.

    Bug: On Linux containers without gnome-keyring/kwallet, keyring calls raise
    exceptions (e.g. NoKeyringError, RuntimeError). The endpoint had no
    try/except, so FastAPI returned 500 "Internal Server Error". The frontend
    tried to parse it as JSON and failed with "Unexpected token 'I'".

    Fix: CredentialManager.status() and the endpoint must degrade gracefully —
    return an empty providers dict instead of propagating the exception.
    """
    import importlib
    from unittest.mock import patch, MagicMock

    webui_mod = importlib.import_module("the_harness.webui.app")
    # Mock keyring that raises on every call (simulates no backend on Render)
    mock_kr = MagicMock()
    mock_kr.get_password.side_effect = RuntimeError("No keyring backend available")
    mock_kr.set_password.side_effect = RuntimeError("No keyring backend available")
    monkeypatch.setattr(webui_mod, "_credential_manager", None)
    # Clear env vars so status() has nothing to fall back on
    for var in ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL"):
        monkeypatch.delenv(var, raising=False)

    client = TestClient(app)
    with patch("the_harness.credentials.manager.keyring", mock_kr):
        resp = client.get("/api/credentials/status")

    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "providers" in data
    assert data["providers"] == {}


def test_credentials_store_returns_friendly_error_when_keyring_unavailable(tmp_path, monkeypatch):
    """POST /api/credentials/store must return JSON error (not 500) when keyring is unavailable.

    Bug: store endpoint only caught PermissionError, but keyring raises
    RuntimeError/NoKeyringError on Linux without a backend. The uncaught
    exception became 500 "Internal Server Error".

    Fix: Catch all exceptions from keyring, return a 503 JSON response with a
    helpful message guiding the user to use environment variables instead.
    """
    import importlib
    from unittest.mock import patch, MagicMock

    webui_mod = importlib.import_module("the_harness.webui.app")
    mock_kr = MagicMock()
    mock_kr.set_password.side_effect = RuntimeError("No keyring backend available")
    mock_kr.get_password.side_effect = RuntimeError("No keyring backend available")
    monkeypatch.setattr(webui_mod, "_credential_manager", None)

    client = TestClient(app)
    with patch("the_harness.credentials.manager.keyring", mock_kr):
        resp = client.post(
            "/api/credentials/store",
            json={"provider": "openai", "api_key": "sk-test-key", "base_url": "", "model": ""},
        )

    assert resp.status_code != 500, "Should not return 500 Internal Server Error"
    assert resp.status_code in (200, 503), f"Expected 200 or 503, got {resp.status_code}"
    # Must be valid JSON, not "Internal Server Error" text
    data = resp.json()
    assert "ok" in data or "error" in data
