import tempfile
import unittest
from pathlib import Path

from src.artifacts.result_models import LLMResult, SyntaxResult
from src.artifacts.workspace import WorkspaceManager
from src.llm.output_cleaner import OutputCleaner
from src.llm.prompt_builder import PromptBuilder
from src.pipeline.retry_manager import RetryManager
from src.pipeline.translation_pipeline import TranslationPipeline


class FakeLLM:
    model_name = "fake-model"

    def __init__(self) -> None:
        self.responses = [
            "```rebeca\nreactiveclass Broken(1) {}\n```",
            "```rebeca\nreactiveclass Fixed(1) {}\nmain { Fixed f():(); }\n```",
        ]

    def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
        return LLMResult(model=self.model_name, response=self.responses.pop(0))


class FakeSyntaxValidator:
    def __init__(self) -> None:
        self.calls = 0

    def validate(self, candidate_path: Path, attempt_root: Path) -> SyntaxResult:
        self.calls += 1
        if self.calls == 1:
            return SyntaxResult(
                executed=True,
                execution_success=True,
                passed=False,
                return_code=2,
                error_category="COMPILER_REJECTED",
                error_message="line 1: missing main",
            )
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


class TranslationPipelineTests(unittest.TestCase):
    def test_compiler_feedback_reaches_retry_and_artifacts_are_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = WorkspaceManager(directory).create_candidate("counter")
            pipeline = TranslationPipeline(
                llm_client=FakeLLM(),
                prompt_builder=PromptBuilder(),
                output_cleaner=OutputCleaner(),
                syntax_validator=FakeSyntaxValidator(),
                retry_manager=RetryManager(5),
            )
            result = pipeline.run("class Counter extends Actor", workspace)

            self.assertEqual(len(result.attempts), 2)
            self.assertEqual(result.successful_attempt.attempt_number, 2)
            retry_prompt = (workspace.root / "attempt_2" / "prompt.json").read_text(
                encoding="utf-8"
            )
            self.assertIn("line 1: missing main", retry_prompt)
            self.assertTrue(
                (workspace.root / "attempt_1" / "candidate.rebeca").is_file()
            )
            self.assertTrue(
                (workspace.root / "attempt_2" / "candidate.rebeca").is_file()
            )
            self.assertIn("reactiveclass Broken", result.attempts[0].generated_code)
            self.assertIsNotNone(result.attempts[0].generated_code_sha256)

    def test_non_retryable_api_error_stops_after_one_attempt(self) -> None:
        class PermanentFailureLLM:
            model_name = "gpt-5.6-sol"
            provider_name = "openai"
            requested_parameters = {"temperature": 0.0}
            effective_parameters = {"temperature": 0.0}

            def generate(self, system_prompt: str, user_prompt: str) -> LLMResult:
                raise RuntimeError(
                    "Error code: 400 invalid_request_error unsupported value "
                    "for param temperature"
                )

        with tempfile.TemporaryDirectory() as directory:
            workspace = WorkspaceManager(directory).create_candidate("failure")
            pipeline = TranslationPipeline(
                llm_client=PermanentFailureLLM(),
                prompt_builder=PromptBuilder(),
                output_cleaner=OutputCleaner(),
                syntax_validator=FakeSyntaxValidator(),
                retry_manager=RetryManager(5),
            )
            result = pipeline.run("class Counter extends Actor", workspace)

            self.assertEqual(len(result.attempts), 1)
            self.assertTrue(result.terminated_early)
            self.assertEqual(result.stop_reason, "UNSUPPORTED_PARAMETER")
            self.assertEqual(
                result.attempts[0].llm.error_category, "UNSUPPORTED_PARAMETER"
            )


if __name__ == "__main__":
    unittest.main()
