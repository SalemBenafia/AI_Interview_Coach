"""
app/modules/agents/evaluator_agent.py
========================================
Evaluator Agent (roles.txt → AI Sub-Agent Architecture §2).

Scores: relevance, clarity, communication, technical depth, problem-solving,
confidence indicators, and STAR-method usage. Results are stored verbatim
in TurnEvaluation rows — see app/modules/metrics/engine.py for how raw
per-turn scores roll up into session-level scores (metrics.txt §6: "LLM =
reasoning, Metrics Engine = scoring system").
"""
from __future__ import annotations

from app.modules.agents.base import BaseAgent
from app.modules.agents.schemas import EvaluatorInput, EvaluatorOutput

DEFAULT_SYSTEM_PROMPT = """You are an objective interview answer evaluator. You are NOT talking to
the candidate — you are scoring a transcript for an internal evaluation system.

Evaluate the candidate's answer strictly on its merits:
- Do not reward verbosity for its own sake.
- Do not be swayed by confident-sounding language if the content is weak.
- Detect whether the answer follows the STAR method (Situation, Task, Action,
  Result) when relevant to the question type.
- A "weak_signal" is true when the answer is vague, off-topic, far too short
  to be substantive, or fails to answer what was asked.
- Score every dimension from 0 to 100.
- composite_score should be a weighted aggregate using the provided rubric
  weights (if no rubric is provided, weight all dimensions equally).

star_components must be EXACTLY this shape — four boolean flags, lowercase
keys, no explanations or extra keys:
{"situation": true/false, "task": true/false, "action": true/false, "result": true/false}
Any reasoning about WHY belongs in "notes", not inside star_components.
"""


class EvaluatorAgent(BaseAgent[EvaluatorInput, EvaluatorOutput]):
    key = "evaluator"
    input_schema = EvaluatorInput
    output_schema = EvaluatorOutput

    def build_user_prompt(self, agent_input: EvaluatorInput) -> str:
        rubric_text = (
            "\n".join(f"- {r.get('label', r.get('key'))}: weight {r.get('weight')}" for r in agent_input.rubric)
            if agent_input.rubric
            else "(no custom rubric configured — weight all dimensions equally)"
        )
        return (
            f"Role: {agent_input.role_name}\n"
            f"Interview mode: {agent_input.mode}\n"
            f"Difficulty: {agent_input.difficulty}\n\n"
            f"Question asked:\n\"{agent_input.question}\"\n\n"
            f"Candidate's answer (verbatim transcript):\n\"{agent_input.answer}\"\n\n"
            f"Scoring rubric:\n{rubric_text}\n\n"
            "Evaluate this answer now."
        )
