import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from .pipeline import read_json, write_json
from .retest_stateful import SUITE, digest, freeze_translation, main, scenario_steps, make_spec, verify_generated_inputs


class RetestStatefulTests(unittest.TestCase):
    def test_plans_are_reproducible_varied_and_protocol_bounded(self):
        for case_id in ("ACSU-09", "ACSU-10", "ACSU-25", "FSM-01"):
            plans = make_spec(case_id, range(20000, 20050), 16)
            self.assertEqual(plans, make_spec(case_id, range(20000, 20050), 16))
            steps = [x[0]["steps"] for x in plans["seeded_sequence_templates"].values()]
            self.assertGreaterEqual(len({json.dumps(s) for s in steps}), 49)
            for scenario in steps:
                self.assertEqual(len(scenario), 16)
                for step in scenario:
                    self.assertEqual(step["sender"], "client")
                    self.assertIn(step["receiver"], {"worker", "client"})
                    for arg in step["arguments"]:
                        self.assertTrue(-7 <= arg["literal"] <= 7)
        with self.assertRaises(ValueError):
            scenario_steps("FSM-01", 1, 7)

    def prepare_archive(self, root):
        entry = read_json(SUITE / "manifest.json")["cases"][-1]
        folder = root / "FSM-01/translation"
        (folder / "semantic_checks/attempt/fuzzing").mkdir(parents=True)
        code = "frozen code"
        write_json(folder / "ScalarFsm_result.json", {"success": True, "final_code": code,
                                                    "semantic_status": "BOUNDED_MATCH"})
        write_json(folder / "semantic_checks/attempt/fuzzing/result.json", {
            "status": "BOUNDED_MATCH", "inputs": [
                {"path": "/old/ScalarFsm.scala", "sha256": digest((SUITE / entry["source"]).read_bytes())},
                {"path": "/old/candidate.rebeca", "sha256": digest(code.encode())}]})
        return entry, folder, code

    def test_relocated_archive_hash_check_and_tampering_rejection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry, folder, code = self.prepare_archive(root)
            self.assertEqual(freeze_translation(entry, root)[0], code)
            write_json(folder / "ScalarFsm_result.json", {"success": True, "final_code": "changed"})
            with self.assertRaisesRegex(ValueError, "hashes"):
                freeze_translation(entry, root)

    def test_plan_only_does_not_invoke_pipeline_or_credentials(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.prepare_archive(root / "archives")
            engine = root / "engine"
            (engine / "scripts").mkdir(parents=True)
            (engine / "scripts/generate_random_scenario.py").write_text("seeded_sequence_templates")
            write_json(root / "config.json", {"fuzzing_repo": str(engine), "rmc_jar": "/unused"})
            with patch("semantic_fuzzing.retest_stateful.FuzzingPipeline") as pipeline, \
                    patch("semantic_fuzzing.__main__.prepare_credentials") as credentials, \
                    contextlib.redirect_stdout(io.StringIO()):
                code = main(["--translations-root", str(root / "archives"), "--config", str(root / "config.json"),
                             "--case", "FSM-01", "--plan-only", "--output", str(root / "out")])
                pipeline.assert_not_called()
                credentials.assert_not_called()
            self.assertEqual(code, 0)
            report = read_json(root / "out/summary.json")
            self.assertEqual(report["cases"][0]["unique_planned_inputs"], 50)
            self.assertEqual((root / "out/FSM-01/candidate.rebeca").read_text(), "frozen code")

    def test_generated_input_mismatch_cannot_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_json(root / "scenario.json", {"messages": []})
            report = {"status": "BOUNDED_MATCH", "campaign": {"cases": [{"seed": 1, "case_directory": str(root)}]}}
            with self.assertRaisesRegex(ValueError, "differs"):
                verify_generated_inputs(report, make_spec("FSM-01", [1], 16))
            with self.assertRaisesRegex(ValueError, "every planned seed"):
                verify_generated_inputs({"status": "BOUNDED_MATCH"}, make_spec("FSM-01", [1], 16))


if __name__ == "__main__":
    unittest.main()
