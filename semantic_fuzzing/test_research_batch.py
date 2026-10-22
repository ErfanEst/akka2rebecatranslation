import contextlib
import io
import json
from pathlib import Path
import tempfile
import sys
import unittest
from unittest.mock import patch

from .pipeline import FuzzingConfig, read_json, write_json
from .research_batch import main, prepare_config, run_translation, select_cases, summarize_result


class ResearchBatchTests(unittest.TestCase):
    def test_real_process_logs_both_streams_and_returns_exit_code(self):
        with tempfile.TemporaryDirectory(prefix="logs with spaces ") as directory:
            logs = Path(directory)
            code = run_translation([sys.executable, "-c",
                                    "import sys; print('output'); print('diagnostic', file=sys.stderr); sys.exit(7)"],
                                   logs)
            self.assertEqual(code, 7)
            self.assertIn("output", (logs / "translate.stdout.log").read_text())
            self.assertIn("diagnostic", (logs / "translate.stderr.log").read_text())

    def test_groups_preserve_original_numbers(self):
        groups = [select_cases(i, 5) for i in range(1, 11)]
        self.assertEqual(len({p for group in groups for p in group}), 50)
        self.assertEqual([read_json(p)["id"] for p in groups[0]],
                         [f"ACSU-{i:02d}" for i in range(1, 6)])
        with self.assertRaises(ValueError):
            select_cases(11, 5)

    def test_config_clears_unrelated_scenario_constraints(self):
        base = FuzzingConfig(Path("/engine"), Path("/rmc.jar"),
                            generation_spec=Path("/session.json"),
                            first_case_scenario=Path("/replay.json"),
                            initial_priority_branches=[{"branch": "session"}])
        result = prepare_config(base, 50, 10000)
        self.assertEqual(result["case_count"], 50)
        self.assertEqual(result["coverage_mode"], "random")
        self.assertEqual(result["value_coverage"], "random")
        self.assertIsNone(result["generation_spec"])
        self.assertIsNone(result["first_case_scenario"])
        self.assertEqual(result["initial_priority_branches"], [])

    def test_batch_continues_after_failure_and_resumes_without_rebilling(self):
        with tempfile.TemporaryDirectory(prefix="batch with spaces ") as directory:
            root = Path(directory)
            write_json(root / "runtime.json", {"fuzzing_repo": "/engine", "rmc_jar": "/rmc.jar"})
            write_json(root / "translation.json", {"max_retries": 1})
            arguments = ["--group", "1", "--config", str(root / "runtime.json"),
                         "--translation-config", str(root / "translation.json"),
                         "--output", str(root / "output")]
            calls = []

            def execute(command, logs):
                calls.append(command)
                config = read_json(Path(command[command.index("--config") + 1]))
                self.assertEqual(config["case_count"], 50)
                self.assertEqual(config["start_seed"], 10000)
                source = Path(command[command.index("--akka-source") + 1])
                if source.stem == "RouterDocSpec":
                    return 3  # Missing result must not prevent the next example.
                output = Path(command[command.index("--output") + 1])
                output.mkdir()
                write_json(output / f"{source.stem}_result.json", {
                    "pipeline_status": "INCONCLUSIVE", "syntax_status": "PASSED",
                    "semantic_status": "INCONCLUSIVE", "total_attempts": 1})
                return 2

            with patch("semantic_fuzzing.research_batch.run_translation", side_effect=execute), \
                    patch("semantic_fuzzing.research_batch.FuzzingConfig.validate"), \
                    patch("semantic_fuzzing.__main__.prepare_credentials"), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(arguments), 1)
                self.assertEqual(len(calls), 5)
                report = read_json(root / "output/summary.json")
                self.assertEqual(report["cases"][0]["status"], "ERROR")
                self.assertEqual(report["cases"][1]["status"], "INCONCLUSIVE")
                self.assertTrue((root / "output/compatibility.md").is_file())
                self.assertEqual(report["identity"]["inputs"][0]["status"], "PENDING")
                self.assertEqual(main(arguments + ["--resume"]), 1)
                self.assertEqual(len(calls), 5)
                with contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(main(arguments + ["--resume", "--cases", "51"]), 2)

    def test_summary_counts_actual_evidence_not_requested_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "fuzzing.json", {"campaign": {"cases": [
                {"model_results": [{"kind": "candidate", "trusted_trace_result": True,
                                    "trace_status": "TRACE_PREFIX_MATCH", "observed_event_count": 2}]},
                {"model_results": [{"kind": "candidate", "trusted_trace_result": False,
                                    "trace_status": "TRACE_PREFIX_MATCH", "observed_event_count": 0}]}]}})
            write_json(root / "translation.json", {"pipeline_status": "INCONCLUSIVE",
                       "semantic_checks": [{"result_file": str(root / "fuzzing.json")}]})
            result = summarize_result(root / "translation.json")
            self.assertEqual(result["completed_cases"], 2)
            self.assertEqual(result["matched_cases"], 1)

    def test_dry_run_needs_no_runtime_or_api(self):
        with patch("semantic_fuzzing.research_batch.run_translation") as stage, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--group", "10", "--dry-run", "--config", "/missing"]), 0)
            stage.assert_not_called()


if __name__ == "__main__":
    unittest.main()
