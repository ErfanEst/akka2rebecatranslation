import unittest

from src.artifacts.result_models import (
    CandidateResult,
    PipelineStatus,
    SemanticResult,
)
from src.pipeline.candidate_pipeline import CandidatePipeline


class ResultModelTests(unittest.TestCase):
    def test_candidate_report_contains_derived_attempt_count_and_status(self) -> None:
        result = CandidateResult(
            candidate_id="x",
            source_akka_path="source.scala",
            source_sha256="abc",
            workspace_path="workspace/x",
            benchmark=None,
            max_attempts=5,
            attempts=[],
            started_at="start",
            finished_at="finish",
            elapsed_seconds=1.0,
            translation_success=False,
            syntax_pass=False,
            syntax_valid_attempt=None,
            syntax_valid_code_path=None,
            semantic=SemanticResult(),
            overall_status=PipelineStatus.SYNTAX_FAIL,
        )
        payload = result.to_dict()
        self.assertEqual(payload["attempts_used"], 0)
        self.assertEqual(payload["final_status"], "SYNTAX_FAIL")

    def test_infrastructure_failure_is_not_reported_as_syntax_failure(self) -> None:
        status = CandidatePipeline._overall_status(
            syntax_pass=False,
            semantic=SemanticResult(),
            all_attempts_were_compiler_rejections=False,
        )
        self.assertEqual(status, PipelineStatus.INFRA_ERROR)

    def test_rmc_rejections_are_reported_as_syntax_failure(self) -> None:
        status = CandidatePipeline._overall_status(
            syntax_pass=False,
            semantic=SemanticResult(),
            all_attempts_were_compiler_rejections=True,
        )
        self.assertEqual(status, PipelineStatus.SYNTAX_FAIL)

    def test_codegen_failure_has_its_own_pipeline_status(self) -> None:
        status = CandidatePipeline._overall_status(
            syntax_pass=True,
            semantic=SemanticResult(status="CODEGEN_FAIL", passed=False),
            all_attempts_were_compiler_rejections=False,
        )
        self.assertEqual(status, PipelineStatus.CODEGEN_FAIL)


if __name__ == "__main__":
    unittest.main()
