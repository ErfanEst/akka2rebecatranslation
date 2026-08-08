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

BENCHMARK_ID = "all_pings_to_one_pong"
EXPECTED_PING_COUNT = 12


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
    transition: dict[str, Any]
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
            "removed_messages": [message.to_dict() for message in self.removed],
            "added_messages": [message.to_dict() for message in self.added],
        }


@dataclass
class ProtocolDiscovery:
    pong: str | None
    pings: list[str]
    request_events: dict[str, list[TransitionEvidence]]
    reply_events: dict[str, list[TransitionEvidence]]
    startup_witnesses: dict[str, list[TransitionEvidence] | None]
    recurrence_witnesses: dict[str, list[TransitionEvidence] | None]
    interleaving_state_id: Any | None
    interleaving_ping_owners: list[str]
    recurrent_scc_state_ids: list[Any]

    @property
    def all_pings_discovered(self) -> bool:
        return len(self.pings) == EXPECTED_PING_COUNT

    @property
    def all_startup_observed(self) -> bool:
        return self.all_pings_discovered and all(
            self.startup_witnesses.get(ping) for ping in self.pings
        )

    @property
    def all_recurrence_observed(self) -> bool:
        return self.all_pings_discovered and all(
            self.recurrence_witnesses.get(ping) for ping in self.pings
        )


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
    result: list[str] = []
    if isinstance(rebecs, list):
        for rebec in rebecs:
            if not isinstance(rebec, dict):
                continue
            name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
            if name:
                result.append(normalize_name(str(name)))
    return result


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


