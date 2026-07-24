from __future__ import annotations

import json
import sys

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


from semantic_validation.core.base_evaluator import (
    BaseSemanticEvaluator,
)

from semantic_validation.core.evaluator_models import (
    SemanticEvaluationResult,
    SemanticTestResult,
    TestStatus,
)

from semantic_validation.core.trace_utils import (
    find_transitions,
    get_queue,
    get_state_by_id,
    get_states,
    get_transitions,
    get_variable,
    normalize_name,
    transition_message,
    transition_owner,
    transition_sequence,
)

BENCHMARK_ID = "simple_counter"


def _state_id(
    state: dict[str, Any] | None,
) -> Any:
    if not state:
        return None

    return state.get("id") if state.get("id") is not None else state.get("state_id")


def _transition_source(
    transition: dict[str, Any],
) -> Any:
    return transition.get("source")


def _transition_destination(
    transition: dict[str, Any],
) -> Any:
    return transition.get("destination")


def _transition_sender(
    transition: dict[str, Any],
) -> str:
    return normalize_name(transition.get("sender"))


def _counter_value(
    state: dict[str, Any] | None,
) -> Any:
    for variable_name in (
        "Counter.count",
        "count",
        "Counter.value",
        "value",
    ):
        value = get_variable(
            state,
            "counter",
            variable_name,
        )

        if value is not None:
            return value

    return None


def _all_counter_values(
    parsed_result: dict[str, Any],
) -> list[Any]:
    values: list[Any] = []

    for state in get_states(parsed_result):
        value = _counter_value(state)

        if value is not None:
            values.append(value)

    return values


def _rebec_names(
    parsed_result: dict[str, Any],
) -> set[str]:
    names: set[str] = set()

    for state in get_states(parsed_result):
        rebecs = state.get("rebecs", {})

        if isinstance(rebecs, dict):
            names.update(normalize_name(name) for name in rebecs)

        elif isinstance(rebecs, list):
            for rebec in rebecs:
                if not isinstance(rebec, dict):
                    continue

                name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")

                if name:
                    names.add(normalize_name(name))

    return names


def _message_name(
    message: dict[str, Any],
) -> str:
    value = (
        message.get("message")
        or message.get("name")
        or message.get("message_name")
        or message.get("message_server")
        or ""
    )

    return normalize_name(str(value))


def _message_sender(
    message: dict[str, Any],
) -> str:
    return normalize_name(message.get("sender"))


def _message_parameters(
    message: dict[str, Any],
) -> dict[str, Any]:
    parameters = message.get("parameters") or message.get("params") or {}

    if isinstance(parameters, dict):
        return parameters

    return {}


def _message_value(
    message: dict[str, Any],
) -> Any:
    parameters = _message_parameters(message)

    for key in (
        "value",
        "count",
        "counterValue",
        "counter_value",
        "arg0",
        "parameter0",
    ):
        if key in parameters:
            return parameters[key]

    for key in (
        "value",
        "count",
    ):
        if key in message:
            return message[key]

    raw_message = str(message.get("message") or message.get("name") or "")

    if "(" in raw_message and ")" in raw_message:
        inner = raw_message[raw_message.find("(") + 1 : raw_message.rfind(")")].strip()

        try:
            return int(inner)
        except ValueError:
            return None

    return None


def _queue_contains_response(
    state: dict[str, Any] | None,
    receiver: str,
    *,
    value: Any | None = None,
    sender: str | None = "counter",
) -> bool:
    for message in get_queue(
        state,
        receiver,
    ):
        if _message_name(message) != normalize_name("ValueResponse"):
            continue

        if (
            sender is not None
            and _message_sender(message)
            and _message_sender(message) != normalize_name(sender)
        ):
            continue

        if value is not None and _message_value(message) != value:
            continue

        return True

    return False


