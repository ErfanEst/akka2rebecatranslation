"""Provider adapters and a single factory for all experiment models."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Protocol

from src.artifacts.result_models import LLMResult

from .model_config import GenerationConfig


class LLMClient(Protocol):
    model_name: str
    provider_name: str
    requested_parameters: dict[str, Any]
    effective_parameters: dict[str, Any]

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult: ...


NON_RETRYABLE_LLM_ERRORS = frozenset(
    {
        "AUTHENTICATION",
        "INVALID_MODEL",
        "INVALID_REQUEST",
        "UNSUPPORTED_PARAMETER",
        "CONFIGURATION_ERROR",
    }
)


class ModelConfigurationError(ValueError):
    """A provider/model/parameter combination is invalid before API execution."""


def categorize_llm_error(exc: Exception) -> str:
    name = type(exc).__name__.lower()
    message = str(exc).lower()
    if isinstance(exc, ModelConfigurationError):
        return "CONFIGURATION_ERROR"
    if "rate" in name or "rate limit" in message:
        return "RATE_LIMIT"
    if "timeout" in name or "timed out" in message:
        return "TIMEOUT"
    if "auth" in name or "api key" in message or "401" in message:
        return "AUTHENTICATION"
    if "unsupported value" in message or (
        "unsupported" in message and "param" in message
    ):
        return "UNSUPPORTED_PARAMETER"
    if "connection" in name or "network" in message:
        return "NETWORK"
    if "model" in message and (
        "not found" in message
        or "invalid" in message
        or "does not exist" in message
        or "not available" in message
    ):
        return "INVALID_MODEL"
    if (
        "invalid_request_error" in message
        or "bad request" in message
        or "400" in message
    ):
        return "INVALID_REQUEST"
    if "500" in message or "502" in message or "503" in message or "504" in message:
        return "SERVER_ERROR"
    return "LLM_ERROR"


def is_retryable_llm_error(category: str | None) -> bool:
    if category is None:
        return True
    return category not in NON_RETRYABLE_LLM_ERRORS


def infer_provider(model: str) -> str:
    normalized = model.lower()
    if normalized.startswith("claude"):
        return "anthropic"
    if normalized.startswith("deepseek"):
        return "deepseek"
    return "openai"


def normalize_provider(provider: str, model: str) -> str:
    normalized = provider.strip().lower().replace("-", "_")
    aliases = {
        "auto": infer_provider(model),
        "claude": "anthropic",
        "openai_compatible": "openai_compatible",
        "compatible": "openai_compatible",
    }
    return aliases.get(normalized, normalized)


def _effective_parameters(
    provider: str, model: str, config: GenerationConfig
) -> dict[str, Any]:
    """Validate known restrictions and return only parameters actually sent."""

    parameters = config.explicit_parameters()
    normalized_model = model.lower()

    # The GPT-5.6 API accepts only default sampling values. Omitting them is
    # preferable because it records the provider default unambiguously and
    # avoids the observed HTTP 400 for temperature=0.
    if provider == "openai" and re.match(r"^gpt-5\.6(?:-|$)", normalized_model):
        defaults = {
            "temperature": 1.0,
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }
        for name, default in defaults.items():
            if name not in parameters:
                continue
            if parameters[name] != default:
                raise ModelConfigurationError(
                    f"{model} only supports the default {name}={default}; "
                    f"received {parameters[name]}. Use '{name}=auto'."
                )
            parameters.pop(name)
        if parameters.get("reasoning_effort") == "minimal":
            raise ModelConfigurationError(
                f"{model} does not support reasoning_effort=minimal; "
                "use none, low, medium, high, xhigh, max, or auto."
            )

    if provider == "anthropic":
        unsupported = {
            name
            for name in ("frequency_penalty", "presence_penalty", "reasoning_effort")
            if name in parameters
        }
        if unsupported:
            raise ModelConfigurationError(
                "Anthropic adapter does not support: " + ", ".join(sorted(unsupported))
            )

    if provider in {"deepseek", "openai_compatible"} and "reasoning_effort" in parameters:
        raise ModelConfigurationError(
            f"{provider} adapter does not expose reasoning_effort; use auto."
        )
    return parameters


def validate_generation_config(
    provider: str, model: str, config: GenerationConfig
) -> tuple[str, dict[str, Any]]:
    """Resolve a provider and validate parameters without creating an API client."""

    resolved = normalize_provider(provider, model)
    return resolved, _effective_parameters(resolved, model, config)


def _response_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                chunks.append(str(item.get("text", "")))
        return "".join(chunks)
    return str(content)


class _LangChainChatClient:
    provider_name = "unknown"

    def __init__(self, *, model: str, config: GenerationConfig) -> None:
        self.model_name = model
        self.requested_parameters = config.requested_parameters()
        self.effective_parameters = _effective_parameters(
            self.provider_name, model, config
        )

    def _invoke(self, system_prompt: str, user_prompt: str):
        from langchain_core.messages import HumanMessage, SystemMessage

        return self._client.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        started = time.monotonic()
        response = self._invoke(system_prompt, user_prompt)
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
            provider=self.provider_name,
            model=self.model_name,
            response=_response_text(response.content),
            latency_seconds=latency,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            response_id=getattr(response, "id", None),
            retryable=None,
            requested_parameters=dict(self.requested_parameters),
            effective_parameters=dict(self.effective_parameters),
            metadata={
                key: value
                for key, value in response_metadata.items()
                if key != "token_usage"
            },
        )


class OpenAILangChainClient(_LangChainChatClient):
    """Create the provider client lazily so non-LLM tests need no API packages."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        config: GenerationConfig | None = None,
        base_url: str | None = None,
        provider_name: str = "openai",
    ) -> None:
        self.provider_name = provider_name
        super().__init__(model=model, config=config or GenerationConfig())
        if not api_key:
            raise ModelConfigurationError(
                f"API key is required for provider {self.provider_name}."
            )

        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:
            raise RuntimeError(
                "langchain-openai is not installed. Run: pip install -r requirements.txt"
            ) from exc

        direct_names = {
            "temperature",
            "top_p",
            "frequency_penalty",
            "presence_penalty",
            "max_tokens",
        }
        client_kwargs = {
            key: value
            for key, value in self.effective_parameters.items()
            if key in direct_names
        }
        model_kwargs = {
            key: value
            for key, value in self.effective_parameters.items()
            if key not in direct_names
        }
        if model_kwargs:
            client_kwargs["model_kwargs"] = model_kwargs
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = ChatOpenAI(
            model=model,
            api_key=api_key,
            **client_kwargs,
        )


