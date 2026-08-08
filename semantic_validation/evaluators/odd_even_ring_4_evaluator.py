from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict, deque
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

BENCHMARK_ID = "odd_even_ring_4"
EXPECTED_PINGS = 2
EXPECTED_PONGS = 2
EXPECTED_ROLES = 4


@dataclass(frozen=True)
class QMsg:
    recipient: str
    raw: str
    name: str
    sender: str

    def as_dict(self) -> dict[str, str]:
        return {
            "recipient": self.recipient,
            "raw_message": self.raw,
            "message_name": self.name,
            "sender": self.sender,
        }


@dataclass
class Event:
    source: Any
    destination: Any
    owner: str
    handler: str
    removed: list[QMsg]
    added: list[QMsg]

    def as_dict(self) -> dict[str, Any]:
        return {
            "source_state_id": self.source,
            "destination_state_id": self.destination,
            "owner": self.owner,
            "message_server": self.handler,
            "removed_messages": [m.as_dict() for m in self.removed],
            "added_messages": [m.as_dict() for m in self.added],
        }


def _sid(state: dict[str, Any] | None) -> Any:
    if not state:
        return None
    return state.get("id") if state.get("id") is not None else state.get("state_id")


def _initial_ids(data: dict[str, Any]) -> list[Any]:
    ids = [_sid(s) for s in get_states(data) if _sid(s) is not None]
    if not ids:
        return []
    destinations = {t.get("destination") for t in get_transitions(data)}
    roots = [x for x in ids if x not in destinations]
    if roots:
        return roots
    if 0 in ids:
        return [0]
    return ids[:1]


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
            value = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
            if value is not None:
                result.append(normalize_name(str(value)))
    return result


def _all_rebecs(data: dict[str, Any]) -> list[str]:
    result: set[str] = set()
    for state in get_states(data):
        result.update(_rebec_names(state))
    return sorted(result)


def _raw_message(message: dict[str, Any]) -> str:
    return str(
        message.get("message")
        or message.get("name")
        or message.get("message_name")
        or message.get("message_server")
        or ""
    ).strip()


def _message_name(message: dict[str, Any]) -> str:
    raw = _raw_message(message)
    return normalize_name(raw.split("(", 1)[0])


def _sender(message: dict[str, Any]) -> str:
    return normalize_name(str(message.get("sender") or ""))


def _protocol_label_from_raw(raw: str) -> str:
    """
    Logical protocol-message label.

    Preserve arguments so encodings such as Token(0) and Token(1)
    remain distinguishable even when they share one message-server name.
    """
    return normalize_name(raw.replace(" ", ""))


def _protocol_label(message: QMsg) -> str:
    return _protocol_label_from_raw(message.raw)


def _queue_message_protocol_label(message: dict[str, Any]) -> str:
    return _protocol_label_from_raw(_raw_message(message))


def _queue_signatures(
    state: dict[str, Any] | None,
    rebec: str,
) -> list[tuple[str, str, str]]:
    return [
        (_raw_message(m), _message_name(m), _sender(m)) for m in get_queue(state, rebec)
    ]


def _positive_delta(left, right):
    delta = Counter(left) - Counter(right)
    out = []
    for item, count in delta.items():
        out.extend([item] * count)
    return out


def _queue_delta(src, dst):
    removed: list[QMsg] = []
    added: list[QMsg] = []

    for rebec in sorted(set(_rebec_names(src)) | set(_rebec_names(dst))):
        before = _queue_signatures(src, rebec)
        after = _queue_signatures(dst, rebec)

        for raw, name, sender in _positive_delta(before, after):
            removed.append(QMsg(rebec, raw, name, sender))

        for raw, name, sender in _positive_delta(after, before):
            added.append(QMsg(rebec, raw, name, sender))

    return removed, added


