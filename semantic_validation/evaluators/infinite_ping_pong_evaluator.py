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


BENCHMARK_ID = "infinite_ping_pong"


@dataclass(frozen=True)
class QueueMessage:
    recipient: str
    raw_message: str
    message_name: str
    sender: str

    def to_dict(self) -> dict[str, str]:
        return {
            "recipient": self.recipient,
            "raw_message": self.raw_message,
            "message_name": self.message_name,
            "sender": self.sender,
        }


@dataclass
class TransitionEvidence:
    source: Any
    destination: Any
    owner: str
    handler: str
    removed: list[QueueMessage]
    added: list[QueueMessage]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_state_id": self.source,
            "destination_state_id": self.destination,
            "owner": self.owner,
            "message_server": self.handler,
            "removed_messages": [item.to_dict() for item in self.removed],
            "added_messages": [item.to_dict() for item in self.added],
        }


@dataclass
class ProtocolDiscovery:
    ping: str | None
    pong: str | None
    request_events: list[TransitionEvidence]
    reply_events: list[TransitionEvidence]
    startup_witness: list[TransitionEvidence] | None
    first_round_witness: list[TransitionEvidence] | None
    recurrence_witness: list[TransitionEvidence] | None
    recurrent_scc_state_ids: list[Any]


def _state_id(state: dict[str, Any] | None) -> Any:
    if not state:
        return None
    return state.get("id") if state.get("id") is not None else state.get("state_id")


def _initial_state_ids(parsed_result: dict[str, Any]) -> list[Any]:
    ids = [
        _state_id(state)
        for state in get_states(parsed_result)
        if _state_id(state) is not None
    ]
    if not ids:
        return []

    destinations = {
        transition.get("destination")
        for transition in get_transitions(parsed_result)
    }
    roots = [state_id for state_id in ids if state_id not in destinations]

    if roots:
        return roots
    if 0 in ids:
        return [0]
    return [ids[0]]


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
            value = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
            if value is not None:
                names.append(normalize_name(str(value)))
    return names


def _all_rebec_names(parsed_result: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for state in get_states(parsed_result):
        result.update(_rebec_names(state))
    return result


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
) -> list[tuple[str, str, str]]:
    return [
        (
            _message_raw(message),
            _message_name(message),
            _message_sender(message),
        )
        for message in get_queue(state, rebec)
    ]


def _positive_multiset_delta(
    left: list[tuple[str, str, str]],
    right: list[tuple[str, str, str]],
) -> list[tuple[str, str, str]]:
    delta = MultisetCounter(left) - MultisetCounter(right)
    result: list[tuple[str, str, str]] = []
    for signature, count in delta.items():
        result.extend([signature] * count)
    return result


def _queue_delta(
    source_state: dict[str, Any] | None,
    destination_state: dict[str, Any] | None,
) -> tuple[list[QueueMessage], list[QueueMessage]]:
    removed: list[QueueMessage] = []
    added: list[QueueMessage] = []

    rebecs = sorted(
        set(_rebec_names(source_state)) | set(_rebec_names(destination_state))
    )

    for rebec in rebecs:
        source_signatures = _queue_signatures(source_state, rebec)
        destination_signatures = _queue_signatures(destination_state, rebec)

        for raw, name, sender in _positive_multiset_delta(
            source_signatures,
            destination_signatures,
        ):
            removed.append(
                QueueMessage(
                    recipient=rebec,
                    raw_message=raw,
                    message_name=name,
                    sender=sender,
                )
            )

        for raw, name, sender in _positive_multiset_delta(
            destination_signatures,
            source_signatures,
        ):
            added.append(
                QueueMessage(
                    recipient=rebec,
                    raw_message=raw,
                    message_name=name,
                    sender=sender,
                )
            )

    return removed, added


