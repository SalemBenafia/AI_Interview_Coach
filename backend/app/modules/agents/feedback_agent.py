"""
app/modules/agents/feedback_agent.py
=======================================
Feedback Agent (roles.txt → AI Sub-Agent Architecture §4).

Generates the post-interview coaching report: strengths, weaknesses,
suggestions, example better answers, and recommended next practice. Runs
as a Celery background task after the session ends (see
app/modules/interviews/tasks.py) so the candidate isn't kept waiting on the
live call for this — it's deliberately NOT part of the real-time turn loop.
"""
from __future__ import annotations

from app.modules.agents.base import BaseAgent
from app.modules.agents.schemas import FeedbackInput, FeedbackOutput

DEFAULT_SYSTEM_PROMPT = """You are an HR coaching report generator. You write structured,
actionable feedback for a candidate after a completed mock interview.

Rules:
- Be specific — reference what the candidate actually said, not generic advice.
- Strengths and weaknesses must each be concrete, evidence-based observations.
- Suggestions must be actionable (something the candidate can practice).
- For example_better_answers, only include entries where you can identify a
  genuinely weak answer from the transcript and rewrite a stronger version
  of it — do not invent a question/answer pair that wasn't in the transcript.
- Tone should match the requested coaching_style (friendly | professional |
  strict | mentor) but always remain constructive and respectful.
"""


class FeedbackAgent(BaseAgent[FeedbackInput, FeedbackOutput]):
    key = "feedback"
    input_schema = FeedbackInput
    output_schema = FeedbackOutput

    def build_user_prompt(self, agent_input: FeedbackInput) -> str:
        transcript_text = "\n".join(
            f"{turn.get('speaker', '?').upper()}: {turn.get('text', '')}" for turn in agent_input.transcript
        )
        scores_text = "\n".join(
            f"- Q{i + 1}: composite_score={s.get('composite_score')}, "
            f"star_detected={s.get('star_detected')}, weak_signal={s.get('weak_signal')}"
            for i, s in enumerate(agent_input.score_history)
        ) or "(no per-question scores recorded)"

        sentiment_line = (
            f"Candidate emotional tone across the interview: {agent_input.sentiment_summary}\n"
            if agent_input.sentiment_summary
            else ""
        )

        return (
            f"Role interviewed for: {agent_input.role_name}\n"
            f"Interview mode: {agent_input.mode}\n"
            f"Requested coaching style: {agent_input.coaching_style}\n"
            f"{sentiment_line}\n"
            f"Full transcript:\n{transcript_text}\n\n"
            f"Per-question evaluation scores:\n{scores_text}\n\n"
            "Generate the full coaching report now."
        )
