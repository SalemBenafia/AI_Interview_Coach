"""
app/modules/agents/router_agent.py
=====================================
Router / Conversation Router Agent (roles.txt → AI Sub-Agent Architecture §3,
admin_ai_manage_ui.txt → "Router Agent Management" — a declarative,
admin-editable rule table, NOT free-form LLM judgment).

DESIGN NOTE: branching ("should we follow up, advance, coach, or end?") is
control flow over real, already-computed numbers (the Evaluator Agent's
scores). Asking an LLM to re-decide this non-deterministically would make
the product less reliable, not more "AI" — so the Router Agent is a real,
deterministic rule engine that evaluates admin-configured `decision_rules`
against the actual session state. This matches scalability.txt's core
principle: "Avoid hardcoded conversation logic... use a DECLARATIVE GRAPH +
STATE MACHINE" — the rules are data (editable from the admin UI), the
engine that evaluates them is simple, real, auditable code.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Optional

import structlog

from app.modules.agents.schemas import RouterInput, RouterOutput

logger = structlog.get_logger()

_CONDITION_RE = re.compile(r"^\s*(not\s+)?([a-zA-Z_]\w*)\s*(>=|<=|==|!=|>|<)?\s*([\w.]+)?\s*$")

_VALID_ACTIONS = {"ask_followup", "next_question", "increase_difficulty", "coaching", "end"}

DEFAULT_DECISION_RULES: list[dict[str, str]] = [
    {"condition": "questions_asked_count >= max_questions", "action": "end"},
    {"condition": "weak_signal == true", "action": "ask_followup"},
    {"condition": "score < 50", "action": "coaching"},
    {"condition": "score > 80", "action": "increase_difficulty"},
]


@dataclass
class RouterRunResult:
    output: RouterOutput
    latency_ms: int
    model_name: str = "rule_engine"
    tokens_used: Optional[int] = None
    used_simulation: bool = False  # kept for interface parity with AgentRunResult


def _coerce(value: str) -> Any:
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _evaluate_condition(condition: str, context: dict[str, Any]) -> bool:
    """
    Evaluate a single admin-authored condition string, e.g.:
        "score > 80"
        "weak_signal == true"
        "follow_up_count >= 2"
        "questions_asked_count >= max_questions"
    Intentionally NOT a generic `eval()` — only a restricted comparison
    grammar is accepted, so admin-edited rules can never execute arbitrary code.
    """
    match = _CONDITION_RE.match(condition)
    if not match:
        logger.warning("router_rule_unparseable", condition=condition)
        return False

    negate, var_name, op, raw_value = match.groups()
    if var_name not in context:
        logger.warning("router_rule_unknown_variable", condition=condition, variable=var_name)
        return False

    left = context[var_name]

    if op is None:  # bare boolean condition, e.g. "weak_signal"
        result = bool(left)
        return (not result) if negate else result

    right_raw = raw_value
    right = context.get(right_raw, _coerce(right_raw)) if right_raw in context else _coerce(right_raw)

    try:
        if op == ">":
            result = left > right
        elif op == "<":
            result = left < right
        elif op == ">=":
            result = left >= right
        elif op == "<=":
            result = left <= right
        elif op == "==":
            result = left == right
        elif op == "!=":
            result = left != right
        else:
            result = False
    except TypeError:
        result = False

    return (not result) if negate else result


class RouterAgent:
    """Pure rule-evaluation agent — no LLM call. Real, deterministic, auditable."""

    key = "router"
    input_schema = RouterInput
    output_schema = RouterOutput

    async def run(self, agent_input: RouterInput) -> RouterRunResult:
        start = time.perf_counter()
        rules = agent_input.decision_rules or DEFAULT_DECISION_RULES

        context = {
            "score": agent_input.composite_score,
            "weak_signal": agent_input.weak_signal,
            "follow_up_count": agent_input.follow_up_count,
            "questions_asked_count": agent_input.questions_asked_count,
            "max_questions": agent_input.max_questions,
            "min_questions": agent_input.min_questions,
        }

        # Guardrail: never ask more than one consecutive follow-up regardless
        # of admin rules — prevents the interview from stalling on one question.
        if context["follow_up_count"] >= 1:
            context_for_followup_guard = dict(context)
            decision = self._first_matching_rule(rules, context_for_followup_guard, skip_followup=True)
        else:
            decision = self._first_matching_rule(rules, context, skip_followup=False)

        # Guardrail: never end before the configured minimum question count
        # unless something is clearly broken (handled upstream by timeouts).
        if decision.action == "end" and context["questions_asked_count"] < context["min_questions"]:
            decision = RouterOutput(action="next_question", reason="Minimum question count not yet reached.")

        latency_ms = int((time.perf_counter() - start) * 1000)
        return RouterRunResult(output=decision, latency_ms=latency_ms)

    @staticmethod
    def _first_matching_rule(
        rules: list[dict[str, str]],
        context: dict[str, Any],
        *,
        skip_followup: bool,
    ) -> RouterOutput:
        for rule in rules:
            condition = rule.get("condition", "")
            action = rule.get("action", "")
            if action not in _VALID_ACTIONS:
                continue
            if skip_followup and action == "ask_followup":
                continue
            if _evaluate_condition(condition, context):
                return RouterOutput(action=action, reason=f"Matched rule: {condition} -> {action}")

        # No rule matched — sensible, real default rather than a random guess.
        return RouterOutput(action="next_question", reason="No configured rule matched; defaulting to next question.")
