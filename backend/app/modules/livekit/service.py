"""
app/modules/livekit/service.py
=================================
Real WebRTC session management via the official `livekit-api` Python SDK
(technologies.txt §2 -- "LiveKit (OSS): WebRTC SFU, real-time voice rooms,
recording + streaming, SDK for Next.js + Python").

Every token issued here is a genuine, signed LiveKit JWT -- there is no
mock/placeholder token path. The frontend uses the returned token directly
with `livekit-client`'s `Room.connect(LIVEKIT_URL, token)`.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

import structlog
from livekit import api

from app.core.settings import settings

logger = structlog.get_logger()


def generate_join_token(
    *,
    room_name: str,
    identity: str,
    display_name: str,
    can_publish: bool = True,
    can_subscribe: bool = True,
    ttl_seconds: Optional[int] = None,
) -> str:
    """
    Issue a real, signed LiveKit access token.

    can_publish=True / can_subscribe=True  -> the candidate (publishes mic audio,
        subscribes to the AI's synthesized voice track).
    can_publish=False / can_subscribe=True -> an admin "observer" token for live
        monitoring (roles.txt -> Admin -> Monitoring -> "Live interview sessions"),
        which can listen in without being able to speak into the room.
    """
    token = (
        api.AccessToken(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
        .with_identity(identity)
        .with_name(display_name)
        .with_ttl(timedelta(seconds=ttl_seconds or settings.LIVEKIT_TOKEN_TTL_SECONDS))
        .with_grants(api.VideoGrants(
            room_join=True,
            room=room_name,
            can_publish=can_publish,
            can_subscribe=can_subscribe,
            can_publish_data=True,
        ))
    )
    return token.to_jwt()


def get_room_service_client() -> api.LiveKitAPI:
    """Server-to-server LiveKit API client for room management (create/list/delete/egress)."""
    return api.LiveKitAPI(
        settings.LIVEKIT_HTTP_URL,
        settings.LIVEKIT_API_KEY,
        settings.LIVEKIT_API_SECRET,
    )


async def ensure_room(room_name: str, *, max_participants: int = 2, empty_timeout_seconds: int = 120) -> None:
    """Explicitly create the room ahead of time so we can set retention/timeout policy."""
    lkapi = get_room_service_client()
    try:
        await lkapi.room.create_room(
            api.CreateRoomRequest(
                name=room_name,
                empty_timeout=empty_timeout_seconds,
                max_participants=max_participants,
            )
        )
    finally:
        await lkapi.aclose()


async def end_room(room_name: str) -> None:
    """Force-close a room (e.g. when a candidate ends the interview early)."""
    lkapi = get_room_service_client()
    try:
        await lkapi.room.delete_room(api.DeleteRoomRequest(room=room_name))
    finally:
        await lkapi.aclose()


def verify_webhook(body: bytes, auth_header: str) -> api.WebhookEvent:
    """
    Verify and decode an incoming LiveKit webhook
    (https://docs.livekit.io -> Webhooks). Raises on signature mismatch.
    """
    token_verifier = api.TokenVerifier(settings.LIVEKIT_API_KEY, settings.LIVEKIT_API_SECRET)
    receiver = api.WebhookReceiver(token_verifier)
    return receiver.receive(body.decode("utf-8"), auth_header)
