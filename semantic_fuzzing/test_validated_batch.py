import contextlib
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .pipeline import FuzzingConfig, read_json, write_json
from .validated_batch import DIRECTORY, main, make_config


class ValidatedBatchTests(unittest.TestCase):
    def test_recorded_verification_matches_current_sources_specs_and_fixtures(self):
        evidence = read_json(DIRECTORY / "verification.json")
        by_id = {row["id"]: row for row in evidence["cases"]}
        self.assertIs(evidence["live_api_executed"], False)
        for entry in read_json(DIRECTORY / "manifest.json")["cases"]:
            row = by_id[entry["id"]]
            for key, hash_key in (("source", "source_sha256"), ("fixture", "fixture_sha256"),
                                  ("generation_spec", "spec_sha256")):
                self.assertEqual(hashlib.sha256((DIRECTORY / entry[key]).read_bytes()).hexdigest(), row[hash_key])
            self.assertEqual(row["status"], "BOUNDED_MATCH")
            self.assertEqual(row["matched_cases"], 2)
            self.assertEqual([s["seed"] for s in row["scenarios"]], [10000, 10001])

    def test_audit_covers_every_original_with_matching_hash(self):
        originals = DIRECTORY.parent / "research50"
        audit = read_json(DIRECTORY / "audit_originals.json")
        self.assertEqual(len(audit["cases"]), 50)
        for case in audit["cases"]:
            self.assertEqual(hashlib.sha256((originals / case["source"]).read_bytes()).hexdigest(),
                             case["source_sha256"])
        self.assertEqual(len({r["source_sha256"] for r in audit["cases"]}), 37)

    def test_manifest_sources_and_specs_are_distinct_and_bounded(self):
        entries = read_json(DIRECTORY / "manifest.json")["cases"]
        self.assertEqual([e["id"] for e in entries], ["ACSU-01", "ACSU-03", "ACSU-04", "ACSU-05", "ACSU-42"])
        base = FuzzingConfig(Path("/engine"), Path("/rmc.jar"), generation_spec=Path("/wrong.json"))
        for entry in entries:
            for key in ("source", "fixture", "generation_spec"):
                self.assertTrue((DIRECTORY / entry[key]).is_file())
            config = make_config(base, entry, 50, 12345)
            self.assertEqual(config["case_count"], 50)
            self.assertEqual(config["start_seed"], 12345)
            self.assertEqual(config["coverage_mode"], "random")
            self.assertEqual(config["value_coverage"], "random")
            self.assertEqual(config["message_count"], 4)
            self.assertEqual(Path(config["generation_spec"]), DIRECTORY / entry["generation_spec"])
        domains = read_json(DIRECTORY / "specs/Fibonacci.json")["parameter_domains"]
        for domain in domains:
            if domain["message"] in {"Request", "Calculate"}:
                self.assertEqual((domain["minimum"], domain["maximum"]), (0, 8))

    def test_fixture_mode_never_requests_credentials_and_continues_after_error(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "config.json", {"fuzzing_repo": "/engine", "rmc_jar": "/rmc.jar"})
            calls = []

            def execute(command, logs):
                calls.append(command)
                self.assertIn("check", command)
                self.assertNotIn("translate", command)
                output = Path(command[command.index("--output") + 1])
                if len(calls) == 1:
                    return 3
                output.mkdir()
                write_json(output / "result.json", {"status": "INCONCLUSIVE",
                    "semantic_status": "INCONCLUSIVE", "syntax_checks": {"candidate": "PASSED"}})
                return 2

            with patch("semantic_fuzzing.validated_batch.run_translation", side_effect=execute), \
                    patch("semantic_fuzzing.validated_batch.FuzzingConfig.validate"), \
                    patch("semantic_fuzzing.__main__.prepare_credentials") as credentials, \
                    contextlib.redirect_stdout(io.StringIO()):
                code = main(["--config", str(root / "config.json"), "--output", str(root / "out"),
                             "--check-fixtures", "--cases", "2"])
                credentials.assert_not_called()
            self.assertEqual(code, 1)
            self.assertEqual(len(calls), 5)
            report = read_json(root / "out/summary.json")
            self.assertEqual(report["validation_mode"], "HAND_WRITTEN_FIXTURES")
            self.assertEqual(report["cases"][0]["status"], "ERROR")
            self.assertEqual(report["cases"][1]["status"], "INCONCLUSIVE")

    def test_translation_mode_does_not_use_fixtures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "config.json", {"fuzzing_repo": "/engine", "rmc_jar": "/rmc.jar"})
            write_json(root / "translation.json", {"model": "test-model"})
            calls = []

            def execute(command, logs):
                calls.append(command)
                self.assertIn("translate", command)
                self.assertNotIn("--candidate", command)
                output = Path(command[command.index("--output") + 1])
                source = Path(command[command.index("--akka-source") + 1])
                output.mkdir()
                write_json(output / f"{source.stem}_result.json", {
                    "pipeline_status": "SYNTAX_ERROR", "syntax_status": "REJECTED",
                    "semantic_status": "NOT_RUN", "total_attempts": 1})
                return 4

            with patch("semantic_fuzzing.validated_batch.run_translation", side_effect=execute), \
                    patch("semantic_fuzzing.validated_batch.FuzzingConfig.validate"), \
                    patch("semantic_fuzzing.__main__.prepare_credentials"), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--config", str(root / "config.json"), "--output", str(root / "out"),
                                       "--translation-config", str(root / "translation.json")]), 1)
            self.assertEqual(len(calls), 5)


if __name__ == "__main__":
    unittest.main()
