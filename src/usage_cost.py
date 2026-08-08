"""Aggregation helpers for request-level token and cost records."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable


def summarize_llm_results(results: Iterable[Any]) -> dict[str, Any]:
    items = list(results)
    numeric_fields = (
        "input_tokens",
        "uncached_input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
    )
    totals = {
        field: sum(int(getattr(item, field, 0) or 0) for item in items)
        for field in numeric_fields
    }
    costed = [
        item
        for item in items
        if getattr(item, "cost_status", None) == "CALCULATED"
        and getattr(item, "cost_usd", None) is not None
    ]
    responses_with_usage = sum(
        getattr(item, "input_tokens", None) is not None
        or getattr(item, "output_tokens", None) is not None
        for item in items
    )
    known_cost = sum(Decimal(str(getattr(item, "cost_usd"))) for item in costed)
    cache_savings = sum(
        Decimal(str(getattr(item, "estimated_cache_savings_usd", 0) or 0))
        for item in items
    )
    cached_input = totals["cached_input_tokens"]
    input_tokens = totals["input_tokens"]
    return {
        "currency": "USD",
        "request_count": len(items),
        "responses_with_usage": responses_with_usage,
        "requests_without_usage": len(items) - responses_with_usage,
        "costed_requests": len(costed),
        "uncosted_requests": len(items) - len(costed),
        **totals,
        "cache_read_request_count": sum(
            int(getattr(item, "cached_input_tokens", 0) or 0) > 0
            for item in items
        ),
        "cache_write_request_count": sum(
            int(getattr(item, "cache_write_input_tokens", 0) or 0) > 0
            for item in items
        ),
        "cache_miss_request_count": sum(
            getattr(item, "input_tokens", None) is not None
            and int(getattr(item, "cached_input_tokens", 0) or 0) == 0
            for item in items
        ),
        "cache_read_ratio": cached_input / input_tokens if input_tokens else None,
        "estimated_cache_savings_usd": float(round(cache_savings, 12)),
        "known_cost_usd": float(round(known_cost, 12)),
        "is_complete": len(costed) == len(items),
    }


def combine_usage_cost_summaries(
    summaries: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    items = list(summaries)
    additive = (
        "request_count",
        "responses_with_usage",
        "requests_without_usage",
        "costed_requests",
        "uncosted_requests",
        "input_tokens",
        "uncached_input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "total_tokens",
        "cache_read_request_count",
        "cache_write_request_count",
        "cache_miss_request_count",
    )
    known_cost = sum(Decimal(str(item.get("known_cost_usd", 0))) for item in items)
    cache_savings = sum(
        Decimal(str(item.get("estimated_cache_savings_usd", 0))) for item in items
    )
    totals = {
        field: sum(int(item.get(field, 0)) for item in items) for field in additive
    }
    input_tokens = totals["input_tokens"]
    return {
        "currency": "USD",
        **totals,
        "cache_read_ratio": (
            totals["cached_input_tokens"] / input_tokens if input_tokens else None
        ),
        "estimated_cache_savings_usd": float(round(cache_savings, 12)),
        "known_cost_usd": float(round(known_cost, 12)),
        "is_complete": all(item.get("is_complete", False) for item in items)
        if items
        else True,
    }
