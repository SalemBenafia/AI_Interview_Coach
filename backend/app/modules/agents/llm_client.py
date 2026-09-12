"""
app/modules/agents/llm_client.py
===================================
Production client around Groq's OpenAI-compatible /chat/completions
endpoint (https://console.groq.com/docs/openai). Groq's LPU inference is
significantly faster than typical GPU inference, which matters for real-time
voice interviews. The free developer plan has per-model rate limits (tokens/
min, requests/day) — see https://console.groq.com/docs/rate-limits.

DESIGN PRINCIPLE (important): this client NEVER fabricates an interview
question, evaluation, or piece of feedback. If Groq is unreachable,
rate-limited, or returns something we can't parse after retrying, we raise
a typed exception. The caller (the agent classes, then the graph engine,
then the API/WebSocket layer) is responsible for surfacing a real "the AI
service is temporarily unavailable, please retry" condition to the
candidate. Silently inventing plausible-looking AI output would be
actively misleading in a product whose entire value is "real, live AI
judgment" — so there is no simulation branch anywhere in this file.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Optional, Type, TypeVar

import httpx
import structlog
from pydantic import BaseModel, ValidationError

from app.core.settings import settings

logger = structlog.get_logger()

T = TypeVar("T", bound=BaseModel)

MAX_RETRIES = 2
RETRY_BACKOFF_SECONDS = 0.8


class AgentServiceError(RuntimeError):
    """Raised when Groq is unreachable, misconfigured, or errors out after retries."""


class AgentOutputParseError(RuntimeError):
    """Raised when the LLM responded but its output could not be validated against the expected schema."""


@dataclass
class LLMCallResult:
    raw_text: str
    latency_ms: int
    tokens_used: Optional[int]
    model_name: str


def _extract_json_block(text: str) -> str:
    """Free models occasionally wrap JSON in ```json fences or prose — strip it."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return brace.group(0)
    return text


# Small/weaker models (observed consistently on allam-2-7b) occasionally
# omit the comma between a JSON value and the next key, e.g.
# `"question": "..."\n  "is_followup": false`. This is a well-known,
# mechanically fixable formatting slip -- distinct from genuinely malformed
# output -- so it's worth repairing before burning a full extra LLM call
# (which has its own chance of repeating the same mistake) on an otherwise
# well-formed response. Matches a value-ending token (closing quote/brace/
# bracket, digit, or true/false/null) followed by whitespace and a new
# opening quote with no comma in between; a real comma there would already
# make \s+ fail to match immediately (it isn't whitespace), so already-valid
# JSON is left untouched.
_MISSING_COMMA_RE = re.compile(r'("|\d|true|false|null|\}|\])(\s+)(")')


def _repair_missing_commas(text: str) -> str:
    return _MISSING_COMMA_RE.sub(r"\1,\2\3", text)


def _schema_to_example(schema: dict) -> dict:
    """
    Convert a Pydantic model_json_schema() dict into a concrete placeholder
    example. Pydantic's raw properties format (with 'title', 'type', 'items'
    keys) confuses small models like llama-3.1-8b-instant — they return the
    schema structure itself instead of filling it with values. A concrete
    example like {"field": "<string>"} is unambiguous.
    """
    defs = schema.get("$defs", {})

    def _resolve(prop: dict) -> object:
        if "$ref" in prop:
            ref_name = prop["$ref"].split("/")[-1]
            return _build_object(defs.get(ref_name, {}))
        t = prop.get("type")
        if t == "string":
            return "<string>"
        if t in ("integer", "number"):
            return 0
        if t == "boolean":
            return False
        if t == "array":
            items = prop.get("items", {})
            return [_resolve(items)]
        if t == "object":
            # Free-form maps (e.g. dict[str, bool]) have no fixed
            # "properties", only "additionalProperties" — without this
            # branch _build_object returns {} for them, which gives the
            # model zero signal about the expected value type and leads it
            # to invent a differently-shaped (often much longer, prose-filled)
            # response instead.
            if "properties" not in prop and isinstance(prop.get("additionalProperties"), dict):
                return {"<key>": _resolve(prop["additionalProperties"])}
            return _build_object(prop)
        # anyOf / allOf (e.g. Optional fields) — take first concrete type
        for wrapper in ("anyOf", "allOf", "oneOf"):
            if wrapper in prop:
                for sub in prop[wrapper]:
                    if sub.get("type") != "null":
                        return _resolve(sub)
        return None

    def _build_object(obj_schema: dict) -> dict:
        return {k: _resolve(v) for k, v in obj_schema.get("properties", {}).items()}

    return _build_object(schema)


def _build_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }


def _classify_status_error(status_code: int, body_text: str) -> str:
    """Turn a Groq HTTP error into an actionable message."""
    if status_code == 401:
        return "Groq rejected the request: invalid or missing GROQ_API_KEY."
    if status_code == 402:
        return "Groq reports insufficient credits for this model/request."
    if status_code == 429:
        return (
            "Groq rate-limited this request. The free developer plan has per-model "
            "limits on requests/day and tokens/minute — see "
            "https://console.groq.com/docs/rate-limits. Switch GROQ_MODEL to a "
            "less-busy model or wait for the rate-limit window to reset."
        )
    if status_code == 404:
        return (
            "Groq could not find the requested model. Check "
            "https://console.groq.com/docs/models and update GROQ_MODEL."
        )
    return f"Groq returned HTTP {status_code}: {body_text[:300]}"


async def _call_groq(
    *,
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float,
    max_tokens: int,
) -> LLMCallResult:
    """One real HTTP call to Groq, no retry logic — see chat_completion() for that."""
    start = time.perf_counter()
    async with httpx.AsyncClient(timeout=settings.GROQ_REQUEST_TIMEOUT_SECONDS) as client:
        r = await client.post(
            f"{settings.GROQ_BASE_URL}/chat/completions",
            headers=_build_headers(),
            json={
                "model": model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
                # Deliberately NOT sending response_format: {"type": "json_object"} —
                # support for strict JSON mode varies across models, and a model that
                # rejects the parameter would hard-fail the whole request. Structured
                # output is handled via schema-hint prompt + parse-retry in
                # complete_structured() below instead.
            },
        )
        if r.status_code >= 400:
            raise httpx.HTTPStatusError(
                _classify_status_error(r.status_code, r.text),
                request=r.request,
                response=r,
            )
        data = r.json()
        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = data["choices"][0]["message"]
        usage = data.get("usage") or {}
        return LLMCallResult(
            raw_text=choice["content"] or "",
            latency_ms=latency_ms,
            tokens_used=usage.get("completion_tokens"),
            model_name=model_name,
        )


_NON_RETRYABLE_STATUS_CODES = {401, 402, 404}


async def chat_completion(
    *,
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 600,
    json_mode: bool = True,  # retained for call-site compatibility; see note above
) -> LLMCallResult:
    """
    Call Groq's /chat/completions endpoint, retrying transient failures
    (timeouts, connection errors, 429, 5xx) on the primary model, then
    falling back through GROQ_FALLBACK_MODEL (comma-separated) one at a
    time. Permanent client errors (401/402/404) skip the retry loop and go
    straight to the fallback list. Raises AgentServiceError if no model
    responds.
    """
    if not settings.GROQ_API_KEY:
        raise AgentServiceError(
            "GROQ_API_KEY is not set. Create a free key at https://console.groq.com/keys "
            "and add GROQ_API_KEY=<your-key> to backend/.env."
        )

    primary_model = model or settings.GROQ_MODEL
    last_error: Optional[Exception] = None

    for attempt in range(MAX_RETRIES + 1):
        try:
            return await _call_groq(
                model_name=primary_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status_code = exc.response.status_code if exc.response is not None else None
            logger.warning(
                "groq_call_failed",
                attempt=attempt + 1,
                max_attempts=MAX_RETRIES + 1,
                error=str(exc),
                model=primary_model,
                status_code=status_code,
            )
            if status_code in _NON_RETRYABLE_STATUS_CODES:
                break  # permanent error — skip remaining retries, go straight to fallback
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            last_error = exc
            logger.warning(
                "groq_call_failed",
                attempt=attempt + 1,
                max_attempts=MAX_RETRIES + 1,
                error=str(exc),
                model=primary_model,
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(RETRY_BACKOFF_SECONDS * (attempt + 1))
                continue
        except Exception as exc:  # noqa: BLE001 - convert anything unexpected too
            last_error = exc
            logger.error("groq_call_unexpected_error", error=str(exc), model=primary_model)
            break

    # Primary model exhausted its retries — work through the comma-separated
    # fallback list (tried once each).
    fallback_models = [
        m.strip()
        for m in settings.GROQ_FALLBACK_MODEL.split(",")
        if m.strip() and m.strip() != primary_model
    ]
    tried_fallbacks: list[str] = []
    for fallback_model in fallback_models:
        tried_fallbacks.append(fallback_model)
        try:
            logger.warning("groq_falling_back", primary=primary_model, fallback=fallback_model)
            return await _call_groq(
                model_name=fallback_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.error("groq_fallback_failed", error=str(exc), model=fallback_model)

    raise AgentServiceError(
        f"Groq did not respond after {MAX_RETRIES + 1} attempts on '{primary_model}' "
        f"and fallback attempts on {tried_fallbacks or ['(none configured)']}: {last_error}"
    )


async def complete_structured(
    *,
    system_prompt: str,
    user_prompt: str,
    output_schema: Type[T],
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 600,
) -> tuple[T, LLMCallResult]:
    """
    Call the LLM and parse+validate its JSON response against output_schema.
    Retries ONCE with a stricter formatting instruction if the first response
    doesn't parse — this handles ordinary LLM flakiness around JSON
    formatting, which is distinct from a service outage (handled inside
    chat_completion above). Raises AgentOutputParseError if the model still
    can't produce valid JSON after retrying.
    """
    _example = _schema_to_example(output_schema.model_json_schema())
    schema_hint = (
        "\n\nRespond with ONLY a single valid JSON object using exactly these keys "
        "(replace every placeholder with real content — no prose, no markdown fences):\n"
        f"{json.dumps(_example, indent=2)}"
    )

    last_raw_preview = ""
    for parse_attempt in range(2):
        result = await chat_completion(
            system_prompt=system_prompt + schema_hint,
            user_prompt=user_prompt,
            model=model,
            temperature=temperature if parse_attempt == 0 else max(0.1, temperature - 0.3),
            max_tokens=max_tokens,
            json_mode=True,
        )
        raw = _extract_json_block(result.raw_text)
        last_raw_preview = result.raw_text[:300]
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            try:
                parsed = json.loads(_repair_missing_commas(raw))
                logger.info("llm_json_repaired", parse_attempt=parse_attempt + 1)
            except json.JSONDecodeError as exc:
                logger.warning(
                    "llm_json_parse_failed",
                    parse_attempt=parse_attempt + 1,
                    error=str(exc),
                    raw_preview=last_raw_preview,
                )
                schema_hint = (
                    "\n\nYour previous response was not valid JSON. Respond again with ONLY a single "
                    "valid JSON object — no prose, no markdown fences — using exactly these keys:\n"
                    f"{json.dumps(_example, indent=2)}"
                )
                continue
        try:
            return output_schema.model_validate(parsed), result
        except ValidationError as exc:
            logger.warning(
                "llm_json_schema_mismatch",
                parse_attempt=parse_attempt + 1,
                error=str(exc),
                raw_preview=last_raw_preview,
            )
            schema_hint = (
                "\n\nYour previous response was not valid JSON. Respond again with ONLY a single "
                "valid JSON object — no prose, no markdown fences — using exactly these keys:\n"
                f"{json.dumps(_example, indent=2)}"
            )
            continue

    raise AgentOutputParseError(
        f"Model {model or settings.GROQ_MODEL} did not return parseable JSON for "
        f"{output_schema.__name__} after 2 attempts. Last response: {last_raw_preview!r}"
    )
