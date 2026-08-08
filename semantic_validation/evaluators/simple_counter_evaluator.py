from __future__ import annotations

import json
import sys

from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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
    get_queue,
    get_state_by_id,
    get_states,
    get_transitions,
    get_variable,
    normalize_name,
    transition_message,
    transition_owner,
)

BENCHMARK_ID = "simple_counter"

COUNTER_OPERATION_NAMES = {
    normalize_name("Increment"),
    normalize_name("GetValue"),
    normalize_name("Decrement"),
}


@dataclass(frozen=True)
class ExpectedCounterStep:
    message_server: str
    source_count: int
    destination_count: int
    response_receiver: str
    response_value: int


@dataclass
class MatchedExecution:
    transitions: list[dict[str, Any]]
    matched_steps: list[dict[str, Any]]
    final_state_id: Any
    terminal_state_id: Any | None = None


BENCHMARK_STEPS = [
    ExpectedCounterStep(
        message_server="Increment",
        source_count=0,
        destination_count=1,
        response_receiver="client1",
        response_value=1,
    ),
    ExpectedCounterStep(
        message_server="Increment",
        source_count=1,
        destination_count=2,
        response_receiver="client2",
        response_value=2,
    ),
    ExpectedCounterStep(
        message_server="Decrement",
        source_count=2,
        destination_count=1,
        response_receiver="client1",
        response_value=1,
    ),
    ExpectedCounterStep(
        message_server="Decrement",
        source_count=1,
        destination_count=0,
        response_receiver="client2",
        response_value=0,
    ),
    ExpectedCounterStep(
        message_server="GetValue",
        source_count=0,
        destination_count=0,
        response_receiver="client1",
        response_value=0,
    ),
    ExpectedCounterStep(
        message_server="GetValue",
        source_count=0,
        destination_count=0,
        response_receiver="client2",
        response_value=0,
    ),
]


def _state_id(
    state: dict[str, Any] | None,
) -> Any:
    if not state:
        return None

    if state.get("id") is not None:
        return state.get("id")

    return state.get("state_id")


def _transition_source(
    transition: dict[str, Any],
) -> Any:
    return transition.get("source")


def _transition_destination(
    transition: dict[str, Any],
) -> Any:
    return transition.get("destination")


def _counter_value(
    state: dict[str, Any] | None,
) -> Any:
    """
    Read Counter's logical integer state without requiring one exact
    generated state-variable spelling.

    `count` is the source-visible name and remains the preferred match.
    The aliases keep the evaluator tolerant of harmless target-side
    representation choices.
    """
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
    """
    Return the logical message-server name without serialized arguments.

    RMC queue entries may be represented as:
        ValueResponse(1)
        PingMessage()

    while semantic checks compare logical names such as:
        ValueResponse
        PingMessage

    Keep argument parsing separate in _message_value().
    """
    value = (
        message.get("message")
        or message.get("name")
        or message.get("message_name")
        or message.get("message_server")
        or ""
    )

    raw = str(value).strip()

    if "(" in raw:
        raw = raw.split("(", 1)[0]

    return normalize_name(raw)


def _message_parameters(
    message: dict[str, Any],
) -> dict[str, Any]:
    parameters = message.get("parameters") or message.get("params") or {}

    return parameters if isinstance(parameters, dict) else {}


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


def _response_count(
    state: dict[str, Any] | None,
    receiver: str,
    value: int,
) -> int:
    """
    Count ValueResponse(value) messages queued for one receiver.

    We intentionally do not require the generated transition's sender field
    to equal the Akka explicit sender. Core Rebeca has no direct equivalent
    of ActorRef.tell(message, explicitSender); a correct translation may
    preserve the logical reply target using a message parameter or another
    behavior-preserving encoding.
    """
    return sum(
        1
        for message in get_queue(
            state,
            receiver,
        )
        if (
            _message_name(message) == normalize_name("ValueResponse")
            and _message_value(message) == value
        )
    )


def _response_was_enqueued(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
    receiver: str,
    value: int,
) -> bool:
    """
    Require a new matching response, rather than merely finding an older
    response that was already waiting in the receiver queue.
    """
    return _response_count(
        destination_state,
        receiver,
        value,
    ) > _response_count(
        source_state,
        receiver,
        value,
    )


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


