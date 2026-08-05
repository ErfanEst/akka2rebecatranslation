"""Small LLM abstraction with a LangChain/OpenAI implementation."""

from __future__ import annotations

import time
from typing import Any, Protocol

from src.artifacts.result_models import LLMResult


class LLMClient(Protocol):
    model_name: str

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult: ...


def categorize_llm_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if "rate" in name or "rate limit" in message:
        return "RATE_LIMIT"
    if "timeout" in name or "timed out" in message:
        return "TIMEOUT"
    if "auth" in name or "api key" in message or "401" in message:
        return "AUTHENTICATION"
    if "connection" in name or "network" in message:
        return "NETWORK"
    if "model" in message and ("not found" in message or "invalid" in message):
        return "INVALID_MODEL"
    return "LLM_ERROR"


class OpenAILangChainClient:
    """Create the provider client lazily so non-LLM tests need no API packages."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        temperature: float = 0.1,
        top_p: float = 1.0,
        frequency_penalty: float = 0.0,
        presence_penalty: float = 0.0,
    ) -> None:
        if not api_key:
            raise ValueError("OPENAI_API_KEY is required to run translation.")

        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "langchain-openai is not installed. Run: pip install -r requirements.txt"
            ) from exc

        self.model_name = model
        self._client = ChatOpenAI(
            model=model,
            temperature=temperature,
            model_kwargs={
                "top_p": top_p,
                "frequency_penalty": frequency_penalty,
                "presence_penalty": presence_penalty,
            },
            api_key=api_key,
        )

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        from langchain_core.messages import HumanMessage, SystemMessage

        started = time.monotonic()
        response = self._client.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )
        latency = time.monotonic() - started

        usage: dict[str, Any] = getattr(response, "usage_metadata", None) or {}
        response_metadata: dict[str, Any] = (
            getattr(response, "response_metadata", None) or {}
        )
        token_usage = response_metadata.get("token_usage", {})

        input_tokens = usage.get("input_tokens", token_usage.get("prompt_tokens"))
        output_tokens = usage.get(
            "output_tokens", token_usage.get("completion_tokens")
        )
        total_tokens = usage.get("total_tokens", token_usage.get("total_tokens"))

        return LLMResult(
            model=self.model_name,
            response=str(response.content),
            latency_seconds=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            response_id=getattr(response, "id", None),
            metadata={
                key: value
                for key, value in response_metadata.items()
                if key != "token_usage"
            },
        )
