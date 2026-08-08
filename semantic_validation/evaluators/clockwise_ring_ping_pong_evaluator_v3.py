from __future__ import annotations

import json
import sys

from collections import Counter as MultisetCounter
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

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

BENCHMARK_ID = "clockwise_ring_ping_pong"

MSG_START = normalize_name("Start")
MSG_SET_NEIGHBOR = normalize_name("SetNeighbor")
MSG_PING = normalize_name("Ping")
MSG_PONG = normalize_name("Pong")
PROTOCOL_MESSAGES = {MSG_PING, MSG_PONG}


@dataclass(frozen=True)
class QueueMessage:
    recipient: str
    message: str
    sender: str

    def to_dict(self) -> dict[str, str]:
        return {
            "recipient": self.recipient,
            "message": self.message,
            "sender": self.sender,
        }


@dataclass
class TransitionEvidence:
    transition: dict[str, Any]
    source: Any
    destination: Any
    owner: str
    handler: str
    removed_protocol: list[QueueMessage]
    added_protocol: list[QueueMessage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_state_id": self.source,
            "destination_state_id": self.destination,
            "owner": self.owner,
            "message_server": self.handler,
            "removed_protocol_messages": [
                message.to_dict() for message in self.removed_protocol
            ],
            "added_protocol_messages": [
                message.to_dict() for message in self.added_protocol
            ],
        }


@dataclass
class MatchedRing:
    cycle_entry_state_id: Any
    steps: list[TransitionEvidence]
    role_to_rebec: dict[str, str]
    bootstrap: TransitionEvidence | None = None
    bootstrap_cleanup: list[TransitionEvidence] | None = None
    setup_path: list[TransitionEvidence] | None = None
    warmup_entry_state_id: Any | None = None
    warmup_steps: list[TransitionEvidence] | None = None
    warmup_round_count: int = 0
    cycle_return_path: list[TransitionEvidence] | None = None

    @property
    def cycle_closes(self) -> bool:
        if len(self.steps) != 5:
            return False
        if self.steps[-1].destination == self.cycle_entry_state_id:
            return True
        return bool(
            self.cycle_return_path
            and self.cycle_return_path[-1].destination == self.cycle_entry_state_id
        )

    @property
    def bootstrap_entry_state_id(self) -> Any:
        if self.warmup_entry_state_id is not None:
            return self.warmup_entry_state_id
        return self.cycle_entry_state_id


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


def _rebec_names(state: dict[str, Any] | None) -> list[str]:
    if not state:
        return []
    rebecs = state.get("rebecs", {})
    if isinstance(rebecs, dict):
        return [normalize_name(name) for name in rebecs]
    names: list[str] = []
    if isinstance(rebecs, list):
        for rebec in rebecs:
            if not isinstance(rebec, dict):
                continue
            name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
            if name:
                names.append(normalize_name(str(name)))
    return names