def _build_events(data):
    events: list[Event] = []
    outgoing: dict[Any, list[Event]] = defaultdict(list)

    for transition in get_transitions(data):
        source = transition.get("source")
        destination = transition.get("destination")
        removed, added = _queue_delta(
            get_state_by_id(data, source),
            get_state_by_id(data, destination),
        )
        event = Event(
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


def _cross_added(event: Event) -> list[QMsg]:
    return [
        message
        for message in event.added
        if (
            message.sender
            and message.recipient
            and message.sender != message.recipient
            and message.sender == event.owner
        )
    ]


def _cross_removed(event: Event) -> list[QMsg]:
    return [
        message
        for message in event.removed
        if (
            message.sender
            and message.recipient == event.owner
            and message.sender != event.owner
        )
    ]


def _single_cross_send(event: Event) -> QMsg | None:
    added = _cross_added(event)
    if len(added) != 1:
        return None
    return added[0]


def _discover_protocol_kinds(events: list[Event]):
    owners_by_kind: dict[str, set[str]] = defaultdict(set)
    event_count_by_kind: dict[str, int] = defaultdict(int)

    for event in events:
        message = _single_cross_send(event)
        if message is None or not message.name:
            continue
        owners_by_kind[_protocol_label(message)].add(event.owner)
        event_count_by_kind[_protocol_label(message)] += 1

    ranked = sorted(
        owners_by_kind,
        key=lambda kind: (
            -len(owners_by_kind[kind]),
            -event_count_by_kind[kind],
            kind,
        ),
    )

    if len(ranked) < 2:
        return None, None, {}, {}

    first, second = ranked[:2]
    return first, second, owners_by_kind, event_count_by_kind


def _protocol_events(
    events: list[Event],
    kinds: set[str],
) -> list[Event]:
    result = []
    for event in events:
        message = _single_cross_send(event)
        if message is not None and _protocol_label(message) in kinds:
            result.append(event)
    return result


def _startup_candidates(
    protocol_events: list[Event],
    protocol_kinds: set[str],
) -> list[Event]:
    candidates = []

    for event in protocol_events:
        consumed_protocol = [
            message
            for message in event.removed
            if _protocol_label(message) in protocol_kinds
        ]
        if not consumed_protocol:
            candidates.append(event)

    return candidates


def _orient_roles(
    kind_a: str | None,
    kind_b: str | None,
    owners_by_kind: dict[str, set[str]],
    protocol_events: list[Event],
):
    if kind_a is None or kind_b is None:
        return None, None, [], [], []

    kinds = {kind_a, kind_b}
    starts = _startup_candidates(protocol_events, kinds)

    start_owners_by_kind: dict[str, set[str]] = defaultdict(set)
    for event in starts:
        message = _single_cross_send(event)
        if message is not None:
            start_owners_by_kind[_protocol_label(message)].add(event.owner)

    score_a = len(start_owners_by_kind.get(kind_a, set()))
    score_b = len(start_owners_by_kind.get(kind_b, set()))

    if score_a and not score_b:
        ping_kind, pong_kind = kind_a, kind_b
    elif score_b and not score_a:
        ping_kind, pong_kind = kind_b, kind_a
    else:
        # Fallback: the source's Ping-role message kind should be associated
        # with the unique startup owner. If ambiguity remains, retain a
        # deterministic orientation and let startup tests expose it.
        ping_kind, pong_kind = kind_a, kind_b

    ping_roles = sorted(owners_by_kind.get(ping_kind, set()))
    pong_roles = sorted(owners_by_kind.get(pong_kind, set()))

    startup_owners = sorted(
        {
            event.owner
            for event in starts
            if (
                (message := _single_cross_send(event)) is not None
                and _protocol_label(message) == ping_kind
            )
        }
    )

    return ping_kind, pong_kind, ping_roles, pong_roles, startup_owners


def _build_successors(
    protocol_events: list[Event],
    role_kind: dict[str, str],
):
    successors: dict[str, set[str]] = defaultdict(set)
    bad_events: list[Event] = []

    for event in protocol_events:
        expected_kind = role_kind.get(event.owner)
        if expected_kind is None:
            continue

        message = _single_cross_send(event)
        if message is None:
            bad_events.append(event)
            continue

        if _protocol_label(message) != expected_kind:
            bad_events.append(event)
            continue

        successors[event.owner].add(message.recipient)

    return {k: set(v) for k, v in successors.items()}, bad_events


def _ring_order(
    start: str | None,
    roles: set[str],
    successors: dict[str, set[str]],
):
    if start is None or start not in roles:
        return []

    order = []
    current = start

    for _ in range(len(roles)):
        if current in order:
            return []
        order.append(current)

        nexts = successors.get(current, set())
        if len(nexts) != 1:
            return []
        current = next(iter(nexts))

    if current != start:
        return []

    if set(order) != roles:
        return []

    return order


def _predecessor_degrees(
    roles: set[str],
    successors: dict[str, set[str]],
):
    indegree = {role: 0 for role in roles}
    for owner in roles:
        for destination in successors.get(owner, set()):
            if destination in indegree:
                indegree[destination] += 1
    return indegree


def _event_consumed_protocol_kind(
    event: Event,
    protocol_kinds: set[str],
) -> list[str]:
    return [
        _protocol_label(message)
        for message in event.removed
        if _protocol_label(message) in protocol_kinds
    ]


def _actor_transform_checks(
    protocol_events: list[Event],
    ping_roles: set[str],
    pong_roles: set[str],
    ping_kind: str | None,
    pong_kind: str | None,
    successors: dict[str, set[str]],
):
    ping_observed = set()
    pong_observed = set()
    bad_ping: list[Event] = []
    bad_pong: list[Event] = []
    bad_multiplicity: list[Event] = []

    if ping_kind is None or pong_kind is None:
        return ping_observed, pong_observed, bad_ping, bad_pong, bad_multiplicity

    protocol_kinds = {ping_kind, pong_kind}

    for event in protocol_events:
        outgoing = _cross_added(event)
        if len(outgoing) != 1:
            bad_multiplicity.append(event)
            continue

        consumed = _event_consumed_protocol_kind(
            event,
            protocol_kinds,
        )

        if event.owner in ping_roles:
            # Ignore startup here; steady reachable Ping-role behavior consumes Pong.
            if not consumed:
                continue
            ping_observed.add(event.owner)
            expected_successor = successors.get(event.owner, set())
            if not (
                pong_kind in consumed
                and _protocol_label(outgoing[0]) == ping_kind
                and outgoing[0].recipient in expected_successor
            ):
                bad_ping.append(event)

        elif event.owner in pong_roles:
            if not consumed:
                continue
            pong_observed.add(event.owner)
            expected_successor = successors.get(event.owner, set())
            if not (
                ping_kind in consumed
                and _protocol_label(outgoing[0]) == pong_kind
                and outgoing[0].recipient in expected_successor
            ):
                bad_pong.append(event)

    return ping_observed, pong_observed, bad_ping, bad_pong, bad_multiplicity


def _sccs(data):
    adjacency: dict[Any, list[Any]] = defaultdict(list)
    nodes = {_sid(state) for state in get_states(data) if _sid(state) is not None}

    for transition in get_transitions(data):
        source = transition.get("source")
        destination = transition.get("destination")
        nodes.add(source)
        nodes.add(destination)
        adjacency[source].append(destination)

    sys.setrecursionlimit(max(sys.getrecursionlimit(), len(nodes) * 2 + 100))

    index = 0
    stack = []
    on_stack = set()
    indices = {}
    low = {}
    components = []

    def strongconnect(node):
        nonlocal index
        indices[node] = index
        low[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for nxt in adjacency.get(node, []):
            if nxt not in indices:
                strongconnect(nxt)
                low[node] = min(low[node], low[nxt])
            elif nxt in on_stack:
                low[node] = min(low[node], indices[nxt])

        if low[node] == indices[node]:
            component = []
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


def _select_recurrent_scc(
    data,
    events: list[Event],
    roles: set[str],
    protocol_kinds: set[str],
):
    by_source: dict[Any, list[Event]] = defaultdict(list)
    for event in events:
        by_source[event.source].append(event)

    edge_pairs = {
        (t.get("source"), t.get("destination")) for t in get_transitions(data)
    }

    candidates = []

    for component in _sccs(data):
        states = set(component)
        cyclic = len(states) > 1 or any(a == b and a in states for a, b in edge_pairs)
        if not cyclic:
            continue

        owners = set()
        internal_protocol_events = []

        for state_id in states:
            for event in by_source.get(state_id, []):
                if event.destination not in states:
                    continue
                message = _single_cross_send(event)
                if (
                    event.owner in roles
                    and message is not None
                    and _protocol_label(message) in protocol_kinds
                ):
                    owners.add(event.owner)
                    internal_protocol_events.append(event)

        if owners == roles:
            candidates.append(
                (len(states), sorted(states, key=str), internal_protocol_events)
            )

    if not candidates:
        return [], []

    # Prefer the smallest stable recurrent component that covers all roles.
    candidates.sort(key=lambda item: item[0])
    _, states, internal_events = candidates[0]
    return states, internal_events


def _protocol_projection(
    data,
    state_id,
    roles: set[str],
    protocol_kinds: set[str],
):
    state = get_state_by_id(data, state_id)
    projection = []

    for role in sorted(roles):
        for message in get_queue(state, role):
            label = _queue_message_protocol_label(message)
            if label in protocol_kinds:
                projection.append(
                    (
                        role,
                        label,
                        _sender(message),
                    )
                )

    return tuple(sorted(projection))


def _token_counts(
    data,
    state_ids: list[Any],
    roles: set[str],
    protocol_kinds: set[str],
):
    counts = {}
    for state_id in state_ids:
        counts[state_id] = len(
            _protocol_projection(
                data,
                state_id,
                roles,
                protocol_kinds,
            )
        )
    return counts


def _find_full_round_witness(
    data,
    outgoing: dict[Any, list[Event]],
    scc_state_ids: list[Any],
    roles: set[str],
    successors: dict[str, set[str]],
    role_kind: dict[str, str],
    protocol_kinds: set[str],
):
    if not scc_state_ids or len(roles) != EXPECTED_ROLES:
        return None

    scc = set(scc_state_ids)

    def is_protocol_event(event: Event) -> bool:
        message = _single_cross_send(event)
        return (
            event.owner in roles
            and message is not None
            and _protocol_label(message) == role_kind.get(event.owner)
            and message.recipient in successors.get(event.owner, set())
        )

    for start_state in scc_state_ids:
        start_projection = _protocol_projection(
            data, start_state, roles, protocol_kinds
        )

        first_events = [
            event
            for event in outgoing.get(start_state, [])
            if event.destination in scc and is_protocol_event(event)
        ]

        for first in first_events:
            path = [first]
            nexts = successors.get(first.owner, set())
            if len(nexts) != 1:
                continue
            expected_owner = next(iter(nexts))

            queue = deque(
                [
                    (
                        first.destination,
                        1,
                        expected_owner,
                        path,
                    )
                ]
            )
            visited = set()

            while queue:
                state_id, steps, expected, current_path = queue.popleft()
                marker = (state_id, steps, expected)
                if marker in visited:
                    continue
                visited.add(marker)

                if steps == EXPECTED_ROLES:
                    if (
                        _protocol_projection(
                            data,
                            state_id,
                            roles,
                            protocol_kinds,
                        )
                        == start_projection
                    ):
                        return current_path
                    continue

                for event in outgoing.get(state_id, []):
                    if event.destination not in scc:
                        continue

                    if is_protocol_event(event):
                        if event.owner != expected:
                            continue
                        nexts = successors.get(event.owner, set())
                        if len(nexts) != 1:
                            continue
                        next_expected = next(iter(nexts))
                        queue.append(
                            (
                                event.destination,
                                steps + 1,
                                next_expected,
                                current_path + [event],
                            )
                        )
                    else:
                        # Protocol-neutral internal transition.
                        queue.append(
                            (
                                event.destination,
                                steps,
                                expected,
                                current_path + [event],
                            )
                        )

    return None


def _reachable_to_scc(
    outgoing: dict[Any, list[Event]],
    initial: list[Any],
    target_states: set[Any],
):
    if not initial or not target_states:
        return False

    queue = deque(initial)
    visited = set()

    while queue:
        state_id = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)

        if state_id in target_states:
            return True

        for event in outgoing.get(state_id, []):
            queue.append(event.destination)

    return False


def _path_json(path):
    return [event.as_dict() for event in (path or [])[:80]]


def _test(test_id, passed, observed, description, evidence):
    if passed:
        status = TestStatus.PASS
    elif observed:
        status = TestStatus.FAIL
    else:
        status = TestStatus.NOT_OBSERVED

    return SemanticTestResult(
        test_id=test_id,
        status=status,
        description=description,
        evidence=evidence,
    )


class OddEvenRingEvaluator(BaseSemanticEvaluator):
    benchmark_id = BENCHMARK_ID

    def __init__(
        self,
        parsed_result: dict[str, Any],
        example_id: str = BENCHMARK_ID,
    ):
        super().__init__(
            parsed_result=parsed_result,
            example_id=example_id,
        )

    def evaluate(
        self,
        data: dict[str, Any],
    ) -> SemanticEvaluationResult:
        states = get_states(data)
        transitions = get_transitions(data)
        events, outgoing = _build_events(data)

        kind_a, kind_b, owners_by_kind, kind_counts = _discover_protocol_kinds(events)

        raw_protocol_kinds = {kind for kind in (kind_a, kind_b) if kind is not None}

        protocol_events = _protocol_events(
            events,
            raw_protocol_kinds,
        )

        (
            ping_kind,
            pong_kind,
            ping_roles,
            pong_roles,
            startup_owners,
        ) = _orient_roles(
            kind_a,
            kind_b,
            owners_by_kind,
            protocol_events,
        )

        ping_set = set(ping_roles)
        pong_set = set(pong_roles)
        roles = ping_set | pong_set
        protocol_kinds = {kind for kind in (ping_kind, pong_kind) if kind is not None}

        roles_complete = (
            len(ping_roles) == EXPECTED_PINGS
            and len(pong_roles) == EXPECTED_PONGS
            and len(roles) == EXPECTED_ROLES
            and ping_set.isdisjoint(pong_set)
        )

        role_kind = {}
        if ping_kind is not None:
            role_kind.update({role: ping_kind for role in ping_roles})
        if pong_kind is not None:
            role_kind.update({role: pong_kind for role in pong_roles})

        successors, bad_successor_events = _build_successors(
            protocol_events,
            role_kind,
        )

        indegree = _predecessor_degrees(
            roles,
            successors,
        )

        unique_successor = roles_complete and all(
            len(successors.get(role, set())) == 1 for role in roles
        )
        unique_predecessor = roles_complete and all(
            indegree.get(role, 0) == 1 for role in roles
        )

        unique_startup = (
            roles_complete
            and len(startup_owners) == 1
            and startup_owners[0] in ping_set
        )
        start_role = startup_owners[0] if len(startup_owners) == 1 else None

        order = _ring_order(
            start_role,
            roles,
            successors,
        )

        directed_ring_ok = (
            roles_complete
            and unique_successor
            and unique_predecessor
            and len(order) == EXPECTED_ROLES
        )

        alternating_roles_ok = directed_ring_ok and all(
            (owner in ping_set and next(iter(successors[owner])) in pong_set)
            or (owner in pong_set and next(iter(successors[owner])) in ping_set)
            for owner in roles
        )

        message_role_ok = (
            roles_complete
            and ping_kind is not None
            and pong_kind is not None
            and ping_kind != pong_kind
            and all(role_kind.get(role) == ping_kind for role in ping_set)
            and all(role_kind.get(role) == pong_kind for role in pong_set)
        )

        (
            ping_transform_observed,
            pong_transform_observed,
            bad_ping_transforms,
            bad_pong_transforms,
            bad_multiplicity,
        ) = _actor_transform_checks(
            protocol_events,
            ping_set,
            pong_set,
            ping_kind,
            pong_kind,
            successors,
        )

        ping_transform_complete = (
            roles_complete
            and ping_transform_observed == ping_set
            and not bad_ping_transforms
        )
        pong_transform_complete = (
            roles_complete
            and pong_transform_observed == pong_set
            and not bad_pong_transforms
        )

        single_send_ok = (
            roles_complete
            and not bad_successor_events
            and not bad_multiplicity
            and all(
                len(_cross_added(event)) == 1
                for event in protocol_events
                if event.owner in roles
            )
        )

        scc_states, scc_events = _select_recurrent_scc(
            data,
            events,
            roles,
            protocol_kinds,
        )

        recurrent_scc_ok = roles_complete and bool(scc_states)

        setup_reaches_ring = recurrent_scc_ok and _reachable_to_scc(
            outgoing,
            _initial_ids(data),
            set(scc_states),
        )

        token_counts = (
            _token_counts(
                data,
                scc_states,
                roles,
                protocol_kinds,
            )
            if scc_states
            else {}
        )

        single_token_ok = (
            recurrent_scc_ok
            and bool(token_counts)
            and all(count == 1 for count in token_counts.values())
        )

        terminal_in_scc = [
            state_id
            for state_id in scc_states
            if not any(
                event.destination in set(scc_states)
                for event in outgoing.get(state_id, [])
            )
        ]

        no_terminal = recurrent_scc_ok and not terminal_in_scc

        full_round = _find_full_round_witness(
            data,
            outgoing,
            scc_states,
            roles,
            successors,
            role_kind,
            protocol_kinds,
        )

        full_round_ok = full_round is not None

        startup_events = (
            [
                event
                for event in protocol_events
                if event.owner == start_role
                and not _event_consumed_protocol_kind(
                    event,
                    protocol_kinds,
                )
            ]
            if start_role is not None
            else []
        )

        startup_single_send_ok = (
            unique_startup
            and bool(startup_events)
            and all(
                len(_cross_added(event)) == 1
                and _protocol_label(_single_cross_send(event)) == ping_kind
                and _single_cross_send(event).recipient
                in successors.get(start_role, set())
                for event in startup_events
            )
        )

        tests = []

        tests.append(
            _test(
                "OER4-XA1",
                startup_single_send_ok,
                unique_startup or bool(startup_events),
                "The unique startup Ping role must emit exactly one Ping-type message to its successor.",
                {
                    "startup_owners": startup_owners,
                    "startup_events": [e.as_dict() for e in startup_events[:20]],
                    "ping_message_kind": ping_kind,
                },
            )
        )

        tests.append(
            _test(
                "OER4-XA2",
                ping_transform_complete,
                bool(ping_transform_observed) or bool(bad_ping_transforms),
                "Each reachable steady Ping role must transform Pong-type input into one Ping-type successor message.",
                {
                    "observed_ping_roles": sorted(ping_transform_observed),
                    "expected_ping_roles": ping_roles,
                    "bad_events": [e.as_dict() for e in bad_ping_transforms[:30]],
                },
            )
        )

        tests.append(
            _test(
                "OER4-XA3",
                pong_transform_complete,
                bool(pong_transform_observed) or bool(bad_pong_transforms),
                "Each Pong role must transform Ping-type input into one Pong-type message to its configured successor.",
                {
                    "observed_pong_roles": sorted(pong_transform_observed),
                    "expected_pong_roles": pong_roles,
                    "bad_events": [e.as_dict() for e in bad_pong_transforms[:30]],
                },
            )
        )

        tests.append(
            _test(
                "OER4-XA4",
                single_send_ok,
                bool(protocol_events),
                "Every protocol transition must preserve single-token multiplicity with one successor send.",
                {
                    "bad_successor_events": [
                        e.as_dict() for e in bad_successor_events[:30]
                    ],
                    "bad_multiplicity_events": [
                        e.as_dict() for e in bad_multiplicity[:30]
                    ],
                },
            )
        )

        tests.append(
            _test(
                "OER4-XI1",
                roles_complete,
                bool(protocol_events),
                "Two Ping roles and two Pong roles must be discovered.",
                {
                    "ping_roles": ping_roles,
                    "pong_roles": pong_roles,
                    "ping_count": len(ping_roles),
                    "pong_count": len(pong_roles),
                    "protocol_kind_owner_counts": {
                        kind: len(owners) for kind, owners in owners_by_kind.items()
                    },
                },
            )
        )

        tests.append(
            _test(
                "OER4-XI2",
                directed_ring_ok,
                roles_complete,
                "All 4 roles must form one directed cycle with one successor and one predecessor each.",
                {
                    "successors": {
                        role: sorted(successors.get(role, set()))
                        for role in sorted(roles)
                    },
                    "predecessor_degrees": indegree,
                    "ring_order": order,
                },
            )
        )

        tests.append(
            _test(
                "OER4-XI3",
                alternating_roles_ok,
                directed_ring_ok,
                "Ping and Pong roles must alternate on every ring edge.",
                {
                    "ring_order": order,
                    "ping_roles": ping_roles,
                    "pong_roles": pong_roles,
                },
            )
        )

        tests.append(
            _test(
                "OER4-XI4",
                message_role_ok,
                roles_complete,
                "Ping roles and Pong roles must use two distinct alternating protocol message kinds.",
                {
                    "ping_message_kind": ping_kind,
                    "pong_message_kind": pong_kind,
                    "kind_event_counts": dict(kind_counts),
                },
            )
        )

        tests.append(
            _test(
                "OER4-XI5",
                unique_startup,
                bool(startup_owners),
                "Exactly one logical Ping role must initiate protocol traffic.",
                {
                    "startup_owners": startup_owners,
                    "startup_owner_count": len(startup_owners),
                },
            )
        )

        tests.append(
            _test(
                "OER4-XI6",
                full_round_ok,
                recurrent_scc_ok,
                "Stable initialized execution must contain a full 4-role round returning to the same observable token projection.",
                {
                    "recurrent_scc_size": len(scc_states),
                    "round_witness": _path_json(full_round),
                },
            )
        )

        tests.append(
            _test(
                "OER4-XSYS1",
                roles_complete,
                bool(states),
                "The initialized protocol must expose two Ping and two Pong roles.",
                {
                    "observed_rebecs": _all_rebecs(data),
                    "logical_ping_roles": ping_roles,
                    "logical_pong_roles": pong_roles,
                },
            )
        )

        tests.append(
            _test(
                "OER4-XSYS2",
                setup_reaches_ring,
                recurrent_scc_ok,
                "Initial execution must reach the stable initialized recurrent ring after setup/warm-up.",
                {
                    "initial_state_ids": _initial_ids(data),
                    "recurrent_scc_size": len(scc_states),
                    "reachable": setup_reaches_ring,
                },
            )
        )

        tests.append(
            _test(
                "OER4-XSYS3",
                recurrent_scc_ok,
                bool(transitions),
                "A reachable cyclic SCC must contain recurrent protocol progress for all four logical roles.",
                {
                    "recurrent_scc_size": len(scc_states),
                    "recurrent_scc_state_ids_sample": scc_states[:100],
                    "internal_protocol_event_owners": sorted(
                        {event.owner for event in scc_events}
                    ),
                },
            )
        )

        tests.append(
            _test(
                "OER4-XSYS4",
                single_token_ok,
                recurrent_scc_ok,
                "Every state in the selected stable recurrent component must contain exactly one logical protocol token.",
                {
                    "token_count_values": sorted(set(token_counts.values())),
                    "violating_states_sample": [
                        {"state_id": state_id, "token_count": count}
                        for state_id, count in token_counts.items()
                        if count != 1
                    ][:50],
                },
            )
        )

        tests.append(
            _test(
                "OER4-XSYS5",
                no_terminal,
                recurrent_scc_ok,
                "The selected recurrent component must contain no terminal/quiescent protocol state.",
                {
                    "terminal_states_inside_recurrent_scc": terminal_in_scc,
                },
            )
        )

        complete_ok = all(
            [
                roles_complete,
                directed_ring_ok,
                alternating_roles_ok,
                message_role_ok,
                unique_startup,
                startup_single_send_ok,
                ping_transform_complete,
                pong_transform_complete,
                single_send_ok,
                setup_reaches_ring,
                recurrent_scc_ok,
                single_token_ok,
                no_terminal,
                full_round_ok,
            ]
        )

        tests.append(
            _test(
                "OER4-XSYS6",
                complete_ok,
                roles_complete and directed_ring_ok,
                "The complete initialized Odd-Even recurrent-ring contract must be preserved.",
                {
                    "roles_complete": roles_complete,
                    "directed_ring_ok": directed_ring_ok,
                    "alternating_roles_ok": alternating_roles_ok,
                    "message_role_ok": message_role_ok,
                    "unique_startup": unique_startup,
                    "startup_single_send_ok": startup_single_send_ok,
                    "ping_transform_complete": ping_transform_complete,
                    "pong_transform_complete": pong_transform_complete,
                    "single_send_ok": single_send_ok,
                    "setup_reaches_ring": setup_reaches_ring,
                    "recurrent_scc_ok": recurrent_scc_ok,
                    "single_token_ok": single_token_ok,
                    "no_terminal": no_terminal,
                    "full_round_ok": full_round_ok,
                },
            )
        )

        issues = []
        if not transitions:
            issues.append("NO_TRANSITIONS")
        if not roles_complete:
            issues.append("INCOMPLETE_PROTOCOL_ROLE_DISCOVERY")
        if roles_complete and not directed_ring_ok:
            issues.append("DIRECTED_RING_TOPOLOGY_VIOLATION")
        if directed_ring_ok and not alternating_roles_ok:
            issues.append("ROLE_ALTERNATION_VIOLATION")
        if roles_complete and not message_role_ok:
            issues.append("MESSAGE_ROLE_ALTERNATION_VIOLATION")
        if startup_owners and not unique_startup:
            issues.append("MULTIPLE_OR_INVALID_STARTUP_ROLES")
        if bad_ping_transforms:
            issues.append("PING_ROLE_TRANSFORMATION_VIOLATION")
        if bad_pong_transforms:
            issues.append("PONG_ROLE_TRANSFORMATION_VIOLATION")
        if bad_multiplicity or bad_successor_events:
            issues.append("PROTOCOL_TOKEN_MULTIPLICITY_OR_ROUTING_VIOLATION")
        if roles_complete and not recurrent_scc_ok:
            issues.append("RECURRENT_COMPONENT_NOT_OBSERVED")
        if recurrent_scc_ok and not single_token_ok:
            issues.append("SINGLE_TOKEN_CONSERVATION_VIOLATION")
        if recurrent_scc_ok and not full_round_ok:
            issues.append("FULL_STEADY_ROUND_NOT_OBSERVED")
        if any(test.status == TestStatus.NOT_OBSERVED for test in tests):
            issues.append("INCOMPLETE_OBSERVABILITY")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "semantic_backend": "statespace",
                "evaluation_style": "initialized_recurrent_scc_plus_observable_projection",
                "semantic_scope": "scenario-bounded observational equivalence for OddEvenRingApp reduced 4-actor scenario",
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": _initial_ids(data),
                "observed_rebecs": _all_rebecs(data),
                "ping_message_kind": ping_kind,
                "pong_message_kind": pong_kind,
                "logical_ping_roles": ping_roles,
                "logical_pong_roles": pong_roles,
                "logical_ping_count": len(ping_roles),
                "logical_pong_count": len(pong_roles),
                "startup_owners": startup_owners,
                "successors": {
                    role: sorted(successors.get(role, set())) for role in sorted(roles)
                },
                "predecessor_degrees": indegree,
                "ring_order": order,
                "recurrent_scc_size": len(scc_states),
                "recurrent_scc_state_ids_sample": scc_states[:100],
                "token_count_values_in_recurrent_scc": sorted(
                    set(token_counts.values())
                ),
                "full_round_observed": full_round_ok,
                "full_round_witness": _path_json(full_round),
                "setup_reaches_recurrent_ring": setup_reaches_ring,
                "target_name_hard_coding": False,
                "setneighbor_required_in_target": False,
                "missing_positive_evidence_policy": "NOT_OBSERVED",
            },
        )


def evaluate_odd_even_ring(data: dict[str, Any]) -> dict[str, Any]:
    return OddEvenRingEvaluator(data).evaluate(data).to_dict()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Evaluate reduced 4-actor Odd-Even Ring from normalized full RMC state-space JSON."
    )
    parser.add_argument("parsed_result")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.parsed_result).read_text(encoding="utf-8"))
        result = evaluate_odd_even_ring(data)
        serialized = json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )

        if args.output:
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                serialized + "\n",
                encoding="utf-8",
            )
        else:
            print(serialized)

        return 0

    except Exception as exc:
        print(
            f"OddEvenRing evaluator infrastructure error: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
