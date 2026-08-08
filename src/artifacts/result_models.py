"""Serializable result contracts shared by all pipeline stages."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from src.usage_cost import summarize_llm_results


class PipelineStatus(str, Enum):
    SYNTAX_FAIL = "SYNTAX_FAIL"
    SYNTAX_PASS = "SYNTAX_PASS"
    CODEGEN_FAIL = "CODEGEN_FAIL"
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
    provider: str = "unknown"
    response: str = ""
    latency_seconds: float = 0.0
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    uncached_input_tokens: int | None = None
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    cache_status: str = "NOT_MEASURED"
    cache_read_ratio: float | None = None
    estimated_cache_savings_usd: float = 0.0
    reasoning_tokens: int = 0
    cost_usd: float | None = None
    cost_status: str = "USAGE_UNAVAILABLE"
    cost_details: dict[str, Any] = field(default_factory=dict)
    response_id: str | None = None
    error_category: str | None = None
    error_message: str | None = None
    retryable: bool | None = None
    requested_parameters: dict[str, Any] = field(default_factory=dict)
    effective_parameters: dict[str, Any] = field(default_factory=dict)
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
    semantic_test_results: list[dict[str, Any]] = field(default_factory=list)
    trace_xml_path: str | None = None
    state_space_xml_path: str | None = None

    parsed_trace_path: str | None = None
    parsed_state_space_path: str | None = None

    # JSON actually consumed by the benchmark evaluator.
    parsed_result_path: str | None = None

    # Semantic evidence backend: "trace" or "statespace".
    semantic_input: str | None = None

    result_path: str | None = None
    spec_path: str | None = None
    commands: list[dict[str, Any]] = field(default_factory=list)

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
    # The code is intentionally embedded in JSON as well as stored on disk.
    # This keeps failed generations available for later error analysis even if
    # result files are copied away from their original workspace.
    generated_code: str | None = None
    generated_code_sha256: str | None = None


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

    @property
    def usage_and_cost(self) -> dict[str, Any]:
        return summarize_llm_results(attempt.llm for attempt in self.attempts)

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
        result["usage_and_cost"] = self.usage_and_cost
        result["generated_candidates"] = [
            {
                "attempt_number": attempt.attempt_number,
                "code": attempt.generated_code,
                "sha256": attempt.generated_code_sha256,
                "path": attempt.generated_code_path,
                "syntax_pass": attempt.syntax.passed,
                "error_category": attempt.syntax.error_category,
                "error_message": attempt.syntax.error_message,
            }
            for attempt in self.attempts
            if attempt.generated_code is not None
        ]
        result["failed_candidates"] = [
            candidate
            for candidate in result["generated_candidates"]
            if not candidate["syntax_pass"]
        ]
        return result
