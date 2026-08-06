"""FastAPI WebUI — terminal-style streaming output and session history.

Endpoints:
  POST /api/fix          — start a fix task, returns session_id
  WS   /ws/fix/{sid}     — stream agent events in real-time
  GET  /api/sessions     — list past sessions
  GET  /api/sessions/{id} — get session detail
  DELETE /api/sessions/{id} — delete a single session
  POST /api/sessions/batch-delete — delete multiple sessions by ids
  GET  /                 — serve static index.html
"""

import asyncio
import os
import queue
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from the_harness.agent_loop import AgentLoop
from the_harness.config import Config
from the_harness.credentials.manager import CredentialManager
from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.feedback.validator import TestValidator
from the_harness.guardrail.guardrail import Guardrail
from the_harness.llm.base import LLMProvider
from the_harness.llm.openai_provider import OpenAILLMProvider, _FREEFORM_SYSTEM_PROMPT
from the_harness.memory.store import MemoryStore
from the_harness.models import Action, ActionResult, Result, Task
from the_harness.tools.dispatcher import ToolDispatcher

# Load .env file if present (for local dev / pre-configured keys).
# NOTE: .env is plaintext and process-visible; it is a convenience for
# development only.  Production deployments should use the OS keychain
# (via the WebUI settings page or `the-harness-creds store` CLI).
try:
    from dotenv import load_dotenv

    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_PROJECT_ROOT / ".env")