def _build_events(
    parsed_result: dict[str, Any],
) -> tuple[list[TransitionEvidence], dict[Any, list[TransitionEvidence]]]:
    events: list[TransitionEvidence] = []
    outgoing: dict[Any, list[TransitionEvidence]] = defaultdict(list)

    for transition in get_transitions(parsed_result):
        source = transition.get("source")
        destination = transition.get("destination")
        source_state = get_state_by_id(parsed_result, source)
        destination_state = get_state_by_id(parsed_result, destination)
        removed, added = _queue_delta(source_state, destination_state)

        event = TransitionEvidence(
            source=source,
            destination=destination,
            owner=transition_owner(transition),
            handler=transition_message(transition),
            removed=removed,
            added=added,
        )
        events.append(event)
        outgoing[source].append(event)

    return events, outgoing


def _cross_added(
    event: TransitionEvidence,
    *,
    sender: str,
    recipient: str,
) -> list[QueueMessage]:
    sender = normalize_name(sender)
    recipient = normalize_name(recipient)
    return [
        message
        for message in event.added
        if message.sender == sender and message.recipient == recipient
    ]


def _cross_removed(
    event: TransitionEvidence,
    *,
    sender: str,
    recipient: str,
) -> list[QueueMessage]:
    sender = normalize_name(sender)
    recipient = normalize_name(recipient)
    return [
        message
        for message in event.removed
        if message.sender == sender and message.recipient == recipient
    ]


def _shortest_cross_send_distance(
    parsed_result: dict[str, Any],
    outgoing: dict[Any, list[TransitionEvidence]],
    *,
    sender: str,
    recipient: str,
) -> int | None:
    sender = normalize_name(sender)
    recipient = normalize_name(recipient)

    queue: deque[tuple[Any, int]] = deque(
        (state_id, 0)
        for state_id in _initial_state_ids(parsed_result)
    )
    visited: set[Any] = set()

    while queue:
        state_id, distance = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)

        for event in outgoing.get(state_id, []):
            if (
                event.owner == sender
                and _cross_added(
                    event,
                    sender=sender,
                    recipient=recipient,
                )
            ):
                return distance + 1

            queue.append(
                (event.destination, distance + 1)
            )

    return None


def _discover_protocol_pair(
    parsed_result: dict[str, Any],
    events: list[TransitionEvidence],
    outgoing: dict[Any, list[TransitionEvidence]],
) -> tuple[str | None, str | None]:
    directed_send_counts: dict[tuple[str, str], int] = defaultdict(int)
    reply_like_counts: dict[tuple[str, str], int] = defaultdict(int)

    for event in events:
        for message in event.added:
            if (
                message.sender
                and message.recipient
                and message.sender != message.recipient
                and event.owner == message.sender
            ):
                directed_send_counts[
                    (message.sender, message.recipient)
                ] += 1

        for removed in event.removed:
            if (
                removed.recipient != event.owner
                or not removed.sender
                or removed.sender == event.owner
            ):
                continue

            opposite = [
                added
                for added in event.added
                if (
                    added.sender == event.owner
                    and added.recipient == removed.sender
                )
            ]
            if len(opposite) == 1:
                reply_like_counts[
                    (removed.sender, event.owner)
                ] += 1

    actors = sorted(
        {
            actor
            for pair in directed_send_counts
            for actor in pair
        }
    )

    unordered_pairs: list[tuple[int, str, str]] = []

    for index, first in enumerate(actors):
        for second in actors[index + 1:]:
            forward = directed_send_counts.get((first, second), 0)
            backward = directed_send_counts.get((second, first), 0)

            if not forward or not backward:
                continue

            reciprocal_reply_score = (
                reply_like_counts.get((first, second), 0)
                + reply_like_counts.get((second, first), 0)
            )

            unordered_pairs.append(
                (
                    forward + backward + (2 * reciprocal_reply_score),
                    first,
                    second,
                )
            )

    if not unordered_pairs:
        return None, None

    unordered_pairs.sort(
        key=lambda item: (-item[0], item[1], item[2])
    )
    _, first, second = unordered_pairs[0]

    first_distance = _shortest_cross_send_distance(
        parsed_result,
        outgoing,
        sender=first,
        recipient=second,
    )
    second_distance = _shortest_cross_send_distance(
        parsed_result,
        outgoing,
        sender=second,
        recipient=first,
    )

    if (
        first_distance is not None
        and (
            second_distance is None
            or first_distance < second_distance
        )
    ):
        return first, second

    if (
        second_distance is not None
        and (
            first_distance is None
            or second_distance < first_distance
        )
    ):
        return second, first

    # Fallback when both directions first appear at the same graph depth:
    # orient the actor whose counterpart more strongly behaves as a
    # reply-to-sender server as Ping.
    second_reply_score = reply_like_counts.get((first, second), 0)
    first_reply_score = reply_like_counts.get((second, first), 0)

    if second_reply_score >= first_reply_score:
        return first, second
    return second, first


