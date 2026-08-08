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
    get_rebec,
    get_state_by_id,
    get_states,
    get_transitions,
    normalize_name,
    transition_message,
    transition_owner,
)

BENCHMARK_ID = "ping_pong_periodic_untimed_finite"
EXPECTED_ROLES = 2
MODULUS = 5


@dataclass(frozen=True)
class QMsg:
    recipient: str
    raw: str
    label: str
    sender: str

    def as_dict(self) -> dict[str, str]:
        return {
            "recipient": self.recipient,
            "raw_message": self.raw,
            "message_label": self.label,
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


def _rebec_names(state: dict[str, Any] | None) -> list[str]:
    if not state:
        return []
    rebecs = state.get("rebecs", {})
    if isinstance(rebecs, dict):
        return [normalize_name(name) for name in rebecs]
    result = []
    if isinstance(rebecs, list):
        for rebec in rebecs:
            if not isinstance(rebec, dict):
                continue
            name = rebec.get("name") or rebec.get("id") or rebec.get("rebec")
            if name is not None:
                result.append(normalize_name(str(name)))
    return result


def _raw_message(message: dict[str, Any]) -> str:
    return str(
        message.get("message")
        or message.get("name")
        or message.get("message_name")
        or message.get("message_server")
        or ""
    ).strip()


def _label_from_raw(raw: str) -> str:
    return normalize_name(raw.replace(" ", ""))


def _message_label(message: dict[str, Any]) -> str:
    return _label_from_raw(_raw_message(message))


def _sender(message: dict[str, Any]) -> str:
    return normalize_name(str(message.get("sender") or ""))


def _queue_signatures(state, rebec):
    return [
        (_raw_message(m), _message_label(m), _sender(m))
        for m in get_queue(state, rebec)
    ]


def _positive_delta(left, right):
    delta = Counter(left) - Counter(right)
    out = []
    for item, count in delta.items():
        out.extend([item] * count)
    return out


def _message_base(value):
    text = normalize_name(str(value or "").replace(" ", ""))
    return text.split("(", 1)[0]


def _queue_delta(src, dst, owner="", handler=""):
    """
    Reconstruct one consumed message plus all messages emitted by a transition.

    A plain multiset difference is insufficient for self loops. For example:

        before: [Ping(sender=PING)]
        execute Ping()
        after:  [Ping(sender=PING)]

    means one Ping was consumed and one identical Ping was emitted, but
    Counter(before) - Counter(after) would report no change. We therefore
    identify the consumed handler message first, remove exactly one occurrence
    from the source queue, and only then compute additions.
    """
    removed = []
    added = []

    owner = normalize_name(owner)
    handler_base = _message_base(handler)

    for rebec in sorted(set(_rebec_names(src)) | set(_rebec_names(dst))):
        before = list(_queue_signatures(src, rebec))
        after = list(_queue_signatures(dst, rebec))
        remaining_before = list(before)

        consumed = None

        if rebec == owner and handler_base:
            for index, item in enumerate(remaining_before):
                raw, label, sender = item
                if (
                    _message_base(label) == handler_base
                    or _message_base(raw) == handler_base
                ):
                    consumed = remaining_before.pop(index)
                    removed.append(
                        QMsg(rebec, raw, label, sender)
                    )
                    break

        # If the handler message could not be reconstructed from the owner's
        # source queue, retain the conservative old multiset-delta behavior.
        if consumed is None:
            for raw, label, sender in _positive_delta(before, after):
                removed.append(
                    QMsg(rebec, raw, label, sender)
                )

            for raw, label, sender in _positive_delta(after, before):
                added.append(
                    QMsg(rebec, raw, label, sender)
                )

            continue

        # The consumed message has already been removed from remaining_before.
        # Any identical self-message present in `after` now appears as a genuine
        # addition rather than cancelling the consumption.
        for raw, label, sender in _positive_delta(
            remaining_before,
            after,
        ):
            removed.append(
                QMsg(rebec, raw, label, sender)
            )

        for raw, label, sender in _positive_delta(
            after,
            remaining_before,
        ):
            added.append(
                QMsg(rebec, raw, label, sender)
            )

    return removed, added


def _build_events(data):
    events = []
    outgoing = defaultdict(list)

    for transition in get_transitions(data):
        source = transition.get("source")
        destination = transition.get("destination")
        owner = transition_owner(transition)
        handler = transition_message(transition)

        removed, added = _queue_delta(
            get_state_by_id(data, source),
            get_state_by_id(data, destination),
            owner=owner,
            handler=handler,
        )

        event = Event(
            source=source,
            destination=destination,
            owner=owner,
            handler=handler,
            removed=removed,
            added=added,
        )
        events.append(event)
        outgoing[source].append(event)

    return events, outgoing


def _statevars(state, rebec_name):
    rebec = get_rebec(state, rebec_name)
    if not rebec:
        return {}
    return (
        rebec.get("state_variables")
        or rebec.get("statevars")
        or rebec.get("variables")
        or {}
    )


def _numeric(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    try:
        text = str(value).strip()
        if text.startswith("-"):
            return -int(text[1:])
        return int(text)
    except Exception:
        return None


def _discover_phase_variable(data, owner, candidate_events):
    """
    Discover a persistent numeric variable whose modulo-5 value advances by one
    on local-kind processing and remains stable on peer-kind processing.

    We do not require the variable to be named count or phase.
    """
    scores = defaultdict(lambda: {"progress": 0, "stable": 0, "bad": 0})

    for event in candidate_events:
        if event.owner != owner:
            continue

        src = get_state_by_id(data, event.source)
        dst = get_state_by_id(data, event.destination)
        before = _statevars(src, owner)
        after = _statevars(dst, owner)

        for name in set(before) & set(after):
            a = _numeric(before.get(name))
            b = _numeric(after.get(name))
            if a is None or b is None:
                continue

            key = normalize_name(str(name))
            if (b - a) % MODULUS == 1:
                scores[key]["progress"] += 1
            elif b == a:
                scores[key]["stable"] += 1
            else:
                scores[key]["bad"] += 1

    if not scores:
        return None

    ranked = sorted(
        scores.items(),
        key=lambda item: (
            -(item[1]["progress"]),
            item[1]["bad"],
            -(item[1]["stable"]),
            item[0],
        ),
    )

    name, score = ranked[0]
    if score["progress"] == 0:
        return None
    return name


def _get_numeric_statevar(state, rebec_name, normalized_var_name):
    if normalized_var_name is None:
        return None

    variables = _statevars(state, rebec_name)
    for name, value in variables.items():
        if normalize_name(str(name)) == normalized_var_name:
            return _numeric(value)
    return None


def _self_added(event):
    return [
        m for m in event.added
        if m.sender == event.owner and m.recipient == event.owner
    ]


def _cross_added(event):
    return [
        m for m in event.added
        if (
            m.sender == event.owner
            and m.recipient
            and m.recipient != event.owner
        )
    ]


def _consumed_by_owner(event):
    return [
        m for m in event.removed
        if m.recipient == event.owner
    ]


def _discover_roles(events):
    """
    A protocol role must exhibit both self-continuation and a cross-send using
    the same message label. Auxiliary bootstrap actors are thereby excluded.
    """
    self_kinds = defaultdict(set)
    cross_kinds = defaultdict(set)

    for event in events:
        for message in _self_added(event):
            self_kinds[event.owner].add(message.label)
        for message in _cross_added(event):
            cross_kinds[event.owner].add(message.label)

    candidates = []
    for owner in set(self_kinds) | set(cross_kinds):
        common = self_kinds[owner] & cross_kinds[owner]
        for kind in common:
            candidates.append((owner, kind))

    # Keep one strongest local kind per owner.
    by_owner = {}
    for owner, kind in candidates:
        score = sum(
            1
            for event in events
            if event.owner == owner
            and any(
                m.label == kind
                for m in (_self_added(event) + _cross_added(event))
            )
        )
        previous = by_owner.get(owner)
        if previous is None or score > previous[1]:
            by_owner[owner] = (kind, score)

    ranked = sorted(
        [(owner, kind, score) for owner, (kind, score) in by_owner.items()],
        key=lambda item: (-item[2], item[0], item[1]),
    )

    return ranked[:EXPECTED_ROLES]


def _protocol_messages(event, protocol_kinds):
    return [
        m for m in event.added
        if m.label in protocol_kinds
    ]


def _consumed_protocol(event, protocol_kinds):
    return [
        m for m in _consumed_by_owner(event)
        if m.label in protocol_kinds
    ]


def _initial_ids(data):
    ids = [_sid(state) for state in get_states(data) if _sid(state) is not None]
    if not ids:
        return []
    destinations = {t.get("destination") for t in get_transitions(data)}
    roots = [state_id for state_id in ids if state_id not in destinations]
    if roots:
        return roots
    if 0 in ids:
        return [0]
    return ids[:1]


def _reachable_states(outgoing, initial_ids):
    queue = deque(initial_ids)
    visited = set()

    while queue:
        state_id = queue.popleft()
        if state_id in visited:
            continue
        visited.add(state_id)
        for event in outgoing.get(state_id, []):
            queue.append(event.destination)

    return visited


def _sccs(data):
    adjacency = defaultdict(list)
    nodes = {
        _sid(state)
        for state in get_states(data)
        if _sid(state) is not None
    }

    for transition in get_transitions(data):
        source = transition.get("source")
        destination = transition.get("destination")
        nodes.add(source)
        nodes.add(destination)
        adjacency[source].append(destination)

    sys.setrecursionlimit(
        max(sys.getrecursionlimit(), len(nodes) * 2 + 100)
    )

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


def _test(test_id, passed, observed, description, evidence):
    status = (
        TestStatus.PASS
        if passed
        else TestStatus.FAIL
        if observed
        else TestStatus.NOT_OBSERVED
    )

    return SemanticTestResult(
        test_id=test_id,
        status=status,
        description=description,
        evidence=evidence,
    )


def _all_roles_observed(counter_map, roles):
    return (
        bool(roles)
        and all(counter_map.get(role, 0) > 0 for role in roles)
    )


def _has_definite_contract_violation(
    *,
    bad_local_progress,
    bad_self_continue,
    bad_boundary_cross,
    bad_boundary_echo,
    bad_offboundary_drop,
    fanout_bad,
    roles_complete,
    reciprocal_ok,
    cross_kind_preserved,
):
    """
    Return True only for a witnessed contradiction.

    Missing positive evidence is intentionally excluded. In particular, failure
    to discover a recurrent SCC in an exploration with an unbounded source
    counter is not treated as a semantic contradiction.
    """
    return any([
        bool(bad_local_progress),
        bool(bad_self_continue),
        bool(bad_boundary_cross),
        bool(bad_boundary_echo),
        bool(bad_offboundary_drop),
        bool(fanout_bad),
        roles_complete and not reciprocal_ok,
        roles_complete and not cross_kind_preserved,
    ])


class PingPongPeriodicUntimedFiniteEvaluator(BaseSemanticEvaluator):
    benchmark_id = BENCHMARK_ID

    def __init__(self, parsed_result, example_id=BENCHMARK_ID):
        super().__init__(
            parsed_result=parsed_result,
            example_id=example_id,
        )

    def evaluate(self, data):
        states = get_states(data)
        transitions = get_transitions(data)
        events, outgoing = _build_events(data)

        discovered = _discover_roles(events)
        roles = [owner for owner, _, _ in discovered]
        local_kind = {
            owner: kind
            for owner, kind, _ in discovered
        }
        protocol_kinds = set(local_kind.values())

        roles_complete = (
            len(roles) == EXPECTED_ROLES
            and len(set(roles)) == EXPECTED_ROLES
            and len(protocol_kinds) == EXPECTED_ROLES
        )

        peer = {}
        if roles_complete:
            peer[roles[0]] = roles[1]
            peer[roles[1]] = roles[0]

        phase_var = {
            role: _discover_phase_variable(
                data,
                role,
                events,
            )
            for role in roles
        }

        phase_vars_complete = (
            roles_complete
            and all(phase_var.get(role) for role in roles)
        )

        startup_events = defaultdict(list)
        local_events = defaultdict(list)
        peer_events = defaultdict(list)

        for event in events:
            if event.owner not in roles:
                continue

            consumed = _consumed_protocol(
                event,
                protocol_kinds,
            )

            if not consumed:
                self_out = [
                    m for m in _self_added(event)
                    if m.label == local_kind[event.owner]
                ]
                if self_out:
                    startup_events[event.owner].append(event)
                continue

            consumed_labels = {m.label for m in consumed}

            if local_kind[event.owner] in consumed_labels:
                local_events[event.owner].append(event)
            else:
                peer_events[event.owner].append(event)

        startup_ok_by_role = {}
        local_progress_ok_by_role = {}
        self_continue_ok_by_role = {}
        boundary_cross_ok_by_role = {}
        boundary_echo_ok_by_role = {}
        offboundary_drop_ok_by_role = {}

        bad_local_progress = []
        bad_self_continue = []
        bad_boundary_cross = []
        bad_boundary_echo = []
        bad_offboundary_drop = []

        observed_nonboundary = defaultdict(int)
        observed_boundary_local = defaultdict(int)
        observed_boundary_peer = defaultdict(int)
        observed_offboundary_peer = defaultdict(int)

        for role in roles:
            other = peer.get(role)
            kind = local_kind.get(role)
            peer_kind = local_kind.get(other)
            var = phase_var.get(role)

            startup_ok_by_role[role] = any(
                len([
                    m for m in _self_added(event)
                    if m.label == kind
                ]) == 1
                and len(_protocol_messages(event, protocol_kinds)) == 1
                for event in startup_events.get(role, [])
            )

            local_good = True
            self_good = True
            boundary_good = True

            for event in local_events.get(role, []):
                src = get_state_by_id(data, event.source)
                dst = get_state_by_id(data, event.destination)
                before = _get_numeric_statevar(src, role, var)
                after = _get_numeric_statevar(dst, role, var)

                if before is None or after is None:
                    local_good = False
                    bad_local_progress.append(event)
                    continue

                if (after - before) % MODULUS != 1:
                    local_good = False
                    bad_local_progress.append(event)
                    continue

                protocol_out = _protocol_messages(
                    event,
                    protocol_kinds,
                )

                if after % MODULUS != 0:
                    observed_nonboundary[role] += 1
                    correct = (
                        len(protocol_out) == 1
                        and protocol_out[0].recipient == role
                        and protocol_out[0].sender == role
                        and protocol_out[0].label == kind
                    )
                    if not correct:
                        self_good = False
                        bad_self_continue.append(event)
                else:
                    observed_boundary_local[role] += 1
                    correct = (
                        other is not None
                        and len(protocol_out) == 1
                        and protocol_out[0].recipient == other
                        and protocol_out[0].sender == role
                        and protocol_out[0].label == kind
                    )
                    if not correct:
                        boundary_good = False
                        bad_boundary_cross.append(event)

            local_progress_ok_by_role[role] = (
                bool(local_events.get(role))
                and local_good
            )
            self_continue_ok_by_role[role] = (
                observed_nonboundary[role] > 0
                and self_good
            )
            boundary_cross_ok_by_role[role] = (
                observed_boundary_local[role] > 0
                and boundary_good
            )

            echo_good = True
            drop_good = True

            for event in peer_events.get(role, []):
                src = get_state_by_id(data, event.source)
                dst = get_state_by_id(data, event.destination)
                before = _get_numeric_statevar(src, role, var)
                after = _get_numeric_statevar(dst, role, var)

                if before is None or after is None:
                    continue

                protocol_out = _protocol_messages(
                    event,
                    protocol_kinds,
                )

                phase_stable = (after % MODULUS) == (before % MODULUS)

                if before % MODULUS == 0:
                    observed_boundary_peer[role] += 1
                    correct = (
                        phase_stable
                        and other is not None
                        and len(protocol_out) == 1
                        and protocol_out[0].recipient == other
                        and protocol_out[0].sender == role
                        and protocol_out[0].label == peer_kind
                    )
                    if not correct:
                        echo_good = False
                        bad_boundary_echo.append(event)
                else:
                    observed_offboundary_peer[role] += 1
                    correct = (
                        phase_stable
                        and len(protocol_out) == 0
                    )
                    if not correct:
                        drop_good = False
                        bad_offboundary_drop.append(event)

            boundary_echo_ok_by_role[role] = (
                observed_boundary_peer[role] > 0
                and echo_good
            )
            offboundary_drop_ok_by_role[role] = (
                observed_offboundary_peer[role] > 0
                and drop_good
            )

        # Interaction-level routing from boundary local sends.
        reciprocal_ok = roles_complete
        cross_kind_preserved = roles_complete
        fanout_ok = True
        fanout_bad = []

        for event in events:
            protocol_out = _protocol_messages(
                event,
                protocol_kinds,
            )
            if len(protocol_out) > 1:
                fanout_ok = False
                fanout_bad.append(event)

        if roles_complete:
            for role in roles:
                other = peer[role]
                kind = local_kind[role]

                witnessed = False
                for event in local_events.get(role, []):
                    dst = get_state_by_id(data, event.destination)
                    after = _get_numeric_statevar(
                        dst,
                        role,
                        phase_var.get(role),
                    )
                    if after is None or after % MODULUS != 0:
                        continue

                    out = _protocol_messages(
                        event,
                        protocol_kinds,
                    )
                    if (
                        len(out) == 1
                        and out[0].recipient == other
                        and out[0].label == kind
                    ):
                        witnessed = True
                        break

                reciprocal_ok = reciprocal_ok and witnessed

                echo_witness = False
                for event in peer_events.get(role, []):
                    src = get_state_by_id(data, event.source)
                    before = _get_numeric_statevar(
                        src,
                        role,
                        phase_var.get(role),
                    )
                    if before is None or before % MODULUS != 0:
                        continue

                    consumed = _consumed_protocol(
                        event,
                        protocol_kinds,
                    )
                    out = _protocol_messages(
                        event,
                        protocol_kinds,
                    )

                    if (
                        len(consumed) >= 1
                        and len(out) == 1
                        and out[0].label == consumed[0].label
                        and out[0].recipient == other
                    ):
                        echo_witness = True
                        break

                cross_kind_preserved = (
                    cross_kind_preserved
                    and echo_witness
                )

        # SCC analysis.
        reachable = _reachable_states(
            outgoing,
            _initial_ids(data),
        )
        edge_pairs = {
            (t.get("source"), t.get("destination"))
            for t in transitions
        }

        recurrent_candidates = []

        for component in _sccs(data):
            component_set = set(component)

            cyclic = (
                len(component_set) > 1
                or any(
                    a == b and a in component_set
                    for a, b in edge_pairs
                )
            )
            if not cyclic:
                continue

            if not (component_set & reachable):
                continue

            owners = set()
            internal_protocol_events = []

            for event in events:
                if (
                    event.source in component_set
                    and event.destination in component_set
                    and event.owner in roles
                ):
                    if (
                        _consumed_protocol(event, protocol_kinds)
                        or _protocol_messages(event, protocol_kinds)
                    ):
                        owners.add(event.owner)
                        internal_protocol_events.append(event)

            if owners == set(roles):
                recurrent_candidates.append(
                    (
                        len(component_set),
                        sorted(component_set, key=str),
                        internal_protocol_events,
                    )
                )

        recurrent_candidates.sort(
            key=lambda item: item[0]
        )

        recurrent_co_progress = bool(recurrent_candidates)

        def five_step_coverage(component_states, component_events):
            component = set(component_states)
            coverage = {}

            for role in roles:
                phases_seen = set()
                nonboundary_seen = set()
                boundary_seen = False

                for event in component_events:
                    if event.owner != role:
                        continue
                    if (
                        event.source not in component
                        or event.destination not in component
                    ):
                        continue
                    if event not in local_events.get(role, []):
                        continue

                    dst = get_state_by_id(
                        data,
                        event.destination,
                    )
                    after = _get_numeric_statevar(
                        dst,
                        role,
                        phase_var.get(role),
                    )
                    if after is None:
                        continue

                    phase = after % MODULUS
                    phases_seen.add(phase)

                    out = _protocol_messages(
                        event,
                        protocol_kinds,
                    )

                    if phase == 0:
                        if (
                            len(out) == 1
                            and out[0].recipient == peer.get(role)
                            and out[0].label == local_kind.get(role)
                        ):
                            boundary_seen = True
                    else:
                        if (
                            len(out) == 1
                            and out[0].recipient == role
                            and out[0].label == local_kind.get(role)
                        ):
                            nonboundary_seen.add(phase)

                coverage[role] = {
                    "phases_seen": sorted(phases_seen),
                    "nonboundary_self_phases": sorted(nonboundary_seen),
                    "boundary_cross_seen": boundary_seen,
                    "full_five_step_coverage": (
                        phases_seen == {0, 1, 2, 3, 4}
                        and nonboundary_seen == {1, 2, 3, 4}
                        and boundary_seen
                    ),
                }

            return coverage

        candidate_diagnostics = []
        witness_candidate = None

        for size, states_in_component, events_in_component in recurrent_candidates:
            coverage = five_step_coverage(
                states_in_component,
                events_in_component,
            )

            full = (
                roles_complete
                and all(
                    coverage.get(role, {}).get(
                        "full_five_step_coverage",
                        False,
                    )
                    for role in roles
                )
            )

            candidate_diagnostics.append({
                "size": size,
                "state_ids_sample": states_in_component[:100],
                "coverage": coverage,
                "full_five_step_cycle": full,
            })

            if full and witness_candidate is None:
                witness_candidate = (
                    size,
                    states_in_component,
                    events_in_component,
                    coverage,
                )

        # The property is existential: use any recurrent SCC that witnesses the
        # complete five-step behavior. If none does, keep the largest candidate
        # for diagnostic evidence rather than arbitrarily choosing the smallest.
        if witness_candidate is not None:
            (
                _,
                recurrent_scc_states,
                recurrent_scc_events,
                recurrent_coverage,
            ) = witness_candidate
        elif recurrent_candidates:
            _, recurrent_scc_states, recurrent_scc_events = max(
                recurrent_candidates,
                key=lambda item: item[0],
            )
            recurrent_coverage = five_step_coverage(
                recurrent_scc_states,
                recurrent_scc_events,
            )
        else:
            recurrent_scc_states = []
            recurrent_scc_events = []
            recurrent_coverage = {}

        five_step_ok_by_role = {
            role: recurrent_coverage.get(role, {}).get(
                "full_five_step_coverage",
                False,
            )
            for role in roles
        }

        five_step_cycle_ok = (
            roles_complete
            and witness_candidate is not None
        )

        recurrent_nonamplifying = (
            recurrent_co_progress
            and all(
                len(
                    _protocol_messages(
                        event,
                        protocol_kinds,
                    )
                ) <= 1
                for event in recurrent_scc_events
            )
        )

        dual_startup_ok = (
            roles_complete
            and all(
                startup_ok_by_role.get(role, False)
                for role in roles
            )
        )

        local_progress_ok = (
            roles_complete
            and phase_vars_complete
            and all(
                local_progress_ok_by_role.get(role, False)
                for role in roles
            )
        )

        self_continue_ok = (
            roles_complete
            and all(
                self_continue_ok_by_role.get(role, False)
                for role in roles
            )
        )

        boundary_cross_ok = (
            roles_complete
            and all(
                boundary_cross_ok_by_role.get(role, False)
                for role in roles
            )
        )

        boundary_echo_ok = (
            roles_complete
            and all(
                boundary_echo_ok_by_role.get(role, False)
                for role in roles
            )
        )

        offboundary_drop_ok = (
            roles_complete
            and all(
                offboundary_drop_ok_by_role.get(role, False)
                for role in roles
            )
        )

        tests = []

        tests.append(_test(
            "PPUF-XA1",
            dual_startup_ok,
            any(startup_events.values()),
            "Each logical role must have startup behavior that seeds exactly one local protocol message.",
            {
                "roles": roles,
                "startup_event_counts": {
                    role: len(startup_events.get(role, []))
                    for role in roles
                },
                "startup_ok_by_role": dict(startup_ok_by_role),
            },
        ))

        tests.append(_test(
            "PPUF-XA2",
            local_progress_ok,
            phase_vars_complete and any(local_events.values()),
            "Processing local-kind messages must advance logical phase by one modulo five.",
            {
                "phase_variables": dict(phase_var),
                "local_progress_ok_by_role": dict(local_progress_ok_by_role),
                "bad_events": [
                    event.as_dict()
                    for event in bad_local_progress[:30]
                ],
            },
        ))

        tests.append(_test(
            "PPUF-XA3",
            self_continue_ok,
            any(observed_nonboundary.values()),
            "At phases 1..4, local processing must emit exactly one same-kind self-message.",
            {
                "observed_nonboundary_counts": dict(observed_nonboundary),
                "self_continue_ok_by_role": dict(self_continue_ok_by_role),
                "bad_events": [
                    event.as_dict()
                    for event in bad_self_continue[:30]
                ],
            },
        ))

        tests.append(_test(
            "PPUF-XA4",
            boundary_cross_ok,
            any(observed_boundary_local.values()),
            "At phase 0, local processing must emit exactly one same-kind message to the peer.",
            {
                "observed_boundary_local_counts": dict(observed_boundary_local),
                "boundary_cross_ok_by_role": dict(boundary_cross_ok_by_role),
                "bad_events": [
                    event.as_dict()
                    for event in bad_boundary_cross[:30]
                ],
            },
        ))

        tests.append(_test(
            "PPUF-XA5",
            boundary_echo_ok,
            any(observed_boundary_peer.values()),
            "At phase 0, a peer-kind input must be echoed unchanged back to the peer without changing phase.",
            {
                "observed_boundary_peer_counts": dict(observed_boundary_peer),
                "boundary_echo_ok_by_role": dict(boundary_echo_ok_by_role),
                "bad_events": [
                    event.as_dict()
                    for event in bad_boundary_echo[:30]
                ],
            },
        ))

        tests.append(_test(
            "PPUF-XA6",
            offboundary_drop_ok,
            _all_roles_observed(observed_offboundary_peer, roles),
            "Away from phase 0, a peer-kind input must be consumed without protocol output and without phase change.",
            {
                "observed_offboundary_peer_counts": dict(observed_offboundary_peer),
                "offboundary_drop_ok_by_role": dict(offboundary_drop_ok_by_role),
                "bad_events": [
                    event.as_dict()
                    for event in bad_offboundary_drop[:30]
                ],
            },
        ))

        tests.append(_test(
            "PPUF-XI1",
            roles_complete,
            bool(discovered),
            "Exactly two logical protocol roles must be discovered.",
            {
                "discovered_roles": discovered,
                "logical_roles": roles,
            },
        ))

        tests.append(_test(
            "PPUF-XI2",
            roles_complete and len(protocol_kinds) == 2,
            roles_complete,
            "The two roles must use distinct local protocol message kinds.",
            {
                "local_message_kind_by_role": dict(local_kind),
            },
        ))

        tests.append(_test(
            "PPUF-XI3",
            reciprocal_ok,
            roles_complete,
            "Each role's fifth-step cross-send must target the other logical role.",
            {
                "peer_map": dict(peer),
                "reciprocal_peer_routing": reciprocal_ok,
            },
        ))

        tests.append(_test(
            "PPUF-XI4",
            cross_kind_preserved,
            any(observed_boundary_peer.values()),
            "Boundary peer responses must preserve the consumed peer-message kind.",
            {
                "cross_echo_kind_preserved": cross_kind_preserved,
            },
        ))

        tests.append(_test(
            "PPUF-XI5",
            fanout_ok,
            bool(events),
            "No protocol transition may emit more than one protocol message.",
            {
                "bad_fanout_events": [
                    event.as_dict()
                    for event in fanout_bad[:30]
                ],
            },
        ))

        tests.append(_test(
            "PPUF-XSYS1",
            dual_startup_ok,
            any(startup_events.values()),
            "Reachable startup behavior must seed both independent local loops.",
            {
                "startup_ok_by_role": dict(startup_ok_by_role),
                "initial_state_ids": _initial_ids(data),
            },
        ))

        tests.append(_test(
            "PPUF-XSYS2",
            five_step_cycle_ok,
            recurrent_co_progress,
            "Each role must exhibit a recurrent modulo-five cycle with four self continuations followed by one peer send.",
            {
                "five_step_ok_by_role": dict(five_step_ok_by_role),
                "recurrent_scc_size": len(recurrent_scc_states),
            },
        ))

        tests.append(_test(
            "PPUF-XSYS3",
            recurrent_co_progress,
            recurrent_co_progress,
            "At least one reachable cyclic SCC must contain recurrent protocol progress by both logical roles.",
            {
                "recurrent_scc_size": len(recurrent_scc_states),
                "recurrent_scc_state_ids_sample": recurrent_scc_states[:100],
                "internal_protocol_owners": sorted({
                    event.owner
                    for event in recurrent_scc_events
                }),
            },
        ))

        tests.append(_test(
            "PPUF-XSYS4",
            recurrent_nonamplifying,
            recurrent_co_progress,
            "Recurrent protocol behavior must preserve the at-most-one-output non-amplification invariant.",
            {
                "recurrent_nonamplifying": recurrent_nonamplifying,
            },
        ))

        complete_ok = all([
            roles_complete,
            phase_vars_complete,
            dual_startup_ok,
            local_progress_ok,
            self_continue_ok,
            boundary_cross_ok,
            boundary_echo_ok,
            offboundary_drop_ok,
            reciprocal_ok,
            cross_kind_preserved,
            fanout_ok,
            five_step_cycle_ok,
            recurrent_co_progress,
            recurrent_nonamplifying,
        ])

        definite_contract_violation = _has_definite_contract_violation(
            bad_local_progress=bad_local_progress,
            bad_self_continue=bad_self_continue,
            bad_boundary_cross=bad_boundary_cross,
            bad_boundary_echo=bad_boundary_echo,
            bad_offboundary_drop=bad_offboundary_drop,
            fanout_bad=fanout_bad,
            roles_complete=roles_complete,
            reciprocal_ok=reciprocal_ok,
            cross_kind_preserved=cross_kind_preserved,
        )

        complete_contract_fully_observed = all([
            roles_complete,
            phase_vars_complete,
            dual_startup_ok,
            _all_roles_observed(observed_nonboundary, roles),
            _all_roles_observed(observed_boundary_local, roles),
            _all_roles_observed(observed_boundary_peer, roles),
            _all_roles_observed(observed_offboundary_peer, roles),
            recurrent_co_progress,
            five_step_cycle_ok,
        ])

        tests.append(_test(
            "PPUF-XSYS5",
            complete_ok,
            complete_contract_fully_observed or definite_contract_violation,
            "The complete untimed modulo-five periodic Ping/Pong contract must be preserved.",
            {
                "roles_complete": roles_complete,
                "phase_vars_complete": phase_vars_complete,
                "dual_startup_ok": dual_startup_ok,
                "local_progress_ok": local_progress_ok,
                "self_continue_ok": self_continue_ok,
                "boundary_cross_ok": boundary_cross_ok,
                "boundary_echo_ok": boundary_echo_ok,
                "offboundary_drop_ok": offboundary_drop_ok,
                "reciprocal_ok": reciprocal_ok,
                "cross_kind_preserved": cross_kind_preserved,
                "fanout_ok": fanout_ok,
                "five_step_cycle_ok": five_step_cycle_ok,
                "recurrent_co_progress": recurrent_co_progress,
                "recurrent_nonamplifying": recurrent_nonamplifying,
            },
        ))

        issues = []

        if not roles_complete:
            issues.append("INCOMPLETE_PROTOCOL_ROLE_DISCOVERY")
        if roles_complete and not phase_vars_complete:
            issues.append("PHASE_VARIABLE_NOT_OBSERVED")
        if phase_vars_complete and not local_progress_ok:
            issues.append("MOD5_LOCAL_PHASE_PROGRESSION_VIOLATION")
        if any(observed_nonboundary.values()) and not self_continue_ok:
            issues.append("NONBOUNDARY_SELF_CONTINUATION_VIOLATION")
        if any(observed_boundary_local.values()) and not boundary_cross_ok:
            issues.append("BOUNDARY_CROSS_SEND_VIOLATION")
        if any(observed_boundary_peer.values()) and not boundary_echo_ok:
            issues.append("BOUNDARY_PEER_ECHO_VIOLATION")
        if bad_offboundary_drop:
            issues.append("OFFBOUNDARY_PEER_DROP_VIOLATION")
        elif not _all_roles_observed(observed_offboundary_peer, roles):
            issues.append("OFFBOUNDARY_PEER_DROP_NOT_FULLY_OBSERVED")
        if roles_complete and not reciprocal_ok:
            issues.append("RECIPROCAL_PEER_ROUTING_VIOLATION")
        if not fanout_ok:
            issues.append("PROTOCOL_FANOUT_VIOLATION")
        if roles_complete and not recurrent_co_progress:
            issues.append("CO_PROGRESS_RECURRENT_COMPONENT_NOT_OBSERVED")
        if recurrent_co_progress and not five_step_cycle_ok:
            issues.append("FIVE_STEP_RECURRENT_CYCLE_NOT_OBSERVED")
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
                "evaluation_style": "mod5_transition_invariants_plus_recurrent_scc_v3_consumption_aware",
                "semantic_scope": (
                    "scenario-bounded observational equivalence for the "
                    "explicitly untimed finite modulo-five PingPongPeriodic abstraction"
                ),
                "timing_semantics_checked": False,
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": _initial_ids(data),
                "discovered_roles": discovered,
                "logical_roles": roles,
                "local_message_kind_by_role": dict(local_kind),
                "peer_map": dict(peer),
                "phase_variable_by_role": dict(phase_var),
                "modulus": MODULUS,
                "startup_ok_by_role": dict(startup_ok_by_role),
                "observed_nonboundary_counts": dict(observed_nonboundary),
                "observed_boundary_local_counts": dict(observed_boundary_local),
                "observed_boundary_peer_counts": dict(observed_boundary_peer),
                "observed_offboundary_peer_counts": dict(observed_offboundary_peer),
                "five_step_ok_by_role": dict(five_step_ok_by_role),
                "recurrent_scc_size": len(recurrent_scc_states),
                "recurrent_scc_state_ids_sample": recurrent_scc_states[:100],
                "recurrent_protocol_owners": sorted({
                    event.owner
                    for event in recurrent_scc_events
                }),
                "recurrent_scc_candidate_count": len(recurrent_candidates),
                "recurrent_scc_candidates": candidate_diagnostics,
                "target_name_hard_coding": False,
                "absolute_counter_required": False,
                "missing_positive_evidence_policy": "NOT_OBSERVED",
                "evaluator_version": "v3_consumption_aware_recurrent_witness",
                "raw_state_recurrence_policy": (
                    "Absence of an SCC is not a semantic contradiction when "
                    "positive recurrence is not observable in the explored raw state space."
                ),
            },
        )


def evaluate_ping_pong_periodic_untimed_finite(
    data: dict[str, Any],
) -> dict[str, Any]:
    return (
        PingPongPeriodicUntimedFiniteEvaluator(data)
        .evaluate(data)
        .to_dict()
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the untimed modulo-five Ping/Pong periodic protocol "
            "from normalized full RMC state-space JSON."
        )
    )
    parser.add_argument("parsed_result")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    try:
        data = json.loads(
            Path(args.parsed_result).read_text(
                encoding="utf-8"
            )
        )

        result = evaluate_ping_pong_periodic_untimed_finite(data)

        serialized = json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        )

        if args.output:
            output = Path(args.output)
            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            output.write_text(
                serialized + "\n",
                encoding="utf-8",
            )
        else:
            print(serialized)

        return 0

    except Exception as exc:
        print(
            "PingPongPeriodicUntimedFinite evaluator "
            f"infrastructure error: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