def _all_rebec_names(parsed_result: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for state in get_states(parsed_result):
        names.update(_rebec_names(state))
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
    raw = _message_raw(message)
    if "(" in raw:
        raw = raw.split("(", 1)[0]
    return normalize_name(raw)


def _message_sender(message: dict[str, Any]) -> str:
    return normalize_name(str(message.get("sender") or ""))


def _queue_signatures(
    state: dict[str, Any] | None,
    rebec: str,
) -> list[tuple[str, str]]:
    return [
        (_message_name(message), _message_sender(message))
        for message in get_queue(state, rebec)
    ]


def _positive_multiset_delta(
    left: list[tuple[str, str]],
    right: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    delta = MultisetCounter(left) - MultisetCounter(right)
    result: list[tuple[str, str]] = []
    for signature, count in delta.items():
        result.extend([signature] * count)
    return result


def _protocol_queue_delta(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
) -> tuple[list[QueueMessage], list[QueueMessage]]:
    removed: list[QueueMessage] = []
    added: list[QueueMessage] = []

    rebec_names = sorted(
        set(_rebec_names(source_state)) | set(_rebec_names(destination_state))
    )

    for rebec in rebec_names:
        source_signatures = _queue_signatures(source_state, rebec)
        destination_signatures = _queue_signatures(destination_state, rebec)

        for message_name, sender in _positive_multiset_delta(
            source_signatures,
            destination_signatures,
        ):
            if message_name in PROTOCOL_MESSAGES:
                removed.append(
                    QueueMessage(
                        recipient=rebec,
                        message=message_name,
                        sender=sender,
                    )
                )

        for message_name, sender in _positive_multiset_delta(
            destination_signatures,
            source_signatures,
        ):
            if message_name in PROTOCOL_MESSAGES:
                added.append(
                    QueueMessage(
                        recipient=rebec,
                        message=message_name,
                        sender=sender,
                    )
                )

    return removed, added


def _transition_evidence(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
) -> TransitionEvidence:
    source = _transition_source(transition)
    destination = _transition_destination(transition)
    source_state = get_state_by_id(parsed_result, source)
    destination_state = get_state_by_id(parsed_result, destination)
    removed, added = _protocol_queue_delta(source_state, destination_state)

    return TransitionEvidence(
        transition=transition,
        source=source,
        destination=destination,
        owner=transition_owner(transition),
        handler=transition_message(transition),
        removed_protocol=removed,
        added_protocol=added,
    )


def _build_events(
    parsed_result: dict[str, Any],
) -> tuple[list[TransitionEvidence], dict[Any, list[TransitionEvidence]]]:
    events = [
        _transition_evidence(parsed_result, transition)
        for transition in get_transitions(parsed_result)
    ]
    outgoing: dict[Any, list[TransitionEvidence]] = defaultdict(list)
    for event in events:
        outgoing[event.source].append(event)
    return events, outgoing


def _protocol_message_count(
    state: dict[str, Any] | None,
) -> int:
    count = 0
    for rebec in _rebec_names(state):
        for message in get_queue(state, rebec):
            if _message_name(message) in PROTOCOL_MESSAGES:
                count += 1
    return count


def _exact_protocol_forward(
    event: TransitionEvidence,
    *,
    input_message: str,
    output_message: str,
    expected_owner: str | None = None,
    expected_input_sender: str | None = None,
    expected_recipient: str | None = None,
) -> bool:
    if event.handler != normalize_name(input_message):
        return False
    if expected_owner is not None and event.owner != normalize_name(expected_owner):
        return False
    if len(event.removed_protocol) != 1 or len(event.added_protocol) != 1:
        return False

    removed = event.removed_protocol[0]
    added = event.added_protocol[0]

    if removed.recipient != event.owner:
        return False
    if removed.message != normalize_name(input_message):
        return False
    if expected_input_sender is not None:
        if removed.sender != normalize_name(expected_input_sender):
            return False

    if added.message != normalize_name(output_message):
        return False
    if expected_recipient is not None:
        if added.recipient != normalize_name(expected_recipient):
            return False

    return True


def _start_bootstrap_matches(
    event: TransitionEvidence,
    *,
    logical_pong2: str,
) -> bool:
    return (
        event.handler == MSG_START
        and len(event.added_protocol) == 1
        and event.added_protocol[0].message == MSG_PING
        and event.added_protocol[0].recipient == normalize_name(logical_pong2)
    )


def _event_has_protocol_activity(event: TransitionEvidence) -> bool:
    return bool(
        event.removed_protocol
        or event.added_protocol
        or event.handler in PROTOCOL_MESSAGES
    )


def _find_next_matching_event(
    outgoing: dict[Any, list[TransitionEvidence]],
    start_state_id: Any,
    predicate: Callable[[TransitionEvidence], bool],
    *,
    max_non_protocol_steps: int = 8,
) -> tuple[TransitionEvidence | None, list[TransitionEvidence]]:
    """
    Find the next expected protocol transition, allowing a small number of
    protocol-neutral helper/setup transitions between observable steps.

    Any competing protocol transition blocks that branch, because accepting it
    would silently skip observable behavior.
    """
    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque([(start_state_id, [])])
    best_depth: dict[Any, int] = {}

    while queue:
        state_id, neutral_path = queue.popleft()
        depth = len(neutral_path)
        previous_depth = best_depth.get(state_id)
        if previous_depth is not None and previous_depth <= depth:
            continue
        best_depth[state_id] = depth

        for event in outgoing.get(state_id, []):
            if predicate(event):
                return event, neutral_path

            if _event_has_protocol_activity(event):
                continue

            if depth < max_non_protocol_steps:
                queue.append((event.destination, neutral_path + [event]))

    return None, []


def _match_round_with_roles(
    outgoing: dict[Any, list[TransitionEvidence]],
    start_state_id: Any,
    role_to_rebec: dict[str, str],
) -> list[TransitionEvidence] | None:
    """Match one complete clockwise protocol round using fixed logical roles."""
    logical_ping1 = role_to_rebec["ping1"]
    logical_pong2 = role_to_rebec["pong2"]
    logical_ping3 = role_to_rebec["ping3"]
    logical_pong4 = role_to_rebec["pong4"]
    logical_ping5 = role_to_rebec["ping5"]

    step1, _ = _find_next_matching_event(
        outgoing,
        start_state_id,
        lambda event: _exact_protocol_forward(
            event,
            input_message="Ping",
            output_message="Pong",
            expected_owner=logical_pong2,
            expected_recipient=logical_ping3,
        ),
    )
    if step1 is None:
        return None

    step2, _ = _find_next_matching_event(
        outgoing,
        step1.destination,
        lambda event: _exact_protocol_forward(
            event,
            input_message="Pong",
            output_message="Ping",
            expected_owner=logical_ping3,
            expected_recipient=logical_pong4,
        ),
    )
    if step2 is None:
        return None

    step3, _ = _find_next_matching_event(
        outgoing,
        step2.destination,
        lambda event: _exact_protocol_forward(
            event,
            input_message="Ping",
            output_message="Pong",
            expected_owner=logical_pong4,
            expected_recipient=logical_ping5,
        ),
    )
    if step3 is None:
        return None

    step4, _ = _find_next_matching_event(
        outgoing,
        step3.destination,
        lambda event: _exact_protocol_forward(
            event,
            input_message="Pong",
            output_message="Ping",
            expected_owner=logical_ping5,
            expected_recipient=logical_ping1,
        ),
    )
    if step4 is None:
        return None

    step5, _ = _find_next_matching_event(
        outgoing,
        step4.destination,
        lambda event: _exact_protocol_forward(
            event,
            input_message="Ping",
            output_message="Ping",
            expected_owner=logical_ping1,
            expected_recipient=logical_pong2,
        ),
    )
    if step5 is None:
        return None

    return [step1, step2, step3, step4, step5]


def _round_return_path(
    outgoing: dict[Any, list[TransitionEvidence]],
    entry_state_id: Any,
    steps: list[TransitionEvidence],
) -> list[TransitionEvidence] | None:
    """
    Return the protocol-neutral path that closes a matched round.

    An empty list means the fifth protocol transition returns directly to the
    round entry state. None means the round does not close.
    """
    if len(steps) != 5:
        return None
    return _neutral_path_to_state(
        outgoing,
        steps[-1].destination,
        entry_state_id,
    )


def _find_recurrent_round_after_warmup(
    outgoing: dict[Any, list[TransitionEvidence]],
    start_state_id: Any,
    role_to_rebec: dict[str, str],
    *,
    max_rounds: int = 8,
) -> (
    tuple[
        Any,
        list[TransitionEvidence],
        list[TransitionEvidence],
        list[TransitionEvidence],
        int,
    ]
    | None
):
    """
    Starting after an initial behaviorally correct round, find a recurrent
    round with the same logical roles.

    Additional non-closing rounds are treated as finite warm-up. This matters
    when setup messages are still being consumed during the first observable
    protocol round. The recurrent round is the first matched round whose fifth
    protocol step returns, directly or through protocol-neutral transitions,
    to that round's own entry state.
    """
    current_state_id = start_state_id
    extra_warmup_steps: list[TransitionEvidence] = []
    seen_entries: set[Any] = set()

    for round_index in range(max_rounds):
        steps = _match_round_with_roles(
            outgoing,
            current_state_id,
            role_to_rebec,
        )
        if steps is None:
            return None

        entry_state_id = steps[0].source
        if entry_state_id in seen_entries:
            return None
        seen_entries.add(entry_state_id)

        return_path = _round_return_path(
            outgoing,
            entry_state_id,
            steps,
        )
        if return_path is not None:
            return (
                entry_state_id,
                steps,
                return_path,
                extra_warmup_steps,
                round_index,
            )

        extra_warmup_steps.extend(steps)
        current_state_id = steps[-1].destination

    return None


def _find_ring_cycle(
    parsed_result: dict[str, Any],
    events: list[TransitionEvidence],
    outgoing: dict[Any, list[TransitionEvidence]],
) -> MatchedRing | None:
    """
    Discover the five logical roles behaviorally and distinguish finite warm-up
    behavior from the steady recurrent clockwise cycle.

    The protocol round is:

      logical pong2: Ping -> Pong  (to ping3)
      logical ping3: Pong -> Ping  (to pong4)
      logical pong4: Ping -> Pong  (to ping5)
      logical ping5: Pong -> Ping  (to ping1)
      logical ping1: Ping -> Ping  (to pong2)

    The first valid round after Start is not assumed to be recurrent. Setup
    messages may still be consumed during that round. If it does not close, the
    evaluator follows subsequent rounds with the same discovered role mapping
    and selects the first round that closes on its own entry state. The initial
    valid round(s) are retained as warm-up evidence for bootstrap validation.

    sender().path.name is used only by source logging, which is outside the
    semantic contract, so sender identity is deliberately not hard-coded.
    """
    fallback: MatchedRing | None = None

    for step1 in events:
        if not _exact_protocol_forward(
            step1,
            input_message="Ping",
            output_message="Pong",
        ):
            continue

        logical_pong2 = step1.owner
        logical_ping3 = step1.added_protocol[0].recipient

        if logical_pong2 == logical_ping3:
            continue

        step2, _ = _find_next_matching_event(
            outgoing,
            step1.destination,
            lambda event: _exact_protocol_forward(
                event,
                input_message="Pong",
                output_message="Ping",
                expected_owner=logical_ping3,
            ),
        )
        if step2 is None:
            continue

        logical_pong4 = step2.added_protocol[0].recipient
        if logical_pong4 in {logical_pong2, logical_ping3}:
            continue

        step3, _ = _find_next_matching_event(
            outgoing,
            step2.destination,
            lambda event: _exact_protocol_forward(
                event,
                input_message="Ping",
                output_message="Pong",
                expected_owner=logical_pong4,
            ),
        )
        if step3 is None:
            continue

        logical_ping5 = step3.added_protocol[0].recipient
        if logical_ping5 in {
            logical_pong2,
            logical_ping3,
            logical_pong4,
        }:
            continue

        step4, _ = _find_next_matching_event(
            outgoing,
            step3.destination,
            lambda event: _exact_protocol_forward(
                event,
                input_message="Pong",
                output_message="Ping",
                expected_owner=logical_ping5,
            ),
        )
        if step4 is None:
            continue

        logical_ping1 = step4.added_protocol[0].recipient
        if logical_ping1 in {
            logical_pong2,
            logical_ping3,
            logical_pong4,
            logical_ping5,
        }:
            continue

        step5, _ = _find_next_matching_event(
            outgoing,
            step4.destination,
            lambda event: _exact_protocol_forward(
                event,
                input_message="Ping",
                output_message="Ping",
                expected_owner=logical_ping1,
                expected_recipient=logical_pong2,
            ),
        )
        if step5 is None:
            continue

        role_to_rebec = {
            "ping1": logical_ping1,
            "pong2": logical_pong2,
            "ping3": logical_ping3,
            "pong4": logical_pong4,
            "ping5": logical_ping5,
        }

        if len(set(role_to_rebec.values())) != 5:
            continue

        first_round_steps = [step1, step2, step3, step4, step5]
        first_return_path = _round_return_path(
            outgoing,
            step1.source,
            first_round_steps,
        )

        if first_return_path is not None:
            ring = MatchedRing(
                cycle_entry_state_id=step1.source,
                steps=first_round_steps,
                role_to_rebec=role_to_rebec,
                cycle_return_path=first_return_path,
            )
        else:
            recurrent = _find_recurrent_round_after_warmup(
                outgoing,
                step5.destination,
                role_to_rebec,
            )

            if recurrent is not None:
                (
                    recurrent_entry,
                    recurrent_steps,
                    recurrent_return_path,
                    extra_warmup_steps,
                    extra_warmup_round_count,
                ) = recurrent
                ring = MatchedRing(
                    cycle_entry_state_id=recurrent_entry,
                    steps=recurrent_steps,
                    role_to_rebec=role_to_rebec,
                    warmup_entry_state_id=step1.source,
                    warmup_steps=first_round_steps + extra_warmup_steps,
                    warmup_round_count=1 + extra_warmup_round_count,
                    cycle_return_path=recurrent_return_path,
                )
            else:
                ring = MatchedRing(
                    cycle_entry_state_id=step1.source,
                    steps=first_round_steps,
                    role_to_rebec=role_to_rebec,
                )

        ring.bootstrap, ring.bootstrap_cleanup = _find_bootstrap(
            outgoing,
            events,
            ring,
        )
        ring.setup_path = _find_setup_path(
            parsed_result,
            outgoing,
            ring.bootstrap.source if ring.bootstrap is not None else None,
        )

        if (
            ring.cycle_closes
            and ring.bootstrap is not None
            and ring.setup_path is not None
        ):
            return ring

        if fallback is None:
            fallback = ring

    return fallback


def _find_bootstrap(
    outgoing: dict[Any, list[TransitionEvidence]],
    events: list[TransitionEvidence],
    ring: MatchedRing,
) -> tuple[TransitionEvidence | None, list[TransitionEvidence]]:
    """Find Start bootstrap to the first operational round, not necessarily the steady cycle."""
    logical_pong2 = ring.role_to_rebec["pong2"]
    target_state_id = ring.bootstrap_entry_state_id

    for event in events:
        if not _start_bootstrap_matches(
            event,
            logical_pong2=logical_pong2,
        ):
            continue

        if event.destination == target_state_id:
            return event, []

        path = _neutral_path_to_state(
            outgoing,
            event.destination,
            target_state_id,
        )
        if path is not None:
            return event, path

    return None, []


def _neutral_path_to_state(
    outgoing: dict[Any, list[TransitionEvidence]],
    start_state_id: Any,
    target_state_id: Any,
    *,
    max_steps: int = 12,
) -> list[TransitionEvidence] | None:
    if start_state_id == target_state_id:
        return []

    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque([(start_state_id, [])])
    visited: set[Any] = set()

    while queue:
        state_id, path = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)

        if len(path) >= max_steps:
            continue

        for event in outgoing.get(state_id, []):
            if _event_has_protocol_activity(event):
                continue
            next_path = path + [event]
            if event.destination == target_state_id:
                return next_path
            queue.append((event.destination, next_path))

    return None


def _find_setup_path(
    parsed_result: dict[str, Any],
    outgoing: dict[Any, list[TransitionEvidence]],
    target_state_id: Any | None,
) -> list[TransitionEvidence] | None:
    if target_state_id is None:
        return None

    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque(
        (state_id, []) for state_id in _initial_state_ids(parsed_result)
    )
    visited: set[Any] = set()

    while queue:
        state_id, path = queue.popleft()
        if state_id == target_state_id:
            return path
        if state_id in visited:
            continue
        visited.add(state_id)

        for event in outgoing.get(state_id, []):
            if event.handler in PROTOCOL_MESSAGES or event.handler == MSG_START:
                continue
            queue.append((event.destination, path + [event]))

    return None


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


def _status_from_observation(
    condition: bool,
    *,
    observed: bool,
) -> TestStatus:
    if condition:
        return TestStatus.PASS
    return TestStatus.FAIL if observed else TestStatus.NOT_OBSERVED


def _protocol_step_summary(
    ring: MatchedRing | None,
) -> list[dict[str, Any]]:
    if ring is None:
        return []
    return [step.to_dict() for step in ring.steps]


class ClockwiseRingPingPongEvaluator(BaseSemanticEvaluator):
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
        events, outgoing = _build_events(parsed_result)
        ring = _find_ring_cycle(parsed_result, events, outgoing)

        tests: list[SemanticTestResult] = []
        tests.extend(
            self._evaluate_actor_tests(
                parsed_result,
                events,
                ring,
            )
        )
        tests.extend(
            self._evaluate_interaction_tests(
                parsed_result,
                events,
                ring,
            )
        )
        tests.extend(
            self._evaluate_system_tests(
                parsed_result,
                events,
                ring,
            )
        )

        issues: list[str] = []
        if not transitions:
            issues.append("NO_TRANSITIONS")
        if ring is None:
            issues.append("RING_CYCLE_NOT_FOUND")
        elif ring.bootstrap is None:
            issues.append("BOOTSTRAP_NOT_FOUND")
        if ring is not None and ring.bootstrap is not None and ring.setup_path is None:
            issues.append("SETUP_PATH_NOT_FOUND")
        if any(test.status == TestStatus.NOT_OBSERVED for test in tests):
            issues.append("INCOMPLETE_OBSERVABILITY")

        protocol_transition_count = sum(
            event.handler in PROTOCOL_MESSAGES for event in events
        )
        set_neighbor_transition_count = sum(
            event.handler == MSG_SET_NEIGHBOR for event in events
        )

        role_mapping = ring.role_to_rebec if ring is not None else {}
        cycle_state_ids = (
            [ring.cycle_entry_state_id] + [step.destination for step in ring.steps]
            if ring is not None
            else []
        )
        cycle_protocol_counts = (
            [
                _protocol_message_count(get_state_by_id(parsed_result, state_id))
                for state_id in cycle_state_ids
            ]
            if ring is not None
            else []
        )

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": _initial_state_ids(parsed_result),
                "observed_rebecs": sorted(_all_rebec_names(parsed_result)),
                "protocol_transition_count": protocol_transition_count,
                "set_neighbor_transition_count": set_neighbor_transition_count,
                "ring_cycle_found": ring is not None,
                "cycle_closes": ring.cycle_closes if ring is not None else False,
                "cycle_entry_state_id": (
                    ring.cycle_entry_state_id if ring is not None else None
                ),
                "cycle_state_ids": cycle_state_ids,
                "cycle_protocol_message_counts": cycle_protocol_counts,
                "role_mapping": role_mapping,
                "warmup_entry_state_id": (
                    ring.warmup_entry_state_id if ring is not None else None
                ),
                "warmup_round_count": (
                    ring.warmup_round_count if ring is not None else 0
                ),
                "warmup_steps": (
                    [step.to_dict() for step in (ring.warmup_steps or [])]
                    if ring is not None
                    else []
                ),
                "cycle_return_path": (
                    [step.to_dict() for step in (ring.cycle_return_path or [])]
                    if ring is not None
                    else []
                ),
                "bootstrap_found": (ring is not None and ring.bootstrap is not None),
                "bootstrap": (
                    ring.bootstrap.to_dict()
                    if ring is not None and ring.bootstrap is not None
                    else None
                ),
                "setup_path_transition_count": (
                    len(ring.setup_path)
                    if ring is not None and ring.setup_path is not None
                    else None
                ),
                "setup_set_neighbor_count": (
                    sum(event.handler == MSG_SET_NEIGHBOR for event in ring.setup_path)
                    if ring is not None and ring.setup_path is not None
                    else None
                ),
                "bootstrap_cleanup_transition_count": (
                    len(ring.bootstrap_cleanup)
                    if ring is not None and ring.bootstrap_cleanup is not None
                    else None
                ),
                "bootstrap_cleanup_set_neighbor_count": (
                    sum(
                        event.handler == MSG_SET_NEIGHBOR
                        for event in ring.bootstrap_cleanup
                    )
                    if ring is not None and ring.bootstrap_cleanup is not None
                    else None
                ),
                "expected_edge_sequence_after_start": [
                    "Ping",
                    "Pong",
                    "Ping",
                    "Pong",
                    "Ping",
                ],
                "semantic_scope": (
                    "scenario-bounded observable equivalence over the "
                    "initialized recurrent clockwise ring"
                ),
                "terminal_quiescence_required": False,
                "target_name_hard_coding": False,
            },
        )

    def _evaluate_actor_tests(
        self,
        parsed_result: dict[str, Any],
        events: list[TransitionEvidence],
        ring: MatchedRing | None,
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        start_events = [event for event in events if event.handler == MSG_START]
        start_ping_candidates = [
            event
            for event in start_events
            if (
                len(event.added_protocol) == 1
                and event.added_protocol[0].message == MSG_PING
            )
        ]

        xa1_pass = bool(start_ping_candidates)
        tests.append(
            _test(
                "CRPP-XA1",
                _status_from_observation(
                    xa1_pass,
                    observed=bool(start_events),
                ),
                "A reachable Start handler must inject exactly one Ping from its logical Ping-role owner toward the ring.",
                {
                    "observed_start_transition_count": len(start_events),
                    "start_ping_candidates": [
                        event.to_dict() for event in start_ping_candidates
                    ],
                    "matched_ring_bootstrap": (
                        ring.bootstrap.to_dict()
                        if ring is not None and ring.bootstrap is not None
                        else None
                    ),
                },
            )
        )

        ping_to_pong = [
            event
            for event in events
            if _exact_protocol_forward(
                event,
                input_message="Ping",
                output_message="Pong",
            )
        ]
        ping_to_pong_owners = sorted({event.owner for event in ping_to_pong})
        xa2_pass = len(ping_to_pong_owners) >= 2
        tests.append(
            _test(
                "CRPP-XA2",
                _status_from_observation(
                    xa2_pass,
                    observed=any(event.handler == MSG_PING for event in events),
                ),
                "Two distinct reachable Pong-role handlers must each consume one Ping and emit exactly one Pong.",
                {
                    "matching_transition_count": len(ping_to_pong),
                    "distinct_matching_owners": ping_to_pong_owners,
                    "matching_transitions": [event.to_dict() for event in ping_to_pong],
                },
            )
        )

        pong_to_ping = [
            event
            for event in events
            if _exact_protocol_forward(
                event,
                input_message="Pong",
                output_message="Ping",
            )
        ]
        pong_to_ping_owners = sorted({event.owner for event in pong_to_ping})
        xa3_pass = len(pong_to_ping_owners) >= 2
        tests.append(
            _test(
                "CRPP-XA3",
                _status_from_observation(
                    xa3_pass,
                    observed=any(event.handler == MSG_PONG for event in events),
                ),
                "Two distinct reachable Ping-role Pong handlers must each consume one Pong and emit exactly one Ping.",
                {
                    "matching_transition_count": len(pong_to_ping),
                    "distinct_matching_owners": pong_to_ping_owners,
                    "matching_transitions": [event.to_dict() for event in pong_to_ping],
                },
            )
        )

        ping_to_ping = [
            event
            for event in events
            if _exact_protocol_forward(
                event,
                input_message="Ping",
                output_message="Ping",
            )
        ]
        xa4_pass = bool(ping_to_ping)
        if ring is not None:
            return_step = ring.steps[4]
            xa4_pass = _exact_protocol_forward(
                return_step,
                input_message="Ping",
                output_message="Ping",
                expected_owner=ring.role_to_rebec["ping1"],
                expected_recipient=ring.role_to_rebec["pong2"],
            )
        else:
            return_step = None

        tests.append(
            _test(
                "CRPP-XA4",
                _status_from_observation(
                    xa4_pass,
                    observed=any(event.handler == MSG_PING for event in events),
                ),
                "A reachable Ping-role handler must preserve Ping when the clockwise token returns; in the matched ring this is logical ping1 forwarding to logical pong2.",
                {
                    "generic_ping_to_ping_candidates": [
                        event.to_dict() for event in ping_to_ping
                    ],
                    "matched_return_step": (
                        return_step.to_dict() if return_step is not None else None
                    ),
                },
            )
        )

        protocol_handler_events = [
            event for event in events if event.handler in PROTOCOL_MESSAGES
        ]
        xa5_pass = bool(protocol_handler_events) and all(
            len(event.removed_protocol) == 1 and len(event.added_protocol) == 1
            for event in protocol_handler_events
        )
        tests.append(
            _test(
                "CRPP-XA5",
                _status_from_observation(
                    xa5_pass,
                    observed=bool(protocol_handler_events),
                ),
                "Every reachable Ping/Pong protocol handler must conserve the circulating token: exactly one protocol message consumed and one produced.",
                {
                    "protocol_handler_transition_count": len(protocol_handler_events),
                    "one_in_one_out": [
                        {
                            "source_state_id": event.source,
                            "destination_state_id": event.destination,
                            "owner": event.owner,
                            "message_server": event.handler,
                            "removed_count": len(event.removed_protocol),
                            "added_count": len(event.added_protocol),
                        }
                        for event in protocol_handler_events
                    ],
                },
            )
        )

        return tests

    def _evaluate_interaction_tests(
        self,
        parsed_result: dict[str, Any],
        events: list[TransitionEvidence],
        ring: MatchedRing | None,
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        protocol_observed = any(event.handler in PROTOCOL_MESSAGES for event in events)

        xi1_pass = ring is not None and len(ring.steps) == 5
        tests.append(
            _test(
                "CRPP-XI1",
                _status_from_observation(
                    xi1_pass,
                    observed=protocol_observed,
                ),
                "One connected reachable execution must realize the complete five-hop clockwise ring cycle.",
                {
                    "ring_cycle_found": ring is not None,
                    "role_mapping": (ring.role_to_rebec if ring is not None else {}),
                    "matched_steps": _protocol_step_summary(ring),
                },
            )
        )

        observed_edge_sequence: list[str] = []
        if ring is not None:
            observed_edge_sequence = [
                "PING",
                ring.steps[0].added_protocol[0].message,
                ring.steps[1].added_protocol[0].message,
                ring.steps[2].added_protocol[0].message,
                ring.steps[3].added_protocol[0].message,
            ]
        expected_edge_sequence = [
            MSG_PING,
            MSG_PONG,
            MSG_PING,
            MSG_PONG,
            MSG_PING,
        ]
        xi2_pass = observed_edge_sequence == expected_edge_sequence
        tests.append(
            _test(
                "CRPP-XI2",
                _status_from_observation(
                    xi2_pass,
                    observed=protocol_observed,
                ),
                "The observable messages on one clockwise round must be Ping, Pong, Ping, Pong, Ping.",
                {
                    "expected_edge_sequence": expected_edge_sequence,
                    "observed_edge_sequence": observed_edge_sequence,
                },
            )
        )

        role_mapping = ring.role_to_rebec if ring is not None else {}
        routing_edges = (
            [
                [role_mapping["ping1"], role_mapping["pong2"]],
                [role_mapping["pong2"], role_mapping["ping3"]],
                [role_mapping["ping3"], role_mapping["pong4"]],
                [role_mapping["pong4"], role_mapping["ping5"]],
                [role_mapping["ping5"], role_mapping["ping1"]],
            ]
            if ring is not None
            else []
        )
        xi3_pass = (
            ring is not None
            and len(set(role_mapping.values())) == 5
            and len(routing_edges) == 5
        )
        tests.append(
            _test(
                "CRPP-XI3",
                _status_from_observation(
                    xi3_pass,
                    observed=ring is not None or protocol_observed,
                ),
                "The cycle must contain five distinct logical participants and close clockwise back to the first participant.",
                {
                    "role_mapping": role_mapping,
                    "routing_edges": routing_edges,
                    "distinct_participant_count": len(set(role_mapping.values())),
                },
            )
        )

        xi4_pass = ring is not None and ring.cycle_closes
        tests.append(
            _test(
                "CRPP-XI4",
                _status_from_observation(
                    xi4_pass,
                    observed=ring is not None or protocol_observed,
                ),
                "After the returned Ping is handled by logical ping1, the state graph must return to the recurrent cycle entry state.",
                {
                    "cycle_entry_state_id": (
                        ring.cycle_entry_state_id if ring is not None else None
                    ),
                    "post_return_state_id": (
                        ring.steps[-1].destination
                        if ring is not None and ring.steps
                        else None
                    ),
                    "cycle_closes": (ring.cycle_closes if ring is not None else False),
                    "warmup_entry_state_id": (
                        ring.warmup_entry_state_id if ring is not None else None
                    ),
                    "warmup_round_count": (
                        ring.warmup_round_count if ring is not None else 0
                    ),
                    "cycle_return_path": (
                        [step.to_dict() for step in (ring.cycle_return_path or [])]
                        if ring is not None
                        else []
                    ),
                },
            )
        )

        return tests

    def _evaluate_system_tests(
        self,
        parsed_result: dict[str, Any],
        events: list[TransitionEvidence],
        ring: MatchedRing | None,
    ) -> list[SemanticTestResult]:
        tests: list[SemanticTestResult] = []

        protocol_observed = any(event.handler in PROTOCOL_MESSAGES for event in events)

        role_mapping = ring.role_to_rebec if ring is not None else {}
        ping_roles = (
            [
                role_mapping["ping1"],
                role_mapping["ping3"],
                role_mapping["ping5"],
            ]
            if ring is not None
            else []
        )
        pong_roles = (
            [
                role_mapping["pong2"],
                role_mapping["pong4"],
            ]
            if ring is not None
            else []
        )
        xsys1_pass = (
            ring is not None
            and len(set(ping_roles)) == 3
            and len(set(pong_roles)) == 2
            and set(ping_roles).isdisjoint(set(pong_roles))
        )
        tests.append(
            _test(
                "CRPP-XSYS1",
                _status_from_observation(
                    xsys1_pass,
                    observed=ring is not None or protocol_observed,
                ),
                "The recurrent protocol must expose three distinct Ping roles and two distinct Pong roles; auxiliary rebecs are allowed.",
                {
                    "ping_roles": ping_roles,
                    "pong_roles": pong_roles,
                    "observed_rebecs": sorted(_all_rebec_names(parsed_result)),
                },
            )
        )

        global_set_neighbor_count = sum(
            event.handler == MSG_SET_NEIGHBOR for event in events
        )

        setup_path = (
            ring.setup_path
            if ring is not None and ring.setup_path is not None
            else None
        )

        setup_set_neighbor_count = (
            sum(event.handler == MSG_SET_NEIGHBOR for event in setup_path)
            if setup_path is not None
            else 0
        )

        bootstrap_cleanup = (
            ring.bootstrap_cleanup
            if ring is not None and ring.bootstrap_cleanup is not None
            else []
        )

        cleanup_set_neighbor_count = sum(
            event.handler == MSG_SET_NEIGHBOR for event in bootstrap_cleanup
        )

        bootstrap_ok = ring is not None and ring.bootstrap is not None
        setup_reaches_bootstrap = ring is not None and ring.setup_path is not None

        # _find_bootstrap validates Start against the first operational round.
        # That round may be a finite warm-up round while remaining setup/helper
        # messages are consumed. The recurrent cycle is validated separately.
        # _find_setup_path independently requires a protocol-free path from an
        # initial state to the Start source state.
        #
        # Therefore initialization correctness is behavioral: it does not
        # require all five SetNeighbor handlers to execute before Start, and it
        # permits static/constructor, message-based, or mixed topology encodings.
        initialization_ok = bootstrap_ok and setup_reaches_bootstrap

        xsys2_pass = initialization_ok
        tests.append(
            _test(
                "CRPP-XSYS2",
                _status_from_observation(
                    xsys2_pass,
                    observed=(
                        ring is not None
                        or any(event.handler == MSG_START for event in events)
                    ),
                ),
                (
                    "The observed Start bootstrap must be reachable from "
                    "initialization and lead into a behaviorally correct "
                    "clockwise round; finite warm-up rounds are allowed while "
                    "setup/helper work completes before the steady recurrent "
                    "cycle is established."
                ),
                {
                    "bootstrap_found": bootstrap_ok,
                    "setup_path_found": setup_path is not None,
                    "global_set_neighbor_transition_count": global_set_neighbor_count,
                    "set_neighbor_before_start_count": setup_set_neighbor_count,
                    "bootstrap_cleanup_transition_count": len(bootstrap_cleanup),
                    "set_neighbor_after_start_before_warmup_count": (
                        cleanup_set_neighbor_count
                    ),
                    "warmup_entry_state_id": (
                        ring.warmup_entry_state_id if ring is not None else None
                    ),
                    "warmup_round_count": (
                        ring.warmup_round_count if ring is not None else 0
                    ),
                    "recurrent_cycle_entry_state_id": (
                        ring.cycle_entry_state_id if ring is not None else None
                    ),
                    "initialization_ok": initialization_ok,
                },
            )
        )

        cycle_state_ids = (
            [ring.cycle_entry_state_id] + [step.destination for step in ring.steps]
            if ring is not None
            else []
        )
        protocol_counts = [
            _protocol_message_count(get_state_by_id(parsed_result, state_id))
            for state_id in cycle_state_ids
        ]
        xsys3_pass = (
            ring is not None
            and ring.cycle_closes
            and bool(protocol_counts)
            and all(count == 1 for count in protocol_counts)
        )
        tests.append(
            _test(
                "CRPP-XSYS3",
                _status_from_observation(
                    xsys3_pass,
                    observed=ring is not None or protocol_observed,
                ),
                "The intended nonterminating behavior must be represented by a recurrent state-graph cycle with exactly one circulating Ping/Pong token throughout the matched cycle.",
                {
                    "cycle_state_ids": cycle_state_ids,
                    "protocol_message_counts": protocol_counts,
                    "cycle_closes": (ring.cycle_closes if ring is not None else False),
                    "warmup_round_count": (
                        ring.warmup_round_count if ring is not None else 0
                    ),
                    "cycle_return_path": (
                        [step.to_dict() for step in (ring.cycle_return_path or [])]
                        if ring is not None
                        else []
                    ),
                    "terminal_quiescence_expected": False,
                },
            )
        )

        complete_pass = (
            ring is not None
            and ring.bootstrap is not None
            and ring.cycle_closes
            and len(set(role_mapping.values())) == 5
            and all(
                len(step.removed_protocol) == 1 and len(step.added_protocol) == 1
                for step in ring.steps
            )
            and bool(protocol_counts)
            and all(count == 1 for count in protocol_counts)
            and initialization_ok
        )
        tests.append(
            _test(
                "CRPP-XSYS4",
                _status_from_observation(
                    complete_pass,
                    observed=ring is not None or protocol_observed,
                ),
                "The complete observable contract must preserve initialized clockwise routing, the Ping/Pong transformation pattern, five distinct logical participants, one-token conservation, and recurrent cycle closure.",
                {
                    "role_mapping": role_mapping,
                    "matched_steps": _protocol_step_summary(ring),
                    "bootstrap": (
                        ring.bootstrap.to_dict()
                        if ring is not None and ring.bootstrap is not None
                        else None
                    ),
                    "protocol_message_counts": protocol_counts,
                    "cycle_closes": (ring.cycle_closes if ring is not None else False),
                    "initialization_ok": initialization_ok,
                    "set_neighbor_before_start_count": setup_set_neighbor_count,
                    "set_neighbor_after_start_before_warmup_count": (
                        cleanup_set_neighbor_count
                    ),
                    "warmup_entry_state_id": (
                        ring.warmup_entry_state_id if ring is not None else None
                    ),
                    "warmup_round_count": (
                        ring.warmup_round_count if ring is not None else 0
                    ),
                    "recurrent_cycle_entry_state_id": (
                        ring.cycle_entry_state_id if ring is not None else None
                    ),
                },
            )
        )

        return tests


def evaluate_clockwise_ring_ping_pong(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = ClockwiseRingPingPongEvaluator(
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
            "Evaluate the initialized five-node Clockwise Ring Ping-Pong "
            "benchmark from normalized parsed RMC state-graph JSON (warm-up aware V3)."
        )
    )
    parser.add_argument(
        "parsed_result",
        help="Path to the parsed RMC JSON file.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional output JSON path.",
    )
    arguments = parser.parse_args()

    try:
        parsed_result = load_json(arguments.parsed_result)
        result = evaluate_clockwise_ring_ping_pong(parsed_result)
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
            f"ClockwiseRingPingPong evaluator infrastructure error: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