def _is_request_event(
    event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> bool:
    ping = normalize_name(ping)
    pong = normalize_name(pong)
    return (
        event.owner == ping
        and len(_cross_added(event, sender=ping, recipient=pong)) == 1
    )


def _is_reply_event(
    event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> bool:
    ping = normalize_name(ping)
    pong = normalize_name(pong)
    return (
        event.owner == pong
        and len(_cross_removed(event, sender=ping, recipient=pong)) == 1
        and len(_cross_added(event, sender=pong, recipient=ping)) == 1
    )


def _request_send_count(
    event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> int:
    return len(_cross_added(event, sender=ping, recipient=pong))


def _reply_send_count(
    event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> int:
    return len(_cross_added(event, sender=pong, recipient=ping))


def _find_startup_request(
    parsed_result: dict[str, Any],
    outgoing: dict[Any, list[TransitionEvidence]],
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque(
        (state_id, [])
        for state_id in _initial_state_ids(parsed_result)
    )
    visited: set[Any] = set()

    while queue:
        state_id, path = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)

        for event in outgoing.get(state_id, []):
            if _is_request_event(event, ping=ping, pong=pong):
                return path + [event]

            if _is_reply_event(event, ping=ping, pong=pong):
                # A valid first request must precede the first protocol reply.
                continue

            queue.append((event.destination, path + [event]))

    return None


def _find_reply_after_request(
    outgoing: dict[Any, list[TransitionEvidence]],
    request_event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque(
        [(request_event.destination, [])]
    )
    visited: set[Any] = set()

    while queue:
        state_id, path = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)

        for event in outgoing.get(state_id, []):
            if _is_reply_event(event, ping=ping, pong=pong):
                return path + [event]

            # Another request before a reply would duplicate the token.
            if _is_request_event(event, ping=ping, pong=pong):
                continue

            queue.append((event.destination, path + [event]))

    return None


def _find_next_request_after_reply(
    outgoing: dict[Any, list[TransitionEvidence]],
    reply_event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque(
        [(reply_event.destination, [])]
    )
    visited: set[Any] = set()

    while queue:
        state_id, path = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)

        for event in outgoing.get(state_id, []):
            if _is_request_event(event, ping=ping, pong=pong):
                return path + [event]

            if _is_reply_event(event, ping=ping, pong=pong):
                # A second reply before the next request violates alternation.
                continue

            queue.append((event.destination, path + [event]))

    return None


def _find_first_round(
    startup_witness: list[TransitionEvidence] | None,
    outgoing: dict[Any, list[TransitionEvidence]],
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    if not startup_witness:
        return None

    first_request = startup_witness[-1]
    to_reply = _find_reply_after_request(
        outgoing,
        first_request,
        ping=ping,
        pong=pong,
    )
    if not to_reply:
        return None

    return startup_witness + to_reply


def _find_recurrence(
    startup_witness: list[TransitionEvidence] | None,
    outgoing: dict[Any, list[TransitionEvidence]],
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    if not startup_witness:
        return None

    first_request = startup_witness[-1]
    to_reply = _find_reply_after_request(
        outgoing,
        first_request,
        ping=ping,
        pong=pong,
    )
    if not to_reply:
        return None

    reply_event = to_reply[-1]
    to_next_request = _find_next_request_after_reply(
        outgoing,
        reply_event,
        ping=ping,
        pong=pong,
    )
    if not to_next_request:
        return None

    return startup_witness + to_reply + to_next_request


def _strongly_connected_components(
    parsed_result: dict[str, Any],
) -> list[list[Any]]:
    adjacency: dict[Any, list[Any]] = defaultdict(list)
    nodes: set[Any] = {
        _state_id(state)
        for state in get_states(parsed_result)
        if _state_id(state) is not None
    }

    for transition in get_transitions(parsed_result):
        source = transition.get("source")
        destination = transition.get("destination")
        nodes.add(source)
        nodes.add(destination)
        adjacency[source].append(destination)

    index = 0
    stack: list[Any] = []
    on_stack: set[Any] = set()
    indices: dict[Any, int] = {}
    lowlinks: dict[Any, int] = {}
    components: list[list[Any]] = []

    sys.setrecursionlimit(
        max(sys.getrecursionlimit(), len(nodes) * 2 + 100)
    )

    def strongconnect(node: Any) -> None:
        nonlocal index

        indices[node] = index
        lowlinks[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for neighbor in adjacency.get(node, []):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlinks[node] = min(
                    lowlinks[node],
                    lowlinks[neighbor],
                )
            elif neighbor in on_stack:
                lowlinks[node] = min(
                    lowlinks[node],
                    indices[neighbor],
                )

        if lowlinks[node] == indices[node]:
            component: list[Any] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(component)

    for node in nodes:
        if node not in indices:
            strongconnect(node)

    return components


def _find_recurrent_protocol_scc(
    parsed_result: dict[str, Any],
    events: list[TransitionEvidence],
    *,
    ping: str | None,
    pong: str | None,
) -> list[Any]:
    if ping is None or pong is None:
        return []

    by_source: dict[Any, list[TransitionEvidence]] = defaultdict(list)
    for event in events:
        by_source[event.source].append(event)

    edge_pairs = {
        (transition.get("source"), transition.get("destination"))
        for transition in get_transitions(parsed_result)
    }

    for component in sorted(
        _strongly_connected_components(parsed_result),
        key=len,
        reverse=True,
    ):
        states = set(component)

        cyclic = len(states) > 1 or any(
            source == destination and source in states
            for source, destination in edge_pairs
        )
        if not cyclic:
            continue

        has_request = False
        has_reply = False

        for state_id in states:
            for event in by_source.get(state_id, []):
                if event.destination not in states:
                    continue
                if _is_request_event(event, ping=ping, pong=pong):
                    has_request = True
                if _is_reply_event(event, ping=ping, pong=pong):
                    has_reply = True

        if has_request and has_reply:
            return sorted(states, key=str)

    return []


def _terminal_states_in_component(
    outgoing: dict[Any, list[TransitionEvidence]],
    component: list[Any],
) -> list[Any]:
    state_set = set(component)
    return [
        state_id
        for state_id in component
        if not any(
            event.destination in state_set
            for event in outgoing.get(state_id, [])
        )
    ]


def _path_to_dict(
    path: list[TransitionEvidence] | None,
    *,
    max_items: int = 50,
) -> list[dict[str, Any]]:
    if not path:
        return []
    return [event.to_dict() for event in path[:max_items]]


def _test(
    test_id: str,
    condition: bool,
    description: str,
    evidence: dict[str, Any],
    *,
    observed: bool = True,
) -> SemanticTestResult:
    if condition:
        status = TestStatus.PASS
    else:
        status = TestStatus.FAIL if observed else TestStatus.NOT_OBSERVED

    return SemanticTestResult(
        test_id=test_id,
        status=status,
        description=description,
        evidence=evidence,
    )


def _discover_protocol(
    parsed_result: dict[str, Any],
    events: list[TransitionEvidence],
    outgoing: dict[Any, list[TransitionEvidence]],
) -> ProtocolDiscovery:
    ping, pong = _discover_protocol_pair(
        parsed_result,
        events,
        outgoing,
    )

    if ping is None or pong is None:
        return ProtocolDiscovery(
            ping=ping,
            pong=pong,
            request_events=[],
            reply_events=[],
            startup_witness=None,
            first_round_witness=None,
            recurrence_witness=None,
            recurrent_scc_state_ids=[],
        )

    request_events = [
        event
        for event in events
        if _is_request_event(event, ping=ping, pong=pong)
    ]
    reply_events = [
        event
        for event in events
        if _is_reply_event(event, ping=ping, pong=pong)
    ]

    startup_witness = _find_startup_request(
        parsed_result,
        outgoing,
        ping=ping,
        pong=pong,
    )
    first_round_witness = _find_first_round(
        startup_witness,
        outgoing,
        ping=ping,
        pong=pong,
    )
    recurrence_witness = _find_recurrence(
        startup_witness,
        outgoing,
        ping=ping,
        pong=pong,
    )
    recurrent_scc = _find_recurrent_protocol_scc(
        parsed_result,
        events,
        ping=ping,
        pong=pong,
    )

    return ProtocolDiscovery(
        ping=ping,
        pong=pong,
        request_events=request_events,
        reply_events=reply_events,
        startup_witness=startup_witness,
        first_round_witness=first_round_witness,
        recurrence_witness=recurrence_witness,
        recurrent_scc_state_ids=recurrent_scc,
    )


class InfinitePingPongEvaluator(BaseSemanticEvaluator):
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
        discovery = _discover_protocol(
            parsed_result,
            events,
            outgoing,
        )

        ping = discovery.ping
        pong = discovery.pong

        request_single = (
            ping is not None
            and pong is not None
            and bool(discovery.request_events)
            and all(
                _request_send_count(
                    event,
                    ping=ping,
                    pong=pong,
                ) == 1
                for event in discovery.request_events
            )
        )

        reply_single = (
            ping is not None
            and pong is not None
            and bool(discovery.reply_events)
            and all(
                _reply_send_count(
                    event,
                    ping=ping,
                    pong=pong,
                ) == 1
                for event in discovery.reply_events
            )
        )

        bad_cross_duplication: list[dict[str, Any]] = []
        if ping is not None and pong is not None:
            for event in events:
                protocol_added = [
                    message
                    for message in event.added
                    if (
                        (message.sender == ping and message.recipient == pong)
                        or
                        (message.sender == pong and message.recipient == ping)
                    )
                ]
                if len(protocol_added) > 1:
                    bad_cross_duplication.append(event.to_dict())

        startup_ok = discovery.startup_witness is not None
        first_round_ok = discovery.first_round_witness is not None
        recurrence_ok = discovery.recurrence_witness is not None
        topology_ok = ping is not None and pong is not None and ping != pong

        recurrent_scc = discovery.recurrent_scc_state_ids
        recurrent_scc_ok = bool(recurrent_scc)
        terminal_inside_scc = _terminal_states_in_component(
            outgoing,
            recurrent_scc,
        ) if recurrent_scc else []
        no_terminal_inside_scc = (
            recurrent_scc_ok
            and not terminal_inside_scc
        )

        token_conservation_ok = (
            recurrence_ok
            and request_single
            and reply_single
            and not bad_cross_duplication
        )

        tests: list[SemanticTestResult] = []

        tests.append(
            _test(
                "IPP-XA1",
                startup_ok and request_single,
                (
                    "Logical Ping must autonomously emit exactly one first request "
                    "to logical Pong."
                ),
                {
                    "ping": ping,
                    "pong": pong,
                    "startup_witness": _path_to_dict(
                        discovery.startup_witness
                    ),
                    "request_event_count": len(
                        discovery.request_events
                    ),
                },
                observed=topology_ok,
            )
        )

        tests.append(
            _test(
                "IPP-XA2",
                recurrence_ok and request_single,
                (
                    "After consuming a Pong reply, logical Ping must reach exactly "
                    "one next request to the same Pong."
                ),
                {
                    "recurrence_witness": _path_to_dict(
                        discovery.recurrence_witness
                    ),
                    "request_single_send": request_single,
                },
                observed=bool(discovery.reply_events),
            )
        )

        tests.append(
            _test(
                "IPP-XA3",
                reply_single and bool(discovery.reply_events),
                (
                    "Logical Pong must consume a Ping request and emit exactly one "
                    "reply to the same Ping."
                ),
                {
                    "reply_event_count": len(
                        discovery.reply_events
                    ),
                    "reply_events_sample": [
                        event.to_dict()
                        for event in discovery.reply_events[:20]
                    ],
                },
                observed=topology_ok,
            )
        )

        tests.append(
            _test(
                "IPP-XA4",
                request_single
                and reply_single
                and not bad_cross_duplication,
                (
                    "No protocol step may duplicate the next cross-actor "
                    "request/reply message."
                ),
                {
                    "request_single_send": request_single,
                    "reply_single_send": reply_single,
                    "duplicating_events": bad_cross_duplication,
                },
                observed=topology_ok,
            )
        )

        tests.append(
            _test(
                "IPP-XI1",
                topology_ok,
                (
                    "The protocol must expose one logical Ping role and one logical "
                    "Pong role connected in both directions."
                ),
                {
                    "logical_ping": ping,
                    "logical_pong": pong,
                    "observed_rebecs": sorted(
                        _all_rebec_names(parsed_result)
                    ),
                },
                observed=bool(events),
            )
        )

        tests.append(
            _test(
                "IPP-XI2",
                first_round_ok,
                (
                    "A connected execution from initialization must contain the "
                    "first Ping->Pong request followed by Pong->Ping reply."
                ),
                {
                    "first_round_witness": _path_to_dict(
                        discovery.first_round_witness
                    ),
                },
                observed=startup_ok,
            )
        )

        tests.append(
            _test(
                "IPP-XI3",
                recurrence_ok,
                (
                    "A connected execution must realize "
                    "Ping->Pong, Pong->Ping, Ping->Pong."
                ),
                {
                    "recurrence_witness": _path_to_dict(
                        discovery.recurrence_witness
                    ),
                },
                observed=first_round_ok,
            )
        )

        tests.append(
            _test(
                "IPP-XI4",
                token_conservation_ok,
                (
                    "The recurrent interaction must preserve a single logical "
                    "request/reply token without duplication or loss."
                ),
                {
                    "recurrence_observed": recurrence_ok,
                    "request_single_send": request_single,
                    "reply_single_send": reply_single,
                    "duplicating_event_count": len(
                        bad_cross_duplication
                    ),
                },
                observed=topology_ok,
            )
        )

        tests.append(
            _test(
                "IPP-XSYS1",
                topology_ok,
                (
                    "The state-space must expose exactly one logical Ping role and "
                    "one logical Pong role; auxiliary rebecs are permitted."
                ),
                {
                    "logical_ping": ping,
                    "logical_pong": pong,
                    "protocol_role_count": (
                        2 if topology_ok else 0
                    ),
                    "observed_rebecs": sorted(
                        _all_rebec_names(parsed_result)
                    ),
                },
                observed=bool(states),
            )
        )

        tests.append(
            _test(
                "IPP-XSYS2",
                startup_ok,
                (
                    "The generated model must autonomously reach the first "
                    "Ping->Pong request from its initial state."
                ),
                {
                    "initial_state_ids": _initial_state_ids(
                        parsed_result
                    ),
                    "startup_witness": _path_to_dict(
                        discovery.startup_witness
                    ),
                },
                observed=bool(states),
            )
        )

        tests.append(
            _test(
                "IPP-XSYS3",
                recurrent_scc_ok,
                (
                    "The reachable graph must contain a cyclic SCC with both "
                    "Ping->Pong and Pong->Ping protocol progress."
                ),
                {
                    "recurrent_scc_size": len(recurrent_scc),
                    "recurrent_scc_state_ids": recurrent_scc[:100],
                },
                observed=bool(transitions),
            )
        )

        tests.append(
            _test(
                "IPP-XSYS4",
                no_terminal_inside_scc,
                (
                    "The recurrent protocol component must not contain a terminal "
                    "quiescent state."
                ),
                {
                    "recurrent_scc_size": len(recurrent_scc),
                    "terminal_states_inside_recurrent_scc": (
                        terminal_inside_scc
                    ),
                    "terminal_quiescence_expected": False,
                },
                observed=recurrent_scc_ok,
            )
        )

        complete_ok = all(
            [
                topology_ok,
                startup_ok,
                first_round_ok,
                recurrence_ok,
                token_conservation_ok,
                recurrent_scc_ok,
                no_terminal_inside_scc,
            ]
        )

        tests.append(
            _test(
                "IPP-XSYS5",
                complete_ok,
                (
                    "The complete Infinite Ping-Pong contract must preserve "
                    "automatic startup, one-to-one routing, alternating recurrence, "
                    "single-token conservation, and nontermination."
                ),
                {
                    "topology_ok": topology_ok,
                    "startup_ok": startup_ok,
                    "first_round_ok": first_round_ok,
                    "recurrence_ok": recurrence_ok,
                    "token_conservation_ok": token_conservation_ok,
                    "recurrent_scc_ok": recurrent_scc_ok,
                    "no_terminal_inside_recurrent_scc": (
                        no_terminal_inside_scc
                    ),
                },
                observed=bool(states),
            )
        )

        issues: list[str] = []

        if not transitions:
            issues.append("NO_TRANSITIONS")
        if not topology_ok:
            issues.append("PING_PONG_PROTOCOL_PAIR_NOT_DISCOVERED")
        if topology_ok and not startup_ok:
            issues.append("AUTOMATIC_STARTUP_NOT_OBSERVED")
        if startup_ok and not first_round_ok:
            issues.append("FIRST_REQUEST_REPLY_ROUND_NOT_OBSERVED")
        if first_round_ok and not recurrence_ok:
            issues.append("RECURRENT_NEXT_REQUEST_NOT_OBSERVED")
        if bad_cross_duplication:
            issues.append("PROTOCOL_MESSAGE_DUPLICATION")
        if not recurrent_scc_ok:
            issues.append("RECURRENT_PROTOCOL_SCC_NOT_FOUND")
        if recurrent_scc_ok and terminal_inside_scc:
            issues.append("TERMINAL_STATE_INSIDE_RECURRENT_COMPONENT")
        if any(
            test.status == TestStatus.NOT_OBSERVED
            for test in tests
        ):
            issues.append("INCOMPLETE_OBSERVABILITY")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "semantic_backend": "statespace",
                "semantic_scope": (
                    "scenario-bounded observational equivalence for the "
                    "recurrent Infinite Ping-Pong protocol"
                ),
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": _initial_state_ids(
                    parsed_result
                ),
                "observed_rebecs": sorted(
                    _all_rebec_names(parsed_result)
                ),
                "logical_ping": ping,
                "logical_pong": pong,
                "request_event_count": len(
                    discovery.request_events
                ),
                "reply_event_count": len(
                    discovery.reply_events
                ),
                "startup_observed": startup_ok,
                "first_round_observed": first_round_ok,
                "recurrence_observed": recurrence_ok,
                "recurrent_scc_size": len(recurrent_scc),
                "recurrent_scc_state_ids": recurrent_scc[:100],
                "terminal_states_inside_recurrent_scc": (
                    terminal_inside_scc
                ),
                "target_name_hard_coding": False,
                "namespace_qualification_required": False,
            },
        )


def evaluate_infinite_ping_pong(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = InfinitePingPongEvaluator(
        parsed_result=parsed_result,
        example_id=BENCHMARK_ID,
    )
    return evaluator.evaluate(parsed_result).to_dict()


def load_json(path: str | Path) -> dict[str, Any]:
    input_path = Path(path)
    if not input_path.is_file():
        raise FileNotFoundError(
            f"JSON file not found: {input_path}"
        )

    with input_path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)

    if not isinstance(value, dict):
        raise ValueError(
            "Parsed RMC state-space must be a JSON object."
        )

    return value


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Infinite Ping-Pong from normalized full RMC "
            "state-space JSON."
        )
    )
    parser.add_argument(
        "parsed_result",
        help="Path to parsed_statespace.json.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional semantic-result JSON output path.",
    )
    arguments = parser.parse_args()

    try:
        parsed_result = load_json(
            arguments.parsed_result
        )
        result = evaluate_infinite_ping_pong(
            parsed_result
        )
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
            (
                "InfinitePingPong evaluator infrastructure "
                f"error: {exc}"
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