class AnthropicLangChainClient(_LangChainChatClient):
    provider_name = "anthropic"

    def __init__(
        self,
        *,
        model: str,
        api_key: str,
        config: GenerationConfig | None = None,
        base_url: str | None = None,
    ) -> None:
        super().__init__(model=model, config=config or GenerationConfig())
        if not api_key:
            raise ModelConfigurationError("ANTHROPIC_API_KEY is required.")
        try:
            from langchain_anthropic import ChatAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "langchain-anthropic is not installed. Run: pip install -r requirements.txt"
            ) from exc
        kwargs = dict(self.effective_parameters)
        if base_url:
            kwargs["base_url"] = base_url
        self._client = ChatAnthropic(
            model=model,
            api_key=api_key,
            **kwargs,
        )


def create_llm_client(
    *,
    provider: str,
    model: str,
    config: GenerationConfig | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> LLMClient:
    """Build a provider adapter without leaking provider logic into pipelines."""

    resolved = normalize_provider(provider, model)
    keys = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai_compatible": "LLM_API_KEY",
    }
    if resolved not in keys:
        raise ModelConfigurationError(
            f"Unknown provider '{resolved}'. Expected openai, deepseek, "
            "anthropic, or openai_compatible."
        )
    resolved_key = api_key or os.getenv(keys[resolved], "")
    if resolved == "anthropic":
        return AnthropicLangChainClient(
            model=model,
            api_key=resolved_key,
            config=config,
            base_url=base_url or os.getenv("ANTHROPIC_BASE_URL") or None,
        )
    default_base_urls = {
        "deepseek": "https://api.deepseek.com",
        "openai_compatible": os.getenv("LLM_BASE_URL", ""),
    }
    resolved_base_url = base_url or default_base_urls.get(resolved) or None
    if resolved == "openai_compatible" and not resolved_base_url:
        raise ModelConfigurationError(
            "openai_compatible requires --api-base-url or LLM_BASE_URL."
        )
    return OpenAILangChainClient(
        model=model,
        api_key=resolved_key,
        config=config,
        base_url=resolved_base_url,
        provider_name=resolved,
    )
