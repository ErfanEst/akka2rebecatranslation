from __future__ import annotations

import json
import sys

from collections import Counter as MultisetCounter
from collections import defaultdict, deque
from dataclasses import dataclass
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
    get_queue,
    get_state_by_id,
    get_states,
    get_transitions,
    normalize_name,
    transition_message,
    transition_owner,
)

BENCHMARK_ID = "simple_producer_consumer"

PRODUCE_MESSAGE = normalize_name("Produce")
CONSUME_MESSAGE = normalize_name("Consume")


@dataclass(frozen=True)
class ExpectedProducerStep:
    logical_payload: str


@dataclass
class MatchedExecution:
    transitions: list[dict[str, Any]]
    matched_steps: list[dict[str, Any]]
    final_state_id: Any
    terminal_state_id: Any | None = None


BENCHMARK_STEPS = [
    ExpectedProducerStep(
        logical_payload="item1",
    ),
    ExpectedProducerStep(
        logical_payload="item2",
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


def _rebec_names(
    parsed_result: dict[str, Any],
) -> set[str]:
    names: set[str] = set()

    for state in get_states(parsed_result):
        rebecs = state.get(
            "rebecs",
            {},
        )

        if isinstance(
            rebecs,
            dict,
        ):
            names.update(normalize_name(name) for name in rebecs)

        elif isinstance(
            rebecs,
            list,
        ):
            for rebec in rebecs:
                if not isinstance(
                    rebec,
                    dict,
                ):
                    continue

                name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")

                if name:
                    names.add(normalize_name(str(name)))

    return names


def _message_raw(
    message: dict[str, Any],
) -> str:
    return str(
        message.get("message")
        or message.get("name")
        or message.get("message_name")
        or message.get("message_server")
        or ""
    ).strip()


def _message_name(
    message: dict[str, Any],
) -> str:
    """
    Return the logical message-server name without serialized arguments.

    Examples:
        Produce("item1") -> PRODUCE
        Produce(1)       -> PRODUCE
        Consume(1)       -> CONSUME
    """
    raw = _message_raw(message)

    if "(" in raw:
        raw = raw.split(
            "(",
            1,
        )[0]

    return normalize_name(raw)


def _message_parameters(
    message: dict[str, Any],
) -> dict[str, Any]:
    parameters = message.get("parameters") or message.get("params") or {}

    return (
        parameters
        if isinstance(
            parameters,
            dict,
        )
        else {}
    )


def _message_payload(
    message: dict[str, Any],
) -> Any:
    """
    Extract the single payload carried by Produce/Consume.

    The current RMC parser usually exposes queue messages as raw strings such
    as Produce(1) or Consume(1), but this also tolerates future structured
    parser output.
    """
    parameters = _message_parameters(message)

    for key in (
        "item",
        "value",
        "arg0",
        "parameter0",
    ):
        if key in parameters:
            return parameters[key]

    if len(parameters) == 1:
        return next(iter(parameters.values()))

    for key in (
        "item",
        "value",
    ):
        if key in message:
            return message[key]

    raw = _message_raw(message)

    if "(" in raw and ")" in raw:
        inner = raw[raw.find("(") + 1 : raw.rfind(")")].strip()

        if (
            len(inner) >= 2
            and inner[0] == inner[-1]
            and inner[0]
            in {
                '"',
                "'",
            }
        ):
            inner = inner[1:-1]

        return inner

    return None


def _canonical_payload(
    value: Any,
) -> str | None:
    if value is None:
        return None

    text = str(value).strip()

    if (
        len(text) >= 2
        and text[0] == text[-1]
        and text[0]
        in {
            '"',
            "'",
        }
    ):
        text = text[1:-1]

    return text.strip()


def _logical_payload(
    value: Any,
) -> str | None:
    """
    Map common behavior-preserving target encodings back to the two source
    payload identities.

    The preferred representation preserves the source strings directly.
    Integer 1/2 and symbolic ITEM1/ITEM2 are accepted because a Core Rebeca
    translation may encode source string identities symbolically when needed.
    """
    canonical = _canonical_payload(value)

    if canonical is None:
        return None

    compact = (
        canonical.replace(
            "_",
            "",
        )
        .replace(
            "-",
            "",
        )
        .replace(
            " ",
            "",
        )
        .lower()
    )

    if compact in {
        "item1",
        "1",
    }:
        return "item1"

    if compact in {
        "item2",
        "2",
    }:
        return "item2"

    return None


def _message_signature(
    message: dict[str, Any],
) -> tuple[str, str | None]:
    return (
        _message_name(message),
        _canonical_payload(_message_payload(message)),
    )


def _matching_signatures(
    state: dict[str, Any] | None,
    rebec: str,
    message_name: str,
) -> list[tuple[str, str | None]]:
    expected_name = normalize_name(message_name)

    return [
        _message_signature(message)
        for message in get_queue(
            state,
            rebec,
        )
        if _message_name(message) == expected_name
    ]


def _positive_multiset_delta(
    left: list[tuple[str, str | None]],
    right: list[tuple[str, str | None]],
) -> list[tuple[str, str | None]]:
    """
    Return elements present more often in `left` than in `right`.

    This is used to infer which Produce message was consumed and which
    Consume message was newly enqueued across one atomic transition.
    """
    delta = MultisetCounter(left) - MultisetCounter(right)

    result: list[tuple[str, str | None]] = []

    for signature, count in delta.items():
        result.extend([signature] * count)

    return result


def _removed_messages(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
    rebec: str,
    message_name: str,
) -> list[tuple[str, str | None]]:
    return _positive_multiset_delta(
        _matching_signatures(
            source_state,
            rebec,
            message_name,
        ),
        _matching_signatures(
            destination_state,
            rebec,
            message_name,
        ),
    )


def _added_messages(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
    rebec: str,
    message_name: str,
) -> list[tuple[str, str | None]]:
    return _positive_multiset_delta(
        _matching_signatures(
            destination_state,
            rebec,
            message_name,
        ),
        _matching_signatures(
            source_state,
            rebec,
            message_name,
        ),
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

    if 0 in state_ids:
        return [0]

    return [state_ids[0]]


def _is_producer_produce(
    transition: dict[str, Any],
) -> bool:
    return (
        transition_owner(transition) == normalize_name("producer")
        and transition_message(transition) == PRODUCE_MESSAGE
    )


def _is_consumer_consume(
    transition: dict[str, Any],
) -> bool:
    return (
        transition_owner(transition) == normalize_name("consumer")
        and transition_message(transition) == CONSUME_MESSAGE
    )


def _step_matches(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
    expected: ExpectedProducerStep,
) -> tuple[bool, dict[str, Any]]:
    """
    Match one Producer transition by observing queue deltas.

    For a correct Produce(x) transition:
      - exactly one Produce(x) disappears from Producer's queue;
      - exactly one Consume(x) appears in Consumer's queue;
      - x is unchanged;
      - x represents the expected source item at this benchmark position.
    """
    if not _is_producer_produce(transition):
        return False, {}

    source_state = get_state_by_id(
        parsed_result,
        _transition_source(transition),
    )

    destination_state = get_state_by_id(
        parsed_result,
        _transition_destination(transition),
    )

    removed_produce = _removed_messages(
        source_state,
        destination_state,
        "producer",
        "Produce",
    )

    added_consume = _added_messages(
        source_state,
        destination_state,
        "consumer",
        "Consume",
    )

    consumed_payload = removed_produce[0][1] if len(removed_produce) == 1 else None

    forwarded_payload = added_consume[0][1] if len(added_consume) == 1 else None

    consumed_logical = _logical_payload(consumed_payload)

    forwarded_logical = _logical_payload(forwarded_payload)

    exactly_one_input_consumed = len(removed_produce) == 1

    exactly_one_output_enqueued = len(added_consume) == 1

    payload_preserved = (
        exactly_one_input_consumed
        and exactly_one_output_enqueued
        and consumed_payload == forwarded_payload
    )

    expected_identity_preserved = (
        consumed_logical == expected.logical_payload
        and forwarded_logical == expected.logical_payload
    )

    evidence = {
        "message_server": (transition.get("message_server")),
        "source_state_id": (_transition_source(transition)),
        "destination_state_id": (_transition_destination(transition)),
        "removed_produce_messages": (removed_produce),
        "added_consume_messages": (added_consume),
        "consumed_payload": (consumed_payload),
        "forwarded_payload": (forwarded_payload),
        "consumed_logical_payload": (consumed_logical),
        "forwarded_logical_payload": (forwarded_logical),
        "expected_logical_payload": (expected.logical_payload),
        "exactly_one_input_consumed": (exactly_one_input_consumed),
        "exactly_one_output_enqueued": (exactly_one_output_enqueued),
        "payload_preserved": (payload_preserved),
    }

    return (
        payload_preserved and expected_identity_preserved,
        evidence,
    )


def _find_benchmark_execution(
    parsed_result: dict[str, Any],
) -> MatchedExecution | None:
    """
    Find one connected state-graph execution realizing:

        Produce(item1) -> Consume(item1)
        Produce(item2) -> Consume(item2)

    Startup/helper transitions and Consumer transitions may interleave.
    Any out-of-order Producer Produce transition invalidates that branch.
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

            if _is_producer_produce(transition):
                (
                    matches,
                    evidence,
                ) = _step_matches(
                    parsed_result,
                    transition,
                    expected,
                )

                if not matches:
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


def _all_rebec_queues_empty(
    state: dict[str, Any] | None,
) -> bool:
    if not state:
        return False

    rebecs = state.get(
        "rebecs",
        {},
    )

    if isinstance(
        rebecs,
        dict,
    ):
        return all(
            len(
                (
                    data.get(
                        "queue",
                        [],
                    )
                    if isinstance(
                        data,
                        dict,
                    )
                    else []
                )
            )
            == 0
            for data in rebecs.values()
        )

    if isinstance(
        rebecs,
        list,
    ):
        names = []

        for rebec in rebecs:
            if not isinstance(
                rebec,
                dict,
            ):
                continue

            name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")

            if name:
                names.append(str(name))

        return all(
            len(
                get_queue(
                    state,
                    name,
                )
            )
            == 0
            for name in names
        )

    return False


def _find_terminal_completion(
    parsed_result: dict[str, Any],
    start_state_id: Any,
) -> tuple[Any | None, list[dict[str, Any]]]:
    """
    Continue after the two benchmark Produce operations until a quiescent
    terminal state is found.

    No additional Produce operation is allowed. Consumer processing and
    behavior-preserving helper transitions may complete normally.
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
        (
            state_id,
            path,
        ) = queue.popleft()

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

            if _all_rebec_queues_empty(state):
                return (
                    state_id,
                    path,
                )

            continue

        for transition in transitions:
            if _is_producer_produce(transition):
                continue

            queue.append(
                (
                    _transition_destination(transition),
                    path + [transition],
                )
            )

    return (
        None,
        [],
    )


def _matched_step(
    execution: MatchedExecution | None,
    index: int,
) -> dict[str, Any] | None:
    if execution is None or index < 0 or index >= len(execution.matched_steps):
        return None

    return execution.matched_steps[index]


def _consumer_consume_count(
    execution: MatchedExecution | None,
    terminal_path: list[dict[str, Any]],
) -> int:
    transitions = (
        execution.transitions if execution is not None else []
    ) + terminal_path

    return sum(1 for transition in transitions if _is_consumer_consume(transition))


class SimpleProducerConsumerEvaluator(BaseSemanticEvaluator):

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
                "expected_logical_payload_order": [
                    "item1",
                    "item2",
                ],
                "source_only_not_scored": [
                    ("arbitrary payload forwarding " "(PC-SRC-P1)"),
                    ("duplicate payload forwarding " "(PC-SRC-P2)"),
                    ("five-item FIFO stress scenario " "(PC-SRC-P3)"),
                ],
                "evaluation_assumptions": {
                    "failure_free": True,
                    "logging_out_of_scope": True,
                    "payload_identity_is_observable": True,
                    "accepted_item1_encodings": [
                        "item1",
                        "ITEM1",
                        "1",
                    ],
                    "accepted_item2_encodings": [
                        "item2",
                        "ITEM2",
                        "2",
                    ],
                    "no_test_only_messages_in_target": True,
                },
            },
        )

    def _evaluate_actor_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        for (
            test_id,
            step_index,
            description,
        ) in (
            (
                "PC-XA1",
                0,
                (
                    "Produce(item1) must consume exactly one "
                    "input and enqueue exactly Consume(item1)."
                ),
            ),
            (
                "PC-XA2",
                1,
                (
                    "Produce(item2) must consume exactly one "
                    "input and enqueue exactly Consume(item2)."
                ),
            ),
        ):
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
                        "matched_step": (matched),
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

        path_found = execution is not None and len(execution.matched_steps) == 2

        tests.append(
            _test(
                "PC-XI1",
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
                    "One connected execution path must forward "
                    "both benchmark items without loss."
                ),
                {
                    "matched_steps": (
                        execution.matched_steps if execution is not None else []
                    ),
                },
            )
        )

        payload_preserved = path_found and all(
            step.get("payload_preserved") is True for step in (execution.matched_steps)
        )

        tests.append(
            _test(
                "PC-XI2",
                (
                    TestStatus.PASS
                    if payload_preserved
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Each Produce payload must be forwarded "
                    "unchanged in the corresponding Consume."
                ),
                {
                    "payload_pairs": (
                        [
                            {
                                "produce": (step.get("consumed_payload")),
                                "consume": (step.get("forwarded_payload")),
                            }
                            for step in (execution.matched_steps)
                        ]
                        if execution is not None
                        else []
                    ),
                },
            )
        )

        observed_order = (
            [step.get("consumed_logical_payload") for step in (execution.matched_steps)]
            if execution is not None
            else []
        )

        expected_order = [
            "item1",
            "item2",
        ]

        tests.append(
            _test(
                "PC-XI3",
                (
                    TestStatus.PASS
                    if (path_found and observed_order == expected_order)
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                ("Forwarding must preserve benchmark order: " "item1 before item2."),
                {
                    "expected_order": (expected_order),
                    "observed_order": (observed_order),
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
            normalize_name("producer"),
            normalize_name("consumer"),
        }

        topology_passed = required.issubset(rebecs)

        tests.append(
            _test(
                "PC-XSYS1",
                (TestStatus.PASS if topology_passed else TestStatus.FAIL),
                (
                    "The target system must contain Producer "
                    "and Consumer; auxiliary rebecs are allowed."
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
                "PC-XSYS2",
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
                    "The state graph must execute both startup "
                    "Produce requests on one connected path."
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

        observed_output = (
            [
                step.get("forwarded_logical_payload")
                for step in (execution.matched_steps)
            ]
            if execution is not None
            else []
        )

        expected_output = [
            "item1",
            "item2",
        ]

        full_output_contract = (
            execution is not None
            and observed_output == expected_output
            and all(
                step.get("exactly_one_output_enqueued") is True
                for step in (execution.matched_steps)
            )
        )

        tests.append(
            _test(
                "PC-XSYS3",
                (
                    TestStatus.PASS
                    if full_output_contract
                    else (
                        TestStatus.FAIL
                        if execution is not None
                        else TestStatus.NOT_OBSERVED
                    )
                ),
                (
                    "Startup must produce exactly the logical "
                    "Consume sequence [item1, item2]."
                ),
                {
                    "expected_output": (expected_output),
                    "observed_output": (observed_output),
                },
            )
        )

        terminal_state = (
            get_state_by_id(
                parsed_result,
                terminal_state_id,
            )
            if terminal_state_id is not None
            else None
        )

        terminal_queues_empty = (
            terminal_state_id is not None and _all_rebec_queues_empty(terminal_state)
        )

        consume_count = _consumer_consume_count(
            execution,
            terminal_path,
        )

        xsys4_passed = (
            terminal_state_id is not None
            and terminal_queues_empty
            and consume_count == 2
        )

        tests.append(
            _test(
                "PC-XSYS4",
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
                    "After exactly two Consumer deliveries, "
                    "the system must reach terminal quiescence "
                    "with all rebec queues empty."
                ),
                {
                    "terminal_state_id": (terminal_state_id),
                    "all_rebec_queues_empty": (terminal_queues_empty),
                    "consumer_consume_transition_count": (consume_count),
                    "expected_consume_transition_count": 2,
                    "terminal_completion_transition_count": (len(terminal_path)),
                },
            )
        )

        return tests


def evaluate_simple_producer_consumer(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = SimpleProducerConsumerEvaluator(
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
        description=(
            "Evaluate the Simple Producer-Consumer " "benchmark from parsed RMC JSON."
        )
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

        result = evaluate_simple_producer_consumer(parsed_result)

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
            ("SimpleProducerConsumer evaluator " f"infrastructure error: {exc}"),
            file=sys.stderr,
        )

        return 2


if __name__ == "__main__":
    raise SystemExit(main())
