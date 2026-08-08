import json
import tempfile
import unittest
from pathlib import Path

from src.reporting.grid_markdown_report import write_grid_markdown_report


class GridMarkdownReportTests(unittest.TestCase):
    def test_embeds_failed_code_compiler_log_and_semantic_test_details(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidate_root = root / "setting" / "simplePingPong"
            semantic_root = candidate_root / "attempt_1" / "semantic"
            semantic_root.mkdir(parents=True)
            stdout_path = candidate_root / "attempt_1" / "rmc_stdout.log"
            stderr_path = candidate_root / "attempt_1" / "rmc_stderr.log"
            stdout_path.write_text("line 7 parser error", encoding="utf-8")
            stderr_path.write_text("full stack trace", encoding="utf-8")
            semantic_path = semantic_root / "semantic_result.json"
            semantic_payload = {
                "semantic_tests": [
                    {
                        "test_id": "PING-A1",
                        "passed": False,
                        "details": "PingMessage was not observed",
                    }
                ]
            }
            semantic_path.write_text(json.dumps(semantic_payload), encoding="utf-8")
            candidate_path = candidate_root / "candidate_result.json"
            candidate_path.write_text(
                json.dumps(
                    {
                        "candidate_id": "simplePingPong",
                        "final_status": "SEMANTIC_FAIL",
                        "syntax_pass": True,
                        "semantic": {
                            "status": "SEMANTIC_FAIL",
                            "failed_test_ids": ["PING-A1"],
                            "not_observed_test_ids": [],
                            "semantic_test_results": semantic_payload["semantic_tests"],
                        },
                        "attempts": [
                            {
                                "attempt_number": 1,
                                "prompt": {"phase": "initial_generation"},
                                "llm": {
                                    "cache_status": "HIT",
                                    "input_tokens": 2000,
                                    "cached_input_tokens": 1500,
                                    "output_tokens": 100,
                                    "cost_usd": 0.001,
                                },
                                "generated_code": "reactiveclass Broken(1) {}",
                                "syntax": {
                                    "passed": False,
                                    "error_category": "COMPILER_REJECTED",
                                    "error_message": "bad syntax",
                                    "stdout_path": str(stdout_path),
                                    "stderr_path": str(stderr_path),
                                },
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            grid_result = {
                "started_at": "start",
                "finished_at": "finish",
                "input": "simplePingPong.txt",
                "workspace_root": str(root),
                "completed_settings": 1,
                "total_settings": 1,
                "setting_status_counts": {"COMPLETED_WITH_VALIDATION_FAILURES": 1},
                "candidate_status_counts": {"SEMANTIC_FAIL": 1},
                "usage_and_cost": {"request_count": 1, "known_cost_usd": 0.001},
                "usage_and_cost_by_model": [],
                "outcome_index": [
                    {
                        "setting_id": "openai/gpt-5.1/handbook/temp0_topp1",
                        "candidate_id": "simplePingPong",
                        "status": "SEMANTIC_FAIL",
                        "syntax_valid_attempt": 1,
                        "final_codegen_status": "CODEGEN_PASS",
                        "semantic_status": "SEMANTIC_FAIL",
                        "report": str(candidate_path),
                    }
                ],
                "semantic_passes": [],
                "settings": [
                    {
                        "setting_id": "openai/gpt-5.1/handbook/temp0_topp1",
                        "status": "COMPLETED_WITH_VALIDATION_FAILURES",
                        "requested_parameters": {},
                        "effective_parameters": {},
                        "candidates": [{"report": str(candidate_path)}],
                    }
                ],
            }
            (root / "grid_result.json").write_text(
                json.dumps(grid_result), encoding="utf-8"
            )

            report_path = write_grid_markdown_report(root)
            report = report_path.read_text(encoding="utf-8")
            for expected in (
                "reactiveclass Broken(1)",
                "line 7 parser error",
                "full stack trace",
                "PING-A1",
                "PingMessage was not observed",
                "Cache: `HIT`",
                "## Outcome index",
                "CODEGEN_PASS",
            ):
                self.assertIn(expected, report)


if __name__ == "__main__":
    unittest.main()
