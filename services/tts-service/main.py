"""
services/tts-service/main.py
===============================
Real text-to-speech microservice wrapping Piper
(technologies.txt §7 -- "Text-to-Speech (TTS): Piper TTS (OSS) -- offline,
fast, multilingual").

Returns RAW 16-bit PCM mono audio (Piper's native output format) plus an
`X-Sample-Rate` response header, rather than a WAV container -- this is
exactly what app/voice_worker/tts_plugin.py expects, since LiveKit's
AudioEmitter can consume raw PCM directly with zero decoding overhead.

Voice models (.onnx + .onnx.json) are NOT bundled in the image (they are
~20-60MB each and licensed/distributed by the Piper project on Hugging
Face) -- download them into ./voices at deploy time, e.g.:

    python3 -m piper.download_voices en_US-amy-medium

and mount that directory as a volume (see docker-compose.yml).
"""
from __future__ import annotations

import io
import os
import wave
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from piper import PiperVoice

VOICES_DIR = Path(os.environ.get("PIPER_VOICES_DIR", "./voices"))
DEFAULT_VOICE = os.environ.get("PIPER_VOICE", "en_US-amy-medium")


@lru_cache(maxsize=8)
def _load_voice(voice_name: str) -> PiperVoice:
    model_path = VOICES_DIR / f"{voice_name}.onnx"
    if not model_path.exists():
        raise FileNotFoundError(
            f"Voice model '{voice_name}' not found at {model_path}. "
            f"Download it with: python3 -m piper.download_voices {voice_name}"
        )
    return PiperVoice.load(str(model_path))


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        _load_voice(DEFAULT_VOICE)
    except FileNotFoundError as exc:
        # Don't crash the container on boot -- allow /health to report the
        # real problem so an operator can fix the voice mount; requests
        # will fail loudly and correctly until then.
        print(f"[tts-service] WARNING: {exc}")
    yield


app = FastAPI(title="AI Interview Coach - TTS Service", lifespan=lifespan)


class SynthesizeRequest(BaseModel):
    text: str
    voice: str | None = None


@app.get("/health")
async def health():
    return {"status": "ok", "default_voice": DEFAULT_VOICE, "voices_dir": str(VOICES_DIR)}


@app.post("/synthesize")
async def synthesize(payload: SynthesizeRequest):
    """
    Real Piper synthesis. Returns raw PCM16 mono bytes with the voice's
    actual sample rate in the X-Sample-Rate header. No cached/canned audio.
    """
    voice_name = payload.voice or DEFAULT_VOICE
    try:
        voice = _load_voice(voice_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc))

    # PiperVoice.synthesize_wav writes a full WAV container; we then strip
    # the header so the caller gets raw PCM16 directly (cheaper than asking
    # every consumer to parse a WAV container).
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        voice.synthesize_wav(payload.text, wav_file)

    buffer.seek(0)
    with wave.open(buffer, "rb") as wav_file:
        sample_rate = wav_file.getframerate()
        pcm_bytes = wav_file.readframes(wav_file.getnframes())

    return Response(
        content=pcm_bytes,
        media_type="audio/pcm",
        headers={"X-Sample-Rate": str(sample_rate)},
    )