except ImportError:
    # python-dotenv not installed — env vars must be set externally
    pass

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="the-harness WebUI", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def prevent_browser_caching(request, call_next):
    """Add Cache-Control: no-cache to all responses so browsers always fetch
    the latest HTML/JS/CSS.  Without this, browsers cache old app.js and
    users see removed error messages like 'Credential store is locked'.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response

# Sessions store: session_id -> {task, workspace, status, mode}
_sessions: dict[str, dict[str, Any]] = {}

# Sentinel to signal the consumer that the worker thread is done
_DONE = object()

# Credential manager singleton (initialized lazily)
_credential_manager: CredentialManager | None = None
# Keyring service name — namespaces credentials in the OS keychain.
# This is a constant string (not a file path) so credentials stay
# accessible regardless of where the server process was started from.
_SERVICE_NAME = "the-harness"


def _get_credential_manager() -> CredentialManager:
    """Get or create the singleton CredentialManager."""
    global _credential_manager
    if _credential_manager is None:
        _credential_manager = CredentialManager(_SERVICE_NAME)
    return _credential_manager


def _validate_workspace(workspace: str) -> str:
    """Validate workspace path to prevent path traversal.

    Blocks system directories and resolves the path.
    """
    ws_path = Path(workspace).resolve()
    blocked_prefixes = ("C:\\Windows", "/etc", "/sys", "/proc", "/boot", "/dev")
    resolved_str = str(ws_path)
    for prefix in blocked_prefixes:
        if resolved_str.startswith(prefix):
            raise HTTPException(status_code=400, detail="Invalid workspace path")
    return str(ws_path)


class _EmittingLLM:
    """Wraps an LLM provider to emit action events into a thread-safe queue."""

    def __init__(self, inner: LLMProvider, event_queue: queue.Queue) -> None:
        self._inner = inner
        self._queue = event_queue

    def complete(self, messages: list[dict[str, str]]) -> dict[str, Any]:
        resp = self._inner.complete(messages)
        self._queue.put(("action", {
            "action": resp.get("action", ""),
            "params": resp.get("params", {}),
            "reasoning": resp.get("reasoning", ""),
        }))
        return resp

    def reset(self) -> None:
        if hasattr(self._inner, "reset"):
            self._inner.reset()

    def summarize_session(self, task_desc: str, action_summaries: list[str], success: bool, reason: str) -> str:
        """Delegate to the inner provider without emitting an event.

        summarize_session is called after the loop finishes, so emitting
        an 'action' event here would confuse the WebSocket consumer.
        """
        return self._inner.summarize_session(task_desc, action_summaries, success, reason)


class _EmittingValidator:
    """Wraps a validator to emit feedback events into a thread-safe queue."""

    __test__ = False

    def __init__(self, inner: Any, event_queue: queue.Queue) -> None:
        self._inner = inner
        self._queue = event_queue

    def validate(self, test_path: str) -> Any:
        tr = self._inner.validate(test_path)
        self._queue.put(("feedback", {
            "passed": tr.passed,
            "exit_code": tr.exit_code,
            "stdout": tr.stdout[-500:],
            "stderr": tr.stderr[-500:],
        }))
        return tr


class _EmittingDispatcher:
    """Wraps a ToolDispatcher to emit execution results into a thread-safe queue."""

    def __init__(self, inner: ToolDispatcher, event_queue: queue.Queue) -> None:
        self._inner = inner
        self._queue = event_queue

    def execute(self, action: Action) -> ActionResult:
        result = self._inner.execute(action)
        self._queue.put(("execution", {
            "action": action.type.value,
            "params": action.params,
            "success": result.success,
            "output": result.output[:2000] if result.output else "",
            "error": result.error,
        }))
        return result


def _default_agent_loop_factory(
    workspace: str,
    event_queue: queue.Queue | None = None,
    freeform: bool = False,
) -> AgentLoop:
    """Create a default AgentLoop with real components.

    If any provider's credentials are available in CredentialManager,
    uses OpenAILLMProvider (all OpenAI-compatible endpoints work via
    base_url); otherwise falls back to MockLLMProvider.

    If event_queue is provided, LLM, validator, and dispatcher are wrapped
    to emit events. If freeform is True, uses the freeform system prompt.

    Tests override this with a mock factory.
    """
    config = Config(workspace=workspace)
    from the_harness.llm.mock_provider import MockLLMProvider

    # Try to use real OpenAI provider if credentials are available.
    # Iterate over all configured providers (not just 'openai') so that users
    # who stored credentials under a different name (e.g. 'deepseek') still
    # get a real LLM.  All OpenAI-compatible endpoints (DeepSeek, Moonshot,
    # etc.) work with OpenAILLMProvider via the base_url parameter.
    cm = _get_credential_manager()
    api_key: str | None = None
    base_url: str | None = None
    provider_model: str | None = None
    try:
        status = cm.status()
        for provider_name in status:
            creds = cm.get(provider_name)
            if creds and creds.get("api_key"):
                api_key = creds["api_key"]
                base_url = creds.get("base_url") or None
                provider_model = creds.get("model") or None
                break
    except Exception:
        api_key = None

    if api_key:
        system_prompt = _FREEFORM_SYSTEM_PROMPT if freeform else None
        model = provider_model or config.model
        llm: LLMProvider = OpenAILLMProvider(
            api_key=api_key,
            model=model,
            system_prompt=system_prompt,
            base_url=base_url,
        )
    else:
        llm = MockLLMProvider([])

    validator: Any = TestValidator(workspace)
    dispatcher: ToolDispatcher | _EmittingDispatcher = ToolDispatcher(workspace)

    if event_queue is not None:
        llm = _EmittingLLM(llm, event_queue)
        validator = _EmittingValidator(validator, event_queue)
        dispatcher = _EmittingDispatcher(dispatcher, event_queue)

    return AgentLoop(
        config=config,
        llm_provider=llm,
        guardrail=Guardrail(workspace),
        tool_dispatcher=dispatcher,
        validator=validator,
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(workspace),
    )


# Module-level reference so tests can monkey-patch it.
# Signature: (workspace, event_queue=None, freeform=False) -> AgentLoop
_agent_loop_factory: Callable[..., AgentLoop] = _default_agent_loop_factory


@app.post("/api/fix")
async def start_fix(payload: dict[str, Any]) -> JSONResponse:
    """Start a fix task.

    Body: {"test_path": "...", "workspace": "..."}
    Returns: {"session_id": "..."}
    """
    test_path = payload.get("test_path", "")
    workspace = _validate_workspace(payload.get("workspace", "."))
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "task": Task(test_path=test_path, workspace=workspace),
        "workspace": workspace,
        "status": "pending",
    }
    return JSONResponse({"session_id": session_id})


@app.post("/api/instruct")
async def start_instruct(payload: dict[str, Any]) -> JSONResponse:
    """Start a freeform instruction task.

    Body: {"description": "...", "workspace": "...", "history": [...], "session_id": <int|null>}
    Returns: {"session_id": "..."}  (WebSocket session ID, not DB session ID)
    """
    description = payload.get("description", "").strip()
    if not description:
        raise HTTPException(status_code=400, detail="description is required")
    workspace = _validate_workspace(payload.get("workspace", "."))
    history = payload.get("history", []) or []
    # DB session ID for follow-up questions — when provided, the agent
    # appends to this session instead of creating a new one.
    db_session_id = payload.get("session_id")
    if db_session_id is not None:
        db_session_id = int(db_session_id)
    session_id = str(uuid.uuid4())
    _sessions[session_id] = {
        "task": Task(test_path="", workspace=workspace, description=description),
        "workspace": workspace,
        "status": "pending",
        "mode": "freeform",
        "history": history,
        "db_session_id": db_session_id,
    }
    return JSONResponse({"session_id": session_id})


@app.get("/api/sessions")
async def list_sessions(workspace: str = ".") -> JSONResponse:
    """List past sessions from the memory store."""
    ws = _validate_workspace(workspace)
    store = MemoryStore(ws)
    return JSONResponse(store.get_sessions())


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int, workspace: str = ".") -> JSONResponse:
    """Get a specific session by ID, including its full actions list.

    The frontend renders this actions list as conversation bubbles when a
    past session is opened from the sidebar, so the response must include
    actions (not just the summary fields returned by get_sessions()).
    """
    ws = _validate_workspace(workspace)
    store = MemoryStore(ws)
    session = store.get_session(session_id)
    if session is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse(session)


@app.post("/api/sessions/batch-delete")
async def batch_delete_sessions(
    payload: dict[str, Any], workspace: str = "."
) -> JSONResponse:
    """Delete multiple sessions at once.

    Body: {"ids": [1, 2, 3]}
    Returns: {"ok": true, "deleted": <count>}. Unknown ids are silently
    skipped. Used by the UI's "批量删除" button.
    """
    ws = _validate_workspace(workspace)
    ids = payload.get("ids", []) or []
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids must be a list")
    store = MemoryStore(ws)
    deleted = store.delete_sessions([int(i) for i in ids])
    return JSONResponse({"ok": True, "deleted": deleted})


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: int, workspace: str = ".") -> JSONResponse:
    """Delete a single session and its actions by ID.

    Returns 200 {"ok": true} on success, or 404 if the session doesn't exist.
    """
    ws = _validate_workspace(workspace)
    store = MemoryStore(ws)
    deleted = store.delete_session(session_id)
    if not deleted:
        return JSONResponse({"error": "not found"}, status_code=404)
    return JSONResponse({"ok": True})


# ── Credential Management API ────────────────────────────────────────


@app.get("/api/credentials/status")
async def credentials_status() -> JSONResponse:
    """Check credential store status — always available, no unlock needed."""
    cm = _get_credential_manager()
    providers = cm.status()
    return JSONResponse({
        "providers": providers,
    })


@app.post("/api/credentials/store")
async def credentials_store(payload: dict[str, Any]) -> JSONResponse:
    """Store or update credentials for a provider.

    Body: {"provider": "openai", "api_key": "sk-...", "base_url": "", "model": "gpt-4o-mini"}
    """
    provider = payload.get("provider", "").strip()
    api_key = payload.get("api_key", "").strip()
    if not provider or not api_key:
        raise HTTPException(status_code=400, detail="provider and api_key are required")
    base_url = payload.get("base_url", "").strip()
    model = payload.get("model", "").strip()
    cm = _get_credential_manager()
    try:
        cm.store(provider, api_key, base_url, model)
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot write credential file: {e}.",
        ) from e
    return JSONResponse({"ok": True, "status": cm.status()})


@app.delete("/api/credentials/{provider}")
async def credentials_delete(provider: str) -> JSONResponse:
    """Delete a provider's API key."""
    cm = _get_credential_manager()
    try:
        cm.delete(provider)
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"Cannot write credential file: {e}.",
        ) from e
    return JSONResponse({"ok": True, "status": cm.status()})


