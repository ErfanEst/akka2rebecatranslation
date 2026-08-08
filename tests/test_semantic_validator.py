import json
import tempfile
import unittest
from pathlib import Path

from src.artifacts.result_models import SyntaxResult
from src.semantic.semantic_validator import SemanticValidator
from src.syntax.rmc_compiler import CommandResult


class FakeSemanticRunner:
    def run(self, command, *, cwd, timeout_seconds):
        if command[0] == "g++":
            (cwd / "model_checker").write_text("fake", encoding="utf-8")
        elif command[0].endswith("model_checker"):
            (cwd / command[command.index("-o") + 1]).write_text(
                "<result/>", encoding="utf-8"
            )
        elif command[1].endswith("rmc_result_parser.py"):
            Path(command[command.index("-o") + 1]).write_text(
                json.dumps({"states": [], "transitions": []}), encoding="utf-8"
            )
        else:
            Path(command[command.index("-o") + 1]).write_text(
                json.dumps(
                    {
                        "semantic_pass": False,
                        "passed_tests": 2,
                        "failed_tests": 0,
                        "not_observed_tests": 1,
                        "total_tests": 3,
                        "not_observed_test_ids": ["COUNTER-A3"],
                    }
                ),
                encoding="utf-8",
            )
        return CommandResult(
            command=command,
            return_code=0,
            stdout="ok",
            stderr="",
            duration_seconds=0.01,
        )


class SemanticValidatorTests(unittest.TestCase):
    def test_cpp_rejection_is_candidate_codegen_failure_not_infra_error(self) -> None:
        class RejectingCppRunner:
            def run(self, command, *, cwd, timeout_seconds):
                return CommandResult(
                    command=command,
                    return_code=1,
                    stdout="",
                    stderr="PingActor.cpp: error: _ref_pong collision",
                    duration_seconds=0.01,
                )

        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            attempt_root = Path(directory)
            generated = attempt_root / "generated_cpp"
            generated.mkdir()
            (generated / "PingActor.cpp").write_text(
                "int main() {}", encoding="utf-8"
            )
            result = SemanticValidator(
                project_root=project_root, runner=RejectingCppRunner()
            ).validate(
                syntax_result=SyntaxResult(
                    executed=True,
                    execution_success=True,
                    passed=True,
                    generated_cpp_path=str(generated),
                ),
                attempt_root=attempt_root,
                benchmark="simple_ping_pong",
            )

            self.assertEqual(result.status, "CODEGEN_FAIL")
            self.assertFalse(result.passed)
            self.assertEqual(result.error_stage, "cpp_compilation")
            self.assertIn("_ref_pong collision", result.error_message)
            self.assertIn(
                "_ref_pong collision",
                (attempt_root / "semantic" / "cpp_compile_stderr.log").read_text(),
            )

    def test_reuses_generated_cpp_and_preserves_not_observed(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            attempt_root = Path(directory)
            generated = attempt_root / "generated_cpp"
            generated.mkdir()
            (generated / "model.cpp").write_text("int main() {}", encoding="utf-8")
            syntax = SyntaxResult(
                executed=True,
                execution_success=True,
                passed=True,
                generated_cpp_path=str(generated),
            )
            result = SemanticValidator(
                project_root=project_root, runner=FakeSemanticRunner()
            ).validate(
                syntax_result=syntax,
                attempt_root=attempt_root,
                benchmark="simple_counter",
            )

            self.assertEqual(result.status, "SEMANTIC_NOT_OBSERVED")
            self.assertFalse(result.passed)
            self.assertEqual(result.not_observed_test_ids, ["COUNTER-A3"])
            self.assertTrue((generated / "result.xml").is_file())
            self.assertEqual(len(result.commands), 4)

    def test_derives_failed_ids_and_keeps_full_legacy_test_details(self) -> None:
        class LegacyResultRunner(FakeSemanticRunner):
            def run(self, command, *, cwd, timeout_seconds):
                if command[0] == "g++":
                    (cwd / "model_checker").write_text("fake", encoding="utf-8")
                elif command[0].endswith("model_checker"):
                    (cwd / command[command.index("-o") + 1]).write_text(
                        "<result/>", encoding="utf-8"
                    )
                elif command[1].endswith("rmc_result_parser.py"):
                    Path(command[command.index("-o") + 1]).write_text(
                        json.dumps({"states": [], "transitions": []}),
                        encoding="utf-8",
                    )
                else:
                    Path(command[command.index("-o") + 1]).write_text(
                        json.dumps(
                            {
                                "semantic_tests": [
                                    {
                                        "test_id": "PING-A1",
                                        "passed": False,
                                        "details": "message missing",
                                    },
                                    {
                                        "test_id": "PING-A2",
                                        "passed": True,
                                        "details": "ok",
                                    },
                                ],
                                "summary": {
                                    "passed": 1,
                                    "failed": 1,
                                    "total": 2,
                                    "semantic_pass": False,
                                },
                            }
                        ),
                        encoding="utf-8",
                    )
                return CommandResult(
                    command=command,
                    return_code=0,
                    stdout="ok",
                    stderr="",
                    duration_seconds=0.01,
                )

        project_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as directory:
            attempt_root = Path(directory)
            generated = attempt_root / "generated_cpp"
            generated.mkdir()
            (generated / "model.cpp").write_text("int main() {}", encoding="utf-8")
            result = SemanticValidator(
                project_root=project_root, runner=LegacyResultRunner()
            ).validate(
                syntax_result=SyntaxResult(
                    executed=True,
                    execution_success=True,
                    passed=True,
                    generated_cpp_path=str(generated),
                ),
                attempt_root=attempt_root,
                benchmark="simple_ping_pong",
            )
            self.assertEqual(result.failed_test_ids, ["PING-A1"])
            self.assertEqual(
                result.semantic_test_results[0]["details"], "message missing"
            )


if __name__ == "__main__":
    unittest.main()
