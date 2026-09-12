"""
app/modules/metrics/engine.py
================================
The Metrics Engine (metrics.txt §5-6): turns raw, real per-turn
TurnEvaluation rows (produced by the Evaluator Agent's real LLM calls)
into session-level scores using plain, deterministic arithmetic --
NOT another LLM call. This is the "Correct way" metrics.txt insists on:

    LLM            = reasoning (per-turn judgment)
    Metrics Engine = scoring system (real aggregation, this file)
    Rules          = final normalisation

Platform-wide KPIs (DAU/MAU, completion rate, agent performance, ...) are
computed separately in app/modules/admin/analytics/ since they're driven by
SQL aggregation over many sessions rather than a single session's turns.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.db.models import InterviewTurn, TurnSpeaker

STAR_BONUS_POINTS = 10.0


@dataclass
class SessionScores:
    overall: Optional[float]
    communication: Optional[float]
    technical: Optional[float]
    behavioral: Optional[float]
    confidence: Optional[float]
    star_method: Optional[float]   # 0-100: percentage of answers that used STAR structure


def _avg(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


class MetricsEngine:
    """Stateless aggregator -- safe to instantiate once and reuse freely."""

    def compute_session_scores(self, turns: list[InterviewTurn]) -> SessionScores:
        evaluated = [
            t for t in turns
            if t.speaker == TurnSpeaker.CANDIDATE and t.evaluation is not None
        ]

        composite = [t.evaluation.composite_score for t in evaluated if t.evaluation.composite_score is not None]
        communication = [t.evaluation.communication for t in evaluated if t.evaluation.communication is not None]
        technical = [t.evaluation.technical_depth for t in evaluated if t.evaluation.technical_depth is not None]
        confidence = [t.evaluation.confidence for t in evaluated if t.evaluation.confidence is not None]

        behavioral_components: list[float] = []
        star_hits = 0
        for t in evaluated:
            ev = t.evaluation
            parts = [v for v in (ev.relevance, ev.clarity) if v is not None]
            if not parts:
                continue
            base = sum(parts) / len(parts)
            if ev.star_detected:
                base = min(100.0, base + STAR_BONUS_POINTS)
                star_hits += 1
            behavioral_components.append(base)

        star_method = round((star_hits / len(evaluated)) * 100, 1) if evaluated else None

        return SessionScores(
            overall=_avg(composite),
            communication=_avg(communication),
            technical=_avg(technical),
            behavioral=_avg(behavioral_components),
            confidence=_avg(confidence),
            star_method=star_method,
        )