def _transition_observations(
    parsed_result: dict[str, Any],
    message_server: str | None = None,
) -> list[dict[str, Any]]:
    transitions = (
        find_transitions(
            parsed_result,
            owner="counter",
            message_server=message_server,
        )
        if message_server is not None
        else find_transitions(
            parsed_result,
            owner="counter",
        )
    )

    observations: list[dict[str, Any]] = []

    for transition in transitions:
        source_state = get_state_by_id(
            parsed_result,
            _transition_source(transition),
        )

        destination_state = get_state_by_id(
            parsed_result,
            _transition_destination(transition),
        )

        observations.append(
            {
                "transition": transition,
                "source_state": source_state,
                "destination_state": destination_state,
                "source_count": _counter_value(source_state),
                "destination_count": _counter_value(destination_state),
                "sender": _transition_sender(transition),
            }
        )

    return observations


def _increment_observations(
    parsed_result: dict[str, Any],
) -> list[dict[str, Any]]:
    return _transition_observations(
        parsed_result,
        "Increment",
    )


def _decrement_observations(
    parsed_result: dict[str, Any],
) -> list[dict[str, Any]]:
    return _transition_observations(
        parsed_result,
        "Decrement",
    )


def _get_value_observations(
    parsed_result: dict[str, Any],
) -> list[dict[str, Any]]:
    return _transition_observations(
        parsed_result,
        "GetValue",
    )


def _status_for_matches(
    observations: list[Any],
    matches: list[Any],
) -> TestStatus:
    if matches:
        return TestStatus.PASS

    if observations:
        return TestStatus.FAIL

    return TestStatus.NOT_OBSERVED


def _test(
    test_id: str,
    status: TestStatus,
    description: str,
    evidence: dict[str, Any],
) -> SemanticTestResult:
    return SemanticTestResult(
        test_id=test_id,
        status=status,
        description=description,
        evidence=evidence,
    )


def _path_exists(
    observations: list[dict[str, Any]],
    expected_values: list[Any],
) -> bool:
    if len(expected_values) < 2:
        return False

    expected_edges = list(
        zip(
            expected_values,
            expected_values[1:],
        )
    )

    observed_edges = {
        (
            observation["source_count"],
            observation["destination_count"],
        )
        for observation in observations
    }

    return all(edge in observed_edges for edge in expected_edges)