def _outgoing_transitions(
    parsed_result: dict[str, Any],
) -> dict[Any, list[dict[str, Any]]]:
    outgoing: dict[
        Any,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for transition in get_transitions(parsed_result):
        outgoing[_transition_source(transition)].append(transition)

    return outgoing


def _initial_state_ids(
    parsed_result: dict[str, Any],
) -> list[Any]:
    states = get_states(parsed_result)

    state_ids = [_state_id(state) for state in states if _state_id(state) is not None]

    if not state_ids:
        return []

    destination_ids = {
        _transition_destination(transition)
        for transition in get_transitions(parsed_result)
    }

    roots = [state_id for state_id in state_ids if state_id not in destination_ids]

    if roots:
        return roots

    # RMC commonly numbers the initial state as zero.
    if 0 in state_ids:
        return [0]

    return [state_ids[0]]


def _is_counter_operation(
    transition: dict[str, Any],
) -> bool:
    return (
        transition_owner(transition) == normalize_name("counter")
        and transition_message(transition) in COUNTER_OPERATION_NAMES
    )


def _step_matches(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
    expected: ExpectedCounterStep,
) -> tuple[bool, dict[str, Any]]:
    if transition_owner(transition) != normalize_name("counter") or transition_message(
        transition
    ) != normalize_name(expected.message_server):
        return False, {}

    source_state = get_state_by_id(
        parsed_result,
        _transition_source(transition),
    )

    destination_state = get_state_by_id(
        parsed_result,
        _transition_destination(transition),
    )

    source_count = _counter_value(source_state)

    destination_count = _counter_value(destination_state)

    response_enqueued = _response_was_enqueued(
        source_state,
        destination_state,
        expected.response_receiver,
        expected.response_value,
    )

    evidence = {
        "message_server": (transition.get("message_server")),
        "source_state_id": (_transition_source(transition)),
        "destination_state_id": (_transition_destination(transition)),
        "source_count": source_count,
        "destination_count": (destination_count),
        "expected_response_receiver": (expected.response_receiver),
        "expected_response_value": (expected.response_value),
        "response_enqueued": (response_enqueued),
    }

    return (
        source_count == expected.source_count
        and destination_count == expected.destination_count
        and response_enqueued,
        evidence,
    )


def _find_benchmark_execution(
    parsed_result: dict[str, Any],
) -> MatchedExecution | None:
    """
    Find one *connected path* in the RMC state graph that realizes the
    CounterApp benchmark scenario.

    This replaces the old approach of collecting state-change edges from
    unrelated branches and pretending they formed one execution path.

    Non-Counter transitions, such as clients consuming ValueResponse, may
    occur between Counter operations. An out-of-order Counter operation,
    however, invalidates that branch for the benchmark scenario.
    """
    outgoing = _outgoing_transitions(parsed_result)

    queue: deque[
        tuple[
            Any,
            int,
            list[dict[str, Any]],
            list[dict[str, Any]],
        ]
    ] = deque()

    for initial_state_id in _initial_state_ids(parsed_result):
        queue.append(
            (
                initial_state_id,
                0,
                [],
                [],
            )
        )

    visited: set[tuple[Any, int]] = set()

    while queue:
        (
            state_id,
            step_index,
            path,
            matched_steps,
        ) = queue.popleft()

        visit_key = (
            state_id,
            step_index,
        )

        if visit_key in visited:
            continue

        visited.add(visit_key)

        if step_index == len(BENCHMARK_STEPS):
            return MatchedExecution(
                transitions=path,
                matched_steps=matched_steps,
                final_state_id=state_id,
            )

        expected = BENCHMARK_STEPS[step_index]

        for transition in outgoing.get(
            state_id,
            [],
        ):
            destination = _transition_destination(transition)

            if _is_counter_operation(transition):
                matches, evidence = _step_matches(
                    parsed_result,
                    transition,
                    expected,
                )

                if not matches:
                    # A Counter request was consumed, but not the request
                    # required at this position in the source scenario.
                    # This branch cannot later become the same execution.
                    continue

                queue.append(
                    (
                        destination,
                        step_index + 1,
                        path + [transition],
                        matched_steps + [evidence],
                    )
                )

            else:
                queue.append(
                    (
                        destination,
                        step_index,
                        path + [transition],
                        matched_steps,
                    )
                )

    return None


def _find_terminal_completion(
    parsed_result: dict[str, Any],
    start_state_id: Any,
) -> tuple[Any | None, list[dict[str, Any]]]:
    """
    Starting after all six CounterApp requests have been processed, find a
    reachable *quiescent* terminal state.

    Client-side ValueResponse consumption is allowed. No additional Counter
    Increment/Decrement/GetValue operation may execute after the benchmark
    sequence. A dead-end with pending messages is not accepted as successful
    terminal quiescence.
    """
    outgoing = _outgoing_transitions(parsed_result)

    queue: deque[
        tuple[
            Any,
            list[dict[str, Any]],
        ]
    ] = deque(
        [
            (
                start_state_id,
                [],
            )
        ]
    )

    visited: set[Any] = set()

    while queue:
        state_id, path = queue.popleft()

        if state_id in visited:
            continue

        visited.add(state_id)

        transitions = outgoing.get(
            state_id,
            [],
        )

        if not transitions:
            state = get_state_by_id(
                parsed_result,
                state_id,
            )

            if state and all(
                len(
                    get_queue(
                        state,
                        rebec,
                    )
                )
                == 0
                for rebec in (
                    "counter",
                    "client1",
                    "client2",
                )
            ):
                return state_id, path

            # Deadlock / terminal-looking state with pending messages:
            # do not treat it as successful quiescence.
            continue

        for transition in transitions:
            if _is_counter_operation(transition):
                continue

            queue.append(
                (
                    _transition_destination(transition),
                    path + [transition],
                )
            )

    return None, []


def _queues_empty_for_required_rebecs(
    parsed_result: dict[str, Any],
    state_id: Any,
) -> bool:
    state = get_state_by_id(
        parsed_result,
        state_id,
    )

    if not state:
        return False

    return all(
        len(
            get_queue(
                state,
                rebec,
            )
        )
        == 0
        for rebec in (
            "counter",
            "client1",
            "client2",
        )
    )


def _matched_step(
    execution: MatchedExecution | None,
    index: int,
) -> dict[str, Any] | None:
    if execution is None or index < 0 or index >= len(execution.matched_steps):
        return None

    return execution.matched_steps[index]


class SimpleCounterEvaluator(BaseSemanticEvaluator):

    benchmark_id = BENCHMARK_ID

    def __init__(
        self,
        parsed_result: dict[str, Any],
        example_id: str = BENCHMARK_ID,
    ) -> None:
        super().__init__(
            parsed_result=parsed_result,
            example_id=example_id,
        )

    def evaluate(
        self,
        parsed_result: dict[str, Any],
    ) -> SemanticEvaluationResult:
        states = get_states(parsed_result)

        transitions = get_transitions(parsed_result)

        execution = _find_benchmark_execution(parsed_result)

        terminal_state_id: Any | None = None
        terminal_path: list[dict[str, Any]] = []

        if execution is not None:
            (
                terminal_state_id,
                terminal_path,
            ) = _find_terminal_completion(
                parsed_result,
                execution.final_state_id,
            )

            execution.terminal_state_id = terminal_state_id

        tests: list[SemanticTestResult] = []

        tests.extend(
            self._evaluate_actor_tests(
                parsed_result,
                execution,
            )
        )

        tests.extend(
            self._evaluate_interaction_tests(
                parsed_result,
                execution,
            )
        )

        tests.extend(
            self._evaluate_system_tests(
                parsed_result,
                execution,
                terminal_state_id,
                terminal_path,
            )
        )

        issues: list[str] = []

        if not transitions:
            issues.append("NO_TRANSITIONS")

        if execution is None:
            issues.append("BENCHMARK_PATH_NOT_FOUND")

        if execution is not None and terminal_state_id is None:
            issues.append("TERMINAL_QUIESCENCE_NOT_FOUND")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": (_initial_state_ids(parsed_result)),
                "benchmark_path_found": (execution is not None),
                "matched_step_count": (
                    len(execution.matched_steps) if execution is not None else 0
                ),
                "benchmark_path_transition_count": (
                    len(execution.transitions) if execution is not None else 0
                ),
                "terminal_state_id": (terminal_state_id),
                "expected_state_evolution": [
                    0,
                    1,
                    2,
                    1,
                    0,
                    0,
                    0,
                ],
                "expected_client_responses": {
                    "client1": [
                        1,
                        1,
                        0,
                    ],
                    "client2": [
                        2,
                        0,
                        0,
                    ],
                },
                "source_only_not_scored": [
                    "five repeated Increment operations",
                    "five repeated Decrement operations",
                ],
                "evaluation_assumptions": {
                    "failure_free": True,
                    "logging_out_of_scope": True,
                    "controlled_startup_order": [
                        "Increment(client1)",
                        "Increment(client2)",
                        "Decrement(client1)",
                        "Decrement(client2)",
                        "GetValue(client1)",
                        "GetValue(client2)",
                    ],
                    "no_test_only_messages_in_target": True,
                    "explicit_sender_checked_via_reply_destination": True,
                },
            },
        )

    def _evaluate_actor_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        initial_state_ids = _initial_state_ids(parsed_result)

        initial_values = [
            _counter_value(
                get_state_by_id(
                    parsed_result,
                    state_id,
                )
            )
            for state_id in initial_state_ids
        ]

        xa1_status = (
            TestStatus.PASS
            if (initial_values and all(value == 0 for value in initial_values))
            else (
                TestStatus.NOT_OBSERVED
                if (
                    not initial_values or all(value is None for value in initial_values)
                )
                else TestStatus.FAIL
            )
        )

        tests.append(
            _test(
                "COUNTER-XA1",
                xa1_status,
                "Counter must begin with logical value 0.",
                {
                    "initial_state_ids": initial_state_ids,
                    "observed_initial_values": initial_values,
                    "expected": 0,
                },
            )
        )

        descriptions = [
            (
                "COUNTER-XA2",
                0,
                "First Increment must change 0 -> 1 and enqueue ValueResponse(1) for client1.",
            ),
            (
                "COUNTER-XA3",
                1,
                "Second Increment must change 1 -> 2 and enqueue ValueResponse(2) for client2.",
            ),
            (
                "COUNTER-XA4",
                2,
                "First Decrement must change 2 -> 1 and enqueue ValueResponse(1) for client1.",
            ),
            (
                "COUNTER-XA5",
                3,
                "Second Decrement must change 1 -> 0 and enqueue ValueResponse(0) for client2.",
            ),
        ]

        for test_id, step_index, description in descriptions:
            matched = _matched_step(
                execution,
                step_index,
            )

            tests.append(
                _test(
                    test_id,
                    (
                        TestStatus.PASS
                        if matched is not None
                        else (
                            TestStatus.FAIL
                            if get_transitions(parsed_result)
                            else TestStatus.NOT_OBSERVED
                        )
                    ),
                    description,
                    {
                        "matched_step": matched,
                    },
                )
            )

        get_value_client1 = _matched_step(
            execution,
            4,
        )

        get_value_client2 = _matched_step(
            execution,
            5,
        )

        xa6_passed = (
            get_value_client1 is not None
            and get_value_client2 is not None
            and get_value_client1["source_count"] == 0
            and get_value_client1["destination_count"] == 0
            and get_value_client2["source_count"] == 0
            and get_value_client2["destination_count"] == 0
            and get_value_client1["response_enqueued"]
            and get_value_client2["response_enqueued"]
        )

        tests.append(
            _test(
                "COUNTER-XA6",
                (
                    TestStatus.PASS
                    if xa6_passed
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Both benchmark GetValue operations must preserve "
                    "0 -> 0 and enqueue ValueResponse(0) for their "
                    "intended clients."
                ),
                {
                    "client1_get_value": get_value_client1,
                    "client2_get_value": get_value_client2,
                },
            )
        )

        expected_receivers = [
            "client1",
            "client2",
            "client1",
            "client2",
            "client1",
            "client2",
        ]

        expected_values = [
            1,
            2,
            1,
            0,
            0,
            0,
        ]

        xa7_passed = (
            execution is not None
            and len(execution.matched_steps) == 6
            and [step["expected_response_receiver"] for step in execution.matched_steps]
            == expected_receivers
            and [step["expected_response_value"] for step in execution.matched_steps]
            == expected_values
            and all(step["response_enqueued"] for step in execution.matched_steps)
        )

        tests.append(
            _test(
                "COUNTER-XA7",
                (
                    TestStatus.PASS
                    if xa7_passed
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "All six benchmark responses must preserve the "
                    "expected values and logical reply destinations."
                ),
                {
                    "expected_receivers": expected_receivers,
                    "expected_values": expected_values,
                    "matched_steps": (
                        execution.matched_steps if execution is not None else []
                    ),
                },
            )
        )

        return tests

    def _evaluate_interaction_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        path_found = execution is not None and len(execution.matched_steps) == 6

        tests.append(
            _test(
                "COUNTER-XI1",
                (
                    TestStatus.PASS
                    if path_found
                    else (
                        TestStatus.FAIL
                        if get_transitions(parsed_result)
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "One connected RMC execution path must realize "
                    "Increment, Increment, Decrement, Decrement, "
                    "GetValue, GetValue with the expected responses."
                ),
                {
                    "matched_steps": (
                        execution.matched_steps if execution is not None else []
                    ),
                },
            )
        )

        expected_edges = [
            (0, 1),
            (1, 2),
            (2, 1),
            (1, 0),
            (0, 0),
            (0, 0),
        ]

        observed_edges = (
            [
                (
                    step["source_count"],
                    step["destination_count"],
                )
                for step in execution.matched_steps
            ]
            if execution is not None
            else []
        )

        xi2_passed = path_found and observed_edges == expected_edges

        tests.append(
            _test(
                "COUNTER-XI2",
                (
                    TestStatus.PASS
                    if xi2_passed
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "The connected benchmark path must preserve "
                    "state evolution 0 -> 1 -> 2 -> 1 -> 0 -> 0 -> 0."
                ),
                {
                    "expected_edges": expected_edges,
                    "observed_edges": observed_edges,
                },
            )
        )

        xi3_passed = path_found and all(
            step["source_count"] == 0
            and step["destination_count"] == 0
            and step["response_enqueued"]
            for step in (execution.matched_steps[4:])
        )

        tests.append(
            _test(
                "COUNTER-XI3",
                (
                    TestStatus.PASS
                    if xi3_passed
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Both benchmark GetValue operations must be "
                    "read-only at final logical value 0."
                ),
                {
                    "get_value_steps": (
                        execution.matched_steps[4:] if execution is not None else []
                    ),
                },
            )
        )

        return tests

    def _evaluate_system_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
        terminal_state_id: Any | None,
        terminal_path: list[dict[str, Any]],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        rebecs = _rebec_names(parsed_result)

        required = {
            normalize_name("counter"),
            normalize_name("client1"),
            normalize_name("client2"),
        }

        topology_passed = required.issubset(rebecs)

        tests.append(
            _test(
                "COUNTER-XSYS1",
                (TestStatus.PASS if topology_passed else TestStatus.FAIL),
                (
                    "The target model must contain Counter, "
                    "client1, and client2. Behavior-preserving "
                    "auxiliary rebecs are allowed."
                ),
                {
                    "required_rebecs": sorted(required),
                    "observed_rebecs": sorted(rebecs),
                    "missing_rebecs": sorted(required - rebecs),
                },
            )
        )

        tests.append(
            _test(
                "COUNTER-XSYS2",
                (
                    TestStatus.PASS
                    if execution is not None
                    else (
                        TestStatus.FAIL
                        if get_transitions(parsed_result)
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "The state graph must contain one connected "
                    "execution of all six CounterApp requests; "
                    "client-side response handling may interleave."
                ),
                {
                    "benchmark_path_found": (execution is not None),
                    "matched_step_count": (
                        len(execution.matched_steps) if execution is not None else 0
                    ),
                    "path_transition_count": (
                        len(execution.transitions) if execution is not None else 0
                    ),
                },
            )
        )

        expected_contract = [
            ("client1", 1),
            ("client2", 2),
            ("client1", 1),
            ("client2", 0),
            ("client1", 0),
            ("client2", 0),
        ]

        observed_contract = (
            [
                (
                    step["expected_response_receiver"],
                    step["expected_response_value"],
                )
                for step in execution.matched_steps
            ]
            if execution is not None
            else []
        )

        full_response_contract = (
            execution is not None
            and observed_contract == expected_contract
            and all(step["response_enqueued"] for step in execution.matched_steps)
        )

        tests.append(
            _test(
                "COUNTER-XSYS3",
                (
                    TestStatus.PASS
                    if full_response_contract
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "The complete benchmark execution must preserve "
                    "client1=[1,1,0] and client2=[2,0,0]."
                ),
                {
                    "expected_contract": expected_contract,
                    "observed_contract": observed_contract,
                },
            )
        )

        terminal_count = (
            _counter_value(
                get_state_by_id(
                    parsed_result,
                    terminal_state_id,
                )
            )
            if terminal_state_id is not None
            else None
        )

        terminal_queues_empty = (
            terminal_state_id is not None
            and _queues_empty_for_required_rebecs(
                parsed_result,
                terminal_state_id,
            )
        )

        xsys4_passed = (
            terminal_state_id is not None
            and terminal_count == 0
            and terminal_queues_empty
        )

        tests.append(
            _test(
                "COUNTER-XSYS4",
                (
                    TestStatus.PASS
                    if xsys4_passed
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "After all six benchmark requests and client "
                    "response handling, the system must reach "
                    "quiescence with Counter value 0."
                ),
                {
                    "terminal_state_id": (terminal_state_id),
                    "terminal_count": (terminal_count),
                    "required_queues_empty": (terminal_queues_empty),
                    "terminal_completion_transition_count": (len(terminal_path)),
                },
            )
        )

        return tests


def evaluate_simple_counter(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = SimpleCounterEvaluator(
        parsed_result=parsed_result,
        example_id=BENCHMARK_ID,
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

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError("Parsed RMC JSON must contain a JSON object.")

    return value


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=("Evaluate the Simple Counter benchmark " "from parsed RMC JSON.")
    )

    parser.add_argument(
        "parsed_result",
        help=("Path to the parsed RMC JSON file."),
    )

    parser.add_argument(
        "--output",
        "-o",
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
