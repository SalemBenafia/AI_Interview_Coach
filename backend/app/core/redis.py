"""
app/core/redis.py
==================
Redis async client singleton.

Redis is the "memory + state layer" described in technologies.txt:
* live interview state (conversation memory the agent graph reads/writes)
* LangGraph-style checkpoints, keyed per session
* pub/sub for real-time events consumed by the WebSocket layer
* simple rate limiting / session locking
"""
from __future__ import annotations

import json
from typing import Any, Optional

import redis.asyncio as aioredis

from app.core.settings import settings

_redis_client: Optional[aioredis.Redis] = None  # type: ignore[type-arg]


def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return the shared Redis client, creating it if needed."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
            health_check_interval=30,
        )
    return _redis_client


async def close_redis() -> None:
    global _redis_client
    if _redis_client:
        await _redis_client.aclose()
        _redis_client = None


# ─── Generic cache helpers ─────────────────────────────────────────────────────

async def cache_get(key: str) -> Any:
    client = get_redis()
    value = await client.get(key)
    if value is None:
        return None
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return value


async def cache_set(key: str, value: Any, ttl: int = settings.REDIS_CACHE_TTL) -> None:
    client = get_redis()
    serialized = json.dumps(value) if not isinstance(value, str) else value
    await client.setex(key, ttl, serialized)


async def cache_delete(key: str) -> None:
    client = get_redis()
    await client.delete(key)


async def cache_delete_pattern(pattern: str) -> None:
    client = get_redis()
    keys = await client.keys(pattern)
    if keys:
        await client.delete(*keys)


# ─── Interview session state (agent graph "memory") ───────────────────────────
#
# Key layout:
#   interview:{session_id}:state    -> JSON-serialised InterviewState (graph checkpoint)
#   interview:{session_id}:lock     -> short-lived lock to avoid concurrent turn processing
#
# This is intentionally a thin convenience wrapper. The graph engine
# (app/modules/agents/engine.py) is the only caller that should write here;
# everything else should go through the InterviewSession row in Postgres for
# anything that needs to survive a Redis flush.

def _state_key(session_id: str) -> str:
    return f"{settings.AGENT_CHECKPOINT_NAMESPACE}:{session_id}"


def _lock_key(session_id: str) -> str:
    return f"interview:{session_id}:lock"


async def get_session_state(session_id: str) -> Optional[dict]:
    return await cache_get(_state_key(session_id))


async def set_session_state(session_id: str, state: dict) -> None:
    await cache_set(_state_key(session_id), state, ttl=settings.REDIS_SESSION_STATE_TTL)


async def delete_session_state(session_id: str) -> None:
    await cache_delete(_state_key(session_id))


async def acquire_turn_lock(session_id: str, ttl_seconds: int = 30) -> bool:
    """Best-effort lock so two turns for the same session never overlap."""
    client = get_redis()
    return bool(await client.set(_lock_key(session_id), "1", nx=True, ex=ttl_seconds))


async def release_turn_lock(session_id: str) -> None:
    await cache_delete(_lock_key(session_id))


# ─── Pub/Sub helpers (bridges agent engine -> WebSocket connection manager) ────

def event_channel(session_id: str) -> str:
    return f"interview:{session_id}:events"


async def publish_event(session_id: str, payload: dict) -> None:
    client = get_redis()
    await client.publish(event_channel(session_id), json.dumps(payload))
