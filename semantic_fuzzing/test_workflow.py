import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .__main__ import prepare_credentials
from .pipeline import FuzzingConfig, FuzzingPipeline, StageError, read_json


class SyntaxGateTests(unittest.TestCase):
    def run_gate(self, root, stage):
        source = root / "Example.scala"
        model = root / "Example.rebeca"
        source.write_text("object Example {}")
        model.write_text("invalid")
        cfg = FuzzingConfig(root / "missing-engine", model)
        with patch.object(cfg, "validate"), patch("semantic_fuzzing.pipeline.run_stage", side_effect=stage):
            return FuzzingPipeline(cfg).check([source], model, root / "output")

    def test_zero_exit_without_artifact_stops_before_semantics(self):
        calls = []
        def stage(name, command, cwd, logs, timeout):
            calls.append(name)
            for stream in ("stdout", "stderr"):
                (logs / f"{name}.{stream}.log").write_text("syntax error")
            return 0
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = self.run_gate(root, stage)
            self.assertEqual(calls, ["rmc_candidate"])
            self.assertEqual(result["status"], "SYNTAX_ERROR")
            self.assertEqual(result["semantic_status"], "NOT_RUN")
            self.assertFalse(result["success"])
            self.assertFalse((root / "output/akka-interface-extractor").exists())
            self.assertEqual(read_json(root / "output/result.json"), result)
            self.assertTrue((root / "output/report.md").is_file())
            self.assertTrue((root / "output/sources/Example.scala").is_file())

    def test_compiler_failure_is_not_misreported_as_semantic_mismatch(self):
        def stage(*args):
            raise StageError("rmc_candidate", "java failed")
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_gate(Path(directory), stage)
            self.assertEqual(result["status"], "ERROR")
            self.assertEqual(result["syntax_checks"], {"candidate": "ERROR"})
            self.assertEqual(result["semantic_status"], "NOT_RUN")

    def test_syntax_pass_is_retained_when_later_setup_fails(self):
        def stage(name, command, cwd, logs, timeout):
            generated = Path(command[command.index("-o") + 1])
            generated.mkdir(parents=True)
            (generated / "CoreRebecaModelChecker.cpp").write_text("generated")
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_gate(Path(directory), stage)
            self.assertEqual(result["syntax_checks"], {"candidate": "PASSED"})
            self.assertEqual(result["semantic_status"], "ERROR")
            self.assertFalse(result["success"])


class CredentialTests(unittest.TestCase):
    def test_cloud_alias_maps_without_exposing_secret(self):
        with patch.dict(os.environ, {"TRANSLATION_API_KEY": "unit-test-placeholder"}, clear=True), \
                patch("dotenv.load_dotenv"):
            prepare_credentials()
            self.assertEqual(os.environ["OPENAI_API_KEY"], "unit-test-placeholder")

    def test_missing_key_fails_before_client_creation(self):
        with patch.dict(os.environ, {}, clear=True), patch("dotenv.load_dotenv"), \
                self.assertRaisesRegex(ValueError, "No translation request was made"):
            prepare_credentials()


if __name__ == "__main__":
    unittest.main()
