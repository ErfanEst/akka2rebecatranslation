"""Provider-neutral generation settings and model-target parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REASONING_EFFORTS = frozenset(
    {"none", "minimal", "low", "medium", "high", "xhigh", "max"}
)
PROMPT_CACHE_RETENTIONS = frozenset({"in_memory", "24h"})


@dataclass(frozen=True)
class ModelTarget:
    provider: str
    model: str

    @property
    def identifier(self) -> str:
        return f"{self.provider}:{self.model}"


@dataclass(frozen=True)
class GenerationConfig:
    """Only non-None values are sent to a provider.

    ``None`` means provider/model default. This distinction is important for
    reasoning models that reject explicit sampling values even when a caller
    considers those values harmless defaults.
    """

    temperature: float | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    max_tokens: int | None = None
    reasoning_effort: str | None = None
    prompt_cache_key: str | None = None
    prompt_cache_retention: str | None = None

    def __post_init__(self) -> None:
        if self.temperature is not None and not 0.0 <= self.temperature <= 2.0:
            raise ValueError("temperature must be between 0 and 2")
        if self.top_p is not None and not 0.0 <= self.top_p <= 1.0:
            raise ValueError("top_p must be between 0 and 1")
        for name, value in (
            ("frequency_penalty", self.frequency_penalty),
            ("presence_penalty", self.presence_penalty),
        ):
            if value is not None and not -2.0 <= value <= 2.0:
                raise ValueError(f"{name} must be between -2 and 2")
        if self.max_tokens is not None and self.max_tokens < 1:
            raise ValueError("max_tokens must be at least 1")
        if (
            self.reasoning_effort is not None
            and self.reasoning_effort not in REASONING_EFFORTS
        ):
            allowed = ", ".join(sorted(REASONING_EFFORTS))
            raise ValueError(f"reasoning_effort must be one of: {allowed}")
        if self.prompt_cache_key is not None and not self.prompt_cache_key.strip():
            raise ValueError("prompt_cache_key cannot be empty")
        if (
            self.prompt_cache_retention is not None
            and self.prompt_cache_retention not in PROMPT_CACHE_RETENTIONS
        ):
            allowed = ", ".join(sorted(PROMPT_CACHE_RETENTIONS))
            raise ValueError(f"prompt_cache_retention must be one of: {allowed}")

    def requested_parameters(self) -> dict[str, Any]:
        """Return the full experimental request, including omitted parameters."""

        return {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "max_tokens": self.max_tokens,
            "reasoning_effort": self.reasoning_effort,
            "prompt_cache_key": self.prompt_cache_key,
            "prompt_cache_retention": self.prompt_cache_retention,
        }

    def explicit_parameters(self) -> dict[str, Any]:
        return {
            key: value
            for key, value in self.requested_parameters().items()
            if value is not None
        }


def parse_optional_float(value: str) -> float | None:
    if value.strip().lower() in {"auto", "default"}:
        return None
    return float(value)


def parse_optional_int(value: str) -> int | None:
    if value.strip().lower() in {"auto", "default"}:
        return None
    return int(value)


def parse_reasoning_effort(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"auto", "default"}:
        return None
    if normalized not in REASONING_EFFORTS:
        allowed = ", ".join(["auto", *sorted(REASONING_EFFORTS)])
        raise ValueError(f"reasoning effort must be one of: {allowed}")
    return normalized


def parse_prompt_cache_retention(value: str) -> str | None:
    normalized = value.strip().lower()
    if normalized in {"auto", "default"}:
        return None
    if normalized not in PROMPT_CACHE_RETENTIONS:
        allowed = ", ".join(["auto", *sorted(PROMPT_CACHE_RETENTIONS)])
        raise ValueError(f"prompt cache retention must be one of: {allowed}")
    return normalized


def parse_model_target(value: str, *, default_provider: str = "auto") -> ModelTarget:
    """Parse ``provider:model`` while keeping plain model names convenient."""

    raw = value.strip()
    if not raw:
        raise ValueError("model target cannot be empty")
    if ":" not in raw:
        return ModelTarget(provider=default_provider, model=raw)
    provider, model = raw.split(":", 1)
    if not provider or not model:
        raise ValueError("model target must use provider:model")
    return ModelTarget(provider=provider.strip().lower(), model=model.strip())
