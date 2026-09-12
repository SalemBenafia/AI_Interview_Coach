"""
app/modules/ws/router.py
===========================
Live transcript / turn-event stream for the browser UI
(roles.txt -> User -> During Interview -> "View optional live transcript").

This is intentionally SEPARATE from the WebRTC audio path (LiveKit handles
the actual voice). The voice worker (app/voice_worker/) drives the real
conversation and publishes every turn's text to a real Redis pub/sub
channel (app/core/redis.py: publish_event); this router fans those events
out to any connected browser tabs so the frontend can render captions,
score updates, and "interview ended" transitions without polling.

AUTH NOTE: the access token is read from the same HttpOnly cookie used by
every REST endpoint (app/modules/auth/jwt.py) -- browsers include
SameSite=Lax cookies on same-site WebSocket handshake requests
automatically, so the frontend never needs to read or pass the JWT itself.
"""
from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select

from app.core.redis import event_channel, get_redis
from app.core.settings import settings
from app.db.session import AsyncSessionLocal
from app.modules.auth.jwt import TokenClaims, decode_token

logger = structlog.get_logger()
router = APIRouter(tags=["WebSocket"])


def _get_access_token(websocket: WebSocket) -> str | None:
    return websocket.cookies.get(settings.ACCESS_COOKIE_NAME)


async def _authorized_candidate_id(session_id: str, access_token: str) -> str | None:
    try:
        payload = decode_token(access_token)
    except Exception:
        return None
    if payload.get("type") != "access" or payload.get(TokenClaims.PRINCIPAL_TYPE) != "candidate":
        return None

    candidate_id = payload.get(TokenClaims.PRINCIPAL_ID)
    from app.db.models import InterviewSession

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(InterviewSession.id).where(
                InterviewSession.id == uuid.UUID(session_id),
                InterviewSession.candidate_id == uuid.UUID(candidate_id),
            )
        )
        if result.scalar_one_or_none() is None:
            return None
    return candidate_id


@router.websocket("/ws/interview/{session_id}")
async def interview_events_ws(websocket: WebSocket, session_id: str):
    """
    Client connects: ws://localhost:8000/ws/interview/{session_id}
    Receives: {"type": "ai_turn", "text": ..., "hint": ..., "should_end": ...}
          or: {"type": "candidate_turn", "text": ...} (the candidate's own
              STT transcript, broadcast right before the ai_turn it triggered)
    """
    access_token = _get_access_token(websocket)
    candidate_id = await _authorized_candidate_id(session_id, access_token) if access_token else None
    if candidate_id is None:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(event_channel(session_id))

    async def forward_redis_events() -> None:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                await websocket.send_text(message["data"])
            except Exception:
                break

    async def heartbeat() -> None:
        while True:
            await asyncio.sleep(20)
            try:
                await websocket.send_text(json.dumps({"type": "heartbeat"}))
            except Exception:
                break

    forward_task = asyncio.create_task(forward_redis_events())
    heartbeat_task = asyncio.create_task(heartbeat())

    try:
        await websocket.send_text(json.dumps({"type": "connected", "session_id": session_id}))
        while True:
            # We don't expect meaningful client->server messages on this
            # channel (the real audio goes over LiveKit) -- just drain pings.
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        forward_task.cancel()
        heartbeat_task.cancel()
        await pubsub.unsubscribe(event_channel(session_id))
        await pubsub.aclose()


@router.websocket("/ws/admin/monitoring/{session_id}")
async def admin_monitoring_ws(websocket: WebSocket, session_id: str):
    """Read-only live monitoring feed for admins (roles.txt -> Admin -> Monitoring -> Live interview sessions)."""
    access_token = _get_access_token(websocket)
    if not access_token:
        await websocket.close(code=4401)
        return
    try:
        payload = decode_token(access_token)
    except Exception:
        await websocket.close(code=4401)
        return
    if payload.get("type") != "access" or payload.get(TokenClaims.PRINCIPAL_TYPE) != "admin":
        await websocket.close(code=4403)
        return

    await websocket.accept()
    redis_client = get_redis()
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(event_channel(session_id))

    try:
        await websocket.send_text(json.dumps({"type": "connected", "session_id": session_id}))
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(event_channel(session_id))
        await pubsub.aclose()
