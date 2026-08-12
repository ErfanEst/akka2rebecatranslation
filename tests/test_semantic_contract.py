import json
import tempfile
import unittest
from pathlib import Path

from semantic_validation.core.semantic_contract import (
    load_semantic_contract,
    validate_evaluator_contract,
)


class SemanticContractTests(unittest.TestCase):
    def _write_spec(self, directory: str, payload: dict) -> Path:
        path = Path(directory) / "semantic_spec.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return path

    def test_loads_nested_tests_shape_and_mandatory_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_spec(
                directory,
                {
                    "example_id": "demo",
                    "version": "v1",
                    "levels": {
                        "actor": {
                            "tests": [
                                {
                                    "test_id": "A1",
                                    "property": "first",
                                    "mandatory": True,
                                },
                                {
                                    "test_id": "A2",
                                    "property": "second",
                                    "mandatory": False,
                                },
                            ]
                        }
                    },
                },
            )
            contract = load_semantic_contract(path)
            self.assertEqual(contract.example_id, "demo")
            self.assertEqual(contract.mandatory_test_ids, ["A1"])
            self.assertEqual(contract.all_test_ids, ["A1", "A2"])

    def test_loads_historical_level_list_shape(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_spec(
                directory,
                {
                    "example_id": "legacy",
                    "levels": {
                        "actor": [
                            {"test_id": "A1", "property": "first"},
                        ],
                        "system": [
                            {"test_id": "S1", "property": "system"},
                        ],
                    },
                },
            )
            contract = load_semantic_contract(path)
            self.assertEqual(contract.mandatory_test_ids, ["A1", "S1"])

    def test_detects_missing_mandatory_evaluator_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_spec(
                directory,
                {
                    "example_id": "demo",
                    "levels": {
                        "actor": {
                            "tests": [
                                {"test_id": "A1", "property": "first", "mandatory": True},
                                {"test_id": "A2", "property": "second", "mandatory": True},
                            ]
                        }
                    },
                },
            )
            contract = load_semantic_contract(path)
            validation = validate_evaluator_contract(
                contract,
                [{"test_id": "A1", "status": "PASS"}],
            )
            self.assertFalse(validation["coverage_ok"])
            self.assertEqual(validation["missing_mandatory_test_ids"], ["A2"])
            self.assertFalse(validation["semantic_pass"])

    def test_mandatory_not_observed_is_not_semantic_pass(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write_spec(
                directory,
                {
                    "example_id": "demo",
                    "levels": {
                        "actor": {
                            "tests": [
                                {"test_id": "A1", "property": "first", "mandatory": True},
                            ]
                        }
                    },
                },
            )
            contract = load_semantic_contract(path)
            validation = validate_evaluator_contract(
                contract,
                [{"test_id": "A1", "status": "NOT_OBSERVED"}],
            )
            self.assertTrue(validation["coverage_ok"])
            self.assertEqual(validation["mandatory_not_observed_test_ids"], ["A1"])
            self.assertFalse(validation["semantic_pass"])


if __name__ == "__main__":
    unittest.main()
