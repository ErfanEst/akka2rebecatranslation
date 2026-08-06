import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from src.semantic.semantic_diagnostics import SemanticDiagnosticBuilder


class SemanticDiagnosticBuilderTests(unittest.TestCase):
    def test_includes_diagnostic_trace_but_not_evaluator_source_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            trace = root / "semantic_trace.json"
            evaluator = root / "oracle_implementation.txt"
            trace.write_text('{"expected": 10, "observed": 9}', encoding="utf-8")
            evaluator.write_text("FULL EXPECTED REBECA ANSWER", encoding="utf-8")
            result = SimpleNamespace(
                status="SEMANTIC_FAIL",
                passed=False,
                trace_path=str(trace),
                evaluator_source_path=str(evaluator),
            )

            rendered = SemanticDiagnosticBuilder().format(result, attempt_root=root)
            payload = json.loads(rendered)

            self.assertIn("expected", next(iter(payload["diagnostic_artifacts"].values())))
            self.assertNotIn("FULL EXPECTED REBECA ANSWER", rendered)
            self.assertEqual(payload["result"]["status"], "SEMANTIC_FAIL")


if __name__ == "__main__":
    unittest.main()
