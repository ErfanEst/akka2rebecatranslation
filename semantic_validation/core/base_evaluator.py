from __future__ import annotations

from typing import Any


class BaseSemanticEvaluator:
    """
    Base class for example-specific semantic evaluators.

    Provides:
      - common state/transition access
      - result collection
      - summary generation
    """

    def __init__(
        self,
        parsed_result: dict[str, Any],
        example_id: str,
    ):
        self.parsed_result = parsed_result
        self.example_id = example_id

        self.states = parsed_result.get(
            "states",
            [],
        )

        self.transitions = parsed_result.get(
            "transitions",
            [],
        )

        if not self.states:
            raise ValueError(
                "No states found in parsed RMC result."
            )

        self.results: list[dict[str, Any]] = []

    def add_result(
        self,
        test_id: str,
        passed: bool,
        details: str,
    ) -> None:
        """
        Add one semantic test result.
        """

        self.results.append(
            {
                "test_id": test_id,
                "passed": bool(passed),
                "details": details,
            }
        )

    def build_summary(
        self,
    ) -> dict[str, Any]:
        """
        Build final semantic evaluation result.
        """

        passed_count = sum(
            1
            for result in self.results
            if result["passed"]
        )

        total_count = len(
            self.results
        )

        return {
            "example_id": self.example_id,
            "semantic_tests": self.results,
            "summary": {
                "passed": passed_count,
                "failed": (
                    total_count
                    - passed_count
                ),
                "total": total_count,
                "semantic_pass": (
                    passed_count
                    == total_count
                ),
            },
        }
