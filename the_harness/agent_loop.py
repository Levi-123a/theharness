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

        for round_num in range(1, self._config.max_rounds + 1):
            # a. Call LLM
            messages = [{"role": "system", "content": "\n\n".join(context_parts)}]
            response = self._llm.complete(messages)

            # b. Parse action
            action = self._parse_action(response, context_parts)
            if action is None:
                continue

            # c. Check give_up
            if action.type == ActionType.GIVE_UP:
                self._save_session(task, False, round_num, "LLM gave up", action_history)
                return Result(
                    success=False,
                    rounds=round_num,
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
            action_history.append(action)

            # g. Run tests
            test_result = self._validator.validate(task.test_path)

            # h. Classify feedback
            feedback = self._classifier.classify(test_result)

            # i. Check pass
            if feedback.type == FeedbackType.PASS:
                self._save_session(task, True, round_num, "All tests passed", action_history)
                return Result(
                    success=True,
                    rounds=round_num,
                    reason="All tests passed",
                    action_history=action_history,
                )

            # j. Check repeated action
            if self._is_repeated(action_history):
                self._save_session(task, False, round_num, "Stuck in loop: repeated action", action_history)
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
        self._save_session(task, False, self._config.max_rounds, "Max rounds exceeded", action_history)
        return Result(
            success=False,
            rounds=self._config.max_rounds,
            reason="Max rounds exceeded",
            action_history=action_history,
        )

    def _save_session(
        self,
        task: Task,
        success: bool,
        rounds: int,
        reason: str,
        action_history: list[Action],
    ) -> None:
        """Save session data to the memory store on all exit paths.

        Args:
            task: The task that was worked on.
            success: Whether the task succeeded.
            rounds: Number of rounds executed.
            reason: Exit reason.
            action_history: List of actions taken.
        """
        self._memory.save_session({
            "test_path": task.test_path,
            "success": success,
            "rounds": rounds,
            "reason": reason,
            "actions": [
                {
                    "round": i + 1,
                    "action_type": a.type.value,
                    "action_params": a.params,
                    "reasoning": a.reasoning,
                }
                for i, a in enumerate(action_history)
            ],
        })

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
