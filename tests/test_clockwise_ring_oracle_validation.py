import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from semantic_validation.core.evaluator_registry import get_benchmark_config
from semantic_validation.core.semantic_contract import (
    load_semantic_contract,
    validate_evaluator_contract,
)
from src.semantic.semantic_validator import SemanticValidator
from src.syntax.rmc_compiler import RmcCompiler
from src.syntax.syntax_validator import SyntaxValidator


BENCHMARK = "clockwise_ring_ping_pong"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = (
    PROJECT_ROOT
    / "tests"
    / "fixtures"
    / "clockwise_ring_oracle"
)
EXPECTATIONS_PATH = FIXTURE_ROOT / "expectations.json"


def load_expectations() -> dict:
    return json.loads(EXPECTATIONS_PATH.read_text(encoding="utf-8"))


def classify_contract_result(contract_check: dict) -> str:
    if contract_check["semantic_pass"]:
        return "SEMANTIC_PASS"

    failed_ids = contract_check["mandatory_failed_test_ids"]
    not_observed_ids = contract_check[
        "mandatory_not_observed_test_ids"
    ]

    if not_observed_ids and not failed_ids:
        return "SEMANTIC_NOT_OBSERVED"

    return "SEMANTIC_FAIL"


class ClockwiseRingOracleEvaluatorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = get_benchmark_config(BENCHMARK)
        cls.contract = load_semantic_contract(cls.config.spec_path)
        cls.expectations = load_expectations()["cases"]

    def test_all_fixtures_exist(self) -> None:
        self.assertTrue(EXPECTATIONS_PATH.is_file())

        for case_name in self.expectations:
            with self.subTest(case=case_name):
                case_root = FIXTURE_ROOT / case_name
                self.assertTrue(
                    (case_root / "candidate.rebeca").is_file()
                )
                self.assertTrue(
                    (case_root / "parsed_statespace.json").is_file()
                )

    def test_evaluator_matches_recorded_oracle_expectations(self) -> None:
        for case_name, expected in self.expectations.items():
            with self.subTest(case=case_name):
                parsed_path = (
                    FIXTURE_ROOT
                    / case_name
                    / "parsed_statespace.json"
                )

                with tempfile.TemporaryDirectory() as directory:
                    result_path = (
                        Path(directory) / "semantic_result.json"
                    )

                    completed = subprocess.run(
                        [
                            sys.executable,
                            str(self.config.evaluator_path),
                            str(parsed_path),
                            "-o",
                            str(result_path),
                        ],
                        cwd=PROJECT_ROOT,
                        capture_output=True,
                        text=True,
                        timeout=120,
                        check=False,
                    )

                    self.assertEqual(
                        completed.returncode,
                        0,
                        msg=(
                            f"Evaluator failed for {case_name}.\n"
                            f"stdout:\n{completed.stdout}\n"
                            f"stderr:\n{completed.stderr}"
                        ),
                    )
                    self.assertTrue(result_path.is_file())

                    payload = json.loads(
                        result_path.read_text(encoding="utf-8")
                    )
                    semantic_tests = payload.get(
                        "semantic_tests",
                        [],
                    )

                    contract_check = validate_evaluator_contract(
                        self.contract,
                        semantic_tests,
                    )

                    self.assertTrue(
                        contract_check["coverage_ok"],
                        msg=contract_check,
                    )

                    actual_status = classify_contract_result(
                        contract_check
                    )
                    actual_failed_ids = contract_check[
                        "mandatory_failed_test_ids"
                    ]
                    actual_not_observed_ids = contract_check[
                        "mandatory_not_observed_test_ids"
                    ]
                    actual_passed_tests = (
                        len(self.contract.mandatory_test_ids)
                        - len(actual_failed_ids)
                        - len(actual_not_observed_ids)
                    )

                    self.assertEqual(
                        actual_status,
                        expected["expected_status"],
                    )
                    self.assertEqual(
                        actual_passed_tests,
                        expected["passed_tests"],
                    )
                    self.assertEqual(
                        actual_failed_ids,
                        expected["failed_test_ids"],
                    )
                    self.assertEqual(
                        actual_not_observed_ids,
                        expected["not_observed_test_ids"],
                    )

    def test_negative_mutation_score_is_one_hundred_percent(self) -> None:
        mutants = [
            expected
            for expected in self.expectations.values()
            if expected["control_type"] == "negative_mutant"
        ]

        killed = [
            expected
            for expected in mutants
            if expected["expected_status"] != "SEMANTIC_PASS"
        ]

        self.assertEqual(len(mutants), 4)
        self.assertEqual(len(killed), len(mutants))

    def test_positive_controls_are_expected_to_pass(self) -> None:
        positive_controls = [
            expected
            for expected in self.expectations.values()
            if expected["control_type"]
            in {
                "reference",
                "positive_equivalent_variant",
            }
        ]

        self.assertEqual(len(positive_controls), 2)
        self.assertTrue(
            all(
                item["expected_status"] == "SEMANTIC_PASS"
                for item in positive_controls
            )
        )


@unittest.skipUnless(
    os.environ.get("RUN_RMC_INTEGRATION") == "1",
    "Set RUN_RMC_INTEGRATION=1 to run full RMC integration cases.",
)
class ClockwiseRingOracleFullPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.expectations = load_expectations()["cases"]

    def test_full_rmc_pipeline_matches_expectations(self) -> None:
        for case_name, expected in self.expectations.items():
            with self.subTest(case=case_name):
                with tempfile.TemporaryDirectory() as directory:
                    attempt_root = Path(directory) / case_name
                    attempt_root.mkdir()

                    candidate = attempt_root / "candidate.rebeca"
                    shutil.copy2(
                        FIXTURE_ROOT
                        / case_name
                        / "candidate.rebeca",
                        candidate,
                    )

                    syntax = SyntaxValidator(
                        RmcCompiler()
                    ).validate(
                        candidate_path=candidate,
                        attempt_root=attempt_root,
                    )

                    self.assertTrue(
                        syntax.passed,
                        msg=syntax.error_message,
                    )

                    semantic = SemanticValidator(
                        project_root=PROJECT_ROOT
                    ).validate(
                        syntax_result=syntax,
                        attempt_root=attempt_root,
                        benchmark=BENCHMARK,
                    )

                    self.assertEqual(
                        semantic.status,
                        expected["expected_status"],
                    )
                    self.assertEqual(
                        semantic.passed_tests,
                        expected["passed_tests"],
                    )
                    self.assertEqual(
                        semantic.failed_test_ids,
                        expected["failed_test_ids"],
                    )
                    self.assertEqual(
                        semantic.not_observed_test_ids,
                        expected["not_observed_test_ids"],
                    )


if __name__ == "__main__":
    unittest.main()
