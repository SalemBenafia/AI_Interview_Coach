"""
app/modules/agents/coach_agent.py
====================================
Coach Agent — powers "Live Coaching Mode" (description.txt §D): short,
actionable hints surfaced to the candidate mid-interview (disabled by
default for interview realism; the candidate opts in during practice setup).
"""
from __future__ import annotations

from app.modules.agents.base import BaseAgent
from app.modules.agents.schemas import CoachInput, CoachOutput

DEFAULT_SYSTEM_PROMPT = """You generate ONE short, actionable coaching hint (max 20 words) for a
candidate currently answering a mock interview question out loud.

Rules:
- The hint must be immediately actionable (e.g. "Try the STAR method",
  "Add a measurable result", "Be specific about your role").
- Never give away a "correct answer" — only structural/communication guidance.
- Keep it to one short sentence.
"""


class CoachAgent(BaseAgent[CoachInput, CoachOutput]):
    key = "coach"
    input_schema = CoachInput
    output_schema = CoachOutput

    def build_user_prompt(self, agent_input: CoachInput) -> str:
        lines = [f"Current question: \"{agent_input.question}\""]
        if agent_input.last_answer:
            lines.append(f"What the candidate has said so far: \"{agent_input.last_answer}\"")
        if agent_input.weak_signal:
            lines.append("Signal: the candidate's answer so far looks vague or unstructured.")
        lines.append("Generate one short coaching hint now.")
        return "\n".join(lines)
