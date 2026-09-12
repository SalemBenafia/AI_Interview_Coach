"""
services/stt-service/main.py
===============================
Real speech-to-text microservice wrapping faster-whisper
(technologies.txt §7 -- "Speech-to-Text (STT): Whisper (open-source)").

Deployed as its own container so the heavy CTranslate2/Whisper model
weights and runtime never need to live inside the main API image. The main
backend talks to this service exclusively over HTTP -- see
backend/app/modules/speech/pipeline.py.

Run directly:
    uvicorn main:app --host 0.0.0.0 --port 9001

Model size/device/compute type are configured via environment variables so
the same image works on a CPU-only dev box (int8) or a GPU production node
(float16) -- see the Dockerfile and docker-compose.yml for the two profiles.
"""
from __future__ import annotations

import ctypes
import gc
import os
import tempfile
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel

WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
# beam_size=1 (greedy decode) on CPU: same accuracy for short utterances,
# ~5× less compute than the old default of 5.
WHISPER_BEAM_SIZE = int(os.environ.get("WHISPER_BEAM_SIZE", "1"))
# Leave one logical thread free for the event loop and OS scheduler.
WHISPER_CPU_THREADS = int(os.environ.get("WHISPER_CPU_THREADS", "1"))

_model: Optional[WhisperModel] = None

# CTranslate2 (faster-whisper's C++ backend) uses the system allocator on
# Linux. After inference its freed buffers sit in glibc's free-list — they
# count as RSS but are never returned to the OS. Without explicit trimming
# the process leaks ~70–100 MB per transcription call and is OOM-killed
# (exit 137) after only a handful of requests.
# malloc_trim(0) is a glibc extension that flushes the top-of-heap free pages
# back to the OS immediately. We call it after every inference to keep RSS
# stable across the life of the container.
try:
    _libc = ctypes.cdll.LoadLibrary("libc.so.6")
    _HAS_MALLOC_TRIM = True
except Exception:
    _HAS_MALLOC_TRIM = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    _model = WhisperModel(
        WHISPER_MODEL_SIZE,
        device=WHISPER_DEVICE,
        compute_type=WHISPER_COMPUTE_TYPE,
        cpu_threads=WHISPER_CPU_THREADS,
        num_workers=1,
    )
    yield
    _model = None


app = FastAPI(title="AI Interview Coach - STT Service", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "model": WHISPER_MODEL_SIZE, "device": WHISPER_DEVICE}


@app.post("/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: Optional[str] = Form(default=None),
):
    """
    Accepts a WAV file (the candidate's spoken turn, already mixed down by
    the voice worker / LiveKit room) and returns a real faster-whisper
    transcription. No simulated or cached transcripts -- every call runs
    actual inference.
    """
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet.")

    suffix = os.path.splitext(file.filename or "audio.wav")[1] or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
        contents = await file.read()
        tmp.write(contents)
        tmp.flush()

        try:
            segments, info = _model.transcribe(
                tmp.name,
                language=language if language else None,
                beam_size=WHISPER_BEAM_SIZE,
                vad_filter=True,
            )
            text = " ".join(segment.text.strip() for segment in segments).strip()
        except ValueError:
            # vad_filter removed all audio (silence / pure noise). faster-whisper
            # then calls max() over an empty language-probability sequence → ValueError.
            # Return empty text (200, not 500) so the voice agent treats this chunk
            # as silence instead of closing the session as "unrecoverable".
            text = ""
            info = None

    # Reclaim CTranslate2's freed inference buffers so RSS stays flat across
    # requests. gc.collect() handles Python-level objects; malloc_trim(0) tells
    # glibc to return the top-of-heap free pages to the OS.
    gc.collect()
    if _HAS_MALLOC_TRIM:
        _libc.malloc_trim(0)

    return JSONResponse({
        "text": text,
        "language": info.language if info else "en",
        "language_probability": info.language_probability if info else 0.0,
    })
