"""
app/voice_worker/llm_plugin.py
=================================
A real `livekit.agents.llm.LLM` plugin that does NOT call a third-party
model. Instead, its `chat()` implementation is the bridge into OUR actual
agentic brain: every time LiveKit Agents' VAD + turn-detection decides the
candidate has finished speaking, it calls this plugin with the updated
chat context; we pull the candidate's just-transcribed answer out of it and
hand it straight to `app.modules.agents.engine.submit_answer()` -- the same
real LangGraph turn graph used by the WebSocket/REST fallback path (see
app/modules/ws/router.py). This way LiveKit Agents supplies the audio
plumbing (VAD, barge-in/interruptions, turn detection) while our own
Evaluator/Router/Interviewer/Coach agents remain the single source of truth
for interview decisions, exactly as designed in app/modules/agents/.
"""
from __future__ import annotations

import uuid

import structlog
from livekit.agents import APIConnectOptions
from livekit.agents.llm import LLM, ChatChunk, ChatContext, ChoiceDelta, FunctionTool, LLMStream, ToolChoice
from livekit.agents.types import NOT_GIVEN, NotGivenOr

from app.db.session import get_db_context
from app.modules.agents.engine import InterviewEngineError, start_session, submit_answer

logger = structlog.get_logger()


class InterviewEngineLLM(LLM):
    """
    `session_id` is bound when the voice worker's entrypoint creates this
    plugin for a specific room/session -- see app/voice_worker/worker.py.
    """

    def __init__(self, *, session_id: str) -> None:
        super().__init__()
        self.session_id = session_id

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool] | None = None,
        conn_options: APIConnectOptions,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict] = NOT_GIVEN,
    ) -> LLMStream:
        return _InterviewLLMStream(
            llm=self,
            chat_ctx=chat_ctx,
            tools=tools or [],
            conn_options=conn_options,
            session_id=self.session_id,
        )


class _InterviewLLMStream(LLMStream):
    def __init__(self, *, llm: InterviewEngineLLM, chat_ctx, tools, conn_options, session_id: str) -> None:
        super().__init__(llm, chat_ctx=chat_ctx, tools=tools, conn_options=conn_options)
        self._session_id = session_id

    async def _run(self) -> None:
        messages = self._chat_ctx.messages()
        last_user_text = ""
        for message in reversed(messages):
            if message.role == "user" and message.text_content:
                last_user_text = message.text_content
                break

        async with get_db_context() as db:
            from sqlalchemy import select
            from sqlalchemy.orm import selectinload

            from app.db.models import InterviewSession

            result = await db.execute(
                select(InterviewSession)
                .where(InterviewSession.id == uuid.UUID(self._session_id))
                .options(selectinload(InterviewSession.flow), selectinload(InterviewSession.target_role))
            )
            session = result.scalar_one_or_none()
            if not session:
                logger.error("voice_worker_session_missing", session_id=self._session_id)
                self._event_ch.send_nowait(_text_chunk(
                    "I'm sorry, I lost track of this interview session. Let's reconnect."
                ))
                return

            from app.db.models import SessionStatus

            if session.status == SessionStatus.PAUSED:
                self._event_ch.send_nowait(_text_chunk(
                    "This interview is currently paused. Resume it from your dashboard to continue."
                ))
                return

            try:
                if not last_user_text.strip():
                    turn = await start_session(
                        db, session,
                        role_name=session.target_role.title if session.target_role else "this role",
                    )
                else:
                    turn = await submit_answer(db, session, last_user_text)
            except InterviewEngineError as exc:
                logger.error("voice_worker_turn_failed", session_id=self._session_id, error=str(exc))
                self._event_ch.send_nowait(_text_chunk(str(exc)))
                return

        spoken_text = turn.ai_message
        if turn.hint:
            spoken_text = f"{spoken_text} ({turn.hint})"
        self._event_ch.send_nowait(_text_chunk(spoken_text))


def _text_chunk(text: str) -> ChatChunk:
    return ChatChunk(id=str(uuid.uuid4()), delta=ChoiceDelta(role="assistant", content=text))
