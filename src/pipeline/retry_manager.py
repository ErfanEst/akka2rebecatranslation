"""Retry policy only; generation and validation stay outside this component."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.artifacts.result_models import AttemptResult


@dataclass(frozen=True)
class RetryOutcome:
    attempts: list[AttemptResult]
    successful_attempt: AttemptResult | None
    exhausted: bool


class RetryManager:
    def __init__(self, max_attempts: int) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        self.max_attempts = max_attempts

    def run(
        self,
        attempt_factory: Callable[[int, AttemptResult | None], AttemptResult],
    ) -> RetryOutcome:
        attempts: list[AttemptResult] = []
        previous: AttemptResult | None = None
        for attempt_number in range(1, self.max_attempts + 1):
            current = attempt_factory(attempt_number, previous)
            attempts.append(current)
            if current.syntax.passed:
                return RetryOutcome(
                    attempts=attempts,
                    successful_attempt=current,
                    exhausted=False,
                )
            previous = current
        return RetryOutcome(
            attempts=attempts, successful_attempt=None, exhausted=True
        )