@app.websocket("/ws/fix/{session_id}")
async def ws_fix(websocket: WebSocket, session_id: str) -> None:
    """Stream agent events over WebSocket in real-time."""
    await websocket.accept()

    if session_id not in _sessions:
        await websocket.send_json({"type": "error", "data": {"message": "unknown session"}})
        await websocket.close()
        return

    session = _sessions[session_id]
    task: Task = session["task"]
    workspace = session["workspace"]

    # Thread-safe queue for cross-thread event passing
    event_queue: queue.Queue = queue.Queue()

    # Create the agent loop with emitting wrappers (no private attribute access)
    loop = _agent_loop_factory(workspace, event_queue, freeform=session.get("mode") == "freeform")

    try:
        # Run the synchronous loop in a background thread.
        # Freeform mode uses run_freeform (with optional conversation history);
        # fix mode uses run.
        if session.get("mode") == "freeform":
            history = session.get("history", [])
            run_task = asyncio.create_task(asyncio.to_thread(loop.run_freeform, task, history))
        else:
            run_task = asyncio.create_task(asyncio.to_thread(loop.run, task))

        # Consume events from the queue and send them over WebSocket in real-time
        while True:
            try:
                item = await asyncio.to_thread(event_queue.get, True, timeout=0.1)
            except queue.Empty:
                if run_task.done():
                    break
                continue

            if item is _DONE:
                break

            event_type, event_data = item
            await websocket.send_json({"type": event_type, "data": event_data})

        result = await run_task
        await websocket.send_json({
            "type": "result",
            "data": {
                "success": result.success,
                "rounds": result.rounds,
                "reason": result.reason,
            },
        })
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "error", "data": {"message": str(exc)}})
    finally:
        # Clean up session from memory
        _sessions.pop(session_id, None)
        await websocket.close()


