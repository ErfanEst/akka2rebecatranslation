import tempfile
import unittest
from pathlib import Path

from src.artifacts.result_models import SemanticResult
from src.semantic.codegen_diagnostics import CodegenDiagnosticBuilder


class CodegenDiagnosticTests(unittest.TestCase):
    def test_keeps_complete_stdout_and_stderr_and_marks_no_oracle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            stdout_path = root / "stdout.log"
            stderr_path = root / "stderr.log"
            stdout_path.write_text("compiler stdout", encoding="utf-8")
            stderr_path.write_text("line 1\nline 2\n_ref_pong", encoding="utf-8")
            result = SemanticResult(
                executed=True,
                passed=False,
                status="CODEGEN_FAIL",
                error_stage="cpp_compilation",
                error_message="backend rejected",
                commands=[
                    {
                        "stage": "cpp_compile",
                        "stdout_path": str(stdout_path),
                        "stderr_path": str(stderr_path),
                    }
                ],
            )

            payload = CodegenDiagnosticBuilder().build(result)

            self.assertFalse(payload["benchmark_oracle_exposed"])
            self.assertEqual(payload["logs"][0]["stdout"], "compiler stdout")
            self.assertEqual(
                payload["logs"][0]["stderr"], "line 1\nline 2\n_ref_pong"
            )


if __name__ == "__main__":
    unittest.main()
