import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from src.artifacts.result_models import SyntaxResult
from src.cli.validate_candidate import validate


class ValidateCandidateCliTests(unittest.TestCase):
    def test_offline_path_records_zero_llm_requests(self) -> None:
        class FakeCompiler:
            def preflight(self) -> None:
                return None

        class FakeSyntaxValidator:
            def __init__(self, compiler) -> None:
                self.compiler = compiler

            def validate(self, candidate_path, attempt_root):
                return SyntaxResult(
                    executed=True,
                    execution_success=True,
                    passed=False,
                    return_code=0,
                    error_category="COMPILER_REJECTED",
                    error_message="test rejection",
                )

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate = root / "candidate.rebeca"
            candidate.write_text("main {}", encoding="utf-8")
            workspace = root / "offline"
            args = Namespace(
                candidate=candidate,
                benchmark="simple_counter",
                workspace_root=workspace,
                rmc_jar=Path("rmc.jar"),
                java_bin=Path("java"),
                rmc_extension="CORE_REBECA",
                rmc_timeout=120,
                gpp_bin="g++",
                compile_timeout=120,
                model_checker_timeout=300,
                evaluator_timeout=120,
            )

            with patch(
                "src.cli.validate_candidate.shutil.which", return_value="/usr/bin/g++"
            ), patch(
                "src.cli.validate_candidate.RmcCompiler", return_value=FakeCompiler()
            ), patch(
                "src.cli.validate_candidate.SyntaxValidator", FakeSyntaxValidator
            ):
                payload, exit_code = validate(args)

            self.assertEqual(exit_code, 2)
            self.assertEqual(payload["llm_request_count"], 0)
            self.assertEqual(payload["final_status"], "SYNTAX_FAIL")
            self.assertTrue(
                (workspace / "offline_validation_result.json").is_file()
            )


if __name__ == "__main__":
    unittest.main()
