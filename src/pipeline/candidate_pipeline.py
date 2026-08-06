"""Complete per-candidate orchestration and unified reporting."""

from __future__ import annotations

import hashlib
import shutil
import time
from pathlib import Path
from typing import Any

from src.artifacts.report_writer import ReportWriter
from src.artifacts.result_models import CandidateResult, PipelineStatus, SemanticResult
from src.artifacts.workspace import WorkspaceManager
from src.semantic.semantic_validator import SemanticValidator
from src.semantic.semantic_diagnostics import SemanticDiagnosticBuilder

from .translation_pipeline import TranslationPipeline, utc_now


class CandidatePipeline:
    def __init__(
        self,
        *,
        translation_pipeline: TranslationPipeline,
        workspace_manager: WorkspaceManager,
        max_attempts: int,
        max_semantic_repairs: int = 0,
        semantic_validator: SemanticValidator | None = None,
        semantic_diagnostic_builder: SemanticDiagnosticBuilder | None = None,
        report_writer: ReportWriter | None = None,
    ) -> None:
        self.translation_pipeline = translation_pipeline
        self.workspace_manager = workspace_manager
        self.max_attempts = max_attempts
        if max_semantic_repairs < 0:
            raise ValueError("max_semantic_repairs cannot be negative")
        self.max_semantic_repairs = max_semantic_repairs
        self.semantic_validator = semantic_validator
        self.semantic_diagnostic_builder = (
            semantic_diagnostic_builder or SemanticDiagnosticBuilder()
        )
        self.report_writer = report_writer or ReportWriter()

    @staticmethod
    def _overall_status(
        *, syntax_pass: bool, semantic: SemanticResult, all_attempts_were_compiler_rejections: bool
    ) -> PipelineStatus:
        if not syntax_pass:
            return PipelineStatus.SYNTAX_FAIL if all_attempts_were_compiler_rejections else PipelineStatus.INFRA_ERROR
        mapping = {
            "NOT_RUN": PipelineStatus.SYNTAX_PASS,
            "SEMANTIC_PASS": PipelineStatus.SEMANTIC_PASS,
            "SEMANTIC_FAIL": PipelineStatus.SEMANTIC_FAIL,
            "SEMANTIC_NOT_OBSERVED": PipelineStatus.SEMANTIC_NOT_OBSERVED,
            "INFRA_ERROR": PipelineStatus.INFRA_ERROR,
        }
        return mapping.get(semantic.status, PipelineStatus.INFRA_ERROR)

    def run(
        self,
        source_path: str | Path,
        *,
        candidate_id: str | None = None,
        benchmark: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CandidateResult:
        started = time.monotonic()
        started_at = utc_now()
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Akka source not found: {source}")

        akka_code = source.read_text(encoding="utf-8")
        source_hash = hashlib.sha256(akka_code.encode("utf-8")).hexdigest()
        workspace = self.workspace_manager.create_candidate(candidate_id or source.stem)
        translation = self.translation_pipeline.run(
            akka_code, workspace, benchmark=benchmark
        )
        successful = translation.successful_attempt
        all_attempts = list(translation.attempts)
        semantic_history: list[dict[str, Any]] = []

        if successful and successful.generated_code_path:
            shutil.copy2(successful.generated_code_path, workspace.final_candidate_path)
            syntax_valid_code_path: str | None = str(workspace.final_candidate_path)
            syntax_valid_attempt: int | None = successful.attempt_number
            if benchmark and self.semantic_validator:
                attempt_root = Path(successful.generated_code_path).parent
                try:
                    semantic = self.semantic_validator.validate(
                        syntax_result=successful.syntax,
                        attempt_root=attempt_root,
                        benchmark=benchmark,
                    )
                except Exception as exc:
                    semantic = SemanticResult(
                        executed=False,
                        passed=None,
                        status="INFRA_ERROR",
                        error_stage="semantic_setup",
                        error_message=str(exc),
                    )
            else:
                semantic = SemanticResult(status="NOT_RUN")

            semantic_history.append(
                {
                    "evaluation": "first_pass",
                    "repair_number": 0,
                    "syntax_valid_attempt": successful.attempt_number,
                    "status": semantic.status,
                    "passed": semantic.passed,
                    "error_stage": semantic.error_stage,
                    "error_message": semantic.error_message,
                }
            )

            for repair_number in range(1, self.max_semantic_repairs + 1):
                if semantic.status != "SEMANTIC_FAIL" or not benchmark:
                    break
                previous_code = Path(successful.generated_code_path).read_text(
                    encoding="utf-8"
                )
                attempt_root = Path(successful.generated_code_path).parent
                diagnostic_payload = self.semantic_diagnostic_builder.build(
                    semantic, attempt_root=attempt_root
                )
                diagnostic_path = (
                    workspace.root
                    / f"semantic_repair_{repair_number:02d}_diagnostic.json"
                )
                WorkspaceManager.write_json(diagnostic_path, diagnostic_payload)
                semantic_translation = self.translation_pipeline.repair_semantic(
                    akka_code,
                    workspace,
                    benchmark=benchmark,
                    previous_code=previous_code,
                    semantic_diagnostic=self.semantic_diagnostic_builder.format(
                        semantic, attempt_root=attempt_root
                    ),
                    repair_number=repair_number,
                    start_attempt_number=len(all_attempts) + 1,
                )
                all_attempts.extend(semantic_translation.attempts)
                repaired = semantic_translation.successful_attempt
                if not repaired or not repaired.generated_code_path:
                    semantic_history.append(
                        {
                            "evaluation": "repair_candidate_rejected",
                            "repair_number": repair_number,
                            "status": "SYNTAX_FAIL",
                            "diagnostic_path": str(diagnostic_path),
                            "attempt_numbers": [
                                attempt.attempt_number
                                for attempt in semantic_translation.attempts
                            ],
                        }
                    )
                    break

                successful = repaired
                shutil.copy2(
                    successful.generated_code_path, workspace.final_candidate_path
                )
                syntax_valid_code_path = str(workspace.final_candidate_path)
                syntax_valid_attempt = successful.attempt_number
                repaired_attempt_root = Path(successful.generated_code_path).parent
                try:
                    semantic = self.semantic_validator.validate(
                        syntax_result=successful.syntax,
                        attempt_root=repaired_attempt_root,
                        benchmark=benchmark,
                    )
                except Exception as exc:
                    semantic = SemanticResult(
                        executed=False,
                        passed=None,
                        status="INFRA_ERROR",
                        error_stage="semantic_setup",
                        error_message=str(exc),
                    )
                semantic_history.append(
                    {
                        "evaluation": "repair_assisted",
                        "repair_number": repair_number,
                        "syntax_valid_attempt": successful.attempt_number,
                        "status": semantic.status,
                        "passed": semantic.passed,
                        "error_stage": semantic.error_stage,
                        "error_message": semantic.error_message,
                        "diagnostic_path": str(diagnostic_path),
                    }
                )
        else:
            syntax_valid_code_path = None
            syntax_valid_attempt = None
            semantic = SemanticResult(
                executed=False,
                passed=None,
                status="NOT_RUN",
                error_message="Semantic validation skipped because syntax failed.",
            )

        syntax_pass = successful is not None
        all_attempts_were_compiler_rejections = bool(translation.attempts) and all(
            attempt.syntax.error_category == "COMPILER_REJECTED"
            for attempt in translation.attempts
        )
        result_metadata = dict(metadata or {})
        result_metadata["translation_retry"] = {
            "terminated_early": translation.terminated_early,
            "stop_reason": translation.stop_reason,
            "exhausted": translation.exhausted,
        }
        first_pass_status = (
            semantic_history[0]["status"] if semantic_history else "NOT_RUN"
        )
        result_metadata["semantic_evaluation"] = {
            "max_semantic_repairs": self.max_semantic_repairs,
            "first_pass_status": first_pass_status,
            "final_status": semantic.status,
            "first_pass_semantic_pass": first_pass_status == "SEMANTIC_PASS",
            "repair_assisted_semantic_pass": (
                first_pass_status == "SEMANTIC_FAIL"
                and semantic.status == "SEMANTIC_PASS"
            ),
            "oracle_feedback_used": any(
                entry.get("repair_number", 0) > 0 for entry in semantic_history
            ),
            "history": semantic_history,
        }
        result = CandidateResult(
            candidate_id=candidate_id or source.stem,
            source_akka_path=str(source),
            source_sha256=source_hash,
            workspace_path=str(workspace.root),
            benchmark=benchmark,
            max_attempts=self.max_attempts,
            attempts=all_attempts,
            started_at=started_at,
            finished_at=utc_now(),
            elapsed_seconds=time.monotonic() - started,
            translation_success=syntax_pass,
            syntax_pass=syntax_pass,
            syntax_valid_attempt=syntax_valid_attempt,
            syntax_valid_code_path=syntax_valid_code_path,
            semantic=semantic,
            overall_status=self._overall_status(
                syntax_pass=syntax_pass,
                semantic=semantic,
                all_attempts_were_compiler_rejections=all_attempts_were_compiler_rejections,
            ),
            metadata=result_metadata,
        )
        self.report_writer.write_candidate(result, workspace.result_path)
        return result
