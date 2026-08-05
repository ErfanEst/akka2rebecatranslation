"""Serializable result contracts shared by all pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class PipelineStatus(str, Enum):
    SYNTAX_FAIL = "SYNTAX_FAIL"
    SYNTAX_PASS = "SYNTAX_PASS"
    SEMANTIC_PASS = "SEMANTIC_PASS"
    SEMANTIC_FAIL = "SEMANTIC_FAIL"
    SEMANTIC_NOT_OBSERVED = "SEMANTIC_NOT_OBSERVED"
    INFRA_ERROR = "INFRA_ERROR"


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value


class SerializableResult:
    def to_dict(self) -> dict[str, Any]:
        return _json_value(asdict(self))


@dataclass
class LLMResult(SerializableResult):
    model: str
    response: str = ""
    latency_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    response_id: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyntaxResult(SerializableResult):
    executed: bool = False
    execution_success: bool = False
    passed: bool = False
    duration_seconds: float = 0.0
    return_code: int | None = None
    command: list[str] = field(default_factory=list)
    error_category: str | None = None
    error_message: str | None = None
    stdout_path: str | None = None
    stderr_path: str | None = None
    generated_cpp_path: str | None = None


@dataclass
class SemanticResult(SerializableResult):
    executed: bool = False
    passed: bool | None = None
    status: str = "NOT_RUN"
    duration_seconds: float = 0.0
    error_stage: str | None = None
    error_message: str | None = None
    passed_tests: int | None = None
    failed_tests: int | None = None
    not_observed_tests: int | None = None
    total_tests: int | None = None
    failed_test_ids: list[str] = field(default_factory=list)
    not_observed_test_ids: list[str] = field(default_factory=list)
    trace_xml_path: str | None = None
    parsed_result_path: str | None = None
    result_path: str | None = None
    spec_path: str | None = None
    commands: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AttemptResult(SerializableResult):
    attempt_number: int
    started_at: str
    finished_at: str
    prompt: dict[str, Any]
    llm: LLMResult
    generated_code_path: str | None
    raw_response_path: str | None
    syntax: SyntaxResult


@dataclass
class CandidateResult(SerializableResult):
    candidate_id: str
    source_akka_path: str
    source_sha256: str
    workspace_path: str
    benchmark: str | None
    max_attempts: int
    attempts: list[AttemptResult]
    started_at: str
    finished_at: str
    elapsed_seconds: float
    translation_success: bool
    syntax_pass: bool
    syntax_valid_attempt: int | None
    syntax_valid_code_path: str | None
    semantic: SemanticResult
    overall_status: PipelineStatus
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def attempts_used(self) -> int:
        return len(self.attempts)

    def to_dict(self) -> dict[str, Any]:
        result = super().to_dict()
        selected_syntax = None
        if self.attempts:
            selected_attempt = next(
                (
                    attempt
                    for attempt in self.attempts
                    if attempt.attempt_number == self.syntax_valid_attempt
                ),
                self.attempts[-1],
            )
            selected_syntax = selected_attempt.syntax.to_dict()
        result["syntax"] = {
            "passed": self.syntax_pass,
            "valid_attempt": self.syntax_valid_attempt,
            "valid_code_path": self.syntax_valid_code_path,
            "result": selected_syntax,
        }
        result["attempts_used"] = self.attempts_used
        result["final_status"] = result["overall_status"]
        return result
