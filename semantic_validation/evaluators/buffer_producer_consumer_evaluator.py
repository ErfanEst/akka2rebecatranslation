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
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic_validation.core.base_evaluator import BaseSemanticEvaluator
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


BENCHMARK_ID = "buffer_producer_consumer"

PRODUCER_NAME = "producer"
BUFFER_NAME = "buffer"
CONSUMER_NAME = "consumer"

MSG_BUFFERED_PRODUCE = normalize_name("BufferedProduce")
MSG_BUFFERED_CONSUME_NEXT = normalize_name("BufferedConsumeNext")
MSG_ADD_ITEM = normalize_name("AddItem")
MSG_GET_ITEM = normalize_name("GetItem")
MSG_BUFFERED_CONSUME = normalize_name("BufferedConsume")


@dataclass(frozen=True)
class ExpectedBufferStep:
    message_server: str
    role: str
    output_role: str | None = None
    expect_consumer_output: bool | None = None


@dataclass
class MatchedExecution:
    transitions: list[dict[str, Any]]
    matched_steps: list[dict[str, Any]]
    final_state_id: Any
    item_tokens: dict[str, str]
    terminal_state_id: Any | None = None
    terminal_completion: list[dict[str, Any]] | None = None


EXPECTED_BUFFER_STEPS = [
    ExpectedBufferStep("AddItem", "item1", expect_consumer_output=False),
    ExpectedBufferStep("AddItem", "item2", expect_consumer_output=False),
    ExpectedBufferStep("AddItem", "item3_initial", expect_consumer_output=False),
    ExpectedBufferStep("GetItem", "consume_item1", "item1", True),
    ExpectedBufferStep("GetItem", "consume_item2", "item2", True),
    ExpectedBufferStep("GetItem", "pre_retry_empty_get", expect_consumer_output=False),
    ExpectedBufferStep("AddItem", "item3_retry", expect_consumer_output=False),
    ExpectedBufferStep("GetItem", "consume_item3", "item3", True),
    ExpectedBufferStep("GetItem", "final_empty_get", expect_consumer_output=False),
]


def _state_id(state: dict[str, Any] | None) -> Any:
    if not state:
        return None
    return state.get("id") if state.get("id") is not None else state.get("state_id")


def _transition_source(transition: dict[str, Any]) -> Any:
    return transition.get("source")


def _transition_destination(transition: dict[str, Any]) -> Any:
    return transition.get("destination")


def _initial_state_ids(parsed_result: dict[str, Any]) -> list[Any]:
    state_ids = [
        _state_id(state)
        for state in get_states(parsed_result)
        if _state_id(state) is not None
    ]
    if not state_ids:
        return []

    destinations = {
        _transition_destination(transition)
        for transition in get_transitions(parsed_result)
    }
    roots = [state_id for state_id in state_ids if state_id not in destinations]
    if roots:
        return roots
    if 0 in state_ids:
        return [0]
    return [state_ids[0]]


def _outgoing_transitions(
    parsed_result: dict[str, Any],
) -> dict[Any, list[dict[str, Any]]]:
    outgoing: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for transition in get_transitions(parsed_result):
        outgoing[_transition_source(transition)].append(transition)
    return outgoing


def _rebec_names(parsed_result: dict[str, Any]) -> set[str]:
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
                    names.add(normalize_name(str(name)))
    return names


def _message_raw(message: dict[str, Any]) -> str:
    return str(
        message.get("message")
        or message.get("name")
        or message.get("message_name")
        or message.get("message_server")
        or ""
    ).strip()


def _message_name(message: dict[str, Any]) -> str:
    """Return logical message-server name without serialized arguments."""
    raw = _message_raw(message)
    if "(" in raw:
        raw = raw.split("(", 1)[0]
    return normalize_name(raw)


def _message_sender(message: dict[str, Any]) -> str:
    return normalize_name(str(message.get("sender") or ""))


def _message_parameters(message: dict[str, Any]) -> dict[str, Any]:
    parameters = message.get("parameters") or message.get("params") or {}
    return parameters if isinstance(parameters, dict) else {}


def _first_argument_from_raw(raw: str) -> str | None:
    if "(" not in raw or ")" not in raw:
        return None
    inner = raw[raw.find("(") + 1 : raw.rfind(")")].strip()
    if not inner:
        return None
    first = inner.split(",", 1)[0].strip()
    if len(first) >= 2 and first[0] == first[-1] and first[0] in {'"', "'"}:
        first = first[1:-1]
    return first.strip()


def _message_payload(message: dict[str, Any]) -> Any:
    """
    Extract the first logical payload parameter.

    The source uses String values, but the target may encode them using any
    three distinct symbolic Core Rebeca tokens. The evaluator infers those
    tokens from the connected execution instead of hard-coding 1/2/3.
    """
    parameters = _message_parameters(message)
    for key in ("item", "value", "arg0", "parameter0"):
        if key in parameters:
            return parameters[key]
    if len(parameters) == 1:
        return next(iter(parameters.values()))
    for key in ("item", "value"):
        if key in message:
            return message[key]
    return _first_argument_from_raw(_message_raw(message))


