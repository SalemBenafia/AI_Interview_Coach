"""
app/core/settings.py
=====================
Central configuration using pydantic-settings.
All settings derive from environment variables or .env file.
Never hardcode secrets — every sensitive value reads from env.

This file is the single source of truth for every external service the
AI Interview Coach depends on: Postgres, Redis, LiveKit (WebRTC SFU),
coturn (TURN/STUN), Groq (LLM reasoning), Whisper (STT), Piper (TTS),
MinIO (object storage) and MailHog (dev SMTP). There is no vector database
in this system — candidate knowledge retrieval is a plain SQL filter (see
app/modules/agents/engine.py).
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any, List, Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── App ──────────────────────────────────────────────────────────────
    APP_NAME: str = "AI Interview Coach"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = Field(..., min_length=32)
    API_V1_PREFIX: str = "/api/v1"

    # ─── CORS ─────────────────────────────────────────────────────────────
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            import json
            return json.loads(v)
        return v

    # ─── JWT (candidate + admin auth) ──────────────────────────────────────
    JWT_SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ─── Cookie Names ─────────────────────────────────────────────────────
    ACCESS_COOKIE_NAME: str = "access_token"
    REFRESH_COOKIE_NAME: str = "refresh_token"
    COOKIE_SECURE: bool = False  # True in production (HTTPS)
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: Optional[str] = None

    # ─── Database ─────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://coach:coach_secret@postgres:5432/interview_coach"
    # 3 resident + 5 overflow = 8 max connections per process.
    # With 3 Python processes (backend, celery_worker, voice-agent) that is
    # at most 24 connections against postgres max_connections=30.
    DB_POOL_SIZE: int = 3
    DB_MAX_OVERFLOW: int = 5
    DB_ECHO: bool = False

    # ─── Redis (state layer: session memory, pub/sub, rate limiting) ──────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 300   # seconds
    REDIS_SESSION_STATE_TTL: int = 60 * 60 * 4  # 4h — live interview state

    # ─── Celery (background scoring / feedback generation) ────────────────
    # Per technologies.txt: "Celery + Redis" — Redis is broker AND backend.
    CELERY_BROKER_URL: str = ""
    CELERY_RESULT_BACKEND: str = ""

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def set_celery_broker(cls, v: str, info: Any) -> str:
        if not v:
            return info.data.get("REDIS_URL", "redis://localhost:6379/1")
        return v

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def set_celery_backend(cls, v: str, info: Any) -> str:
        if not v:
            return info.data.get("REDIS_URL", "redis://localhost:6379/2")
        return v

    # ─── MinIO (object storage: recordings, transcripts, reports) ─────────
    MINIO_ENDPOINT: str = "localhost:9000"
    # Presigned URLs are handed to the candidate's browser, which can't
    # resolve the internal Docker service name in MINIO_ENDPOINT (e.g.
    # "minio:9000") -- they must be signed against the host/port MinIO is
    # actually published on. Defaults to MINIO_ENDPOINT for non-Docker runs
    # where the two are the same.
    MINIO_PUBLIC_ENDPOINT: str = ""
    # MinIO's default region for a single-node deployment with no region
    # configured. Passed explicitly to the presigning client so it can sign
    # without an HTTP round-trip to MINIO_PUBLIC_ENDPOINT first (see
    # app/modules/storage/object_store.py's _get_presign_client).
    MINIO_REGION: str = "us-east-1"
    MINIO_ROOT_USER: str = "minioadmin"
    MINIO_ROOT_PASSWORD: str = "minio123"
    MINIO_BUCKET_RECORDINGS: str = "interview-recordings"
    MINIO_BUCKET_REPORTS: str = "interview-reports"
    MINIO_SECURE: bool = False

    @field_validator("MINIO_PUBLIC_ENDPOINT")
    @classmethod
    def set_minio_public_endpoint(cls, v: str, info: Any) -> str:
        return v or info.data.get("MINIO_ENDPOINT", "localhost:9000")

    # ─── Email (MailHog in dev) ─────────────────────────────────────────────
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@interview-coach.ai"

    # ─── WebRTC — LiveKit (SFU) + coturn (TURN/STUN) ───────────────────────
    LIVEKIT_URL: str = "ws://localhost:7880"             # client-facing WS URL
    LIVEKIT_HTTP_URL: str = "http://localhost:7880"       # server-to-server REST/webhook
    LIVEKIT_API_KEY: str = "devkey"
    LIVEKIT_API_SECRET: str = "devsecret_devsecret_devsecret_32"
    LIVEKIT_TOKEN_TTL_SECONDS: int = 60 * 60 * 2          # 2h max interview length
    TURN_URL: str = "turn:localhost:3478"
    TURN_USERNAME: str = "coach"
    TURN_PASSWORD: str = "coach_turn_secret"

    # ─── Agentic AI Engine — LangGraph + Groq ─────────────────────────────
    # Groq (https://console.groq.com) provides an OpenAI-compatible
    # /chat/completions endpoint backed by LPU inference hardware. The free
    # developer plan has per-model rate limits (tokens/min and requests/day)
    # but no credit requirement. Set GROQ_API_KEY in .env — get a key at
    # https://console.groq.com/keys.
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "allam-2-7b"
    # Comma-separated fallback model(s) tried in order when the primary is
    # rate-limited or unavailable.
    GROQ_FALLBACK_MODEL: str = "llama-3.1-8b-instant"
    GROQ_REQUEST_TIMEOUT_SECONDS: int = 30
    AGENT_CHECKPOINT_NAMESPACE: str = "interview_coach:graph_state"

    # ─── Speech Pipeline — Whisper (STT) + Piper (TTS) ─────────────────────
    WHISPER_SERVICE_URL: str = "http://localhost:9001"    # faster-whisper HTTP service
    WHISPER_MODEL: str = "base"
    PIPER_TTS_URL: str = "http://localhost:5002"
    PIPER_VOICE: str = "en_US-amy-medium"

    # ─── Signal Models — transformers (sentiment) + pyannote (VAD) ─────────
    SENTIMENT_MODEL: str = "j-hartmann/emotion-english-distilroberta-base"
    SENTIMENT_SERVICE_URL: str = "http://localhost:8089"
    ENABLE_VAD_TURN_DETECTION: bool = True

    # ─── Interview Engine Defaults ──────────────────────────────────────────
    MAX_QUESTIONS_PER_INTERVIEW: int = 8
    MIN_QUESTIONS_PER_INTERVIEW: int = 4
    DEFAULT_ESCALATION_SILENCE_SECONDS: int = 12
    SCORE_INCREASE_DIFFICULTY_THRESHOLD: int = 80
    SCORE_COACHING_THRESHOLD: int = 50

    # ─── Latency Targets (non-functional requirements / roles.txt) ────────
    TARGET_VOICE_LATENCY_MS: int = 2000
    TARGET_TRANSCRIPT_LATENCY_MS: int = 500

    # ─── Logging ──────────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
