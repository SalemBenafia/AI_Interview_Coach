"""
app/modules/agents/base.py
=============================
BaseAgent — every sub-agent (Interviewer, Evaluator, Router, Feedback,
Knowledge, Coach) inherits from this. Structure follows agent_compose.txt
exactly:

    Agent
     ├── Identity          -> name / key / version
     ├── Objective          -> objective
     ├── Instructions        -> system_prompt
     ├── State               -> passed into run() as `state: InterviewState`
     ├── Tools               -> self.tools (callables the agent may use)
     ├── Decision Logic      -> subclass-specific (rubric / decision_rules)
     ├── Input Schema        -> input_schema
     ├── Output Schema       -> output_schema
     └── Model Configuration -> model_provider / model_name / temperature / max_tokens

`AgentTemplate` (a DB row, admin-editable) is what supplies most of these
at construction time — see registry.py. Developers own this class and the
subclasses; admins own the AgentTemplate data that parameterises them
(admin_ai_manage_ui.txt — "Locked (Developer)" vs "Configurable (Admin)").
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Type, TypeVar

import structlog
from pydantic import BaseModel

from app.modules.agents.llm_client import complete_structured

logger = structlog.get_logger()

TIn = TypeVar("TIn", bound=BaseModel)
TOut = TypeVar("TOut", bound=BaseModel)


class AgentRunResult(Generic[TOut]):
    def __init__(self, output: TOut, latency_ms: int, model_name: str, tokens_used: Optional[int], used_simulation: bool):
        self.output = output
        self.latency_ms = latency_ms
        self.model_name = model_name
        self.tokens_used = tokens_used
        self.used_simulation = used_simulation


class BaseAgent(ABC, Generic[TIn, TOut]):
    """Abstract base every sub-agent implements."""

    key: str = "base"
    input_schema: Type[TIn]
    output_schema: Type[TOut]

    def __init__(
        self,
        *,
        name: str,
        objective: str,
        system_prompt: str,
        model_provider: str = "groq",
        model_name: str = "allam-2-7b",
        temperature: float = 0.7,
        max_tokens: int = 600,
        tools: Optional[dict[str, Any]] = None,
        template_id: Optional[str] = None,
        template_version: Optional[int] = None,
    ):
        self.name = name
        self.objective = objective
        self.system_prompt = system_prompt
        self.model_provider = model_provider
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.tools = tools or {}
        self.template_id = template_id
        self.template_version = template_version

    @abstractmethod
    def build_user_prompt(self, agent_input: TIn) -> str:
        """Render the input schema into the natural-language prompt body."""
        raise NotImplementedError

    async def run(self, agent_input: TIn) -> AgentRunResult[TOut]:
        """
        Standard execution path for LLM-backed agents: render prompt ->
        call the LLM -> validate structured output. Subclasses that need
        pure-rule logic (e.g. a Router that doesn't always need the LLM)
        may override this entirely.
        """
        start = time.perf_counter()
        user_prompt = self.build_user_prompt(agent_input)
        output, llm_result = await complete_structured(
            system_prompt=self.system_prompt,
            user_prompt=user_prompt,
            output_schema=self.output_schema,
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.debug(
            "agent_run",
            agent=self.key,
            latency_ms=latency_ms,
            model=llm_result.model_name,
            simulated=getattr(llm_result, "used_simulation", False),
        )
        return AgentRunResult(
            output=output,
            latency_ms=latency_ms,
            model_name=llm_result.model_name,
            tokens_used=llm_result.tokens_used,
            used_simulation=getattr(llm_result, "used_simulation", False),
        )