@app.websocket("/ws/instruct/{session_id}")
async def ws_instruct(websocket: WebSocket, session_id: str) -> None:
    """Stream freeform agent events over WebSocket in real-time."""
    await websocket.accept()

    if session_id not in _sessions:
        await websocket.send_json({"type": "error", "data": {"message": "unknown session"}})
        await websocket.close()
        return

    session = _sessions[session_id]
    task: Task = session["task"]
    workspace = session["workspace"]
    history = session.get("history", [])
    db_session_id = session.get("db_session_id")

    # Thread-safe queue for cross-thread event passing
    event_queue: queue.Queue = queue.Queue()

    # Create the agent loop with freeform mode and emitting wrappers
    loop = _agent_loop_factory(workspace, event_queue, freeform=True)

    try:
        # Run the freeform loop in a background thread.
        # Pass history for conversation context and db_session_id for
        # appending to an existing session (follow-up questions).
        run_task = asyncio.create_task(
            asyncio.to_thread(loop.run_freeform, task, history, db_session_id)
        )

        # Consume events from the queue and send them over WebSocket in real-time
        while True:
            try:
                item = await asyncio.to_thread(event_queue.get, True, timeout=0.1)
            except queue.Empty:
                if run_task.done():
                    break
                continue

            if item is _DONE:
                break

            event_type, event_data = item
            await websocket.send_json({"type": event_type, "data": event_data})

        result = await run_task
        await websocket.send_json({
            "type": "result",
            "data": {
                "success": result.success,
                "rounds": result.rounds,
                "reason": result.reason,
                "session_id": result.session_id,
            },
        })
    except WebSocketDisconnect:
        pass
    except Exception as exc:
        await websocket.send_json({"type": "error", "data": {"message": str(exc)}})
    finally:
        _sessions.pop(session_id, None)
        await websocket.close()


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the static index.html."""
    html_path = _STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# Mount static files
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


def main() -> None:
    """Entry point for the-harness CLI command.

    Runs the FastAPI app via uvicorn on 0.0.0.0:8000.
    """
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
