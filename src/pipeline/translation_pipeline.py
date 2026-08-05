"""Akka -> prompt -> LLM -> clean -> RMC syntax orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from src.artifacts.report_writer import ReportWriter
from src.artifacts.result_models import AttemptResult, LLMResult, SyntaxResult
from src.artifacts.workspace import CandidateWorkspace, WorkspaceManager
from src.llm.llm_client import LLMClient, categorize_llm_error
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


class TranslationPipeline:
    def __init__(
        self,
        *,
        llm_client: LLMClient,
        prompt_builder: PromptBuilder,
        output_cleaner: OutputCleaner,
        syntax_validator: SyntaxValidator,
        retry_manager: RetryManager,
        report_writer: ReportWriter | None = None,
    ) -> None:
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder
        self.output_cleaner = output_cleaner
        self.syntax_validator = syntax_validator
        self.retry_manager = retry_manager
        self.report_writer = report_writer or ReportWriter()

    def run(
        self,
        akka_code: str,
        candidate_workspace: CandidateWorkspace,
        *,
        benchmark: str | None = None,
    ) -> TranslationResult:
        def execute_attempt(
            attempt_number: int, previous: AttemptResult | None
        ) -> AttemptResult:
            started_at = utc_now()
            workspace = candidate_workspace.attempt(attempt_number)
            previous_code = None
            previous_error = None
            error_categories = None
            rmc_stdout = None
            rmc_stderr = None
            if previous:
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
                error_categories = ", ".join(categories) or "UNKNOWN"
                rmc_stdout = _read_artifact(previous.syntax.stdout_path)
                rmc_stderr = _read_artifact(previous.syntax.stderr_path)

            prompt = self.prompt_builder.build(
                attempt_number=attempt_number,
                akka_code=akka_code,
                benchmark=benchmark,
                previous_code=previous_code,
                compiler_error=previous_error,
                error_categories=error_categories,
                rmc_stdout=rmc_stdout,
                rmc_stderr=rmc_stderr,
            )
            WorkspaceManager.write_json(workspace.prompt_path, prompt.to_dict())

            try:
                llm_result = self.llm_client.generate(prompt.system, prompt.user)
                WorkspaceManager.write_text(
                    workspace.raw_response_path, llm_result.response
                )
                candidate = self.output_cleaner.clean(llm_result.response)
                if not candidate:
                    raise ValueError("LLM response contained no Rebeca candidate.")
                WorkspaceManager.write_text(workspace.candidate_path, candidate)
                syntax = self.syntax_validator.validate(
                    workspace.candidate_path, workspace.root
                )
                generated_code_path: str | None = str(workspace.candidate_path)
                raw_response_path: str | None = str(workspace.raw_response_path)
            except Exception as exc:
                if "llm_result" not in locals():
                    llm_result = LLMResult(
                        model=self.llm_client.model_name,
                        error_category=categorize_llm_error(exc),
                        error_message=str(exc),
                    )
                else:
                    llm_result.error_category = "MALFORMED_OUTPUT"
                    llm_result.error_message = str(exc)
                syntax = SyntaxResult(
                    executed=False,
                    execution_success=False,
                    passed=False,
                    error_category=(llm_result.error_category or "LLM_ERROR"),
                    error_message=llm_result.error_message,
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
            )
            self.report_writer.write_attempt(attempt, workspace.result_path)
            return attempt

        outcome = self.retry_manager.run(execute_attempt)
        return TranslationResult(
            attempts=outcome.attempts,
            successful_attempt=outcome.successful_attempt,
            exhausted=outcome.exhausted,
        )
