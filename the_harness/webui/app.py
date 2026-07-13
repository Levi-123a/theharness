"""FastAPI WebUI — terminal-style streaming output and session history.

Endpoints:
  POST /api/fix          — start a fix task, returns session_id
  WS   /ws/fix/{sid}     — stream agent events in real-time
  GET  /api/sessions     — list past sessions
  GET  /api/sessions/{id} — get session detail
  GET  /                 — serve static index.html
"""

import asyncio
import queue
import uuid
from pathlib import Path
from typing import Any, Callable

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from the_harness.agent_loop import AgentLoop
from the_harness.config import Config
from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.feedback.validator import TestValidator
from the_harness.guardrail.guardrail import Guardrail
from the_harness.llm.base import LLMProvider
from the_harness.memory.store import MemoryStore
from the_harness.models import Result, Task
from the_harness.tools.dispatcher import ToolDispatcher

_STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="the-harness WebUI", version="0.1.0")

# Sessions store: session_id -> {task, workspace, status}
_sessions: dict[str, dict[str, Any]] = {}

# Sentinel to signal the consumer that the worker thread is done
_DONE = object()


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


def _default_agent_loop_factory(workspace: str, event_queue: queue.Queue | None = None) -> AgentLoop:
    """Create a default AgentLoop with real components.

    If event_queue is provided, LLM and validator are wrapped to emit events.
    Tests override this with a mock factory.
    """
    config = Config(workspace=workspace)
    from the_harness.llm.mock_provider import MockLLMProvider

    llm: LLMProvider = MockLLMProvider([])
    validator: Any = TestValidator(workspace)

    if event_queue is not None:
        llm = _EmittingLLM(llm, event_queue)
        validator = _EmittingValidator(validator, event_queue)

    return AgentLoop(
        config=config,
        llm_provider=llm,
        guardrail=Guardrail(workspace),
        tool_dispatcher=ToolDispatcher(workspace),
        validator=validator,
        classifier=FailureClassifier(),
        injector=FeedbackInjector(),
        memory_store=MemoryStore(workspace),
    )


# Module-level reference so tests can monkey-patch it.
# Signature: (workspace, event_queue=None) -> AgentLoop
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


@app.get("/api/sessions")
async def list_sessions(workspace: str = ".") -> JSONResponse:
    """List past sessions from the memory store."""
    ws = _validate_workspace(workspace)
    store = MemoryStore(ws)
    return JSONResponse(store.get_sessions())


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: int, workspace: str = ".") -> JSONResponse:
    """Get a specific session by ID."""
    ws = _validate_workspace(workspace)
    store = MemoryStore(ws)
    sessions = store.get_sessions()
    for s in sessions:
        if s["id"] == session_id:
            return JSONResponse(s)
    return JSONResponse({"error": "not found"}, status_code=404)


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
    loop = _agent_loop_factory(workspace, event_queue)

    try:
        # Run the synchronous loop in a background thread
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


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Serve the static index.html."""
    html_path = _STATIC_DIR / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


# Mount static files
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
