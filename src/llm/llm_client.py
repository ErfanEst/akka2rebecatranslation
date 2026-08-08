"""Provider adapters and a single factory for all experiment models."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Protocol

from src.artifacts.result_models import LLMResult

from .model_config import GenerationConfig
from .pricing import PricingCatalog, TokenUsage


class LLMClient(Protocol):
    model_name: str
    provider_name: str
    requested_parameters: dict[str, Any]
    effective_parameters: dict[str, Any]
    pricing_snapshot: dict[str, Any]

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

    cache_parameters = {
        name
        for name in ("prompt_cache_key", "prompt_cache_retention")
        if name in parameters
    }
    if provider != "openai" and cache_parameters:
        raise ModelConfigurationError(
            f"{provider} adapter does not expose OpenAI prompt-cache parameters: "
            + ", ".join(sorted(cache_parameters))
        )

    # GPT-5.6 accepts only its default sampling values.
    #
    # Important compatibility note:
    # langchain-openai 0.2.x injects temperature=0.7 when temperature is
    # omitted. GPT-5.6 accepts only temperature=1.0, so we pass 1.0
    # explicitly for GPT-5.6 while still rejecting non-default sampling
    # requests.
    if provider == "openai" and re.match(
        r"^gpt-5\.6(?:-|$)",
        normalized_model,
    ):
        requested_temperature = parameters.get("temperature")

        if requested_temperature is not None and requested_temperature != 1.0:
            raise ModelConfigurationError(
                f"{model} only supports the default temperature=1.0; "
                f"received {requested_temperature}. Use 'temperature=auto'."
            )

        # Keep this explicit so the pinned ChatOpenAI wrapper cannot
        # silently inject temperature=0.7.
        parameters["temperature"] = 1.0

        defaults = {
            "top_p": 1.0,
            "frequency_penalty": 0.0,
            "presence_penalty": 0.0,
        }

        for name, default in defaults.items():
            if name in parameters and parameters[name] != default:
                raise ModelConfigurationError(
                    f"{model} only supports the default {name}={default}; "
                    f"received {parameters[name]}. Use '{name}=auto'."
                )

            # These may safely remain omitted. Unlike temperature, the
            # pinned ChatOpenAI wrapper does not require a compatibility
            # override for them.
            parameters.pop(name, None)

        if parameters.get("reasoning_effort") == "minimal":
            raise ModelConfigurationError(
                f"{model} does not support reasoning_effort=minimal; "
                "use none, low, medium, high, xhigh, max, or auto."
            )

        if "prompt_cache_retention" in parameters:
            raise ModelConfigurationError(
                f"{model} uses the GPT-5.6 cache policy and does not accept "
                "prompt_cache_retention. Use auto; prompt_cache_key remains "
                "supported."
            )

    # GPT-5.1/5.2 expose sampling only in non-reasoning mode. Their
    # provider default is reasoning_effort=none, so omitted/auto is valid
    # as well.
    if provider == "openai" and re.match(
        r"^gpt-5\.[12](?:-|$)",
        normalized_model,
    ):
        sampling = {name for name in ("temperature", "top_p") if name in parameters}
        effort = parameters.get("reasoning_effort")

        if sampling and effort not in {None, "none"}:
            raise ModelConfigurationError(
                f"{model} supports {', '.join(sorted(sampling))} only with "
                "reasoning_effort=none "
                "(or auto, whose model default is none)."
            )

    if provider == "anthropic":
        unsupported = {
            name
            for name in (
                "frequency_penalty",
                "presence_penalty",
                "reasoning_effort",
            )
            if name in parameters
        }

        if unsupported:
            raise ModelConfigurationError(
                "Anthropic adapter does not support: " + ", ".join(sorted(unsupported))
            )

    if (
        provider in {"deepseek", "openai_compatible"}
        and "reasoning_effort" in parameters
    ):
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

    def __init__(
        self,
        *,
        model: str,
        config: GenerationConfig,
        pricing_catalog: PricingCatalog | None = None,
    ) -> None:
        self.model_name = model
        self.requested_parameters = config.requested_parameters()
        self.effective_parameters = _effective_parameters(
            self.provider_name, model, config
        )
        self.pricing_catalog = pricing_catalog or PricingCatalog.from_path()
        self.pricing_snapshot = self.pricing_catalog.snapshot

    def _invoke(self, system_prompt: str, user_prompt: str):
        from langchain_core.messages import HumanMessage, SystemMessage

        return self._client.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        started = time.monotonic()
        response = self._invoke(system_prompt, user_prompt)
        latency = time.monotonic() - started

        response_metadata: dict[str, Any] = (
            getattr(response, "response_metadata", None) or {}
        )
        token_usage = TokenUsage.from_response(response, provider=self.provider_name)
        estimate = self.pricing_catalog.estimate(
            provider=self.provider_name,
            model=self.model_name,
            usage=token_usage,
        )

        return LLMResult(
            provider=self.provider_name,
            model=self.model_name,
            response=_response_text(response.content),
            latency_seconds=latency,
            input_tokens=token_usage.input_tokens,
            output_tokens=token_usage.output_tokens,
            total_tokens=token_usage.total_tokens,
            uncached_input_tokens=token_usage.uncached_input_tokens,
            cached_input_tokens=token_usage.cached_input_tokens,
            cache_write_input_tokens=token_usage.cache_write_input_tokens,
            cache_status=token_usage.cache_status,
            cache_read_ratio=token_usage.cache_read_ratio,
            reasoning_tokens=token_usage.reasoning_tokens,
            cost_usd=estimate.get("total_cost_usd"),
            cost_status=estimate["status"],
            cost_details=estimate,
            estimated_cache_savings_usd=estimate.get(
                "estimated_cache_savings_usd", 0.0
            ),
            response_id=getattr(response, "id", None),
            retryable=None,
            requested_parameters=dict(self.requested_parameters),
            effective_parameters=dict(self.effective_parameters),
            metadata={
                **{
                    key: value
                    for key, value in response_metadata.items()
                    if key not in {"token_usage", "usage"}
                },
                "token_usage_raw": token_usage.raw,
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
        pricing_catalog: PricingCatalog | None = None,
    ) -> None:
        self.provider_name = provider_name
        super().__init__(
            model=model,
            config=config or GenerationConfig(),
            pricing_catalog=pricing_catalog,
        )
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
        openai_extra_body_names = {
            "reasoning_effort",
            "prompt_cache_key",
            "prompt_cache_retention",
        }
        client_kwargs = {
            key: value
            for key, value in self.effective_parameters.items()
            if key in direct_names
        }
        extra_body = {
            key: value
            for key, value in self.effective_parameters.items()
            if self.provider_name == "openai" and key in openai_extra_body_names
        }
        model_kwargs = {
            key: value
            for key, value in self.effective_parameters.items()
            if key not in direct_names and key not in extra_body
        }
        # ``extra_body`` keeps new OpenAI request fields compatible with the
        # pinned LangChain wrapper even when its typed surface predates a field.
        # The official OpenAI client merges these values into the JSON body.
        if extra_body:
            client_kwargs["extra_body"] = extra_body
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
        pricing_catalog: PricingCatalog | None = None,
    ) -> None:
        super().__init__(
            model=model,
            config=config or GenerationConfig(),
            pricing_catalog=pricing_catalog,
        )
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
    pricing_catalog: PricingCatalog | None = None,
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
            pricing_catalog=pricing_catalog,
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
        pricing_catalog=pricing_catalog,
    )
