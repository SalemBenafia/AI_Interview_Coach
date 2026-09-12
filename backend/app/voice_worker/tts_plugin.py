"""
app/voice_worker/tts_plugin.py
=================================
A real `livekit.agents.tts.TTS` plugin that delegates to our own Piper TTS
microservice (app/modules/speech/pipeline.py). The microservice returns raw
16-bit PCM mono audio (the native PiperVoice output format), which we hand
straight to LiveKit's AudioEmitter with mime_type="audio/pcm" -- no
container decoding needed.
"""
from __future__ import annotations

import uuid

from livekit.agents import APIConnectOptions
from livekit.agents.tts import TTS, AudioEmitter, ChunkedStream, TTSCapabilities

from app.core.settings import settings
from app.modules.speech.pipeline import synthesize_speech

# Sample rate of the configured Piper voice (e.g. en_US-amy-medium = 22050Hz).
# Real value is also returned per-call by the TTS microservice; this default
# is only used before the first call completes.
DEFAULT_SAMPLE_RATE = 22050


class PiperServiceTTS(TTS):
    """Non-streaming TTS backed by the real Piper microservice."""

    def __init__(self, *, sample_rate: int = DEFAULT_SAMPLE_RATE) -> None:
        super().__init__(
            capabilities=TTSCapabilities(streaming=False),
            sample_rate=sample_rate,
            num_channels=1,
        )

    def synthesize(self, text: str, *, conn_options: APIConnectOptions) -> ChunkedStream:
        return _PiperChunkedStream(tts=self, input_text=text, conn_options=conn_options)


class _PiperChunkedStream(ChunkedStream):
    async def _run(self, output_emitter: AudioEmitter) -> None:
        result = await synthesize_speech(self.input_text, voice=settings.PIPER_VOICE)

        output_emitter.initialize(
            request_id=str(uuid.uuid4()),
            sample_rate=result.sample_rate,
            num_channels=1,
            mime_type="audio/pcm",
        )
        output_emitter.push(result.audio_bytes)
        output_emitter.flush()
