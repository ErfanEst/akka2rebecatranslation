from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


VALID_TEST_STATUSES = {"PASS", "FAIL", "NOT_OBSERVED"}


@dataclass(frozen=True)
class ContractTest:
    test_id: str
    level: str
    property_name: str
    mandatory: bool = True


@dataclass(frozen=True)
class SemanticContract:
    example_id: str
    version: str
    tests: tuple[ContractTest, ...]
    path: Path

    @property
    def mandatory_test_ids(self) -> list[str]:
        return [test.test_id for test in self.tests if test.mandatory]

    @property
    def all_test_ids(self) -> list[str]:
        return [test.test_id for test in self.tests]


def _tests_for_level(level_payload: Any) -> list[dict[str, Any]]:
    """Support both historical spec shapes: level=[...] and level={tests:[...]} ."""
    if isinstance(level_payload, list):
        return [item for item in level_payload if isinstance(item, dict)]
    if isinstance(level_payload, dict):
        tests = level_payload.get("tests", [])
        if isinstance(tests, list):
            return [item for item in tests if isinstance(item, dict)]
    return []


def load_semantic_contract(path: str | Path) -> SemanticContract:
    spec_path = Path(path)
    if not spec_path.is_file():
        raise FileNotFoundError(f"Semantic specification not found: {spec_path}")

    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Semantic specification must contain a JSON object.")

    example_id = payload.get("example_id")
    if not isinstance(example_id, str) or not example_id.strip():
        raise ValueError("Semantic specification requires a non-empty example_id.")

    levels = payload.get("levels")
    if not isinstance(levels, dict):
        raise ValueError("Semantic specification requires a levels object.")

    tests: list[ContractTest] = []
    seen_ids: set[str] = set()

    for level, level_payload in levels.items():
        for raw_test in _tests_for_level(level_payload):
            test_id = raw_test.get("test_id")
            if not isinstance(test_id, str) or not test_id.strip():
                raise ValueError(f"Semantic test in level {level!r} has no test_id.")
            if test_id in seen_ids:
                raise ValueError(f"Duplicate semantic test_id in specification: {test_id}")
            seen_ids.add(test_id)

            tests.append(
                ContractTest(
                    test_id=test_id,
                    level=str(level),
                    property_name=str(raw_test.get("property") or ""),
                    mandatory=bool(raw_test.get("mandatory", True)),
                )
            )

    if not tests:
        raise ValueError("Semantic specification does not define any tests.")

    return SemanticContract(
        example_id=example_id.strip(),
        version=str(payload.get("version") or "unspecified"),
        tests=tuple(tests),
        path=spec_path,
    )


def _result_status(test: dict[str, Any]) -> str | None:
    raw_status = test.get("status")
    if raw_status is not None:
        return str(raw_status).upper()

    passed = test.get("passed")
    if passed is True:
        return "PASS"
    if passed is False:
        return "FAIL"
    return None


def validate_evaluator_contract(
    contract: SemanticContract,
    semantic_tests: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Check that evaluator output covers the declarative semantic contract.

    The JSON spec defines which tests are part of the contract and which are
    mandatory. Benchmark-specific evaluator code still implements how each
    property is observed from trace/state-space evidence.
    """
    evaluator_statuses: dict[str, str | None] = {}
    duplicate_ids: list[str] = []

    for test in semantic_tests:
        if not isinstance(test, dict):
            continue
        test_id = test.get("test_id")
        if not isinstance(test_id, str) or not test_id:
            continue
        if test_id in evaluator_statuses:
            duplicate_ids.append(test_id)
        evaluator_statuses[test_id] = _result_status(test)

    mandatory_ids = contract.mandatory_test_ids
    missing_mandatory = [
        test_id for test_id in mandatory_ids if test_id not in evaluator_statuses
    ]
    unknown_status_ids = [
        test_id
        for test_id, status in evaluator_statuses.items()
        if status is not None and status not in VALID_TEST_STATUSES
    ]
    mandatory_failed = [
        test_id for test_id in mandatory_ids if evaluator_statuses.get(test_id) == "FAIL"
    ]
    mandatory_not_observed = [
        test_id
        for test_id in mandatory_ids
        if evaluator_statuses.get(test_id) == "NOT_OBSERVED"
    ]
    mandatory_without_status = [
        test_id
        for test_id in mandatory_ids
        if test_id in evaluator_statuses and evaluator_statuses[test_id] is None
    ]
    extra_evaluator_ids = sorted(
        set(evaluator_statuses) - set(contract.all_test_ids)
    )

    coverage_ok = not (
        missing_mandatory
        or duplicate_ids
        or unknown_status_ids
        or mandatory_without_status
    )

    return {
        "enforced": True,
        "contract_example_id": contract.example_id,
        "contract_version": contract.version,
        "mandatory_test_ids": mandatory_ids,
        "evaluator_test_ids": sorted(evaluator_statuses),
        "missing_mandatory_test_ids": missing_mandatory,
        "duplicate_evaluator_test_ids": sorted(set(duplicate_ids)),
        "unknown_status_test_ids": unknown_status_ids,
        "mandatory_without_status_test_ids": mandatory_without_status,
        "extra_evaluator_test_ids": extra_evaluator_ids,
        "mandatory_failed_test_ids": mandatory_failed,
        "mandatory_not_observed_test_ids": mandatory_not_observed,
        "coverage_ok": coverage_ok,
        "semantic_pass": (
            coverage_ok
            and not mandatory_failed
            and not mandatory_not_observed
        ),
    }
