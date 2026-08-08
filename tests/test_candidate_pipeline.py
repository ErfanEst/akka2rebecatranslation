import json
import tempfile
import unittest
from pathlib import Path

from src.artifacts.result_models import LLMResult, PipelineStatus, SemanticResult, SyntaxResult
from src.artifacts.workspace import WorkspaceManager
from src.llm.output_cleaner import OutputCleaner
from src.llm.prompt_builder import PromptBuilder
from src.pipeline.candidate_pipeline import CandidatePipeline
from src.pipeline.retry_manager import RetryManager
from src.pipeline.translation_pipeline import TranslationPipeline


class OneResponseLLM:
    model_name = "fake-model"

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        return LLMResult(
            model=self.model_name,
            response="reactiveclass A(1) {}\nmain { A a():(); }",
        )


class PassingSyntaxValidator:
    def validate(self, candidate_path: Path, attempt_root: Path) -> SyntaxResult:
        generated = attempt_root / "generated_cpp"
        generated.mkdir()
        (generated / "model.cpp").write_text("int main() {}", encoding="utf-8")
        return SyntaxResult(
            executed=True,
            execution_success=True,
            passed=True,
            return_code=0,
            generated_cpp_path=str(generated),
        )


class PassingSemanticValidator:
    def validate(self, *, syntax_result, attempt_root, benchmark) -> SemanticResult:
        return SemanticResult(
            executed=True,
            passed=True,
            status="SEMANTIC_PASS",
            passed_tests=3,
            failed_tests=0,
            not_observed_tests=0,
            total_tests=3,
        )


