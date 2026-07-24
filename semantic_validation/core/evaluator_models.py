from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class TestStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_OBSERVED = "NOT_OBSERVED"


@dataclass
class SemanticTestResult:
    test_id: str
    status: TestStatus
    description: str
    evidence: dict[str, Any] = field(default_factory=dict)
    details: str | None = None

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


@dataclass
class SemanticEvaluationResult:
    benchmark: str
    semantic_tests: list[SemanticTestResult]
    detected_issues: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def passed_tests(self) -> int:
        return sum(
            test.status == TestStatus.PASS
            for test in self.semantic_tests
        )

    @property
    def failed_tests(self) -> int:
        return sum(
            test.status == TestStatus.FAIL
            for test in self.semantic_tests
        )

    @property
    def not_observed_tests(self) -> int:
        return sum(
            test.status == TestStatus.NOT_OBSERVED
            for test in self.semantic_tests
        )

    @property
    def total_tests(self) -> int:
        return len(self.semantic_tests)

    @property
    def semantic_pass(self) -> bool:
        return (
            self.failed_tests == 0
            and self.not_observed_tests == 0
            and self.total_tests > 0
        )

    @property
    def semantic_status(self) -> str:
        return (
            "SEMANTIC_PASS"
            if self.semantic_pass
            else "SEMANTIC_FAIL"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "benchmark": self.benchmark,
            "semantic_status": self.semantic_status,
            "semantic_pass": self.semantic_pass,
            "passed_tests": self.passed_tests,
            "failed_tests": self.failed_tests,
            "not_observed_tests": self.not_observed_tests,
            "total_tests": self.total_tests,
            "passed_test_ids": [
                test.test_id
                for test in self.semantic_tests
                if test.status == TestStatus.PASS
            ],
            "failed_test_ids": [
                test.test_id
                for test in self.semantic_tests
                if test.status == TestStatus.FAIL
            ],
            "not_observed_test_ids": [
                test.test_id
                for test in self.semantic_tests
                if test.status == TestStatus.NOT_OBSERVED
            ],
            "detected_issues": self.detected_issues,
            "metadata": self.metadata,
            "semantic_tests": [
                test.to_dict()
                for test in self.semantic_tests
            ],
        }
