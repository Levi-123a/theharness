"""Agent main loop — the harness kernel that orchestrates all components.

Implements the core feedback loop:
  context → LLM → parse action → guardrail → execute → validate → classify → inject → repeat

All mechanisms are deterministic code, testable with mock LLM.
"""

import json
from typing import Any, Callable

from the_harness.config import Config
from the_harness.feedback.classifier import FailureClassifier
from the_harness.feedback.injector import FeedbackInjector
from the_harness.feedback.validator import TestValidator
from the_harness.guardrail.guardrail import Guardrail
from the_harness.llm.base import LLMProvider
from the_harness.memory.store import MemoryStore
from the_harness.models import (
    Action,
    ActionType,
    FeedbackType,
    Result,
    Task,
)
from the_harness.tools.dispatcher import ToolDispatcher


class AgentLoop:
    """The harness kernel — orchestrates LLM, tools, guardrails, and feedback.

    Attributes:
        config: Global configuration.
        llm_provider: LLM provider (real or mock).
        guardrail: Dangerous action interceptor.
        tool_dispatcher: File/shell action executor.
        validator: Test runner and result capturer.
        classifier: Failure type classifier.
        injector: Feedback-to-prompt converter.
        memory_store: Cross-session memory.
        hitl_callback: Callback for human-in-the-loop approval of blocked actions.
    """

    def __init__(
        self,
        config: Config,
        llm_provider: LLMProvider,
        guardrail: Guardrail,
        tool_dispatcher: ToolDispatcher,
        validator: TestValidator,
        classifier: FailureClassifier,
        injector: FeedbackInjector,
        memory_store: MemoryStore,
        hitl_callback: Callable[[str], bool] | None = None,
    ) -> None:
        self._config = config
        self._llm = llm_provider
        self._guardrail = guardrail
        self._dispatcher = tool_dispatcher
        self._validator = validator
        self._classifier = classifier
        self._injector = injector
        self._memory = memory_store
        # Default: auto-reject blocked actions (safe default for automated runs)
        self._hitl_callback = hitl_callback or (lambda reason: False)

    def run(self, task: Task) -> Result:
        """Run the agent loop on a task.

        Args:
            task: The task to work on (test_path + workspace).

        Returns:
            Result with success status, rounds, reason, and action history.
        """
        context_parts: list[str] = [self._memory.build_context(task)]
        action_history: list[Action] = []
        # Track execution output per action so it can be saved with the session.
        action_results: list[str] = []
        # Only productive iterations (action successfully executed) count
        # against max_rounds. Parse errors, guardrail blocks, and execution
        # failures are retries that do NOT consume a round.
        round_num = 0
        max_iterations = self._config.max_rounds * 4  # safety cap vs infinite loops
        iterations = 0

        while round_num < self._config.max_rounds and iterations < max_iterations:
            iterations += 1
            # a. Call LLM
            messages = [{"role": "system", "content": "\n\n".join(context_parts)}]
            response = self._llm.complete(messages)

            # b. Parse action
            action = self._parse_action(response, context_parts)
            if action is None:
                continue

            # c. Check give_up
            if action.type == ActionType.GIVE_UP:
                self._save_session(task, False, round_num + 1, "LLM gave up", action_history, action_results=action_results)
                return Result(
                    success=False,
                    rounds=round_num + 1,
                    reason="LLM gave up",
                    action_history=action_history,
                )

            # d. Guardrail check
            gr = self._guardrail.check(action)

            # e. HITL if blocked
            if gr.blocked:
                approved = self._hitl_callback(gr.reason)
                if not approved:
                    context_parts.append(f"Action rejected by guardrail: {gr.reason}")
                    continue

            # f. Execute action
            exec_result = self._dispatcher.execute(action)
            if not exec_result.success:
                context_parts.append(f"Action execution failed: {exec_result.error}")
                continue

            # Productive round — increment counter
            round_num += 1
            action_history.append(action)
            action_results.append(exec_result.output or "")

            # g. Run tests
            test_result = self._validator.validate(task.test_path)

            # h. Classify feedback
            feedback = self._classifier.classify(test_result)

            # i. Check pass
            if feedback.type == FeedbackType.PASS:
                self._save_session(task, True, round_num, "All tests passed", action_history, action_results=action_results)
                return Result(
                    success=True,
                    rounds=round_num,
                    reason="All tests passed",
                    action_history=action_history,
                )

            # j. Check repeated action
            if self._is_repeated(action_history):
                self._save_session(task, False, round_num, "Stuck in loop: repeated action", action_history, action_results=action_results)
                return Result(
                    success=False,
                    rounds=round_num,
                    reason="Stuck in loop: repeated action",
                    action_history=action_history,
                )

            # k-l. Inject feedback
            injection = self._injector.inject(feedback)
            context_parts.append(injection)

            # m. Update memory
            self._memory.save_failure_pattern(feedback.type.value, feedback.strategy_hint)

        # 3. Max rounds exceeded
        self._save_session(task, False, self._config.max_rounds, "Max rounds exceeded", action_history, action_results=action_results)
        return Result(
            success=False,
            rounds=self._config.max_rounds,
            reason="Max rounds exceeded",
            action_history=action_history,
        )

    def run_freeform(
        self,
        task: Task,
        history: list[dict[str, str]] | None = None,
        session_id: int | None = None,
    ) -> Result:
        """Run the agent in freeform mode — no test validation, LLM decides when done.

        The agent reads, edits, writes files and runs shell commands based on
        the user's text description in ``task.description``. The loop ends when
        the LLM returns ``done`` or ``give_up``, or when max rounds are exceeded.

        Args:
            task: The task with a ``description`` field containing user instructions.
            history: Optional conversation history for continuation. Each item
                     is ``{"role": "user"|"assistant", "content": "..."}``.
                     When provided, the LLM receives previous Q&A pairs as
                     context so it can answer follow-up questions.
            session_id: Optional existing session ID to append to. When provided,
                        new actions are added to that session instead of creating
                        a new one — used when the user asks follow-up questions
                        in the same conversation.

        Returns:
            Result with success status, rounds, reason, and action history.
        """
        context_parts: list[str] = [
            f"User instruction: {task.description}",
            f"Workspace: {task.workspace}",
        ]
        # 将对话历史作为 system 上下文注入，让 LLM 理解之前聊了什么
        if history:
            history_lines = []
            for h in history:
                role = "用户" if h.get("role") == "user" else "助手"
                history_lines.append(f"{role}: {h.get('content', '')}")
            context_parts.insert(0, "对话历史:\n" + "\n".join(history_lines))
        action_history: list[Action] = []
        action_results: list[str] = []
        # Only productive iterations count against max_rounds.
        round_num = 0
        max_iterations = self._config.max_rounds * 4
        iterations = 0

        while round_num < self._config.max_rounds and iterations < max_iterations:
            iterations += 1
            # a. Call LLM
            messages = [{"role": "system", "content": "\n\n".join(context_parts)}]
            response = self._llm.complete(messages)

            # b. Parse action
            action = self._parse_action(response, context_parts)
            if action is None:
                continue

            # c. Check done / give_up
            if action.type == ActionType.DONE:
                # Include the done action in history so each Q&A exchange
                # has at least one action record (visible in session detail).
                action_history.append(action)
                action_results.append(action.reasoning or "")
                sid = self._save_session(
                    task, True, round_num + 1, "Task completed",
                    action_history, action_results=action_results,
                    final_reply=action.reasoning, session_id=session_id,
                )
                return Result(
                    success=True,
                    rounds=round_num + 1,
                    reason="Task completed",
                    action_history=action_history,
                    session_id=sid,
                )
            if action.type == ActionType.GIVE_UP:
                action_history.append(action)
                action_results.append(action.reasoning or "")
                sid = self._save_session(
                    task, False, round_num + 1, "LLM gave up",
                    action_history, action_results=action_results,
                    final_reply=action.reasoning, session_id=session_id,
                )
                return Result(
                    success=False,
                    rounds=round_num + 1,
                    reason="LLM gave up",
                    action_history=action_history,
                    session_id=sid,
                )

            # d. Guardrail check
            gr = self._guardrail.check(action)

            # e. HITL if blocked
            if gr.blocked:
                approved = self._hitl_callback(gr.reason)
                if not approved:
                    context_parts.append(f"Action rejected by guardrail: {gr.reason}")
                    continue

            # f. Execute action
            exec_result = self._dispatcher.execute(action)
            if not exec_result.success:
                context_parts.append(
                    f"Action execution failed: {exec_result.error}\nOutput: {exec_result.output}"
                )
                continue

            # Productive round
            round_num += 1
            action_history.append(action)
            action_results.append(exec_result.output or "")

            # g. Feed execution output back to LLM
            output_preview = exec_result.output[:2000] if exec_result.output else "(no output)"
            context_parts.append(
                f"Result of {action.type.value}: {output_preview}"
            )

            # h. Check repeated action
            if self._is_repeated(action_history):
                sid = self._save_session(
                    task, False, round_num, "Stuck in loop: repeated action",
                    action_history, action_results=action_results,
                    session_id=session_id,
                )
                return Result(
                    success=False,
                    rounds=round_num,
                    reason="Stuck in loop: repeated action",
                    action_history=action_history,
                    session_id=sid,
                )

        # Max rounds exceeded
        sid = self._save_session(
            task, False, self._config.max_rounds, "Max rounds exceeded",
            action_history, action_results=action_results,
            session_id=session_id,
        )
        return Result(
            success=False,
            rounds=self._config.max_rounds,
            reason="Max rounds exceeded",
            action_history=action_history,
            session_id=sid,
        )

    def _save_session(
        self,
        task: Task,
        success: bool,
        rounds: int,
        reason: str,
        action_history: list[Action],
        action_results: list[str] | None = None,
        final_reply: str = "",
        session_id: int | None = None,
    ) -> int:
        """Save session data to the memory store on all exit paths.

        Args:
            task: The task that was worked on.
            success: Whether the task succeeded.
            rounds: Number of rounds executed.
            reason: Exit reason.
            action_history: List of actions taken.
            action_results: Execution output for each action (parallel list).
            final_reply: The AI's final text reply (from done/give_up
                         responses). For freeform sessions where the LLM
                         immediately returns 'done', this is the only
                         AI output — without it the session detail would
                         show nothing.
            session_id: If provided, append to this existing session instead
                        of creating a new one (used for follow-up questions).

        Returns:
            The session ID (new or existing).
        """
        action_results = action_results or []
        task_desc = task.test_path or task.description or ""
        action_summaries = [a.reasoning for a in action_history if a.reasoning]
        if final_reply:
            action_summaries.append(final_reply)
        summary = self._llm.summarize_session(
            task_desc=task_desc,
            action_summaries=action_summaries,
            success=success,
            reason=reason,
        )
        actions_data = [
            {
                "round": i + 1,
                "action_type": a.type.value,
                "action_params": a.params,
                "reasoning": a.reasoning,
                "result": action_results[i] if i < len(action_results) else "",
            }
            for i, a in enumerate(action_history)
        ]
        session_data = {
            "test_path": task.test_path,
            "description": task.description or "",
            "final_reply": final_reply,
            "success": success,
            "rounds": rounds,
            "reason": reason,
            "summary": summary,
            "actions": actions_data,
        }
        if session_id is not None:
            self._memory.append_to_session(session_id, session_data)
            return session_id
        return self._memory.save_session(session_data)

    def _parse_action(self, response: dict[str, Any], context_parts: list[str]) -> Action | None:
        """Parse LLM response into an Action object.

        Args:
            response: The LLM response dict with "action", "params", "reasoning".
            context_parts: The context list to append error messages to.

        Returns:
            An Action object, or None if parsing failed.
        """
        try:
            action_str = response.get("action", "")
            action_type = ActionType(action_str)
            params = response.get("params", {})
            reasoning = response.get("reasoning", "")
            return Action(type=action_type, params=params, reasoning=reasoning)
        except (ValueError, KeyError, AttributeError, TypeError) as e:
            context_parts.append(f"Parse error: please return valid JSON with 'action', 'params', 'reasoning'. Error: {e}")
            return None

    def _is_repeated(self, history: list[Action]) -> bool:
        """Check if the current action is identical to the previous action.

        Args:
            history: The action history (including the current action at the end).

        Returns:
            True if the last 2 actions are identical.
        """
        if len(history) < 2:
            return False
        return history[-1] == history[-2]