class CandidatePipelineTests(unittest.TestCase):
    def test_codegen_failure_can_be_repaired_without_oracle_feedback(self) -> None:
        class CodegenThenPassingSemanticValidator:
            def __init__(self) -> None:
                self.calls = 0

            def validate(self, *, syntax_result, attempt_root, benchmark):
                self.calls += 1
                if self.calls == 1:
                    return SemanticResult(
                        executed=True,
                        passed=False,
                        status="CODEGEN_FAIL",
                        error_stage="cpp_compilation",
                        error_message="_ref_pong collision",
                    )
                return SemanticResult(
                    executed=True,
                    passed=True,
                    status="SEMANTIC_PASS",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "actor.scala"
            source.write_text("class A extends Actor", encoding="utf-8")
            semantic_validator = CodegenThenPassingSemanticValidator()
            translation = TranslationPipeline(
                llm_client=OneResponseLLM(),
                prompt_builder=PromptBuilder(
                    codegen_retry_template=(
                        "{akka_code}\n{previous_code}\n{codegen_diagnostic}\n"
                        "{rmc_extension}\n{mailbox_policy}"
                    )
                ),
                output_cleaner=OutputCleaner(),
                syntax_validator=PassingSyntaxValidator(),
                retry_manager=RetryManager(1),
            )
            pipeline = CandidatePipeline(
                translation_pipeline=translation,
                workspace_manager=WorkspaceManager(root / "workspace"),
                max_attempts=1,
                max_codegen_repairs=1,
                semantic_validator=semantic_validator,
            )

            result = pipeline.run(
                source, candidate_id="actor", benchmark="simple_counter"
            )

            self.assertEqual(result.overall_status, PipelineStatus.SEMANTIC_PASS)
            self.assertEqual(result.attempts_used, 2)
            self.assertEqual(result.attempts[1].prompt["phase"], "codegen_repair")
            self.assertFalse(
                result.attempts[1].prompt["metadata"]["benchmark_oracle_exposed"]
            )
            self.assertTrue(
                result.metadata["codegen_evaluation"][
                    "repair_assisted_codegen_pass"
                ]
            )
            self.assertEqual(
                result.metadata["codegen_evaluation"]["final_codegen_status"],
                "CODEGEN_PASS",
            )
            self.assertFalse(
                result.metadata["semantic_evaluation"]["oracle_feedback_used"]
            )

    def test_codegen_repair_infra_failure_is_not_counted_as_codegen_pass(self) -> None:
        class CodegenThenInfraValidator:
            def __init__(self) -> None:
                self.calls = 0

            def validate(self, *, syntax_result, attempt_root, benchmark):
                self.calls += 1
                if self.calls == 1:
                    return SemanticResult(
                        executed=True,
                        passed=False,
                        status="CODEGEN_FAIL",
                        error_stage="cpp_compilation",
                    )
                return SemanticResult(
                    executed=False,
                    passed=None,
                    status="INFRA_ERROR",
                    error_stage="model_checker",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "actor.scala"
            source.write_text("class A extends Actor", encoding="utf-8")
            pipeline = CandidatePipeline(
                translation_pipeline=TranslationPipeline(
                    llm_client=OneResponseLLM(),
                    prompt_builder=PromptBuilder(
                        codegen_retry_template=(
                            "{akka_code}\n{previous_code}\n{codegen_diagnostic}\n"
                            "{rmc_extension}\n{mailbox_policy}"
                        )
                    ),
                    output_cleaner=OutputCleaner(),
                    syntax_validator=PassingSyntaxValidator(),
                    retry_manager=RetryManager(1),
                ),
                workspace_manager=WorkspaceManager(root / "workspace"),
                max_attempts=1,
                max_codegen_repairs=1,
                semantic_validator=CodegenThenInfraValidator(),
            )

            result = pipeline.run(
                source, candidate_id="actor", benchmark="simple_counter"
            )

            self.assertEqual(result.overall_status, PipelineStatus.INFRA_ERROR)
            self.assertFalse(
                result.metadata["codegen_evaluation"][
                    "repair_assisted_codegen_pass"
                ]
            )
            self.assertEqual(
                result.metadata["codegen_evaluation"]["final_codegen_status"],
                "INFRA_ERROR",
            )

    def test_writes_one_complete_candidate_report(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "actor.scala"
            source.write_text("class A extends Actor", encoding="utf-8")
            workspace_manager = WorkspaceManager(root / "workspace")
            translation = TranslationPipeline(
                llm_client=OneResponseLLM(),
                prompt_builder=PromptBuilder(),
                output_cleaner=OutputCleaner(),
                syntax_validator=PassingSyntaxValidator(),
                retry_manager=RetryManager(5),
            )
            pipeline = CandidatePipeline(
                translation_pipeline=translation,
                workspace_manager=workspace_manager,
                max_attempts=5,
                semantic_validator=PassingSemanticValidator(),
            )
            result = pipeline.run(
                source, candidate_id="actor", benchmark="simple_counter"
            )

            self.assertEqual(result.overall_status, PipelineStatus.SEMANTIC_PASS)
            report_path = root / "workspace" / "actor" / "candidate_result.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["final_status"], "SEMANTIC_PASS")
            self.assertEqual(report["attempts_used"], 1)
            self.assertTrue(report["syntax_pass"])
            self.assertTrue(report["syntax"]["passed"])
            self.assertEqual(report["syntax"]["valid_attempt"], 1)
            self.assertTrue(report["semantic"]["passed"])
            self.assertIn("usage_and_cost", report)
            self.assertEqual(report["usage_and_cost"]["request_count"], 1)
            self.assertTrue(
                (root / "workspace" / "actor" / "final_candidate.rebeca").is_file()
            )

    def test_failed_code_is_embedded_in_candidate_report(self) -> None:
        class RejectingSyntaxValidator:
            def validate(self, candidate_path: Path, attempt_root: Path) -> SyntaxResult:
                return SyntaxResult(
                    executed=True,
                    execution_success=True,
                    passed=False,
                    error_category="COMPILER_REJECTED",
                    error_message="bad syntax",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "actor.scala"
            source.write_text("class A extends Actor", encoding="utf-8")
            pipeline = CandidatePipeline(
                translation_pipeline=TranslationPipeline(
                    llm_client=OneResponseLLM(),
                    prompt_builder=PromptBuilder(),
                    output_cleaner=OutputCleaner(),
                    syntax_validator=RejectingSyntaxValidator(),
                    retry_manager=RetryManager(1),
                ),
                workspace_manager=WorkspaceManager(root / "workspace"),
                max_attempts=1,
            )

            pipeline.run(source, candidate_id="actor")
            report = json.loads(
                (root / "workspace" / "actor" / "candidate_result.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(report["failed_candidates"]), 1)
            self.assertIn("reactiveclass A", report["failed_candidates"][0]["code"])
            self.assertIn(
                "reactiveclass A", report["attempts"][0]["generated_code"]
            )


if __name__ == "__main__":
    unittest.main()
