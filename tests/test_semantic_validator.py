import json
import tempfile
import unittest
from pathlib import Path

from semantic_validation.core.evaluator_registry import get_benchmark_config
from semantic_validation.core.semantic_contract import load_semantic_contract
from src.artifacts.result_models import SyntaxResult
from src.semantic.semantic_validator import SemanticValidator
from src.syntax.rmc_compiler import CommandResult


def contract_test_results(
    benchmark: str,
    *,
    status_overrides: dict[str, str] | None = None,
    details_overrides: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    contract = load_semantic_contract(get_benchmark_config(benchmark).spec_path)
    status_overrides = status_overrides or {}
    details_overrides = details_overrides or {}

    return [
        {
            "test_id": test_id,
            "status": status_overrides.get(test_id, "PASS"),
            "details": details_overrides.get(test_id, "ok"),
        }
        for test_id in contract.mandatory_test_ids
    ]


class FakeSemanticRunner:
    def __init__(self, semantic_tests: list[dict[str, object]]) -> None:
        self.semantic_tests = semantic_tests

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
                json.dumps({"semantic_tests": self.semantic_tests}),
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
                project_root=project_root,
                runner=RejectingCppRunner(),
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
        semantic_tests = contract_test_results(
            "simple_counter",
            status_overrides={"COUNTER-A3": "NOT_OBSERVED"},
        )

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
                project_root=project_root,
                runner=FakeSemanticRunner(semantic_tests),
            ).validate(
                syntax_result=syntax,
                attempt_root=attempt_root,
                benchmark="simple_counter",
            )

            self.assertEqual(result.status, "SEMANTIC_NOT_OBSERVED")
            self.assertFalse(result.passed)
            self.assertEqual(result.not_observed_test_ids, ["COUNTER-A3"])
            self.assertTrue((generated / "result.xml").is_file())
            self.assertTrue(
                (attempt_root / "semantic" / "semantic_contract_check.json").is_file()
            )
            self.assertEqual(len(result.commands), 4)

    def test_contract_coverage_mismatch_is_infrastructure_error(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        semantic_tests = contract_test_results("simple_counter")[:-1]

        with tempfile.TemporaryDirectory() as directory:
            attempt_root = Path(directory)
            generated = attempt_root / "generated_cpp"
            generated.mkdir()
            (generated / "model.cpp").write_text("int main() {}", encoding="utf-8")

            result = SemanticValidator(
                project_root=project_root,
                runner=FakeSemanticRunner(semantic_tests),
            ).validate(
                syntax_result=SyntaxResult(
                    executed=True,
                    execution_success=True,
                    passed=True,
                    generated_cpp_path=str(generated),
                ),
                attempt_root=attempt_root,
                benchmark="simple_counter",
            )

            self.assertEqual(result.status, "INFRA_ERROR")
            self.assertEqual(result.error_stage, "semantic_contract_consistency")
            self.assertIn("missing_mandatory_test_ids", result.error_message)
            self.assertTrue(
                (attempt_root / "semantic" / "semantic_contract_check.json").is_file()
            )

    def test_keeps_full_test_details_and_uses_contract_for_failed_ids(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        semantic_tests = contract_test_results(
            "simple_ping_pong",
            status_overrides={"PING-A1": "FAIL"},
            details_overrides={"PING-A1": "message missing"},
        )

        with tempfile.TemporaryDirectory() as directory:
            attempt_root = Path(directory)
            generated = attempt_root / "generated_cpp"
            generated.mkdir()
            (generated / "model.cpp").write_text("int main() {}", encoding="utf-8")

            result = SemanticValidator(
                project_root=project_root,
                runner=FakeSemanticRunner(semantic_tests),
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

            self.assertEqual(result.status, "SEMANTIC_FAIL")
            self.assertEqual(result.failed_test_ids, ["PING-A1"])
            ping_a1 = next(
                test
                for test in result.semantic_test_results
                if test["test_id"] == "PING-A1"
            )
            self.assertEqual(ping_a1["details"], "message missing")


if __name__ == "__main__":
    unittest.main()
