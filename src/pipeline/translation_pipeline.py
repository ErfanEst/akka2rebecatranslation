"""Akka -> prompt -> LLM -> clean -> RMC syntax orchestration."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.artifacts.report_writer import ReportWriter
from src.artifacts.result_models import AttemptResult, LLMResult, SyntaxResult
from src.artifacts.workspace import CandidateWorkspace, WorkspaceManager
from src.llm.llm_client import (
    LLMClient,
    categorize_llm_error,
    is_retryable_llm_error,
)
from src.llm.example_retriever import VerifiedExampleRetriever
from src.llm.output_cleaner import OutputCleaner
from src.llm.prompt_builder import PromptBuilder
from src.syntax.syntax_validator import SyntaxValidator

from .retry_manager import RetryManager


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_artifact(path: str | None) -> str | None:
    if not path:
        return None
    artifact = Path(path)
    return WorkspaceManager.read_text(artifact) if artifact.is_file() else None


@dataclass(frozen=True)
class TranslationResult:
    attempts: list[AttemptResult]
    successful_attempt: AttemptResult | None
    exhausted: bool
    terminated_early: bool = False
    stop_reason: str | None = None


class TranslationPipeline:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder,
        output_cleaner: OutputCleaner,
        syntax_validator: SyntaxValidator,
        retry_manager: RetryManager,
        example_retriever: VerifiedExampleRetriever | None = None,
        report_writer: ReportWriter | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.output_cleaner = output_cleaner
        self.syntax_validator = syntax_validator
        self.retry_manager = retry_manager
        self.example_retriever = example_retriever
        self.report_writer = report_writer or ReportWriter()

    def _execute_prompt(
        self,
        *,
        prompt,
        candidate_workspace: CandidateWorkspace,
        attempt_number: int,
    ) -> AttemptResult:
        started_at = utc_now()
        workspace = candidate_workspace.attempt(attempt_number)
        WorkspaceManager.write_json(workspace.prompt_path, prompt.to_dict())

        candidate: str | None = None
        candidate_sha256: str | None = None
        stage = "llm"
        try:
            llm_result = self.llm_client.generate(prompt.system, prompt.user)
            WorkspaceManager.write_text(workspace.raw_response_path, llm_result.response)
            stage = "clean"
            candidate = self.output_cleaner.clean(llm_result.response)
            if not candidate:
                raise ValueError("LLM response contained no Rebeca candidate.")
            WorkspaceManager.write_text(workspace.candidate_path, candidate)
            candidate_sha256 = hashlib.sha256(
                candidate.encode("utf-8")
            ).hexdigest()
            stage = "syntax"
            syntax = self.syntax_validator.validate(
                workspace.candidate_path, workspace.root
            )
            generated_code_path: str | None = str(workspace.candidate_path)
            raw_response_path: str | None = str(workspace.raw_response_path)
        except Exception as exc:
            if stage == "llm":
                category = categorize_llm_error(exc)
                llm_result = LLMResult(
                    provider=self.llm_client.provider_name,
                    model=self.llm_client.model_name,
                    error_category=category,
                    error_message=str(exc),
                    retryable=is_retryable_llm_error(category),
                    requested_parameters=dict(
                        getattr(self.llm_client, "requested_parameters", {})
                    ),
                    effective_parameters=dict(
                        getattr(self.llm_client, "effective_parameters", {})
                    ),
                )
                syntax_category = category
            elif stage == "clean":
                llm_result.error_category = "MALFORMED_OUTPUT"
                llm_result.error_message = str(exc)
                llm_result.retryable = True
                syntax_category = "MALFORMED_OUTPUT"
            else:
                syntax_category = "VALIDATOR_ERROR"
            syntax = SyntaxResult(
                executed=False,
                execution_success=False,
                passed=False,
                error_category=syntax_category,
                error_message=str(exc),
            )
            generated_code_path = (
                str(workspace.candidate_path)
                if workspace.candidate_path.exists()
                else None
            )
            raw_response_path = (
                str(workspace.raw_response_path)
                if workspace.raw_response_path.exists()
                else None
            )

        attempt = AttemptResult(
            attempt_number=attempt_number,
            started_at=started_at,
            finished_at=utc_now(),
            prompt=prompt.to_dict(),
            llm=llm_result,
            generated_code_path=generated_code_path,
            raw_response_path=raw_response_path,
            syntax=syntax,
            generated_code=candidate,
            generated_code_sha256=candidate_sha256,
        )
        self.report_writer.write_attempt(attempt, workspace.result_path)
        return attempt

    @staticmethod
    def _previous_feedback(
        previous: AttemptResult | None,
    ) -> tuple[str | None, str | None, str | None, str | None, str | None]:
        if not previous:
            return None, None, None, None, None
        previous_code = _read_artifact(previous.generated_code_path)
        previous_error = (
            previous.syntax.error_message
            or previous.llm.error_message
            or "Previous attempt failed."
        )
        categories = list(
            dict.fromkeys(
                category
                for category in (
                    previous.syntax.error_category,
                    previous.llm.error_category,
                )
                if category
            )
        )
        return (
            previous_code,
            previous_error,
            ", ".join(categories) or "UNKNOWN",
            _read_artifact(previous.syntax.stdout_path),
            _read_artifact(previous.syntax.stderr_path),
        )

    def _retrieval_context(
        self,
        akka_code: str,
        *,
        benchmark: str | None,
        candidate_workspace: CandidateWorkspace,
    ) -> tuple[str | None, dict]:
        if not self.example_retriever:
            return None, {}
        selected, manifest = self.example_retriever.retrieve(
            akka_code, benchmark=benchmark
        )
        WorkspaceManager.write_json(
            candidate_workspace.root / "retrieval_manifest.json", manifest
        )
        return self.example_retriever.format_for_prompt(selected), manifest

    def run(
        self,
        akka_code: str,
        candidate_workspace: CandidateWorkspace,
        *,
        benchmark: str | None = None,
    ) -> TranslationResult:
        retrieved_examples, retrieval_metadata = self._retrieval_context(
            akka_code,
            benchmark=benchmark,
            candidate_workspace=candidate_workspace,
        )

        def execute_attempt(
            attempt_number: int, previous: AttemptResult | None
        ) -> AttemptResult:
            (
                previous_code,
                previous_error,
                error_categories,
                rmc_stdout,
                rmc_stderr,
            ) = self._previous_feedback(previous)

            prompt = self.prompt_builder.build(
                attempt_number=attempt_number,
                akka_code=akka_code,
                benchmark=benchmark,
                previous_code=previous_code,
                compiler_error=previous_error,
                error_categories=error_categories,
                rmc_stdout=rmc_stdout,
                rmc_stderr=rmc_stderr,
                retrieved_examples=retrieved_examples,
                retrieval_metadata=retrieval_metadata,
            )
            return self._execute_prompt(
                prompt=prompt,
                candidate_workspace=candidate_workspace,
                attempt_number=attempt_number,
            )

        outcome = self.retry_manager.run(execute_attempt)
        return TranslationResult(
            attempts=outcome.attempts,
            successful_attempt=outcome.successful_attempt,
            exhausted=outcome.exhausted,
            terminated_early=outcome.terminated_early,
            stop_reason=outcome.stop_reason,
        )

    def repair_semantic(
        self,
        akka_code: str,
        candidate_workspace: CandidateWorkspace,
        *,
        benchmark: str | None,
        previous_code: str,
        semantic_diagnostic: str,
        repair_number: int,
        start_attempt_number: int,
    ) -> TranslationResult:
        """Run one semantic repair followed by compiler-feedback syntax retries."""

        def execute_attempt(
            local_attempt_number: int, previous: AttemptResult | None
        ) -> AttemptResult:
            actual_attempt_number = start_attempt_number + local_attempt_number - 1
            if local_attempt_number == 1:
                prompt = self.prompt_builder.build_semantic_repair(
                    akka_code=akka_code,
                    previous_code=previous_code,
                    semantic_diagnostic=semantic_diagnostic,
                    benchmark=benchmark,
                    repair_number=repair_number,
                )
            else:
                (
                    failed_code,
                    compiler_error,
                    error_categories,
                    rmc_stdout,
                    rmc_stderr,
                ) = self._previous_feedback(previous)
                prompt = self.prompt_builder.build(
                    attempt_number=local_attempt_number,
                    akka_code=akka_code,
                    benchmark=benchmark,
                    previous_code=failed_code,
                    compiler_error=compiler_error,
                    error_categories=error_categories,
                    rmc_stdout=rmc_stdout,
                    rmc_stderr=rmc_stderr,
                    retrieval_metadata={
                        "semantic_repair_number": repair_number,
                        "repair_origin": "semantic_repair_syntax_failure",
                        "benchmark_oracle_exposed": True,
                    },
                )
            return self._execute_prompt(
                prompt=prompt,
                candidate_workspace=candidate_workspace,
                attempt_number=actual_attempt_number,
            )

        outcome = self.retry_manager.run(execute_attempt)
        return TranslationResult(
            attempts=outcome.attempts,
            successful_attempt=outcome.successful_attempt,
            exhausted=outcome.exhausted,
            terminated_early=outcome.terminated_early,
            stop_reason=outcome.stop_reason,
        )

    def repair_codegen(
        self,
        akka_code: str,
        candidate_workspace: CandidateWorkspace,
        *,
        benchmark: str | None,
        previous_code: str,
        codegen_diagnostic: str,
        repair_number: int,
        start_attempt_number: int,
    ) -> TranslationResult:
        """Run one backend repair followed by ordinary RMC syntax retries."""

        def execute_attempt(
            local_attempt_number: int, previous: AttemptResult | None
        ) -> AttemptResult:
            actual_attempt_number = start_attempt_number + local_attempt_number - 1
            if local_attempt_number == 1:
                prompt = self.prompt_builder.build_codegen_repair(
                    akka_code=akka_code,
                    previous_code=previous_code,
                    codegen_diagnostic=codegen_diagnostic,
                    benchmark=benchmark,
                    repair_number=repair_number,
                )
            else:
                (
                    failed_code,
                    compiler_error,
                    error_categories,
                    rmc_stdout,
                    rmc_stderr,
                ) = self._previous_feedback(previous)
                prompt = self.prompt_builder.build(
                    attempt_number=local_attempt_number,
                    akka_code=akka_code,
                    benchmark=benchmark,
                    previous_code=failed_code,
                    compiler_error=compiler_error,
                    error_categories=error_categories,
                    rmc_stdout=rmc_stdout,
                    rmc_stderr=rmc_stderr,
                    retrieval_metadata={
                        "codegen_repair_number": repair_number,
                        "repair_origin": "codegen_repair_syntax_failure",
                        "benchmark_oracle_exposed": False,
                    },
                )
            return self._execute_prompt(
                prompt=prompt,
                candidate_workspace=candidate_workspace,
                attempt_number=actual_attempt_number,
            )

        outcome = self.retry_manager.run(execute_attempt)
        return TranslationResult(
            attempts=outcome.attempts,
            successful_attempt=outcome.successful_attempt,
            exhausted=outcome.exhausted,
            terminated_early=outcome.terminated_early,
            stop_reason=outcome.stop_reason,
        )
