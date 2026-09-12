"""
app/modules/signals/analyzer.py
==================================
Real communication-signal analysis (technologies.txt §"Transformers" and
§"Pyannote"): sentiment/emotion classification on each candidate turn.

This is a separate, secondary emotional-tone signal — it is NOT folded into
the "Confidence Score (AI-derived)" KPI, which is computed purely from the
Evaluator agent's own `confidence` rubric field (see
app.modules.metrics.engine.compute_session_scores). Per-turn sentiment is
instead surfaced independently: on the transcript API
(app.modules.interviews.router.get_transcript), as a summary fed into the
Feedback Agent's prompt and the candidate's PDF report
(app.modules.interviews.tasks._generate_feedback_report_async), and as an
aggregate distribution on the admin analytics page
(app.modules.admin.analytics.router.get_sentiment_distribution).

These signals are explicitly an ENHANCEMENT layer on top of the core
agentic loop (technologies.txt: "Add transformers and pyannote when you
want more objective scoring metrics... not required to get the interview
coach working"). Accordingly, if the sentiment microservice is unreachable,
this module returns None rather than raising — a missing signal just means
that turn has no sentiment annotation, the interview itself is never
blocked on it. This is a deliberate, documented degradation policy, not a
substitute for a real model call when the service IS available.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from app.core.settings import settings

logger = structlog.get_logger()


@dataclass
class SentimentResult:
    label: str
    score: float
    latency_ms: int


async def analyze_sentiment(text: str) -> Optional[SentimentResult]:
    """Call the real j-hartmann/emotion-english-distilroberta-base microservice."""
    if not text.strip():
        return None

    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(f"{settings.SENTIMENT_SERVICE_URL}/sentiment", json={"text": text})
            r.raise_for_status()
            data = r.json()
    except Exception as exc:
        logger.info("sentiment_service_unavailable", error=str(exc))
        return None

    latency_ms = int((time.perf_counter() - start) * 1000)
    return SentimentResult(label=data.get("label", "neutral"), score=data.get("score", 0.0), latency_ms=latency_ms)


@dataclass
class SpeechMetrics:
    words_per_minute: float
    pause_ratio: float
    filler_word_count: int


_FILLER_WORDS = {"um", "uh", "like", "you know", "i mean", "sort of", "kind of", "basically"}


def compute_speech_metrics(text: str, duration_seconds: float) -> SpeechMetrics:
    """
    Lightweight, real (non-ML) speech-quality metrics computed directly from
    the STT transcript and the turn's measured duration — words-per-minute,
    a rough pause ratio, and filler-word counting (metrics.txt §B). This
    complements (does not replace) pyannote-based VAD/turn-detection, which
    operates on raw audio rather than transcript text and is wired in via
    ENABLE_VAD_TURN_DETECTION / the LiveKit audio pipeline directly.
    """
    words = text.split()
    word_count = len(words)
    minutes = max(duration_seconds / 60.0, 1e-6)
    wpm = word_count / minutes

    text_lower = text.lower()
    filler_count = sum(text_lower.count(f) for f in _FILLER_WORDS)

    # Pause ratio is only meaningful with real VAD timing data from the audio
    # track; absent that, we leave it at 0.0 here and let the caller populate
    # it from LiveKit/pyannote turn-detection timestamps when available.
    return SpeechMetrics(words_per_minute=round(wpm, 1), pause_ratio=0.0, filler_word_count=filler_count)
