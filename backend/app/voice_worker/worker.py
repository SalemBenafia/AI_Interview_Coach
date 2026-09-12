"""
app/voice_worker/worker.py
=============================
The real-time voice worker process (technologies.txt: "LiveKit (OSS): SDK
for Next.js + Python"; description.txt §A: "AI speaks and listens live...
natural interruption handling (barge-in support)").

This is a SEPARATE deployable process from the main FastAPI backend (see
the `voice-agent` service in docker-compose.yml). It connects to the
LiveKit server as a worker, and for every interview room created by
app/modules/interviews/router.py, it:

  1. Joins the room as the "ai-interviewer" participant.
  2. Wires up AgentSession with our own STT (Whisper), TTS (Piper), and a
     custom LLM plugin that is really just a bridge into our LangGraph
     turn engine (app/modules/agents/engine.py) -- see llm_plugin.py.
  3. Lets LiveKit Agents' built-in VAD + turn-detection handle barge-in,
     interruptions, and knowing when the candidate has finished speaking,
     while OUR agents make every actual interview decision.

Run with:
    python -m app.voice_worker.worker dev      # connects to a local LiveKit dev server
    python -m app.voice_worker.worker start    # production worker mode
"""
from __future__ import annotations

import asyncio
import contextlib
import re

import structlog
from livekit.agents import Agent, AgentSession, JobContext, WorkerOptions, cli

from app.core.settings import settings
from app.voice_worker.llm_plugin import InterviewEngineLLM
from app.voice_worker.stt_plugin import WhisperServiceSTT
from app.voice_worker.tts_plugin import PiperServiceTTS

logger = structlog.get_logger()

# Must match the room-naming convention used in
# app/modules/interviews/router.py when a session is created.
_ROOM_NAME_PATTERN = re.compile(r"^interview-(?P<session_id>[0-9a-fA-F-]{36})$")


def _extract_session_id(room_name: str) -> str:
    match = _ROOM_NAME_PATTERN.match(room_name)
    if not match:
        raise ValueError(
            f"Room name '{room_name}' does not match the expected 'interview-<session-uuid>' pattern."
        )
    return match.group("session_id")


async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()

    session_id = _extract_session_id(ctx.room.name)
    logger.info("voice_worker_joining_room", room=ctx.room.name, session_id=session_id)

    agent_session = AgentSession(
        stt=WhisperServiceSTT(),
        llm=InterviewEngineLLM(session_id=session_id),
        tts=PiperServiceTTS(),
        allow_interruptions=True,   # description.txt: "natural interruption handling (barge-in)"
    )

    interviewer = Agent(
        instructions=(
            "You are conducting a live, real-time mock interview. Speak naturally and "
            "wait for the candidate to respond before continuing."
        ),
    )

    await agent_session.start(interviewer, room=ctx.room)

    # Trigger the opening turn: our LLM plugin sees an empty chat context and
    # calls engine.start_session() for the real first question.
    await agent_session.generate_reply()

    # Keep the entrypoint alive for the room's lifetime.
    # Without this the function returns immediately after the opening reply
    # and the agent disconnects — the candidate never hears anything and
    # subsequent turns cannot be processed.
    # The job framework cancels this task when the room ends (all
    # participants leave or the interview is ended via the REST API).
    disconnect_ev = asyncio.Event()
    ctx.room.on("disconnected", lambda *_: disconnect_ev.set())
    with contextlib.suppress(asyncio.CancelledError):
        await disconnect_ev.wait()


def main() -> None:
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            ws_url=settings.LIVEKIT_URL,
            api_key=settings.LIVEKIT_API_KEY,
            api_secret=settings.LIVEKIT_API_SECRET,
            # The parent process alone uses ~240 MB. With num_idle_processes>0
            # a second Python process is pre-spawned immediately, pushing
            # usage past the container limit. Set to 0: subprocesses are
            # spawned on demand when a room is joined (slight first-join
            # latency, but avoids constant OOM kills at idle).
            num_idle_processes=0,
            # Give the forkserver subprocess 30 s to finish importing
            # LangGraph + SQLAlchemy on a busy 2-core machine.
            initialize_process_timeout=30.0,
            # Default CPU-load threshold is 0.65. During child-process
            # initialisation (import of LangGraph + SQLAlchemy takes ~2–4 s)
            # the load spikes above 0.65, causing the worker to refuse new job
            # requests with "no servers available". That leaves the new room
            # without an agent for the entire session.
            # 0.85 keeps rejection rare while still protecting against genuine
            # sustained overload.
            load_threshold=0.85,
        )
    )


if __name__ == "__main__":
    main()
