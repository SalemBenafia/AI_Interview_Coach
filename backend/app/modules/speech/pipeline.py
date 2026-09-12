"""
app/modules/speech/pipeline.py
=================================
Real speech pipeline clients (technologies.txt §7):

  WebRTC audio (LiveKit) -> Whisper STT microservice -> text
  AI response text -> Piper TTS microservice -> audio -> WebRTC playback

Both microservices are real, separately-deployed FastAPI apps (see
/services/stt-service and /services/tts-service in the repo root) so that
heavy ML dependencies (ctranslate2, onnxruntime) never need to be installed
inside the main API container. There is no simulated transcription or
synthesized silence anywhere in this module: if a service is unreachable,
`SpeechServiceError` is raised and the caller must surface a real
connectivity error to the candidate (e.g. "having trouble hearing you,
please check your connection") rather than inventing a transcript.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from app.core.settings import settings

logger = structlog.get_logger()


class SpeechServiceError(RuntimeError):
    """Raised when the STT or TTS microservice is unreachable or errors."""


@dataclass
class STTResult:
    text: str
    language: str
    language_probability: float
    latency_ms: int


@dataclass
class TTSResult:
    audio_bytes: bytes
    content_type: str
    sample_rate: int
    latency_ms: int


async def transcribe_audio(
    audio_bytes: bytes,
    *,
    filename: str = "audio.wav",
    content_type: str = "audio/wav",
    language_hint: Optional[str] = None,
) -> STTResult:
    """
    POST the raw audio captured from the LiveKit room (already mixed down to
    a WAV/PCM segment by the WebRTC ingestion layer) to the real
    faster-whisper microservice.
    """
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            files = {"file": (filename, audio_bytes, content_type)}
            data = {"language": language_hint} if language_hint else {}
            r = await client.post(f"{settings.WHISPER_SERVICE_URL}/transcribe", files=files, data=data)
            r.raise_for_status()
            payload = r.json()
    except Exception as exc:
        raise SpeechServiceError(f"Whisper STT service at {settings.WHISPER_SERVICE_URL} failed: {exc}") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    return STTResult(
        text=payload.get("text", "").strip(),
        language=payload.get("language", "en"),
        language_probability=payload.get("language_probability", 0.0),
        latency_ms=latency_ms,
    )


async def synthesize_speech(
    text: str,
    *,
    voice: Optional[str] = None,
) -> TTSResult:
    """POST text to the real Piper TTS microservice; returns WAV audio bytes."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{settings.PIPER_TTS_URL}/synthesize",
                json={"text": text, "voice": voice or settings.PIPER_VOICE},
            )
            r.raise_for_status()
            audio_bytes = r.content
            content_type = r.headers.get("content-type", "audio/pcm")
            sample_rate = int(r.headers.get("x-sample-rate", "22050"))
    except Exception as exc:
        raise SpeechServiceError(f"Piper TTS service at {settings.PIPER_TTS_URL} failed: {exc}") from exc

    latency_ms = int((time.perf_counter() - start) * 1000)
    return TTSResult(audio_bytes=audio_bytes, content_type=content_type, sample_rate=sample_rate, latency_ms=latency_ms)
