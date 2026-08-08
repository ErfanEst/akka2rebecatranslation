"""Provider-neutral token usage normalization and reproducible cost estimates."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PRICING_PATH = PROJECT_ROOT / "config" / "model_pricing.json"
MILLION = Decimal("1000000")


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _integer(*values: Any) -> int | None:
    for value in values:
        if value is None or isinstance(value, bool):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


@dataclass(frozen=True)
class TokenUsage:
    """Normalized billable token categories from a provider response."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    uncached_input_tokens: int | None = None
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    reasoning_tokens: int = 0
    raw: dict[str, Any] | None = None

    @property
    def cache_status(self) -> str:
        if self.input_tokens is None:
            return "NOT_MEASURED"
        if self.cached_input_tokens > 0:
            return "HIT"
        if self.cache_write_input_tokens > 0:
            return "WRITE"
        return "MISS"

    @property
    def cache_read_ratio(self) -> float | None:
        if self.input_tokens is None or self.input_tokens <= 0:
            return None
        return self.cached_input_tokens / self.input_tokens

    @classmethod
    def from_response(cls, response: Any, *, provider: str) -> "TokenUsage":
        standardized = _mapping(getattr(response, "usage_metadata", None))
        response_metadata = _mapping(getattr(response, "response_metadata", None))
        raw = _mapping(response_metadata.get("token_usage"))
        if not raw:
            raw = _mapping(response_metadata.get("usage"))

        input_details = _mapping(
            standardized.get("input_token_details")
            or standardized.get("input_tokens_details")
        )
        output_details = _mapping(
            standardized.get("output_token_details")
            or standardized.get("output_tokens_details")
        )
        raw_prompt_details = _mapping(raw.get("prompt_tokens_details"))
        raw_completion_details = _mapping(raw.get("completion_tokens_details"))

        cached = _integer(
            input_details.get("cache_read"),
            input_details.get("cached"),
            raw_prompt_details.get("cached_tokens"),
            raw.get("cache_read_input_tokens"),
            raw.get("prompt_cache_hit_tokens"),
        ) or 0
        cache_write = _integer(
            input_details.get("cache_creation"),
            input_details.get("cache_write"),
            raw.get("cache_creation_input_tokens"),
            raw.get("prompt_cache_write_tokens"),
        ) or 0
        reasoning = _integer(
            output_details.get("reasoning"),
            output_details.get("reasoning_tokens"),
            raw_completion_details.get("reasoning_tokens"),
        ) or 0

        standardized_input = _integer(standardized.get("input_tokens"))
        raw_input = _integer(raw.get("prompt_tokens"), raw.get("input_tokens"))
        output = _integer(
            standardized.get("output_tokens"),
            raw.get("completion_tokens"),
            raw.get("output_tokens"),
        )

        # Anthropic's raw usage reports uncached input separately from cache
        # creation/read tokens. DeepSeek can report explicit hit/miss counts.
        deepseek_miss = _integer(raw.get("prompt_cache_miss_tokens"))
        if provider == "anthropic" and raw_input is not None and (cached or cache_write):
            uncached = raw_input
            input_total = raw_input + cached + cache_write
        elif provider == "deepseek" and deepseek_miss is not None:
            uncached = deepseek_miss
            input_total = uncached + cached + cache_write
        else:
            input_total = standardized_input if standardized_input is not None else raw_input
            uncached = (
                max(input_total - cached - cache_write, 0)
                if input_total is not None
                else None
            )

        total = _integer(
            standardized.get("total_tokens"), raw.get("total_tokens")
        )
        if total is None and input_total is not None and output is not None:
            total = input_total + output

        return cls(
            input_tokens=input_total,
            output_tokens=output,
            total_tokens=total,
            uncached_input_tokens=uncached,
            cached_input_tokens=cached,
            cache_write_input_tokens=cache_write,
            reasoning_tokens=reasoning,
            raw={"standardized": standardized, "provider": raw},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "uncached_input_tokens": self.uncached_input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_input_tokens": self.cache_write_input_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "cache_status": self.cache_status,
            "cache_read_ratio": self.cache_read_ratio,
        }


