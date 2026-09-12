"""
app/voice_worker/stt_plugin.py
=================================
A real `livekit.agents.stt.STT` plugin that delegates to our own
faster-whisper microservice (app/modules/speech/pipeline.py) instead of a
third-party STT provider. This is what lets the LiveKit Agents framework's
audio pipeline (VAD -> STT -> LLM -> TTS) use OUR self-hosted Whisper
deployment, per technologies.txt's OSS-only stack.
"""
from __future__ import annotations

from livekit import rtc
from livekit.agents import NOT_GIVEN, APIConnectOptions, NotGivenOr
from livekit.agents.stt import (
    STT,
    SpeechData,
    SpeechEvent,
    SpeechEventType,
    STTCapabilities,
)
from livekit.agents.utils import AudioBuffer

from app.modules.speech.pipeline import SpeechServiceError, transcribe_audio


class WhisperServiceSTT(STT):
    """Non-streaming (offline) STT backed by the real Whisper microservice."""

    def __init__(self) -> None:
        super().__init__(
            capabilities=STTCapabilities(streaming=False, interim_results=False, offline_recognize=True)
        )

    async def _recognize_impl(
        self,
        buffer: AudioBuffer,
        *,
        language: NotGivenOr[str] = NOT_GIVEN,
        conn_options: APIConnectOptions,
    ) -> SpeechEvent:
        frame = rtc.combine_audio_frames(buffer)
        wav_bytes = frame.to_wav_bytes()

        try:
            result = await transcribe_audio(
                wav_bytes,
                language_hint=language if isinstance(language, str) else None,
            )
        except SpeechServiceError as exc:
            # Return an empty transcript rather than re-raising. Re-raising
            # causes livekit-agents to close the AgentSession as "unrecoverable"
            # which ends the entire interview. An empty transcript is treated as
            # silence — the candidate can speak again and the session continues.
            from structlog import get_logger as _glog
            _glog().warning("stt_error_returning_empty", error=str(exc))
            return SpeechEvent(
                type=SpeechEventType.FINAL_TRANSCRIPT,
                alternatives=[SpeechData(language="en", text="", confidence=0.0)],
            )

        return SpeechEvent(
            type=SpeechEventType.FINAL_TRANSCRIPT,
            alternatives=[
                SpeechData(
                    language=result.language,
                    text=result.text,
                    confidence=result.language_probability,
                )
            ],
        )