def _canonical_token(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        text = text[1:-1]
    return text.strip()


def _message_signature(
    message: dict[str, Any],
) -> tuple[str, str | None, str]:
    return (
        _message_name(message),
        _canonical_token(_message_payload(message)),
        _message_sender(message),
    )


def _queue_signatures(
    state: dict[str, Any] | None,
    rebec: str,
    *,
    message_name: str | None = None,
) -> list[tuple[str, str | None, str]]:
    expected = normalize_name(message_name) if message_name is not None else None
    result: list[tuple[str, str | None, str]] = []
    for message in get_queue(state, rebec):
        signature = _message_signature(message)
        if expected is not None and signature[0] != expected:
            continue
        result.append(signature)
    return result


def _positive_multiset_delta(
    left: list[tuple[str, str | None, str]],
    right: list[tuple[str, str | None, str]],
) -> list[tuple[str, str | None, str]]:
    delta = MultisetCounter(left) - MultisetCounter(right)
    result: list[tuple[str, str | None, str]] = []
    for signature, count in delta.items():
        result.extend([signature] * count)
    return result


def _removed_from_queue(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
    rebec: str,
    *,
    message_name: str | None = None,
) -> list[tuple[str, str | None, str]]:
    return _positive_multiset_delta(
        _queue_signatures(source_state, rebec, message_name=message_name),
        _queue_signatures(destination_state, rebec, message_name=message_name),
    )


def _added_to_queue(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
    rebec: str,
    *,
    message_name: str | None = None,
) -> list[tuple[str, str | None, str]]:
    return _positive_multiset_delta(
        _queue_signatures(destination_state, rebec, message_name=message_name),
        _queue_signatures(source_state, rebec, message_name=message_name),
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


def _status_from_observation(condition: bool, *, observed: bool) -> TestStatus:
    if condition:
        return TestStatus.PASS
    return TestStatus.FAIL if observed else TestStatus.NOT_OBSERVED


def _is_transition(
    transition: dict[str, Any],
    *,
    owner: str,
    message_server: str,
) -> bool:
    return (
        transition_owner(transition) == normalize_name(owner)
        and transition_message(transition) == normalize_name(message_server)
    )


def _is_buffer_operation(transition: dict[str, Any]) -> bool:
    return (
        transition_owner(transition) == normalize_name(BUFFER_NAME)
        and transition_message(transition) in {MSG_ADD_ITEM, MSG_GET_ITEM}
    )


def _producer_forwarding_evidence(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
) -> dict[str, Any]:
    source_state = get_state_by_id(parsed_result, _transition_source(transition))
    destination_state = get_state_by_id(
        parsed_result, _transition_destination(transition)
    )
    message_server = transition_message(transition)

    if message_server == MSG_BUFFERED_PRODUCE:
        removed = _removed_from_queue(
            source_state,
            destination_state,
            PRODUCER_NAME,
            message_name="BufferedProduce",
        )
        added = _added_to_queue(
            source_state,
            destination_state,
            BUFFER_NAME,
            message_name="AddItem",
        )
        input_token = removed[0][1] if len(removed) == 1 else None
        output_token = added[0][1] if len(added) == 1 else None
        passed = (
            len(removed) == 1
            and len(added) == 1
            and input_token is not None
            and input_token == output_token
        )
        return {
            "kind": "produce_forwarding",
            "source_state_id": _transition_source(transition),
            "destination_state_id": _transition_destination(transition),
            "removed_buffered_produce": removed,
            "added_add_item": added,
            "input_token": input_token,
            "output_token": output_token,
            "payload_preserved": passed,
            "passed": passed,
        }

    if message_server == MSG_BUFFERED_CONSUME_NEXT:
        removed = _removed_from_queue(
            source_state,
            destination_state,
            PRODUCER_NAME,
            message_name="BufferedConsumeNext",
        )
        added = _added_to_queue(
            source_state,
            destination_state,
            BUFFER_NAME,
            message_name="GetItem",
        )
        passed = len(removed) == 1 and len(added) == 1
        return {
            "kind": "consume_next_forwarding",
            "source_state_id": _transition_source(transition),
            "destination_state_id": _transition_destination(transition),
            "removed_buffered_consume_next": removed,
            "added_get_item": added,
            "passed": passed,
        }

    return {"kind": "unrelated", "passed": False}


def _buffer_step_evidence(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
) -> dict[str, Any]:
    source_state = get_state_by_id(parsed_result, _transition_source(transition))
    destination_state = get_state_by_id(
        parsed_result, _transition_destination(transition)
    )
    message_server = transition_message(transition)
    evidence: dict[str, Any] = {
        "message_server": message_server,
        "source_state_id": _transition_source(transition),
        "destination_state_id": _transition_destination(transition),
    }

    if message_server == MSG_ADD_ITEM:
        removed = _removed_from_queue(
            source_state,
            destination_state,
            BUFFER_NAME,
            message_name="AddItem",
        )
        consumer_added = _added_to_queue(
            source_state,
            destination_state,
            CONSUMER_NAME,
        )
        evidence.update(
            {
                "removed_add_item": removed,
                "input_token": removed[0][1] if len(removed) == 1 else None,
                "consumer_messages_added": consumer_added,
                "exactly_one_add_item_consumed": len(removed) == 1,
                "no_consumer_output": len(consumer_added) == 0,
            }
        )
        return evidence

    if message_server == MSG_GET_ITEM:
        removed = _removed_from_queue(
            source_state,
            destination_state,
            BUFFER_NAME,
            message_name="GetItem",
        )
        added_consume = _added_to_queue(
            source_state,
            destination_state,
            CONSUMER_NAME,
            message_name="BufferedConsume",
        )
        consumer_added_any = _added_to_queue(
            source_state,
            destination_state,
            CONSUMER_NAME,
        )
        evidence.update(
            {
                "removed_get_item": removed,
                "added_buffered_consume": added_consume,
                "consumer_messages_added": consumer_added_any,
                "exactly_one_get_item_consumed": len(removed) == 1,
                "output_token": added_consume[0][1] if len(added_consume) == 1 else None,
                "buffered_consume_count_added": len(added_consume),
                "consumer_message_count_added": len(consumer_added_any),
            }
        )
        return evidence

    return evidence


def _match_expected_buffer_step(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
    expected: ExpectedBufferStep,
    tokens: dict[str, str],
) -> tuple[bool, dict[str, Any], dict[str, str]]:
    if not _is_transition(
        transition,
        owner=BUFFER_NAME,
        message_server=expected.message_server,
    ):
        return False, {}, tokens

    evidence = _buffer_step_evidence(parsed_result, transition)
    new_tokens = dict(tokens)

    if expected.message_server == "AddItem":
        if not evidence.get("exactly_one_add_item_consumed"):
            return False, evidence, tokens
        if not evidence.get("no_consumer_output"):
            return False, evidence, tokens

        token = evidence.get("input_token")
        if token is None:
            return False, evidence, tokens

        if expected.role == "item1":
            if "item1" in new_tokens and token != new_tokens["item1"]:
                return False, evidence, tokens
            new_tokens.setdefault("item1", token)

        elif expected.role == "item2":
            if token == new_tokens.get("item1"):
                return False, evidence, tokens
            if "item2" in new_tokens and token != new_tokens["item2"]:
                return False, evidence, tokens
            new_tokens.setdefault("item2", token)

        elif expected.role == "item3_initial":
            if token in {new_tokens.get("item1"), new_tokens.get("item2")}:
                return False, evidence, tokens
            if "item3" in new_tokens and token != new_tokens["item3"]:
                return False, evidence, tokens
            new_tokens.setdefault("item3", token)

        elif expected.role == "item3_retry":
            if "item3" not in new_tokens or token != new_tokens["item3"]:
                return False, evidence, tokens

        evidence["logical_role"] = expected.role
        evidence["resolved_tokens"] = dict(new_tokens)
        return True, evidence, new_tokens

    if expected.message_server == "GetItem":
        if not evidence.get("exactly_one_get_item_consumed"):
            return False, evidence, tokens

        if expected.expect_consumer_output is True:
            if evidence.get("buffered_consume_count_added") != 1:
                return False, evidence, tokens
            if evidence.get("consumer_message_count_added") != 1:
                return False, evidence, tokens
            output_token = evidence.get("output_token")
            if (
                expected.output_role is None
                or expected.output_role not in new_tokens
                or output_token != new_tokens[expected.output_role]
            ):
                return False, evidence, tokens

        elif expected.expect_consumer_output is False:
            # Source empty behavior only logs locally. It sends nothing to Consumer.
            if evidence.get("consumer_message_count_added") != 0:
                return False, evidence, tokens

        evidence["logical_role"] = expected.role
        evidence["expected_output_role"] = expected.output_role
        evidence["resolved_tokens"] = dict(new_tokens)
        return True, evidence, new_tokens

    return False, evidence, tokens


def _find_benchmark_execution(
    parsed_result: dict[str, Any],
) -> MatchedExecution | None:
    """
    Find one connected graph execution whose Buffer operations are exactly:

        AddItem(item1)
        AddItem(item2)
        AddItem(item3)      # rejected by capacity-two behavior
        GetItem             # emits item1
        AddItem(item3)      # retry
        GetItem             # emits item2
        GetItem             # emits item3
        GetItem             # empty; emits nothing

    Non-Buffer transitions may interleave. Any additional or out-of-order
    AddItem/GetItem Buffer operation invalidates that branch.
    """
    outgoing = _outgoing_transitions(parsed_result)
    queue: deque[
        tuple[
            Any,
            int,
            list[dict[str, Any]],
            list[dict[str, Any]],
            dict[str, str],
        ]
    ] = deque()

    for initial_state_id in _initial_state_ids(parsed_result):
        queue.append((initial_state_id, 0, [], [], {}))

    visited: set[tuple[Any, int, tuple[tuple[str, str], ...]]] = set()

    while queue:
        state_id, step_index, path, matched_steps, tokens = queue.popleft()
        visit_key = (state_id, step_index, tuple(sorted(tokens.items())))
        if visit_key in visited:
            continue
        visited.add(visit_key)

        if step_index == len(EXPECTED_BUFFER_STEPS):
            return MatchedExecution(
                transitions=path,
                matched_steps=matched_steps,
                final_state_id=state_id,
                item_tokens=tokens,
            )

        expected = EXPECTED_BUFFER_STEPS[step_index]
        for transition in outgoing.get(state_id, []):
            destination = _transition_destination(transition)
            if _is_buffer_operation(transition):
                matches, evidence, new_tokens = _match_expected_buffer_step(
                    parsed_result,
                    transition,
                    expected,
                    tokens,
                )
                if not matches:
                    continue
                queue.append(
                    (
                        destination,
                        step_index + 1,
                        path + [transition],
                        matched_steps + [evidence],
                        new_tokens,
                    )
                )
            else:
                queue.append(
                    (
                        destination,
                        step_index,
                        path + [transition],
                        matched_steps,
                        tokens,
                    )
                )

    return None


def _all_rebec_queues_empty(state: dict[str, Any] | None) -> bool:
    if not state:
        return False
    rebecs = state.get("rebecs", {})
    if isinstance(rebecs, dict):
        for data in rebecs.values():
            if not isinstance(data, dict):
                continue
            queue = data.get("queue") or data.get("message_queue") or []
            if len(queue) != 0:
                return False
        return True
    if isinstance(rebecs, list):
        for rebec in rebecs:
            if not isinstance(rebec, dict):
                continue
            name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
            if name and len(get_queue(state, str(name))) != 0:
                return False
        return True
    return False


def _find_terminal_completion(
    parsed_result: dict[str, Any],
    start_state_id: Any,
) -> tuple[Any | None, list[dict[str, Any]]]:
    """
    After the eight benchmark Buffer operations, allow Consumer/helper cleanup,
    but forbid any extra source protocol operation on Producer or Buffer.
    """
    outgoing = _outgoing_transitions(parsed_result)
    queue: deque[tuple[Any, list[dict[str, Any]]]] = deque([(start_state_id, [])])
    visited: set[Any] = set()
    forbidden = {
        (normalize_name(PRODUCER_NAME), MSG_BUFFERED_PRODUCE),
        (normalize_name(PRODUCER_NAME), MSG_BUFFERED_CONSUME_NEXT),
        (normalize_name(BUFFER_NAME), MSG_ADD_ITEM),
        (normalize_name(BUFFER_NAME), MSG_GET_ITEM),
    }

    while queue:
        state_id, path = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)
        transitions = outgoing.get(state_id, [])
        if not transitions:
            state = get_state_by_id(parsed_result, state_id)
            if _all_rebec_queues_empty(state):
                return state_id, path
            continue
        for transition in transitions:
            key = (transition_owner(transition), transition_message(transition))
            if key in forbidden:
                continue
            queue.append((_transition_destination(transition), path + [transition]))

    return None, []


def _path_relevant_transitions(
    execution: MatchedExecution | None,
    terminal_completion: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return (
        (execution.transitions if execution is not None else [])
        + terminal_completion
    )


def _producer_forwarding_on_path(
    parsed_result: dict[str, Any],
    execution: MatchedExecution | None,
    terminal_completion: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    produce_evidence: list[dict[str, Any]] = []
    consume_next_evidence: list[dict[str, Any]] = []

    for transition in _path_relevant_transitions(execution, terminal_completion):
        if _is_transition(
            transition,
            owner=PRODUCER_NAME,
            message_server="BufferedProduce",
        ):
            produce_evidence.append(
                _producer_forwarding_evidence(parsed_result, transition)
            )
        elif _is_transition(
            transition,
            owner=PRODUCER_NAME,
            message_server="BufferedConsumeNext",
        ):
            consume_next_evidence.append(
                _producer_forwarding_evidence(parsed_result, transition)
            )

    return produce_evidence, consume_next_evidence


def _consumer_delivery_tokens_on_path(
    parsed_result: dict[str, Any],
    execution: MatchedExecution | None,
    terminal_completion: list[dict[str, Any]],
) -> list[str | None]:
    """Observe actual BufferedConsumer handler executions."""
    tokens: list[str | None] = []
    for transition in _path_relevant_transitions(execution, terminal_completion):
        if not _is_transition(
            transition,
            owner=CONSUMER_NAME,
            message_server="BufferedConsume",
        ):
            continue
        source_state = get_state_by_id(parsed_result, _transition_source(transition))
        destination_state = get_state_by_id(
            parsed_result, _transition_destination(transition)
        )
        removed = _removed_from_queue(
            source_state,
            destination_state,
            CONSUMER_NAME,
            message_name="BufferedConsume",
        )
        tokens.append(removed[0][1] if len(removed) == 1 else None)
    return tokens


class BufferProducerConsumerEvaluator(BaseSemanticEvaluator):
    benchmark_id = BENCHMARK_ID

    def __init__(
        self,
        parsed_result: dict[str, Any],
        example_id: str = BENCHMARK_ID,
    ) -> None:
        super().__init__(parsed_result=parsed_result, example_id=example_id)

    def evaluate(
        self,
        parsed_result: dict[str, Any],
    ) -> SemanticEvaluationResult:
        states = get_states(parsed_result)
        transitions = get_transitions(parsed_result)
        execution = _find_benchmark_execution(parsed_result)

        terminal_state_id: Any | None = None
        terminal_completion: list[dict[str, Any]] = []
        if execution is not None:
            terminal_state_id, terminal_completion = _find_terminal_completion(
                parsed_result,
                execution.final_state_id,
            )
            execution.terminal_state_id = terminal_state_id
            execution.terminal_completion = terminal_completion

        produce_forwarding, consume_next_forwarding = _producer_forwarding_on_path(
            parsed_result,
            execution,
            terminal_completion,
        )
        consumer_deliveries = _consumer_delivery_tokens_on_path(
            parsed_result,
            execution,
            terminal_completion,
        )

        tests: list[SemanticTestResult] = []
        tests.extend(
            self._evaluate_actor_tests(
                parsed_result,
                execution,
                produce_forwarding,
                consume_next_forwarding,
            )
        )
        tests.extend(
            self._evaluate_interaction_tests(
                parsed_result,
                execution,
                consumer_deliveries,
            )
        )
        tests.extend(
            self._evaluate_system_tests(
                parsed_result,
                execution,
                terminal_state_id,
                terminal_completion,
                produce_forwarding,
                consume_next_forwarding,
                consumer_deliveries,
            )
        )

        issues: list[str] = []
        if not transitions:
            issues.append("NO_TRANSITIONS")
        if execution is None:
            issues.append("BENCHMARK_PATH_NOT_FOUND")
        if execution is not None and terminal_state_id is None:
            issues.append("TERMINAL_QUIESCENCE_NOT_FOUND")
        if any(test.status == TestStatus.NOT_OBSERVED for test in tests):
            issues.append("INCOMPLETE_OBSERVABILITY")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": _initial_state_ids(parsed_result),
                "benchmark_path_found": execution is not None,
                "matched_buffer_step_count": (
                    len(execution.matched_steps) if execution is not None else 0
                ),
                "benchmark_path_transition_count": (
                    len(execution.transitions) if execution is not None else 0
                ),
                "terminal_state_id": terminal_state_id,
                "terminal_completion_transition_count": len(terminal_completion),
                "resolved_item_tokens": (
                    execution.item_tokens if execution is not None else {}
                ),
                "expected_buffer_operation_sequence": [
                    "AddItem(item1)",
                    "AddItem(item2)",
                    "AddItem(item3 initial; must be rejected)",
                    "GetItem -> item1",
                    "GetItem -> item2",
                    "GetItem -> no Consumer output (pre-retry rejection witness)",
                    "AddItem(item3 retry)",
                    "GetItem -> item3",
                    "GetItem -> no Consumer output (final empty)",
                ],
                "expected_logical_consumed_sequence": ["item1", "item2", "item3"],
                "representation_policy": {
                    "source_payload_type": "String",
                    "target_payload_representation": "representation-independent symbolic token",
                    "hard_coded_item_token_mapping": False,
                    "required_distinct_tokens": 3,
                    "retry_must_reuse_item3_token": True,
                },
                "evaluation_assumptions": {
                    "failure_free": True,
                    "logging_out_of_scope": True,
                    "buffer_capacity": 2,
                    "fifo_is_observable": True,
                    "rejection_is_observed_behaviorally": True,
                    "rejection_witness": "third pre-retry GetItem emits no Consumer message",
                    "empty_get_is_observed_as_no_consumer_message": True,
                    "buffer_internal_representation_is_not_observable": True,
                },
            },
        )

    def _evaluate_actor_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
        produce_forwarding: list[dict[str, Any]],
        consume_next_forwarding: list[dict[str, Any]],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        xa1_pass = (
            len(produce_forwarding) == 4
            and all(evidence.get("passed") is True for evidence in produce_forwarding)
        )
        tests.append(
            _test(
                "BPC-XA1",
                _status_from_observation(xa1_pass, observed=bool(produce_forwarding)),
                "BufferedProducer must preserve each payload when forwarding BufferedProduce(x) as AddItem(x).",
                {
                    "expected_forward_count": 4,
                    "observed_forward_count": len(produce_forwarding),
                    "forwarding": produce_forwarding,
                },
            )
        )

        xa2_pass = (
            len(consume_next_forwarding) == 5
            and all(
                evidence.get("passed") is True
                for evidence in consume_next_forwarding
            )
        )
        tests.append(
            _test(
                "BPC-XA2",
                _status_from_observation(
                    xa2_pass,
                    observed=bool(consume_next_forwarding),
                ),
                "BufferedProducer must forward each BufferedConsumeNext as exactly one GetItem.",
                {
                    "expected_forward_count": 5,
                    "observed_forward_count": len(consume_next_forwarding),
                    "forwarding": consume_next_forwarding,
                },
            )
        )

        final_step = (
            execution.matched_steps[8]
            if execution is not None and len(execution.matched_steps) >= 9
            else None
        )
        xa3_pass = (
            final_step is not None
            and final_step.get("logical_role") == "final_empty_get"
            and final_step.get("consumer_message_count_added") == 0
        )
        tests.append(
            _test(
                "BPC-XA3",
                _status_from_observation(xa3_pass, observed=final_step is not None),
                "GetItem on the final empty Buffer state must produce no Consumer message.",
                {"final_get_step": final_step},
            )
        )

        first_get = (
            execution.matched_steps[3]
            if execution is not None and len(execution.matched_steps) >= 4
            else None
        )
        second_get = (
            execution.matched_steps[4]
            if execution is not None and len(execution.matched_steps) >= 5
            else None
        )
        pre_retry_empty_get = (
            execution.matched_steps[5]
            if execution is not None and len(execution.matched_steps) >= 6
            else None
        )
        retry_item3 = (
            execution.matched_steps[6]
            if execution is not None and len(execution.matched_steps) >= 7
            else None
        )
        third_get = (
            execution.matched_steps[7]
            if execution is not None and len(execution.matched_steps) >= 8
            else None
        )

        item1_token = execution.item_tokens.get("item1") if execution else None
        item2_token = execution.item_tokens.get("item2") if execution else None
        item3_token = execution.item_tokens.get("item3") if execution else None

        xa4_pass = (
            first_get is not None
            and item1_token is not None
            and first_get.get("output_token") == item1_token
        )
        tests.append(
            _test(
                "BPC-XA4",
                _status_from_observation(xa4_pass, observed=first_get is not None),
                "An accepted first item must later be consumed with its payload identity preserved.",
                {"item1_token": item1_token, "first_get_step": first_get},
            )
        )

        # Strong rejection witness. After AddItem(item1), AddItem(item2), and
        # the initial AddItem(item3), the next three GetItem operations must
        # yield item1, item2, then no Consumer message. If the initial item3
        # had incorrectly entered the capacity-two buffer, the third GetItem
        # would emit item3 and this test would fail.
        xa5_pass = (
            first_get is not None
            and second_get is not None
            and pre_retry_empty_get is not None
            and item1_token is not None
            and item2_token is not None
            and first_get.get("output_token") == item1_token
            and second_get.get("output_token") == item2_token
            and pre_retry_empty_get.get("logical_role") == "pre_retry_empty_get"
            and pre_retry_empty_get.get("consumer_message_count_added") == 0
        )
        tests.append(
            _test(
                "BPC-XA5",
                _status_from_observation(xa5_pass, observed=execution is not None),
                "Capacity-two rejection must be observable: before retry, three GetItem operations yield item1, item2, then no Consumer message.",
                {
                    "resolved_tokens": execution.item_tokens if execution else {},
                    "first_get_step": first_get,
                    "second_get_step": second_get,
                    "pre_retry_empty_get_step": pre_retry_empty_get,
                },
            )
        )

        xa6_pass = (
            first_get is not None
            and second_get is not None
            and item1_token is not None
            and item2_token is not None
            and first_get.get("output_token") == item1_token
            and second_get.get("output_token") == item2_token
        )
        tests.append(
            _test(
                "BPC-XA6",
                _status_from_observation(
                    xa6_pass,
                    observed=first_get is not None and second_get is not None,
                ),
                "Buffer must preserve FIFO order: item1 must be consumed before item2.",
                {
                    "expected_roles": ["item1", "item2"],
                    "observed_tokens": [
                        first_get.get("output_token") if first_get else None,
                        second_get.get("output_token") if second_get else None,
                    ],
                    "resolved_tokens": execution.item_tokens if execution else {},
                },
            )
        )

        xa7_pass = (
            retry_item3 is not None
            and third_get is not None
            and item3_token is not None
            and retry_item3.get("input_token") == item3_token
            and third_get.get("output_token") == item3_token
        )
        tests.append(
            _test(
                "BPC-XA7",
                _status_from_observation(
                    xa7_pass,
                    observed=retry_item3 is not None and third_get is not None,
                ),
                "After the pre-retry empty checkpoint, retrying item3 must be accepted and later consumed as the same item3 token.",
                {
                    "item3_token": item3_token,
                    "pre_retry_empty_get_step": pre_retry_empty_get,
                    "retry_item3_step": retry_item3,
                    "item3_get_step": third_get,
                },
            )
        )

        return tests

    def _evaluate_interaction_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
        consumer_deliveries: list[str | None],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []
        expected_tokens = (
            [
                execution.item_tokens.get("item1"),
                execution.item_tokens.get("item2"),
                execution.item_tokens.get("item3"),
            ]
            if execution is not None
            else []
        )

        xi1_pass = (
            execution is not None
            and len(execution.matched_steps) == 9
            and bool(expected_tokens)
            and None not in expected_tokens
        )
        tests.append(
            _test(
                "BPC-XI1",
                _status_from_observation(bool(xi1_pass), observed=execution is not None),
                "One connected state-graph execution must realize the complete nine-operation strengthened Buffer benchmark.",
                {
                    "matched_buffer_steps": execution.matched_steps if execution else [],
                    "resolved_tokens": execution.item_tokens if execution else {},
                },
            )
        )

        xi2_pass = len(consumer_deliveries) == 3 and consumer_deliveries == expected_tokens
        tests.append(
            _test(
                "BPC-XI2",
                _status_from_observation(xi2_pass, observed=bool(consumer_deliveries)),
                "Every accepted benchmark item must be delivered to BufferedConsumer exactly once with no loss or duplication.",
                {
                    "expected_delivery_tokens": expected_tokens,
                    "observed_delivery_tokens": consumer_deliveries,
                },
            )
        )

        item3_token = execution.item_tokens.get("item3") if execution else None
        pre_retry_empty_get = (
            execution.matched_steps[5]
            if execution is not None and len(execution.matched_steps) >= 6
            else None
        )
        xi3_pass = (
            item3_token is not None
            and pre_retry_empty_get is not None
            and pre_retry_empty_get.get("consumer_message_count_added") == 0
            and consumer_deliveries.count(item3_token) == 1
        )
        tests.append(
            _test(
                "BPC-XI3",
                _status_from_observation(xi3_pass, observed=bool(consumer_deliveries)),
                "Initial item3 rejection must be separated by a pre-retry empty checkpoint from exactly one later item3 delivery.",
                {
                    "item3_token": item3_token,
                    "pre_retry_empty_get_step": pre_retry_empty_get,
                    "consumer_delivery_tokens": consumer_deliveries,
                    "item3_delivery_count": (
                        consumer_deliveries.count(item3_token)
                        if item3_token is not None
                        else 0
                    ),
                },
            )
        )

        xi4_pass = consumer_deliveries == expected_tokens and len(consumer_deliveries) == 3
        tests.append(
            _test(
                "BPC-XI4",
                _status_from_observation(xi4_pass, observed=bool(consumer_deliveries)),
                "FIFO order must remain item1, item2, item3 across full-buffer rejection and retry.",
                {
                    "expected_delivery_tokens": expected_tokens,
                    "observed_delivery_tokens": consumer_deliveries,
                },
            )
        )
        return tests

    def _evaluate_system_tests(
        self,
        parsed_result: dict[str, Any],
        execution: MatchedExecution | None,
        terminal_state_id: Any | None,
        terminal_completion: list[dict[str, Any]],
        produce_forwarding: list[dict[str, Any]],
        consume_next_forwarding: list[dict[str, Any]],
        consumer_deliveries: list[str | None],
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        observed_rebecs = _rebec_names(parsed_result)
        required = {
            normalize_name(PRODUCER_NAME),
            normalize_name(BUFFER_NAME),
            normalize_name(CONSUMER_NAME),
        }
        topology_pass = required.issubset(observed_rebecs)
        tests.append(
            _test(
                "BPC-XSYS1",
                TestStatus.PASS if topology_pass else TestStatus.FAIL,
                "The target model must contain producer, buffer, and consumer rebecs; behavior-preserving auxiliary rebecs are allowed.",
                {
                    "required_rebecs": sorted(required),
                    "observed_rebecs": sorted(observed_rebecs),
                    "missing_rebecs": sorted(required - observed_rebecs),
                },
            )
        )

        xsys2_pass = (
            execution is not None
            and len(produce_forwarding) == 4
            and len(consume_next_forwarding) == 5
            and all(
                evidence.get("passed") is True
                for evidence in produce_forwarding + consume_next_forwarding
            )
        )
        tests.append(
            _test(
                "BPC-XSYS2",
                _status_from_observation(xsys2_pass, observed=execution is not None),
                "The connected benchmark path must execute four BufferedProduce and five BufferedConsumeNext commands through BufferedProducer with correct forwarding.",
                {
                    "benchmark_path_found": execution is not None,
                    "expected_buffered_produce_count": 4,
                    "observed_buffered_produce_count": len(produce_forwarding),
                    "expected_buffered_consume_next_count": 5,
                    "observed_buffered_consume_next_count": len(consume_next_forwarding),
                },
            )
        )

        final_step = (
            execution.matched_steps[8]
            if execution is not None and len(execution.matched_steps) >= 9
            else None
        )
        terminal_state = (
            get_state_by_id(parsed_result, terminal_state_id)
            if terminal_state_id is not None
            else None
        )
        xsys3_pass = (
            final_step is not None
            and final_step.get("consumer_message_count_added") == 0
            and terminal_state_id is not None
            and _all_rebec_queues_empty(terminal_state)
            and len(consumer_deliveries) == 3
        )
        tests.append(
            _test(
                "BPC-XSYS3",
                _status_from_observation(xsys3_pass, observed=execution is not None),
                "After the final empty GetItem, no additional observable item may be produced and the system must complete with all rebec queues empty.",
                {
                    "final_get_step": final_step,
                    "terminal_state_id": terminal_state_id,
                    "terminal_queues_empty": (
                        _all_rebec_queues_empty(terminal_state)
                        if terminal_state is not None
                        else False
                    ),
                    "consumer_delivery_count": len(consumer_deliveries),
                },
            )
        )

        expected_tokens = (
            [
                execution.item_tokens.get("item1"),
                execution.item_tokens.get("item2"),
                execution.item_tokens.get("item3"),
            ]
            if execution is not None
            else []
        )
        pre_retry_empty_get = (
            execution.matched_steps[5]
            if execution is not None and len(execution.matched_steps) >= 6
            else None
        )
        xsys4_pass = (
            execution is not None
            and len(execution.matched_steps) == 9
            and pre_retry_empty_get is not None
            and pre_retry_empty_get.get("consumer_message_count_added") == 0
            and consumer_deliveries == expected_tokens
            and terminal_state_id is not None
            and _all_rebec_queues_empty(terminal_state)
        )
        tests.append(
            _test(
                "BPC-XSYS4",
                _status_from_observation(xsys4_pass, observed=execution is not None),
                "The complete observable system contract must preserve bounded rejection with a pre-retry empty witness, retry acceptance, FIFO delivery of item1/item2/item3, final empty behavior, and terminal quiescence.",
                {
                    "resolved_item_tokens": execution.item_tokens if execution else {},
                    "matched_buffer_steps": execution.matched_steps if execution else [],
                    "pre_retry_empty_get_step": pre_retry_empty_get,
                    "consumer_delivery_tokens": consumer_deliveries,
                    "terminal_state_id": terminal_state_id,
                    "terminal_completion_transition_count": len(terminal_completion),
                },
            )
        )

        return tests


def evaluate_buffer_producer_consumer(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = BufferProducerConsumerEvaluator(
        parsed_result=parsed_result,
        example_id=BENCHMARK_ID,
    )
    return evaluator.evaluate(parsed_result).to_dict()


def load_json(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.is_file():
        raise FileNotFoundError(f"JSON file not found: {file_path}")
    with file_path.open("r", encoding="utf-8") as file:
        value = json.load(file)
    if not isinstance(value, dict):
        raise ValueError("Parsed RMC JSON must contain a JSON object.")
    return value


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the buffered Producer-Consumer benchmark from parsed RMC JSON."
        )
    )
    parser.add_argument("parsed_result", help="Path to the parsed RMC JSON file.")
    parser.add_argument("--output", "-o", help="Optional output JSON path.")
    arguments = parser.parse_args()

    try:
        parsed_result = load_json(arguments.parsed_result)
        result = evaluate_buffer_producer_consumer(parsed_result)
        serialized = json.dumps(result, indent=2, ensure_ascii=False)
        if arguments.output:
            output_path = Path(arguments.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(serialized + "\n", encoding="utf-8")
        else:
            print(serialized)
        return 0
    except Exception as exc:
        print(
            f"BufferProducerConsumer evaluator infrastructure error: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

# from __future__ import annotations

# import json
# import sys

# from collections import Counter as MultisetCounter
# from collections import defaultdict, deque
# from dataclasses import dataclass
# from pathlib import Path
# from typing import Any

# PROJECT_ROOT = Path(__file__).resolve().parents[2]

# if str(PROJECT_ROOT) not in sys.path:
#     sys.path.insert(0, str(PROJECT_ROOT))

# from semantic_validation.core.base_evaluator import BaseSemanticEvaluator
# from semantic_validation.core.evaluator_models import (
#     SemanticEvaluationResult,
#     SemanticTestResult,
#     TestStatus,
# )
# from semantic_validation.core.trace_utils import (
#     get_queue,
#     get_state_by_id,
#     get_states,
#     get_transitions,
#     normalize_name,
#     transition_message,
#     transition_owner,
# )

# BENCHMARK_ID = "buffer_producer_consumer"

# PRODUCER_NAME = "producer"
# BUFFER_NAME = "buffer"
# CONSUMER_NAME = "consumer"

# MSG_BUFFERED_PRODUCE = normalize_name("BufferedProduce")
# MSG_BUFFERED_CONSUME_NEXT = normalize_name("BufferedConsumeNext")
# MSG_ADD_ITEM = normalize_name("AddItem")
# MSG_GET_ITEM = normalize_name("GetItem")
# MSG_BUFFERED_CONSUME = normalize_name("BufferedConsume")


# @dataclass(frozen=True)
# class ExpectedBufferStep:
#     message_server: str
#     role: str
#     output_role: str | None = None
#     expect_consumer_output: bool | None = None


# @dataclass
# class MatchedExecution:
#     transitions: list[dict[str, Any]]
#     matched_steps: list[dict[str, Any]]
#     final_state_id: Any
#     item_tokens: dict[str, str]
#     terminal_state_id: Any | None = None
#     terminal_completion: list[dict[str, Any]] | None = None


# EXPECTED_BUFFER_STEPS = [
#     ExpectedBufferStep("AddItem", "item1", expect_consumer_output=False),
#     ExpectedBufferStep("AddItem", "item2", expect_consumer_output=False),
#     ExpectedBufferStep("AddItem", "item3_initial", expect_consumer_output=False),
#     ExpectedBufferStep("GetItem", "consume_item1", "item1", True),
#     ExpectedBufferStep("AddItem", "item3_retry", expect_consumer_output=False),
#     ExpectedBufferStep("GetItem", "consume_item2", "item2", True),
#     ExpectedBufferStep("GetItem", "consume_item3", "item3", True),
#     ExpectedBufferStep("GetItem", "empty_get", expect_consumer_output=False),
# ]


# def _state_id(state: dict[str, Any] | None) -> Any:
#     if not state:
#         return None
#     return state.get("id") if state.get("id") is not None else state.get("state_id")


# def _transition_source(transition: dict[str, Any]) -> Any:
#     return transition.get("source")


# def _transition_destination(transition: dict[str, Any]) -> Any:
#     return transition.get("destination")


# def _initial_state_ids(parsed_result: dict[str, Any]) -> list[Any]:
#     state_ids = [
#         _state_id(state)
#         for state in get_states(parsed_result)
#         if _state_id(state) is not None
#     ]
#     if not state_ids:
#         return []

#     destinations = {
#         _transition_destination(transition)
#         for transition in get_transitions(parsed_result)
#     }
#     roots = [state_id for state_id in state_ids if state_id not in destinations]
#     if roots:
#         return roots
#     if 0 in state_ids:
#         return [0]
#     return [state_ids[0]]


# def _outgoing_transitions(
#     parsed_result: dict[str, Any],
# ) -> dict[Any, list[dict[str, Any]]]:
#     outgoing: dict[Any, list[dict[str, Any]]] = defaultdict(list)
#     for transition in get_transitions(parsed_result):
#         outgoing[_transition_source(transition)].append(transition)
#     return outgoing


# def _rebec_names(parsed_result: dict[str, Any]) -> set[str]:
#     names: set[str] = set()
#     for state in get_states(parsed_result):
#         rebecs = state.get("rebecs", {})
#         if isinstance(rebecs, dict):
#             names.update(normalize_name(name) for name in rebecs)
#         elif isinstance(rebecs, list):
#             for rebec in rebecs:
#                 if not isinstance(rebec, dict):
#                     continue
#                 name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
#                 if name:
#                     names.add(normalize_name(str(name)))
#     return names


# def _message_raw(message: dict[str, Any]) -> str:
#     return str(
#         message.get("message")
#         or message.get("name")
#         or message.get("message_name")
#         or message.get("message_server")
#         or ""
#     ).strip()


# def _message_name(message: dict[str, Any]) -> str:
#     """Return logical message-server name without serialized arguments."""
#     raw = _message_raw(message)
#     if "(" in raw:
#         raw = raw.split("(", 1)[0]
#     return normalize_name(raw)


# def _message_sender(message: dict[str, Any]) -> str:
#     return normalize_name(str(message.get("sender") or ""))


# def _message_parameters(message: dict[str, Any]) -> dict[str, Any]:
#     parameters = message.get("parameters") or message.get("params") or {}
#     return parameters if isinstance(parameters, dict) else {}


# def _first_argument_from_raw(raw: str) -> str | None:
#     if "(" not in raw or ")" not in raw:
#         return None
#     inner = raw[raw.find("(") + 1 : raw.rfind(")")].strip()
#     if not inner:
#         return None
#     first = inner.split(",", 1)[0].strip()
#     if len(first) >= 2 and first[0] == first[-1] and first[0] in {'"', "'"}:
#         first = first[1:-1]
#     return first.strip()


# def _message_payload(message: dict[str, Any]) -> Any:
#     """
#     Extract the first logical payload parameter.

#     The source uses String values, but the target may encode them using any
#     three distinct symbolic Core Rebeca tokens. The evaluator infers those
#     tokens from the connected execution instead of hard-coding 1/2/3.
#     """
#     parameters = _message_parameters(message)
#     for key in ("item", "value", "arg0", "parameter0"):
#         if key in parameters:
#             return parameters[key]
#     if len(parameters) == 1:
#         return next(iter(parameters.values()))
#     for key in ("item", "value"):
#         if key in message:
#             return message[key]
#     return _first_argument_from_raw(_message_raw(message))


# def _canonical_token(value: Any) -> str | None:
#     if value is None:
#         return None
#     text = str(value).strip()
#     if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
#         text = text[1:-1]
#     return text.strip()


# def _message_signature(
#     message: dict[str, Any],
# ) -> tuple[str, str | None, str]:
#     return (
#         _message_name(message),
#         _canonical_token(_message_payload(message)),
#         _message_sender(message),
#     )


# def _queue_signatures(
#     state: dict[str, Any] | None,
#     rebec: str,
#     *,
#     message_name: str | None = None,
# ) -> list[tuple[str, str | None, str]]:
#     expected = normalize_name(message_name) if message_name is not None else None
#     result: list[tuple[str, str | None, str]] = []
#     for message in get_queue(state, rebec):
#         signature = _message_signature(message)
#         if expected is not None and signature[0] != expected:
#             continue
#         result.append(signature)
#     return result


# def _positive_multiset_delta(
#     left: list[tuple[str, str | None, str]],
#     right: list[tuple[str, str | None, str]],
# ) -> list[tuple[str, str | None, str]]:
#     delta = MultisetCounter(left) - MultisetCounter(right)
#     result: list[tuple[str, str | None, str]] = []
#     for signature, count in delta.items():
#         result.extend([signature] * count)
#     return result


# def _removed_from_queue(
#     source_state: dict[str, Any] | None,
#     destination_state: dict[str, Any] | None,
#     rebec: str,
#     *,
#     message_name: str | None = None,
# ) -> list[tuple[str, str | None, str]]:
#     return _positive_multiset_delta(
#         _queue_signatures(source_state, rebec, message_name=message_name),
#         _queue_signatures(destination_state, rebec, message_name=message_name),
#     )


# def _added_to_queue(
#     source_state: dict[str, Any] | None,
#     destination_state: dict[str, Any] | None,
#     rebec: str,
#     *,
#     message_name: str | None = None,
# ) -> list[tuple[str, str | None, str]]:
#     return _positive_multiset_delta(
#         _queue_signatures(destination_state, rebec, message_name=message_name),
#         _queue_signatures(source_state, rebec, message_name=message_name),
#     )


# def _test(
#     test_id: str,
#     status: TestStatus,
#     description: str,
#     evidence: dict[str, Any],
# ) -> SemanticTestResult:
#     return SemanticTestResult(
#         test_id=test_id,
#         status=status,
#         description=description,
#         evidence=evidence,
#     )


# def _status_from_observation(condition: bool, *, observed: bool) -> TestStatus:
#     if condition:
#         return TestStatus.PASS
#     return TestStatus.FAIL if observed else TestStatus.NOT_OBSERVED


# def _is_transition(
#     transition: dict[str, Any],
#     *,
#     owner: str,
#     message_server: str,
# ) -> bool:
#     return transition_owner(transition) == normalize_name(owner) and transition_message(
#         transition
#     ) == normalize_name(message_server)


# def _is_buffer_operation(transition: dict[str, Any]) -> bool:
#     return transition_owner(transition) == normalize_name(
#         BUFFER_NAME
#     ) and transition_message(transition) in {MSG_ADD_ITEM, MSG_GET_ITEM}


# def _producer_forwarding_evidence(
#     parsed_result: dict[str, Any],
#     transition: dict[str, Any],
# ) -> dict[str, Any]:
#     source_state = get_state_by_id(parsed_result, _transition_source(transition))
#     destination_state = get_state_by_id(
#         parsed_result, _transition_destination(transition)
#     )
#     message_server = transition_message(transition)

#     if message_server == MSG_BUFFERED_PRODUCE:
#         removed = _removed_from_queue(
#             source_state,
#             destination_state,
#             PRODUCER_NAME,
#             message_name="BufferedProduce",
#         )
#         added = _added_to_queue(
#             source_state,
#             destination_state,
#             BUFFER_NAME,
#             message_name="AddItem",
#         )
#         input_token = removed[0][1] if len(removed) == 1 else None
#         output_token = added[0][1] if len(added) == 1 else None
#         passed = (
#             len(removed) == 1
#             and len(added) == 1
#             and input_token is not None
#             and input_token == output_token
#         )
#         return {
#             "kind": "produce_forwarding",
#             "source_state_id": _transition_source(transition),
#             "destination_state_id": _transition_destination(transition),
#             "removed_buffered_produce": removed,
#             "added_add_item": added,
#             "input_token": input_token,
#             "output_token": output_token,
#             "payload_preserved": passed,
#             "passed": passed,
#         }

#     if message_server == MSG_BUFFERED_CONSUME_NEXT:
#         removed = _removed_from_queue(
#             source_state,
#             destination_state,
#             PRODUCER_NAME,
#             message_name="BufferedConsumeNext",
#         )
#         added = _added_to_queue(
#             source_state,
#             destination_state,
#             BUFFER_NAME,
#             message_name="GetItem",
#         )
#         passed = len(removed) == 1 and len(added) == 1
#         return {
#             "kind": "consume_next_forwarding",
#             "source_state_id": _transition_source(transition),
#             "destination_state_id": _transition_destination(transition),
#             "removed_buffered_consume_next": removed,
#             "added_get_item": added,
#             "passed": passed,
#         }

#     return {"kind": "unrelated", "passed": False}


# def _buffer_step_evidence(
#     parsed_result: dict[str, Any],
#     transition: dict[str, Any],
# ) -> dict[str, Any]:
#     source_state = get_state_by_id(parsed_result, _transition_source(transition))
#     destination_state = get_state_by_id(
#         parsed_result, _transition_destination(transition)
#     )
#     message_server = transition_message(transition)
#     evidence: dict[str, Any] = {
#         "message_server": message_server,
#         "source_state_id": _transition_source(transition),
#         "destination_state_id": _transition_destination(transition),
#     }

#     if message_server == MSG_ADD_ITEM:
#         removed = _removed_from_queue(
#             source_state,
#             destination_state,
#             BUFFER_NAME,
#             message_name="AddItem",
#         )
#         consumer_added = _added_to_queue(
#             source_state,
#             destination_state,
#             CONSUMER_NAME,
#         )
#         evidence.update(
#             {
#                 "removed_add_item": removed,
#                 "input_token": removed[0][1] if len(removed) == 1 else None,
#                 "consumer_messages_added": consumer_added,
#                 "exactly_one_add_item_consumed": len(removed) == 1,
#                 "no_consumer_output": len(consumer_added) == 0,
#             }
#         )
#         return evidence

#     if message_server == MSG_GET_ITEM:
#         removed = _removed_from_queue(
#             source_state,
#             destination_state,
#             BUFFER_NAME,
#             message_name="GetItem",
#         )
#         added_consume = _added_to_queue(
#             source_state,
#             destination_state,
#             CONSUMER_NAME,
#             message_name="BufferedConsume",
#         )
#         consumer_added_any = _added_to_queue(
#             source_state,
#             destination_state,
#             CONSUMER_NAME,
#         )
#         evidence.update(
#             {
#                 "removed_get_item": removed,
#                 "added_buffered_consume": added_consume,
#                 "consumer_messages_added": consumer_added_any,
#                 "exactly_one_get_item_consumed": len(removed) == 1,
#                 "output_token": (
#                     added_consume[0][1] if len(added_consume) == 1 else None
#                 ),
#                 "buffered_consume_count_added": len(added_consume),
#                 "consumer_message_count_added": len(consumer_added_any),
#             }
#         )
#         return evidence

#     return evidence


# def _match_expected_buffer_step(
#     parsed_result: dict[str, Any],
#     transition: dict[str, Any],
#     expected: ExpectedBufferStep,
#     tokens: dict[str, str],
# ) -> tuple[bool, dict[str, Any], dict[str, str]]:
#     if not _is_transition(
#         transition,
#         owner=BUFFER_NAME,
#         message_server=expected.message_server,
#     ):
#         return False, {}, tokens

#     evidence = _buffer_step_evidence(parsed_result, transition)
#     new_tokens = dict(tokens)

#     if expected.message_server == "AddItem":
#         if not evidence.get("exactly_one_add_item_consumed"):
#             return False, evidence, tokens
#         if not evidence.get("no_consumer_output"):
#             return False, evidence, tokens

#         token = evidence.get("input_token")
#         if token is None:
#             return False, evidence, tokens

#         if expected.role == "item1":
#             if "item1" in new_tokens and token != new_tokens["item1"]:
#                 return False, evidence, tokens
#             new_tokens.setdefault("item1", token)

#         elif expected.role == "item2":
#             if token == new_tokens.get("item1"):
#                 return False, evidence, tokens
#             if "item2" in new_tokens and token != new_tokens["item2"]:
#                 return False, evidence, tokens
#             new_tokens.setdefault("item2", token)

#         elif expected.role == "item3_initial":
#             if token in {new_tokens.get("item1"), new_tokens.get("item2")}:
#                 return False, evidence, tokens
#             if "item3" in new_tokens and token != new_tokens["item3"]:
#                 return False, evidence, tokens
#             new_tokens.setdefault("item3", token)

#         elif expected.role == "item3_retry":
#             if "item3" not in new_tokens or token != new_tokens["item3"]:
#                 return False, evidence, tokens

#         evidence["logical_role"] = expected.role
#         evidence["resolved_tokens"] = dict(new_tokens)
#         return True, evidence, new_tokens

#     if expected.message_server == "GetItem":
#         if not evidence.get("exactly_one_get_item_consumed"):
#             return False, evidence, tokens

#         if expected.expect_consumer_output is True:
#             if evidence.get("buffered_consume_count_added") != 1:
#                 return False, evidence, tokens
#             if evidence.get("consumer_message_count_added") != 1:
#                 return False, evidence, tokens
#             output_token = evidence.get("output_token")
#             if (
#                 expected.output_role is None
#                 or expected.output_role not in new_tokens
#                 or output_token != new_tokens[expected.output_role]
#             ):
#                 return False, evidence, tokens

#         elif expected.expect_consumer_output is False:
#             # Source empty behavior only logs locally. It sends nothing to Consumer.
#             if evidence.get("consumer_message_count_added") != 0:
#                 return False, evidence, tokens

#         evidence["logical_role"] = expected.role
#         evidence["expected_output_role"] = expected.output_role
#         evidence["resolved_tokens"] = dict(new_tokens)
#         return True, evidence, new_tokens

#     return False, evidence, tokens


# def _find_benchmark_execution(
#     parsed_result: dict[str, Any],
# ) -> MatchedExecution | None:
#     """
#     Find one connected graph execution whose Buffer operations are exactly:

#         AddItem(item1)
#         AddItem(item2)
#         AddItem(item3)      # rejected by capacity-two behavior
#         GetItem             # emits item1
#         AddItem(item3)      # retry
#         GetItem             # emits item2
#         GetItem             # emits item3
#         GetItem             # empty; emits nothing

#     Non-Buffer transitions may interleave. Any additional or out-of-order
#     AddItem/GetItem Buffer operation invalidates that branch.
#     """
#     outgoing = _outgoing_transitions(parsed_result)
#     queue: deque[
#         tuple[
#             Any,
#             int,
#             list[dict[str, Any]],
#             list[dict[str, Any]],
#             dict[str, str],
#         ]
#     ] = deque()

#     for initial_state_id in _initial_state_ids(parsed_result):
#         queue.append((initial_state_id, 0, [], [], {}))

#     visited: set[tuple[Any, int, tuple[tuple[str, str], ...]]] = set()

#     while queue:
#         state_id, step_index, path, matched_steps, tokens = queue.popleft()
#         visit_key = (state_id, step_index, tuple(sorted(tokens.items())))
#         if visit_key in visited:
#             continue
#         visited.add(visit_key)

#         if step_index == len(EXPECTED_BUFFER_STEPS):
#             return MatchedExecution(
#                 transitions=path,
#                 matched_steps=matched_steps,
#                 final_state_id=state_id,
#                 item_tokens=tokens,
#             )

#         expected = EXPECTED_BUFFER_STEPS[step_index]
#         for transition in outgoing.get(state_id, []):
#             destination = _transition_destination(transition)
#             if _is_buffer_operation(transition):
#                 matches, evidence, new_tokens = _match_expected_buffer_step(
#                     parsed_result,
#                     transition,
#                     expected,
#                     tokens,
#                 )
#                 if not matches:
#                     continue
#                 queue.append(
#                     (
#                         destination,
#                         step_index + 1,
#                         path + [transition],
#                         matched_steps + [evidence],
#                         new_tokens,
#                     )
#                 )
#             else:
#                 queue.append(
#                     (
#                         destination,
#                         step_index,
#                         path + [transition],
#                         matched_steps,
#                         tokens,
#                     )
#                 )

#     return None


# def _all_rebec_queues_empty(state: dict[str, Any] | None) -> bool:
#     if not state:
#         return False
#     rebecs = state.get("rebecs", {})
#     if isinstance(rebecs, dict):
#         for data in rebecs.values():
#             if not isinstance(data, dict):
#                 continue
#             queue = data.get("queue") or data.get("message_queue") or []
#             if len(queue) != 0:
#                 return False
#         return True
#     if isinstance(rebecs, list):
#         for rebec in rebecs:
#             if not isinstance(rebec, dict):
#                 continue
#             name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
#             if name and len(get_queue(state, str(name))) != 0:
#                 return False
#         return True
#     return False


# def _find_terminal_completion(
#     parsed_result: dict[str, Any],
#     start_state_id: Any,
# ) -> tuple[Any | None, list[dict[str, Any]]]:
#     """
#     After the eight benchmark Buffer operations, allow Consumer/helper cleanup,
#     but forbid any extra source protocol operation on Producer or Buffer.
#     """
#     outgoing = _outgoing_transitions(parsed_result)
#     queue: deque[tuple[Any, list[dict[str, Any]]]] = deque([(start_state_id, [])])
#     visited: set[Any] = set()
#     forbidden = {
#         (normalize_name(PRODUCER_NAME), MSG_BUFFERED_PRODUCE),
#         (normalize_name(PRODUCER_NAME), MSG_BUFFERED_CONSUME_NEXT),
#         (normalize_name(BUFFER_NAME), MSG_ADD_ITEM),
#         (normalize_name(BUFFER_NAME), MSG_GET_ITEM),
#     }

#     while queue:
#         state_id, path = queue.popleft()
#         if state_id in visited:
#             continue
#         visited.add(state_id)
#         transitions = outgoing.get(state_id, [])
#         if not transitions:
#             state = get_state_by_id(parsed_result, state_id)
#             if _all_rebec_queues_empty(state):
#                 return state_id, path
#             continue
#         for transition in transitions:
#             key = (transition_owner(transition), transition_message(transition))
#             if key in forbidden:
#                 continue
#             queue.append((_transition_destination(transition), path + [transition]))

#     return None, []


# def _path_relevant_transitions(
#     execution: MatchedExecution | None,
#     terminal_completion: list[dict[str, Any]],
# ) -> list[dict[str, Any]]:
#     return (
#         execution.transitions if execution is not None else []
#     ) + terminal_completion


# def _producer_forwarding_on_path(
#     parsed_result: dict[str, Any],
#     execution: MatchedExecution | None,
#     terminal_completion: list[dict[str, Any]],
# ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
#     produce_evidence: list[dict[str, Any]] = []
#     consume_next_evidence: list[dict[str, Any]] = []

#     for transition in _path_relevant_transitions(execution, terminal_completion):
#         if _is_transition(
#             transition,
#             owner=PRODUCER_NAME,
#             message_server="BufferedProduce",
#         ):
#             produce_evidence.append(
#                 _producer_forwarding_evidence(parsed_result, transition)
#             )
#         elif _is_transition(
#             transition,
#             owner=PRODUCER_NAME,
#             message_server="BufferedConsumeNext",
#         ):
#             consume_next_evidence.append(
#                 _producer_forwarding_evidence(parsed_result, transition)
#             )

#     return produce_evidence, consume_next_evidence


# def _consumer_delivery_tokens_on_path(
#     parsed_result: dict[str, Any],
#     execution: MatchedExecution | None,
#     terminal_completion: list[dict[str, Any]],
# ) -> list[str | None]:
#     """Observe actual BufferedConsumer handler executions."""
#     tokens: list[str | None] = []
#     for transition in _path_relevant_transitions(execution, terminal_completion):
#         if not _is_transition(
#             transition,
#             owner=CONSUMER_NAME,
#             message_server="BufferedConsume",
#         ):
#             continue
#         source_state = get_state_by_id(parsed_result, _transition_source(transition))
#         destination_state = get_state_by_id(
#             parsed_result, _transition_destination(transition)
#         )
#         removed = _removed_from_queue(
#             source_state,
#             destination_state,
#             CONSUMER_NAME,
#             message_name="BufferedConsume",
#         )
#         tokens.append(removed[0][1] if len(removed) == 1 else None)
#     return tokens


# class BufferProducerConsumerEvaluator(BaseSemanticEvaluator):
#     benchmark_id = BENCHMARK_ID

#     def __init__(
#         self,
#         parsed_result: dict[str, Any],
#         example_id: str = BENCHMARK_ID,
#     ) -> None:
#         super().__init__(parsed_result=parsed_result, example_id=example_id)

#     def evaluate(
#         self,
#         parsed_result: dict[str, Any],
#     ) -> SemanticEvaluationResult:
#         states = get_states(parsed_result)
#         transitions = get_transitions(parsed_result)
#         execution = _find_benchmark_execution(parsed_result)

#         terminal_state_id: Any | None = None
#         terminal_completion: list[dict[str, Any]] = []
#         if execution is not None:
#             terminal_state_id, terminal_completion = _find_terminal_completion(
#                 parsed_result,
#                 execution.final_state_id,
#             )
#             execution.terminal_state_id = terminal_state_id
#             execution.terminal_completion = terminal_completion

#         produce_forwarding, consume_next_forwarding = _producer_forwarding_on_path(
#             parsed_result,
#             execution,
#             terminal_completion,
#         )
#         consumer_deliveries = _consumer_delivery_tokens_on_path(
#             parsed_result,
#             execution,
#             terminal_completion,
#         )

#         tests: list[SemanticTestResult] = []
#         tests.extend(
#             self._evaluate_actor_tests(
#                 parsed_result,
#                 execution,
#                 produce_forwarding,
#                 consume_next_forwarding,
#             )
#         )
#         tests.extend(
#             self._evaluate_interaction_tests(
#                 parsed_result,
#                 execution,
#                 consumer_deliveries,
#             )
#         )
#         tests.extend(
#             self._evaluate_system_tests(
#                 parsed_result,
#                 execution,
#                 terminal_state_id,
#                 terminal_completion,
#                 produce_forwarding,
#                 consume_next_forwarding,
#                 consumer_deliveries,
#             )
#         )

#         issues: list[str] = []
#         if not transitions:
#             issues.append("NO_TRANSITIONS")
#         if execution is None:
#             issues.append("BENCHMARK_PATH_NOT_FOUND")
#         if execution is not None and terminal_state_id is None:
#             issues.append("TERMINAL_QUIESCENCE_NOT_FOUND")
#         if any(test.status == TestStatus.NOT_OBSERVED for test in tests):
#             issues.append("INCOMPLETE_OBSERVABILITY")

#         return SemanticEvaluationResult(
#             benchmark=self.benchmark_id,
#             semantic_tests=tests,
#             detected_issues=issues,
#             metadata={
#                 "state_count": len(states),
#                 "transition_count": len(transitions),
#                 "initial_state_ids": _initial_state_ids(parsed_result),
#                 "benchmark_path_found": execution is not None,
#                 "matched_buffer_step_count": (
#                     len(execution.matched_steps) if execution is not None else 0
#                 ),
#                 "benchmark_path_transition_count": (
#                     len(execution.transitions) if execution is not None else 0
#                 ),
#                 "terminal_state_id": terminal_state_id,
#                 "terminal_completion_transition_count": len(terminal_completion),
#                 "resolved_item_tokens": (
#                     execution.item_tokens if execution is not None else {}
#                 ),
#                 "expected_buffer_operation_sequence": [
#                     "AddItem(item1)",
#                     "AddItem(item2)",
#                     "AddItem(item3 initial, rejected)",
#                     "GetItem -> item1",
#                     "AddItem(item3 retry)",
#                     "GetItem -> item2",
#                     "GetItem -> item3",
#                     "GetItem -> no Consumer output",
#                 ],
#                 "expected_logical_consumed_sequence": ["item1", "item2", "item3"],
#                 "representation_policy": {
#                     "source_payload_type": "String",
#                     "target_payload_representation": "representation-independent symbolic token",
#                     "hard_coded_item_token_mapping": False,
#                     "required_distinct_tokens": 3,
#                     "retry_must_reuse_item3_token": True,
#                 },
#                 "evaluation_assumptions": {
#                     "failure_free": True,
#                     "logging_out_of_scope": True,
#                     "buffer_capacity": 2,
#                     "fifo_is_observable": True,
#                     "rejection_is_observed_behaviorally": True,
#                     "empty_get_is_observed_as_no_consumer_message": True,
#                     "buffer_internal_representation_is_not_observable": True,
#                 },
#             },
#         )

#     def _evaluate_actor_tests(
#         self,
#         parsed_result: dict[str, Any],
#         execution: MatchedExecution | None,
#         produce_forwarding: list[dict[str, Any]],
#         consume_next_forwarding: list[dict[str, Any]],
#     ) -> list[SemanticTestResult]:
#         tests: list[SemanticTestResult] = []

#         xa1_pass = len(produce_forwarding) == 4 and all(
#             evidence.get("passed") is True for evidence in produce_forwarding
#         )
#         tests.append(
#             _test(
#                 "BPC-XA1",
#                 _status_from_observation(xa1_pass, observed=bool(produce_forwarding)),
#                 "BufferedProducer must preserve each payload when forwarding BufferedProduce(x) as AddItem(x).",
#                 {
#                     "expected_forward_count": 4,
#                     "observed_forward_count": len(produce_forwarding),
#                     "forwarding": produce_forwarding,
#                 },
#             )
#         )

#         xa2_pass = len(consume_next_forwarding) == 4 and all(
#             evidence.get("passed") is True for evidence in consume_next_forwarding
#         )
#         tests.append(
#             _test(
#                 "BPC-XA2",
#                 _status_from_observation(
#                     xa2_pass,
#                     observed=bool(consume_next_forwarding),
#                 ),
#                 "BufferedProducer must forward each BufferedConsumeNext as exactly one GetItem.",
#                 {
#                     "expected_forward_count": 4,
#                     "observed_forward_count": len(consume_next_forwarding),
#                     "forwarding": consume_next_forwarding,
#                 },
#             )
#         )

#         final_step = (
#             execution.matched_steps[7]
#             if execution is not None and len(execution.matched_steps) >= 8
#             else None
#         )
#         xa3_pass = (
#             final_step is not None
#             and final_step.get("logical_role") == "empty_get"
#             and final_step.get("consumer_message_count_added") == 0
#         )
#         tests.append(
#             _test(
#                 "BPC-XA3",
#                 _status_from_observation(xa3_pass, observed=final_step is not None),
#                 "GetItem on the final empty Buffer state must produce no Consumer message.",
#                 {"final_get_step": final_step},
#             )
#         )

#         first_get = (
#             execution.matched_steps[3]
#             if execution is not None and len(execution.matched_steps) >= 4
#             else None
#         )
#         item1_token = execution.item_tokens.get("item1") if execution else None
#         xa4_pass = (
#             first_get is not None
#             and item1_token is not None
#             and first_get.get("output_token") == item1_token
#         )
#         tests.append(
#             _test(
#                 "BPC-XA4",
#                 _status_from_observation(xa4_pass, observed=first_get is not None),
#                 "An accepted first item must later be consumed with its payload identity preserved.",
#                 {"item1_token": item1_token, "first_get_step": first_get},
#             )
#         )

#         initial_item3 = (
#             execution.matched_steps[2]
#             if execution is not None and len(execution.matched_steps) >= 3
#             else None
#         )
#         retry_item3 = (
#             execution.matched_steps[4]
#             if execution is not None and len(execution.matched_steps) >= 5
#             else None
#         )
#         second_get = (
#             execution.matched_steps[5]
#             if execution is not None and len(execution.matched_steps) >= 6
#             else None
#         )
#         item2_token = execution.item_tokens.get("item2") if execution else None
#         item3_token = execution.item_tokens.get("item3") if execution else None
#         xa5_pass = (
#             initial_item3 is not None
#             and retry_item3 is not None
#             and first_get is not None
#             and second_get is not None
#             and item1_token is not None
#             and item2_token is not None
#             and item3_token is not None
#             and first_get.get("output_token") == item1_token
#             and second_get.get("output_token") == item2_token
#             and retry_item3.get("input_token") == item3_token
#         )
#         tests.append(
#             _test(
#                 "BPC-XA5",
#                 _status_from_observation(xa5_pass, observed=execution is not None),
#                 "Capacity-two behavior must reject the initial third item: before retry, dequeues still yield item1 then item2 rather than item3.",
#                 {
#                     "resolved_tokens": execution.item_tokens if execution else {},
#                     "initial_item3_step": initial_item3,
#                     "first_get_step": first_get,
#                     "retry_item3_step": retry_item3,
#                     "second_get_step": second_get,
#                 },
#             )
#         )

#         xa6_pass = (
#             first_get is not None
#             and second_get is not None
#             and item1_token is not None
#             and item2_token is not None
#             and first_get.get("output_token") == item1_token
#             and second_get.get("output_token") == item2_token
#         )
#         tests.append(
#             _test(
#                 "BPC-XA6",
#                 _status_from_observation(
#                     xa6_pass,
#                     observed=first_get is not None and second_get is not None,
#                 ),
#                 "Buffer must preserve FIFO order: item1 must be consumed before item2.",
#                 {
#                     "expected_roles": ["item1", "item2"],
#                     "observed_tokens": [
#                         first_get.get("output_token") if first_get else None,
#                         second_get.get("output_token") if second_get else None,
#                     ],
#                     "resolved_tokens": execution.item_tokens if execution else {},
#                 },
#             )
#         )

#         third_get = (
#             execution.matched_steps[6]
#             if execution is not None and len(execution.matched_steps) >= 7
#             else None
#         )
#         xa7_pass = (
#             retry_item3 is not None
#             and third_get is not None
#             and item3_token is not None
#             and retry_item3.get("input_token") == item3_token
#             and third_get.get("output_token") == item3_token
#         )
#         tests.append(
#             _test(
#                 "BPC-XA7",
#                 _status_from_observation(
#                     xa7_pass,
#                     observed=retry_item3 is not None and third_get is not None,
#                 ),
#                 "The previously rejected item3 must be accepted after one dequeue frees capacity and later be consumed as the same item3 token.",
#                 {
#                     "item3_token": item3_token,
#                     "retry_item3_step": retry_item3,
#                     "third_get_step": third_get,
#                 },
#             )
#         )

#         return tests

#     def _evaluate_interaction_tests(
#         self,
#         parsed_result: dict[str, Any],
#         execution: MatchedExecution | None,
#         consumer_deliveries: list[str | None],
#     ) -> list[SemanticTestResult]:
#         tests: list[SemanticTestResult] = []
#         expected_tokens = (
#             [
#                 execution.item_tokens.get("item1"),
#                 execution.item_tokens.get("item2"),
#                 execution.item_tokens.get("item3"),
#             ]
#             if execution is not None
#             else []
#         )

#         xi1_pass = (
#             execution is not None
#             and len(execution.matched_steps) == 8
#             and bool(expected_tokens)
#             and None not in expected_tokens
#         )
#         tests.append(
#             _test(
#                 "BPC-XI1",
#                 _status_from_observation(
#                     bool(xi1_pass), observed=execution is not None
#                 ),
#                 "One connected state-graph execution must realize the complete eight-operation Buffer benchmark.",
#                 {
#                     "matched_buffer_steps": (
#                         execution.matched_steps if execution else []
#                     ),
#                     "resolved_tokens": execution.item_tokens if execution else {},
#                 },
#             )
#         )

#         xi2_pass = (
#             len(consumer_deliveries) == 3 and consumer_deliveries == expected_tokens
#         )
#         tests.append(
#             _test(
#                 "BPC-XI2",
#                 _status_from_observation(xi2_pass, observed=bool(consumer_deliveries)),
#                 "Every accepted benchmark item must be delivered to BufferedConsumer exactly once with no loss or duplication.",
#                 {
#                     "expected_delivery_tokens": expected_tokens,
#                     "observed_delivery_tokens": consumer_deliveries,
#                 },
#             )
#         )

#         item3_token = execution.item_tokens.get("item3") if execution else None
#         xi3_pass = (
#             item3_token is not None and consumer_deliveries.count(item3_token) == 1
#         )
#         tests.append(
#             _test(
#                 "BPC-XI3",
#                 _status_from_observation(xi3_pass, observed=bool(consumer_deliveries)),
#                 "The initially rejected item3 must appear at Consumer exactly once, after retry.",
#                 {
#                     "item3_token": item3_token,
#                     "consumer_delivery_tokens": consumer_deliveries,
#                     "item3_delivery_count": (
#                         consumer_deliveries.count(item3_token)
#                         if item3_token is not None
#                         else 0
#                     ),
#                 },
#             )
#         )

#         xi4_pass = (
#             consumer_deliveries == expected_tokens and len(consumer_deliveries) == 3
#         )
#         tests.append(
#             _test(
#                 "BPC-XI4",
#                 _status_from_observation(xi4_pass, observed=bool(consumer_deliveries)),
#                 "FIFO order must remain item1, item2, item3 across full-buffer rejection and retry.",
#                 {
#                     "expected_delivery_tokens": expected_tokens,
#                     "observed_delivery_tokens": consumer_deliveries,
#                 },
#             )
#         )
#         return tests

#     def _evaluate_system_tests(
#         self,
#         parsed_result: dict[str, Any],
#         execution: MatchedExecution | None,
#         terminal_state_id: Any | None,
#         terminal_completion: list[dict[str, Any]],
#         produce_forwarding: list[dict[str, Any]],
#         consume_next_forwarding: list[dict[str, Any]],
#         consumer_deliveries: list[str | None],
#     ) -> list[SemanticTestResult]:
#         tests: list[SemanticTestResult] = []

#         observed_rebecs = _rebec_names(parsed_result)
#         required = {
#             normalize_name(PRODUCER_NAME),
#             normalize_name(BUFFER_NAME),
#             normalize_name(CONSUMER_NAME),
#         }
#         topology_pass = required.issubset(observed_rebecs)
#         tests.append(
#             _test(
#                 "BPC-XSYS1",
#                 TestStatus.PASS if topology_pass else TestStatus.FAIL,
#                 "The target model must contain producer, buffer, and consumer rebecs; behavior-preserving auxiliary rebecs are allowed.",
#                 {
#                     "required_rebecs": sorted(required),
#                     "observed_rebecs": sorted(observed_rebecs),
#                     "missing_rebecs": sorted(required - observed_rebecs),
#                 },
#             )
#         )

#         xsys2_pass = (
#             execution is not None
#             and len(produce_forwarding) == 4
#             and len(consume_next_forwarding) == 4
#             and all(
#                 evidence.get("passed") is True
#                 for evidence in produce_forwarding + consume_next_forwarding
#             )
#         )
#         tests.append(
#             _test(
#                 "BPC-XSYS2",
#                 _status_from_observation(xsys2_pass, observed=execution is not None),
#                 "The connected benchmark path must execute four BufferedProduce and four BufferedConsumeNext commands through BufferedProducer with correct forwarding.",
#                 {
#                     "benchmark_path_found": execution is not None,
#                     "expected_buffered_produce_count": 4,
#                     "observed_buffered_produce_count": len(produce_forwarding),
#                     "expected_buffered_consume_next_count": 4,
#                     "observed_buffered_consume_next_count": len(
#                         consume_next_forwarding
#                     ),
#                 },
#             )
#         )

#         final_step = (
#             execution.matched_steps[7]
#             if execution is not None and len(execution.matched_steps) >= 8
#             else None
#         )
#         terminal_state = (
#             get_state_by_id(parsed_result, terminal_state_id)
#             if terminal_state_id is not None
#             else None
#         )
#         xsys3_pass = (
#             final_step is not None
#             and final_step.get("consumer_message_count_added") == 0
#             and terminal_state_id is not None
#             and _all_rebec_queues_empty(terminal_state)
#             and len(consumer_deliveries) == 3
#         )
#         tests.append(
#             _test(
#                 "BPC-XSYS3",
#                 _status_from_observation(xsys3_pass, observed=execution is not None),
#                 "After the final empty GetItem, no additional observable item may be produced and the system must complete with all rebec queues empty.",
#                 {
#                     "final_get_step": final_step,
#                     "terminal_state_id": terminal_state_id,
#                     "terminal_queues_empty": (
#                         _all_rebec_queues_empty(terminal_state)
#                         if terminal_state is not None
#                         else False
#                     ),
#                     "consumer_delivery_count": len(consumer_deliveries),
#                 },
#             )
#         )

#         expected_tokens = (
#             [
#                 execution.item_tokens.get("item1"),
#                 execution.item_tokens.get("item2"),
#                 execution.item_tokens.get("item3"),
#             ]
#             if execution is not None
#             else []
#         )
#         xsys4_pass = (
#             execution is not None
#             and len(execution.matched_steps) == 8
#             and consumer_deliveries == expected_tokens
#             and terminal_state_id is not None
#             and _all_rebec_queues_empty(terminal_state)
#         )
#         tests.append(
#             _test(
#                 "BPC-XSYS4",
#                 _status_from_observation(xsys4_pass, observed=execution is not None),
#                 "The complete observable system contract must preserve bounded rejection, retry, FIFO delivery of item1/item2/item3, final empty behavior, and terminal quiescence.",
#                 {
#                     "resolved_item_tokens": execution.item_tokens if execution else {},
#                     "matched_buffer_steps": (
#                         execution.matched_steps if execution else []
#                     ),
#                     "consumer_delivery_tokens": consumer_deliveries,
#                     "terminal_state_id": terminal_state_id,
#                     "terminal_completion_transition_count": len(terminal_completion),
#                 },
#             )
#         )

#         return tests


# def evaluate_buffer_producer_consumer(
#     parsed_result: dict[str, Any],
# ) -> dict[str, Any]:
#     evaluator = BufferProducerConsumerEvaluator(
#         parsed_result=parsed_result,
#         example_id=BENCHMARK_ID,
#     )
#     return evaluator.evaluate(parsed_result).to_dict()


# def load_json(path: str | Path) -> dict[str, Any]:
#     file_path = Path(path)
#     if not file_path.is_file():
#         raise FileNotFoundError(f"JSON file not found: {file_path}")
#     with file_path.open("r", encoding="utf-8") as file:
#         value = json.load(file)
#     if not isinstance(value, dict):
#         raise ValueError("Parsed RMC JSON must contain a JSON object.")
#     return value


# def main() -> int:
#     import argparse

#     parser = argparse.ArgumentParser(
#         description=(
#             "Evaluate the buffered Producer-Consumer benchmark from parsed RMC JSON."
#         )
#     )
#     parser.add_argument("parsed_result", help="Path to the parsed RMC JSON file.")
#     parser.add_argument("--output", "-o", help="Optional output JSON path.")
#     arguments = parser.parse_args()

#     try:
#         parsed_result = load_json(arguments.parsed_result)
#         result = evaluate_buffer_producer_consumer(parsed_result)
#         serialized = json.dumps(result, indent=2, ensure_ascii=False)
#         if arguments.output:
#             output_path = Path(arguments.output)
#             output_path.parent.mkdir(parents=True, exist_ok=True)
#             output_path.write_text(serialized + "\n", encoding="utf-8")
#         else:
#             print(serialized)
#         return 0
#     except Exception as exc:
#         print(
#             f"BufferProducerConsumer evaluator infrastructure error: {exc}",
#             file=sys.stderr,
#         )
#         return 2


# if __name__ == "__main__":
#     raise SystemExit(main())