class SimpleCounterEvaluator(BaseSemanticEvaluator):

    def __init__(
        self,
        parsed_result: dict[str, Any],
        example_id: str = "simple_counter",
    ) -> None:
        super().__init__(
            parsed_result=parsed_result,
            example_id=example_id,
        )

    benchmark_id = BENCHMARK_ID

    def evaluate(
        self,
        parsed_result: dict[str, Any],
    ) -> SemanticEvaluationResult:
        states = get_states(parsed_result)
        transitions = get_transitions(parsed_result)

        tests: list[SemanticTestResult] = []

        if not states:
            return SemanticEvaluationResult(
                benchmark=self.benchmark_id,
                semantic_tests=[],
                detected_issues=[
                    "NO_STATES",
                ],
                metadata={
                    "state_count": 0,
                    "transition_count": len(transitions),
                },
            )

        tests.extend(self._evaluate_actor_tests(parsed_result))

        tests.extend(self._evaluate_interaction_tests(parsed_result))

        tests.extend(self._evaluate_system_tests(parsed_result))

        issues: list[str] = []

        if not transitions:
            issues.append("NO_TRANSITIONS")

        if any(test.status == TestStatus.NOT_OBSERVED for test in tests):
            issues.append("INCOMPLETE_OBSERVABILITY")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "state_count": len(states),
                "transition_count": len(transitions),
                "counter_values": (_all_counter_values(parsed_result)),
            },
        )

    def _evaluate_actor_tests(
        self,
        parsed_result: dict[str, Any],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        states = get_states(parsed_result)

        initial_count = _counter_value(states[0])

        tests.append(
            _test(
                "COUNTER-A1",
                (
                    TestStatus.PASS
                    if initial_count == 0
                    else (
                        TestStatus.NOT_OBSERVED
                        if initial_count is None
                        else TestStatus.FAIL
                    )
                ),
                ("Counter must initially " "have value zero."),
                {
                    "expected": 0,
                    "observed": initial_count,
                    "initial_state_id": (_state_id(states[0])),
                },
            )
        )

        increment_observations = _increment_observations(parsed_result)

        valid_single_increment = [
            observation
            for observation in increment_observations
            if (
                observation["source_count"] == 0
                and observation["destination_count"] == 1
            )
        ]

        tests.append(
            _test(
                "COUNTER-A2",
                _status_for_matches(
                    increment_observations,
                    valid_single_increment,
                ),
                ("One Increment must change " "Counter from 0 to 1."),
                {
                    "expected_edge": [0, 1],
                    "increment_observations": (increment_observations),
                },
            )
        )

        consecutive_increment_passed = _path_exists(
            increment_observations,
            [0, 1, 2],
        )

        tests.append(
            _test(
                "COUNTER-A3",
                (
                    TestStatus.PASS
                    if consecutive_increment_passed
                    else (
                        TestStatus.FAIL
                        if increment_observations
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                ("Two Increment operations " "must evolve count as " "0, 1, 2."),
                {
                    "expected_values": [
                        0,
                        1,
                        2,
                    ],
                    "increment_observations": (increment_observations),
                },
            )
        )

        decrement_observations = _decrement_observations(parsed_result)

        valid_single_decrement = [
            observation
            for observation in decrement_observations
            if (
                observation["source_count"] == 0
                and observation["destination_count"] == -1
            )
        ]

        tests.append(
            _test(
                "COUNTER-A4",
                _status_for_matches(
                    decrement_observations,
                    valid_single_decrement,
                ),
                ("One Decrement must change " "Counter from 0 to -1."),
                {
                    "expected_edge": [0, -1],
                    "decrement_observations": (decrement_observations),
                },
            )
        )

        increment_then_decrement = _path_exists(
            increment_observations,
            [0, 1],
        ) and _path_exists(
            decrement_observations,
            [1, 0],
        )

        actor_a5_observed = bool(increment_observations or decrement_observations)

        tests.append(
            _test(
                "COUNTER-A5",
                (
                    TestStatus.PASS
                    if increment_then_decrement
                    else (
                        TestStatus.FAIL
                        if actor_a5_observed
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                ("Increment followed by " "Decrement must restore " "count to zero."),
                {
                    "expected_values": [
                        0,
                        1,
                        0,
                    ],
                    "increment_observations": (increment_observations),
                    "decrement_observations": (decrement_observations),
                },
            )
        )

        repeated_increment_passed = _path_exists(
            increment_observations,
            [0, 1, 2, 3, 4, 5],
        )

        tests.append(
            _test(
                "COUNTER-A6",
                (
                    TestStatus.PASS
                    if repeated_increment_passed
                    else (
                        TestStatus.FAIL
                        if any(
                            observation["source_count"]
                            in {
                                2,
                                3,
                                4,
                            }
                            for observation in increment_observations
                        )
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                ("Five Increment operations " "must evolve count from " "0 through 5."),
                {
                    "expected_values": [
                        0,
                        1,
                        2,
                        3,
                        4,
                        5,
                    ],
                    "increment_observations": (increment_observations),
                },
            )
        )

        repeated_decrement_passed = _path_exists(
            decrement_observations,
            [0, -1, -2, -3, -4, -5],
        )

        tests.append(
            _test(
                "COUNTER-A7",
                (
                    TestStatus.PASS
                    if repeated_decrement_passed
                    else (
                        TestStatus.FAIL
                        if any(
                            observation["source_count"]
                            in {
                                -2,
                                -3,
                                -4,
                            }
                            for observation in decrement_observations
                        )
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Five Decrement operations "
                    "must evolve count from "
                    "0 through -5."
                ),
                {
                    "expected_values": [
                        0,
                        -1,
                        -2,
                        -3,
                        -4,
                        -5,
                    ],
                    "decrement_observations": (decrement_observations),
                },
            )
        )

        routed_responses: list[dict[str, Any]] = []

        routing_failures: list[dict[str, Any]] = []

        routing_observations = [
            *increment_observations,
            *decrement_observations,
            *_get_value_observations(parsed_result),
        ]

        for observation in routing_observations:
            sender = observation["sender"]

            if not sender:
                continue

            destination_state = observation["destination_state"]

            response_value = observation["destination_count"]

            routed = _queue_contains_response(
                destination_state,
                sender,
                value=response_value,
            )

            evidence = {
                "sender": sender,
                "response_value": (response_value),
                "transition": (observation["transition"]),
            }

            if routed:
                routed_responses.append(evidence)
            else:
                routing_failures.append(evidence)

        if routed_responses:
            a8_status = TestStatus.PASS if not routing_failures else TestStatus.FAIL
        elif any(observation["sender"] for observation in routing_observations):
            a8_status = TestStatus.FAIL
        else:
            a8_status = TestStatus.NOT_OBSERVED

        tests.append(
            _test(
                "COUNTER-A8",
                a8_status,
                (
                    "Each ValueResponse must be "
                    "routed to the sender of "
                    "the corresponding request."
                ),
                {
                    "routed_responses": (routed_responses),
                    "routing_failures": (routing_failures),
                },
            )
        )

        return tests

    def _evaluate_interaction_tests(
        self,
        parsed_result: dict[str, Any],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        increments = _increment_observations(parsed_result)

        get_values = _get_value_observations(parsed_result)

        client1_increment = [
            observation
            for observation in increments
            if (
                observation["sender"] == normalize_name("client1")
                and observation["source_count"] == 0
                and observation["destination_count"] == 1
                and _queue_contains_response(
                    observation["destination_state"],
                    "client1",
                    value=1,
                )
            )
        ]

        relevant_client1 = [
            observation
            for observation in increments
            if observation["sender"] == normalize_name("client1")
        ]

        tests.append(
            _test(
                "COUNTER-I1",
                _status_for_matches(
                    relevant_client1,
                    client1_increment,
                ),
                (
                    "Increment from client1 "
                    "must produce "
                    "ValueResponse(1) for "
                    "client1."
                ),
                {
                    "matching_observations": (client1_increment),
                    "client1_observations": (relevant_client1),
                },
            )
        )

        shared_state_passed = _path_exists(
            increments,
            [0, 1, 2],
        )

        observed_senders = {
            observation["sender"] for observation in increments if observation["sender"]
        }

        shared_state_observed = {
            normalize_name("client1"),
            normalize_name("client2"),
        }.issubset(observed_senders)

        tests.append(
            _test(
                "COUNTER-I2",
                (
                    TestStatus.PASS
                    if (shared_state_passed and shared_state_observed)
                    else (
                        TestStatus.FAIL
                        if shared_state_observed
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Requests from both clients "
                    "must operate on the same "
                    "Counter state."
                ),
                {
                    "observed_senders": sorted(observed_senders),
                    "increment_observations": (increments),
                    "expected_values": [
                        0,
                        1,
                        2,
                    ],
                },
            )
        )

        valid_read_only = [
            observation
            for observation in get_values
            if (
                observation["source_count"] is not None
                and observation["source_count"] == observation["destination_count"]
            )
        ]

        tests.append(
            _test(
                "COUNTER-I3",
                _status_for_matches(
                    get_values,
                    valid_read_only,
                ),
                (
                    "GetValue must return the "
                    "current value without "
                    "modifying Counter state."
                ),
                {
                    "get_value_observations": (get_values),
                    "valid_read_only": (valid_read_only),
                },
            )
        )

        controlled_progress = _path_exists(
            increments,
            [0, 1, 2],
        ) and any(
            observation["source_count"] == 2 and observation["destination_count"] == 2
            for observation in get_values
        )

        controlled_observed = bool(increments and get_values)

        tests.append(
            _test(
                "COUNTER-I4",
                (
                    TestStatus.PASS
                    if controlled_progress
                    else (
                        TestStatus.FAIL
                        if controlled_observed
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                ("Controlled execution must " "expose values " "0, 1, 2, 2."),
                {
                    "expected_values": [
                        0,
                        1,
                        2,
                        2,
                    ],
                    "increment_observations": (increments),
                    "get_value_observations": (get_values),
                },
            )
        )

        routed = []
        routing_failures = []

        for observation in [
            *increments,
            *get_values,
        ]:
            sender = observation["sender"]

            if not sender:
                continue

            value = observation["destination_count"]

            response_found = _queue_contains_response(
                observation["destination_state"],
                sender,
                value=value,
            )

            item = {
                "sender": sender,
                "value": value,
                "transition": (observation["transition"]),
            }

            if response_found:
                routed.append(item)
            else:
                routing_failures.append(item)

        if routed:
            i5_status = TestStatus.PASS if not routing_failures else TestStatus.FAIL
        elif any(
            observation["sender"]
            for observation in [
                *increments,
                *get_values,
            ]
        ):
            i5_status = TestStatus.FAIL
        else:
            i5_status = TestStatus.NOT_OBSERVED

        tests.append(
            _test(
                "COUNTER-I5",
                i5_status,
                (
                    "Every response must be "
                    "routed to the client that "
                    "sent its request."
                ),
                {
                    "routed_responses": routed,
                    "routing_failures": (routing_failures),
                },
            )
        )

        return tests

    def _evaluate_system_tests(
        self,
        parsed_result: dict[str, Any],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        states = get_states(parsed_result)

        transitions = get_transitions(parsed_result)

        rebecs = _rebec_names(parsed_result)

        required = {
            normalize_name("counter"),
            normalize_name("client1"),
            normalize_name("client2"),
        }

        tests.append(
            _test(
                "COUNTER-SYS1",
                (TestStatus.PASS if required.issubset(rebecs) else TestStatus.FAIL),
                ("The model must contain " "one Counter and two " "Client rebecs."),
                {
                    "expected_rebecs": sorted(required),
                    "observed_rebecs": sorted(rebecs),
                    "missing_rebecs": sorted(required - rebecs),
                },
            )
        )

        topology_evidence = required.issubset(rebecs) and any(
            transition_owner(transition) == normalize_name("counter")
            and _transition_sender(transition)
            in {
                normalize_name("client1"),
                normalize_name("client2"),
            }
            for transition in transitions
        )

        tests.append(
            _test(
                "COUNTER-SYS2",
                (
                    TestStatus.PASS
                    if topology_evidence
                    else (
                        TestStatus.FAIL
                        if not required.issubset(rebecs)
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Counter and both clients "
                    "must participate in the "
                    "expected actor topology."
                ),
                {
                    "observed_rebecs": sorted(rebecs),
                    "counter_transitions": (
                        find_transitions(
                            parsed_result,
                            owner="counter",
                        )
                    ),
                },
            )
        )

        sequence = [
            normalize_name(message) for message in transition_sequence(parsed_result)
        ]

        expected_startup = [
            normalize_name("Increment"),
            normalize_name("Increment"),
            normalize_name("GetValue"),
            normalize_name("GetValue"),
        ]

        sequence_matches = False

        for index in range(
            0,
            len(sequence) - len(expected_startup) + 1,
        ):
            if sequence[index : index + len(expected_startup)] == expected_startup:
                sequence_matches = True
                break

        startup_messages_observed = any(item in sequence for item in expected_startup)

        tests.append(
            _test(
                "COUNTER-SYS3",
                (
                    TestStatus.PASS
                    if sequence_matches
                    else (
                        TestStatus.FAIL
                        if startup_messages_observed
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Startup must execute two "
                    "Increment operations "
                    "followed by two GetValue "
                    "operations."
                ),
                {
                    "expected_sequence": (expected_startup),
                    "observed_sequence": (sequence),
                },
            )
        )

        counter_values = _all_counter_values(parsed_result)

        progressed = len(states) > 1 and len(set(counter_values)) > 1

        tests.append(
            _test(
                "COUNTER-SYS4",
                (
                    TestStatus.PASS
                    if progressed
                    else (TestStatus.FAIL if transitions else TestStatus.NOT_OBSERVED)
                ),
                ("The system must progress " "from its initial Counter " "state."),
                {
                    "state_count": len(states),
                    "transition_count": len(transitions),
                    "counter_values": (counter_values),
                },
            )
        )

        final_count = _counter_value(states[-1])

        tests.append(
            _test(
                "COUNTER-SYS5",
                (
                    TestStatus.PASS
                    if final_count == 2
                    else (
                        TestStatus.NOT_OBSERVED
                        if final_count is None
                        else TestStatus.FAIL
                    )
                ),
                (
                    "The completed startup "
                    "scenario must terminate "
                    "with count equal to 2."
                ),
                {
                    "expected": 2,
                    "observed": final_count,
                    "final_state_id": (_state_id(states[-1])),
                },
            )
        )

        increments = _increment_observations(parsed_result)

        get_values = _get_value_observations(parsed_result)

        complete_scenario = (
            sequence_matches
            and _path_exists(
                increments,
                [0, 1, 2],
            )
            and sum(
                1
                for observation in get_values
                if (
                    observation["source_count"] == 2
                    and observation["destination_count"] == 2
                )
            )
            >= 2
            and final_count == 2
        )

        scenario_observed = bool(startup_messages_observed or increments or get_values)

        tests.append(
            _test(
                "COUNTER-SYS6",
                (
                    TestStatus.PASS
                    if complete_scenario
                    else (
                        TestStatus.FAIL
                        if scenario_observed
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "The complete benchmark "
                    "scenario must preserve "
                    "operation order, responses "
                    "and final state."
                ),
                {
                    "expected_sequence": (expected_startup),
                    "observed_sequence": (sequence),
                    "increment_observations": (increments),
                    "get_value_observations": (get_values),
                    "final_count": final_count,
                },
            )
        )

        return tests


def evaluate_simple_counter(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = SimpleCounterEvaluator(
        parsed_result=parsed_result,
        example_id="simple_counter",
    )
    return evaluator.evaluate(parsed_result).to_dict()


def load_json(
    path: str | Path,
) -> dict[str, Any]:
    file_path = Path(path)

    if not file_path.is_file():
        raise FileNotFoundError(f"JSON file not found: {file_path}")

    with file_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        value = json.load(file)

    if not isinstance(value, dict):
        raise ValueError("Parsed RMC JSON must contain " "a JSON object.")

    return value


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=("Evaluate the SimpleCounter " "benchmark from parsed RMC JSON.")
    )

    parser.add_argument(
        "parsed_result",
        help=("Path to the parsed RMC JSON file."),
    )

    parser.add_argument(
        "--output",
        help=("Optional output JSON path."),
    )

    arguments = parser.parse_args()

    try:
        parsed_result = load_json(arguments.parsed_result)

        result = evaluate_simple_counter(parsed_result)

        serialized = json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )

        if arguments.output:
            output_path = Path(arguments.output)

            output_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            output_path.write_text(
                serialized + "\n",
                encoding="utf-8",
            )
        else:
            print(serialized)

        return 0

    except Exception as exc:
        print(
            ("SimpleCounter evaluator " f"infrastructure error: {exc}"),
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