def _transition_evidence(
    parsed_result: dict[str, Any],
    transition: dict[str, Any],
) -> TransitionEvidence:
    source = _transition_source(transition)
    destination = _transition_destination(transition)
    source_state = get_state_by_id(parsed_result, source)
    destination_state = get_state_by_id(parsed_result, destination)
    removed, added = _queue_delta(source_state, destination_state)

    return TransitionEvidence(
        transition=transition,
        source=source,
        destination=destination,
        owner=transition_owner(transition),
        handler=transition_message(transition),
        removed=removed,
        added=added,
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


def _messages_added_to(
    event: TransitionEvidence,
    recipient: str,
    sender: str | None = None,
) -> list[QueueMessage]:
    recipient = normalize_name(recipient)
    normalized_sender = normalize_name(sender) if sender is not None else None
    return [
        message
        for message in event.added
        if message.recipient == recipient
        and (normalized_sender is None or message.sender == normalized_sender)
    ]


def _messages_removed_from(
    event: TransitionEvidence,
    recipient: str,
    sender: str | None = None,
) -> list[QueueMessage]:
    recipient = normalize_name(recipient)
    normalized_sender = normalize_name(sender) if sender is not None else None
    return [
        message
        for message in event.removed
        if message.recipient == recipient
        and (normalized_sender is None or message.sender == normalized_sender)
    ]


def _is_request_event(
    event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> bool:
    ping = normalize_name(ping)
    pong = normalize_name(pong)
    return event.owner == ping and len(_messages_added_to(event, pong, ping)) == 1


def _request_count(
    event: TransitionEvidence,
    *,
    ping: str,
    pong: str,
) -> int:
    return len(_messages_added_to(event, pong, ping))


def _is_reply_event(
    event: TransitionEvidence,
    *,
    pong: str,
    ping: str,
) -> bool:
    pong = normalize_name(pong)
    ping = normalize_name(ping)

    requests_consumed = _messages_removed_from(event, pong, ping)
    replies_to_ping = _messages_added_to(event, ping, pong)

    return (
        event.owner == pong
        and len(requests_consumed) == 1
        and len(replies_to_ping) == 1
    )


def _bad_reply_routing(
    event: TransitionEvidence,
    *,
    pong: str,
    known_pings: set[str],
) -> bool:
    if event.owner != normalize_name(pong):
        return False

    removed_requests = [
        message
        for message in event.removed
        if message.recipient == normalize_name(pong) and message.sender in known_pings
    ]
    if len(removed_requests) != 1:
        return False

    source_ping = removed_requests[0].sender
    replies_to_known_pings = [
        message
        for message in event.added
        if message.sender == normalize_name(pong) and message.recipient in known_pings
    ]

    return not (
        len(replies_to_known_pings) == 1
        and replies_to_known_pings[0].recipient == source_ping
    )


def _discover_pong_and_pings(
    events: list[TransitionEvidence],
) -> tuple[str | None, list[str]]:
    reply_pairs_by_owner: dict[str, set[str]] = defaultdict(set)
    request_pairs: set[tuple[str, str]] = set()

    for event in events:
        for added in event.added:
            if added.sender == event.owner and added.recipient != event.owner:
                request_pairs.add((event.owner, added.recipient))

        for removed in event.removed:
            if removed.recipient != event.owner:
                continue
            sender = removed.sender
            if not sender or sender == event.owner:
                continue
            replies = [
                added
                for added in event.added
                if added.sender == event.owner and added.recipient == sender
            ]
            if len(replies) == 1:
                reply_pairs_by_owner[event.owner].add(sender)

    candidates: list[tuple[int, str, list[str]]] = []
    for pong, possible_pings in reply_pairs_by_owner.items():
        supported = sorted(
            ping for ping in possible_pings if (ping, pong) in request_pairs
        )
        candidates.append((len(supported), pong, supported))

    if not candidates:
        return None, []

    candidates.sort(key=lambda item: (-item[0], item[1]))
    _, pong, pings = candidates[0]
    return pong, pings


def _event_is_reply_to_ping(
    event: TransitionEvidence,
    *,
    pong: str,
    ping: str,
) -> bool:
    return _is_reply_event(event, pong=pong, ping=ping)


def _find_first_request_from_initial(
    parsed_result: dict[str, Any],
    outgoing: dict[Any, list[TransitionEvidence]],
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    queue: deque[tuple[Any, list[TransitionEvidence]]] = deque(
        (state_id, []) for state_id in _initial_state_ids(parsed_result)
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

            # A "first request" witness cannot pass through a prior reply
            # to the same logical Ping.
            if _event_is_reply_to_ping(event, pong=pong, ping=ping):
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
            if _is_reply_event(event, pong=pong, ping=ping):
                return path + [event]

            # Do not silently skip a second request from this Ping before
            # its outstanding request has been replied to.
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

            # Another reply to the same Ping before it emitted its next
            # request would violate the one-request/one-reply cycle.
            if _is_reply_event(event, pong=pong, ping=ping):
                continue

            queue.append((event.destination, path + [event]))

    return None


def _find_recurrence_witness(
    outgoing: dict[Any, list[TransitionEvidence]],
    request_events: list[TransitionEvidence],
    *,
    ping: str,
    pong: str,
) -> list[TransitionEvidence] | None:
    for request_event in request_events:
        to_reply = _find_reply_after_request(
            outgoing,
            request_event,
            ping=ping,
            pong=pong,
        )
        if not to_reply:
            continue

        reply_event = to_reply[-1]
        to_next_request = _find_next_request_after_reply(
            outgoing,
            reply_event,
            ping=ping,
            pong=pong,
        )
        if not to_next_request:
            continue

        return [request_event] + to_reply + to_next_request

    return None


def _find_interleaving_state(
    outgoing: dict[Any, list[TransitionEvidence]],
    *,
    pings: set[str],
) -> tuple[Any | None, list[str]]:
    for state_id, state_events in outgoing.items():
        owners = sorted({event.owner for event in state_events if event.owner in pings})
        if len(owners) >= 2:
            return state_id, owners
    return None, []


def _strongly_connected_components(
    parsed_result: dict[str, Any],
) -> list[list[Any]]:
    transitions = get_transitions(parsed_result)
    adjacency: dict[Any, list[Any]] = defaultdict(list)
    nodes: set[Any] = {
        _state_id(state)
        for state in get_states(parsed_result)
        if _state_id(state) is not None
    }

    for transition in transitions:
        source = _transition_source(transition)
        destination = _transition_destination(transition)
        nodes.add(source)
        nodes.add(destination)
        adjacency[source].append(destination)

    index = 0
    stack: list[Any] = []
    on_stack: set[Any] = set()
    indices: dict[Any, int] = {}
    lowlinks: dict[Any, int] = {}
    components: list[list[Any]] = []

    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(nodes) * 2 + 100))

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
                lowlinks[node] = min(lowlinks[node], lowlinks[neighbor])
            elif neighbor in on_stack:
                lowlinks[node] = min(lowlinks[node], indices[neighbor])

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


def _find_protocol_recurrent_scc(
    parsed_result: dict[str, Any],
    events: list[TransitionEvidence],
    *,
    pong: str | None,
    pings: set[str],
) -> list[Any]:
    if pong is None:
        return []

    events_by_source: dict[Any, list[TransitionEvidence]] = defaultdict(list)
    for event in events:
        events_by_source[event.source].append(event)

    transition_pairs = {
        (_transition_source(transition), _transition_destination(transition))
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
            for source, destination in transition_pairs
        )
        if not cyclic:
            continue

        protocol_active = False
        for state_id in states:
            for event in events_by_source.get(state_id, []):
                if event.destination not in states:
                    continue
                if any(
                    _is_request_event(event, ping=ping, pong=pong)
                    or _is_reply_event(event, pong=pong, ping=ping)
                    for ping in pings
                ):
                    protocol_active = True
                    break
            if protocol_active:
                break

        if protocol_active:
            return sorted(states, key=lambda value: (str(type(value)), str(value)))

    return []


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


def _path_to_dict(
    path: list[TransitionEvidence] | None,
    *,
    max_items: int = 40,
) -> list[dict[str, Any]]:
    if not path:
        return []
    return [event.to_dict() for event in path[:max_items]]


def _discover_protocol(
    parsed_result: dict[str, Any],
    events: list[TransitionEvidence],
    outgoing: dict[Any, list[TransitionEvidence]],
) -> ProtocolDiscovery:
    pong, pings = _discover_pong_and_pings(events)

    request_events: dict[str, list[TransitionEvidence]] = {}
    reply_events: dict[str, list[TransitionEvidence]] = {}
    startup_witnesses: dict[str, list[TransitionEvidence] | None] = {}
    recurrence_witnesses: dict[str, list[TransitionEvidence] | None] = {}

    if pong is not None:
        for ping in pings:
            requests = [
                event
                for event in events
                if _is_request_event(event, ping=ping, pong=pong)
            ]
            replies = [
                event
                for event in events
                if _is_reply_event(event, pong=pong, ping=ping)
            ]
            request_events[ping] = requests
            reply_events[ping] = replies

            startup_witnesses[ping] = _find_first_request_from_initial(
                parsed_result,
                outgoing,
                ping=ping,
                pong=pong,
            )
            recurrence_witnesses[ping] = _find_recurrence_witness(
                outgoing,
                requests,
                ping=ping,
                pong=pong,
            )

    interleaving_state_id, interleaving_ping_owners = _find_interleaving_state(
        outgoing,
        pings=set(pings),
    )

    recurrent_scc = _find_protocol_recurrent_scc(
        parsed_result,
        events,
        pong=pong,
        pings=set(pings),
    )

    return ProtocolDiscovery(
        pong=pong,
        pings=pings,
        request_events=request_events,
        reply_events=reply_events,
        startup_witnesses=startup_witnesses,
        recurrence_witnesses=recurrence_witnesses,
        interleaving_state_id=interleaving_state_id,
        interleaving_ping_owners=interleaving_ping_owners,
        recurrent_scc_state_ids=recurrent_scc,
    )


class AllPingsToOnePongEvaluator(BaseSemanticEvaluator):
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
        discovery = _discover_protocol(parsed_result, events, outgoing)

        pong = discovery.pong
        pings = discovery.pings
        ping_set = set(pings)

        tests: list[SemanticTestResult] = []

        startup_found = {
            ping: discovery.startup_witnesses.get(ping) is not None for ping in pings
        }
        recurrence_found = {
            ping: discovery.recurrence_witnesses.get(ping) is not None for ping in pings
        }

        all_request_events = [
            event for ping in pings for event in discovery.request_events.get(ping, [])
        ]

        request_single_send_ok = (
            bool(all_request_events)
            and all(
                _request_count(event, ping=event.owner, pong=pong) == 1
                for event in all_request_events
            )
            if pong is not None
            else False
        )

        bad_reply_events = (
            [
                event
                for event in events
                if _bad_reply_routing(
                    event,
                    pong=pong,
                    known_pings=ping_set,
                )
            ]
            if pong is not None
            else []
        )

        pong_reply_ok = (
            pong is not None
            and len(pings) == EXPECTED_PING_COUNT
            and all(discovery.reply_events.get(ping) for ping in pings)
            and not bad_reply_events
        )

        # XA1
        tests.append(
            _test(
                "APOP-XA1",
                discovery.all_startup_observed,
                (
                    "Each logical Ping must autonomously reach a first request to "
                    "the shared Pong before any reply to that Ping."
                ),
                {
                    "expected_ping_count": EXPECTED_PING_COUNT,
                    "discovered_pings": pings,
                    "startup_found": startup_found,
                    "startup_witnesses": {
                        ping: _path_to_dict(discovery.startup_witnesses.get(ping))
                        for ping in pings
                    },
                },
                observed=bool(pings),
            )
        )

        # XA2
        tests.append(
            _test(
                "APOP-XA2",
                request_single_send_ok,
                (
                    "Every observed request-producing Ping transition must emit "
                    "exactly one request to the shared Pong."
                ),
                {
                    "request_event_count": len(all_request_events),
                    "per_ping_request_event_count": {
                        ping: len(discovery.request_events.get(ping, []))
                        for ping in pings
                    },
                    "violating_events": [
                        event.to_dict()
                        for event in all_request_events
                        if pong is not None
                        and _request_count(event, ping=event.owner, pong=pong) != 1
                    ],
                },
                observed=bool(all_request_events),
            )
        )

        # XA3
        tests.append(
            _test(
                "APOP-XA3",
                discovery.all_recurrence_observed,
                (
                    "For every logical Ping, a received reply must be followed by "
                    "a reachable next request from the same Ping to Pong."
                ),
                {
                    "recurrence_found": recurrence_found,
                    "recurrence_witnesses": {
                        ping: _path_to_dict(discovery.recurrence_witnesses.get(ping))
                        for ping in pings
                    },
                },
                observed=bool(pings),
            )
        )

        # XA4
        cross_ping_continuation_events: list[dict[str, Any]] = []
        if pong is not None:
            for event in events:
                if event.owner not in ping_set:
                    continue
                requests_to_pong = [
                    message
                    for message in event.added
                    if message.recipient == pong and message.sender in ping_set
                ]
                if any(message.sender != event.owner for message in requests_to_pong):
                    cross_ping_continuation_events.append(event.to_dict())

        tests.append(
            _test(
                "APOP-XA4",
                bool(pings) and not cross_ping_continuation_events,
                (
                    "A Ping transition must not create a request whose logical "
                    "sender is another Ping."
                ),
                {
                    "cross_ping_continuation_events": cross_ping_continuation_events,
                },
                observed=bool(pings),
            )
        )

        # XA5
        tests.append(
            _test(
                "APOP-XA5",
                pong_reply_ok,
                (
                    "Whenever the shared Pong consumes a request from Ping i, "
                    "it must emit exactly one reply to Ping i."
                ),
                {
                    "pong": pong,
                    "reply_event_count_by_ping": {
                        ping: len(discovery.reply_events.get(ping, []))
                        for ping in pings
                    },
                    "bad_reply_routing_events": [
                        event.to_dict() for event in bad_reply_events[:40]
                    ],
                },
                observed=pong is not None,
            )
        )

        # XA6
        multi_sender_ok = (
            pong is not None
            and len(pings) == EXPECTED_PING_COUNT
            and all(discovery.reply_events.get(ping) for ping in pings)
        )
        tests.append(
            _test(
                "APOP-XA6",
                multi_sender_ok,
                (
                    "The shared Pong must exhibit correct reply behavior for all "
                    "twelve distinct Ping senders."
                ),
                {
                    "pong": pong,
                    "supported_ping_senders": [
                        ping for ping in pings if discovery.reply_events.get(ping)
                    ],
                    "supported_sender_count": sum(
                        bool(discovery.reply_events.get(ping)) for ping in pings
                    ),
                },
                observed=pong is not None,
            )
        )

        # XI1
        all_to_one_ok = pong is not None and len(pings) == EXPECTED_PING_COUNT
        tests.append(
            _test(
                "APOP-XI1",
                all_to_one_ok,
                (
                    "Exactly twelve distinct logical Ping senders must communicate "
                    "with one common logical Pong."
                ),
                {
                    "expected_ping_count": EXPECTED_PING_COUNT,
                    "discovered_ping_count": len(pings),
                    "pings": pings,
                    "pong": pong,
                },
                observed=pong is not None or bool(pings),
            )
        )

        # XI2
        tests.append(
            _test(
                "APOP-XI2",
                discovery.all_startup_observed,
                (
                    "All twelve Ping roles must autonomously reach their first "
                    "request from initial state-space execution."
                ),
                {
                    "startup_found": startup_found,
                    "initial_state_ids": _initial_state_ids(parsed_result),
                },
                observed=bool(pings),
            )
        )

        # XI3
        tests.append(
            _test(
                "APOP-XI3",
                discovery.all_recurrence_observed,
                (
                    "For every Ping i, one connected execution must realize "
                    "request(i) -> reply(i) -> next request(i)."
                ),
                {
                    "recurrence_found": recurrence_found,
                    "witness_lengths": {
                        ping: (
                            len(discovery.recurrence_witnesses[ping])
                            if discovery.recurrence_witnesses.get(ping)
                            else None
                        )
                        for ping in pings
                    },
                },
                observed=bool(pings),
            )
        )

        # XI4
        sender_isolation_ok = pong is not None and bool(pings) and not bad_reply_events
        tests.append(
            _test(
                "APOP-XI4",
                sender_isolation_ok,
                (
                    "Pong must never route a consumed Ping i request to another "
                    "logical Ping."
                ),
                {
                    "bad_reply_routing_count": len(bad_reply_events),
                    "bad_reply_routing_events": [
                        event.to_dict() for event in bad_reply_events[:40]
                    ],
                },
                observed=pong is not None,
            )
        )

        # XI5
        interleaving_ok = (
            discovery.interleaving_state_id is not None
            and len(discovery.interleaving_ping_owners) >= 2
        )
        tests.append(
            _test(
                "APOP-XI5",
                interleaving_ok,
                (
                    "The state graph must expose at least one branching state "
                    "where two distinct Ping roles can independently progress."
                ),
                {
                    "branching_state_id": discovery.interleaving_state_id,
                    "enabled_ping_owners": discovery.interleaving_ping_owners,
                },
                observed=bool(pings),
            )
        )

        # XI6
        per_ping_cycle_ok = (
            discovery.all_recurrence_observed
            and request_single_send_ok
            and pong_reply_ok
            and not cross_ping_continuation_events
        )
        tests.append(
            _test(
                "APOP-XI6",
                per_ping_cycle_ok,
                (
                    "All twelve Ping cycles must preserve one-request/one-reply "
                    "recurrence without duplication or cross-Ping routing."
                ),
                {
                    "all_recurrence_observed": discovery.all_recurrence_observed,
                    "request_single_send_ok": request_single_send_ok,
                    "pong_reply_ok": pong_reply_ok,
                    "cross_ping_continuation_count": len(
                        cross_ping_continuation_events
                    ),
                },
                observed=bool(pings),
            )
        )

        # XSYS1
        tests.append(
            _test(
                "APOP-XSYS1",
                all_to_one_ok,
                (
                    "The protocol must expose twelve distinct Ping sender roles "
                    "and one shared Pong role; auxiliary rebecs are allowed."
                ),
                {
                    "observed_rebecs": sorted(_all_rebec_names(parsed_result)),
                    "logical_ping_roles": pings,
                    "logical_pong_role": pong,
                },
                observed=bool(states),
            )
        )

        # XSYS2
        tests.append(
            _test(
                "APOP-XSYS2",
                discovery.all_startup_observed,
                (
                    "Every logical Ping must reach its first request from the "
                    "generated model's initial state-space without harness input."
                ),
                {
                    "initial_state_ids": _initial_state_ids(parsed_result),
                    "startup_found": startup_found,
                },
                observed=bool(states),
            )
        )

        # XSYS3
        recurrent_system_ok = discovery.all_recurrence_observed and bool(
            discovery.recurrent_scc_state_ids
        )
        tests.append(
            _test(
                "APOP-XSYS3",
                recurrent_system_ok,
                (
                    "The full graph must contain protocol-active recurrence and "
                    "all twelve Ping roles must individually recur."
                ),
                {
                    "all_ping_recurrence_observed": (discovery.all_recurrence_observed),
                    "recurrent_scc_found": bool(discovery.recurrent_scc_state_ids),
                    "recurrent_scc_size": len(discovery.recurrent_scc_state_ids),
                    "recurrent_scc_state_ids_sample": (
                        discovery.recurrent_scc_state_ids[:80]
                    ),
                    "terminal_quiescence_expected": False,
                },
                observed=bool(transitions),
            )
        )

        # XSYS4
        complete_ok = all(
            [
                all_to_one_ok,
                discovery.all_startup_observed,
                per_ping_cycle_ok,
                interleaving_ok,
                recurrent_system_ok,
            ]
        )
        tests.append(
            _test(
                "APOP-XSYS4",
                complete_ok,
                (
                    "The complete untimed many-to-one contract must preserve "
                    "12-to-1 topology, autonomous startup, reply isolation, "
                    "per-Ping recurrence, interleaving, and recurrent operation."
                ),
                {
                    "all_to_one_ok": all_to_one_ok,
                    "automatic_startup_ok": discovery.all_startup_observed,
                    "per_ping_cycle_ok": per_ping_cycle_ok,
                    "interleaving_ok": interleaving_ok,
                    "recurrent_system_ok": recurrent_system_ok,
                    "timing_semantics_required": False,
                },
                observed=bool(states),
            )
        )

        issues: list[str] = []
        if not transitions:
            issues.append("NO_TRANSITIONS")
        if pong is None:
            issues.append("SHARED_PONG_NOT_DISCOVERED")
        if len(pings) != EXPECTED_PING_COUNT:
            issues.append("EXPECTED_12_PING_ROLES_NOT_DISCOVERED")
        if pings and not discovery.all_startup_observed:
            issues.append("INCOMPLETE_AUTOMATIC_STARTUP")
        if pings and not discovery.all_recurrence_observed:
            issues.append("INCOMPLETE_PER_PING_RECURRENCE")
        if bad_reply_events:
            issues.append("CROSS_PING_OR_INVALID_REPLY_ROUTING")
        if not discovery.recurrent_scc_state_ids:
            issues.append("PROTOCOL_RECURRENT_SCC_NOT_FOUND")
        if any(test.status == TestStatus.NOT_OBSERVED for test in tests):
            issues.append("INCOMPLETE_OBSERVABILITY")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "semantic_backend": "statespace",
                "semantic_scope": (
                    "scenario-bounded observational equivalence for the untimed "
                    "12-to-1 recurrent protocol"
                ),
                "timing_mode": "UNTIMED",
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": _initial_state_ids(parsed_result),
                "observed_rebecs": sorted(_all_rebec_names(parsed_result)),
                "logical_pong": pong,
                "logical_pings": pings,
                "logical_ping_count": len(pings),
                "expected_logical_ping_count": EXPECTED_PING_COUNT,
                "startup_found": startup_found,
                "recurrence_found": recurrence_found,
                "request_event_count_by_ping": {
                    ping: len(discovery.request_events.get(ping, [])) for ping in pings
                },
                "reply_event_count_by_ping": {
                    ping: len(discovery.reply_events.get(ping, [])) for ping in pings
                },
                "interleaving_state_id": discovery.interleaving_state_id,
                "interleaving_ping_owners": (discovery.interleaving_ping_owners),
                "recurrent_scc_size": len(discovery.recurrent_scc_state_ids),
                "recurrent_scc_state_ids_sample": (
                    discovery.recurrent_scc_state_ids[:80]
                ),
                "terminal_quiescence_required": False,
                "target_name_hard_coding": False,
            },
        )


def evaluate_all_pings_to_one_pong(
    parsed_result: dict[str, Any],
) -> dict[str, Any]:
    evaluator = AllPingsToOnePongEvaluator(
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
            "Evaluate the untimed twelve-Ping-to-one-Pong benchmark from "
            "normalized full RMC state-space JSON."
        )
    )
    parser.add_argument(
        "parsed_result",
        help="Path to parsed_statespace.json.",
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Optional semantic-result JSON path.",
    )
    arguments = parser.parse_args()

    try:
        parsed_result = load_json(arguments.parsed_result)
        result = evaluate_all_pings_to_one_pong(parsed_result)
        serialized = json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )

        if arguments.output:
            output_path = Path(arguments.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(
                serialized + "\n",
                encoding="utf-8",
            )
        else:
            print(serialized)

        return 0

    except Exception as exc:
        print(
            f"AllPingsToOnePong evaluator infrastructure error: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