class PricingCatalog:
    """A versioned local snapshot of public list prices."""

    def __init__(self, payload: dict[str, Any], *, path: Path | None = None) -> None:
        self.payload = payload
        self.path = path
        self.entries = list(payload.get("models", []))

    @classmethod
    def from_path(cls, path: str | Path = DEFAULT_PRICING_PATH) -> "PricingCatalog":
        resolved = Path(path).expanduser().resolve()
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(payload.get("models"), list):
            raise ValueError(f"Pricing file has no models list: {resolved}")
        return cls(payload, path=resolved)

    @property
    def snapshot(self) -> dict[str, Any]:
        digest = (
            hashlib.sha256(self.path.read_bytes()).hexdigest()
            if self.path and self.path.is_file()
            else None
        )
        return {
            "schema_version": self.payload.get("schema_version"),
            "snapshot_version": self.payload.get("snapshot_version"),
            "effective_date": self.payload.get("effective_date"),
            "currency": self.payload.get("currency", "USD"),
            "path": str(self.path) if self.path else None,
            "sha256": digest,
        }

    def resolve(self, provider: str, model: str) -> dict[str, Any] | None:
        for entry in self.entries:
            if entry.get("provider") != provider:
                continue
            patterns = entry.get("model_patterns", [])
            if any(
                re.fullmatch(pattern, model, flags=re.IGNORECASE)
                for pattern in patterns
            ):
                return entry
        return None

    def estimate(
        self, *, provider: str, model: str, usage: TokenUsage
    ) -> dict[str, Any]:
        usage_payload = usage.to_dict()
        if usage.input_tokens is None and usage.output_tokens is None:
            return {
                "status": "USAGE_UNAVAILABLE",
                "currency": self.payload.get("currency", "USD"),
                "total_cost_usd": None,
                "usage": usage_payload,
                "pricing_snapshot": self.snapshot,
                "estimate_kind": "public_standard_list_price",
            }

        entry = self.resolve(provider, model)
        if entry is None:
            return {
                "status": "PRICE_UNAVAILABLE",
                "currency": self.payload.get("currency", "USD"),
                "total_cost_usd": None,
                "usage": usage_payload,
                "pricing_snapshot": self.snapshot,
                "provider": provider,
                "model": model,
                "estimate_kind": "public_standard_list_price",
            }

        rates = dict(entry.get("rates_per_million_tokens", {}))
        long_context = dict(entry.get("long_context", {}))
        long_context_applied = bool(
            long_context
            and usage.input_tokens is not None
            and usage.input_tokens > int(long_context.get("input_threshold_tokens", 0))
        )
        multipliers = (
            dict(long_context.get("rate_multipliers", {}))
            if long_context_applied
            else {}
        )

        token_categories = {
            "uncached_input": usage.uncached_input_tokens or 0,
            "cached_input": usage.cached_input_tokens,
            "cache_write_input": usage.cache_write_input_tokens,
            "output": usage.output_tokens or 0,
        }
        rate_names = {
            "uncached_input": "input",
            "cached_input": "cached_input",
            "cache_write_input": "cache_write_input",
            "output": "output",
        }
        components: dict[str, dict[str, Any]] = {}
        missing_rates: list[str] = []
        total_cost = Decimal("0")
        for category, tokens in token_categories.items():
            rate_name = rate_names[category]
            rate = rates.get(rate_name)
            if tokens and rate is None:
                missing_rates.append(rate_name)
                continue
            effective_rate = Decimal(str(rate or 0)) * Decimal(
                str(multipliers.get(rate_name, 1))
            )
            component_cost = Decimal(tokens) * effective_rate / MILLION
            total_cost += component_cost
            components[category] = {
                "tokens": tokens,
                "rate_per_million": float(effective_rate),
                "cost_usd": float(round(component_cost, 12)),
            }

        status = "CALCULATED" if not missing_rates else "PARTIAL_PRICE_UNAVAILABLE"
        uncached_rate = components.get("uncached_input", {}).get(
            "rate_per_million"
        )
        cached_rate = components.get("cached_input", {}).get("rate_per_million")
        cache_savings = Decimal("0")
        if uncached_rate is not None and cached_rate is not None:
            rate_difference = max(
                Decimal(str(uncached_rate)) - Decimal(str(cached_rate)),
                Decimal("0"),
            )
            cache_savings = (
                Decimal(usage.cached_input_tokens) * rate_difference / MILLION
            )
        return {
            "status": status,
            "currency": self.payload.get("currency", "USD"),
            "total_cost_usd": float(round(total_cost, 12)),
            "components": components,
            "usage": usage_payload,
            "provider": provider,
            "model": model,
            "pricing_snapshot": self.snapshot,
            "estimate_kind": "public_standard_list_price",
            "matched_pricing_id": entry.get("id"),
            "source_url": entry.get("source_url"),
            "long_context_applied": long_context_applied,
            "missing_rates": missing_rates,
            "estimated_cache_savings_usd": float(round(cache_savings, 12)),
            "note": (
                "Reasoning tokens are already included in output_tokens and are not charged twice."
            ),
        }
