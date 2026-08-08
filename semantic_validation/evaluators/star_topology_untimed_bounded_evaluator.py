from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
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

BENCHMARK_ID = "star_topology_untimed_bounded"
EXPECTED_CLIENTS = 5


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
    return (
        state.get("id")
        if state.get("id") is not None
        else state.get("state_id")
    )


def _rebec_names(state: dict[str, Any] | None) -> list[str]:
    if not state:
        return []

    rebecs = state.get("rebecs", {})

    if isinstance(rebecs, dict):
        return [
            normalize_name(str(name))
            for name in rebecs
        ]

    result = []
    if isinstance(rebecs, list):
        for rebec in rebecs:
            if not isinstance(rebec, dict):
                continue

            name = (
                rebec.get("name")
                or rebec.get("id")
                or rebec.get("rebec")
            )

            if name is not None:
                result.append(
                    normalize_name(str(name))
                )

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
    return normalize_name(
        raw.replace(" ", "")
    )


def _message_label(message: dict[str, Any]) -> str:
    return _label_from_raw(
        _raw_message(message)
    )


def _sender(message: dict[str, Any]) -> str:
    return normalize_name(
        str(message.get("sender") or "")
    )


def _message_base(value: str) -> str:
    text = normalize_name(
        str(value or "").replace(" ", "")
    )
    return text.split("(", 1)[0]


def _queue_signatures(state, rebec):
    return [
        (
            _raw_message(message),
            _message_label(message),
            _sender(message),
        )
        for message in get_queue(state, rebec)
    ]


def _positive_delta(left, right):
    delta = Counter(left) - Counter(right)
    out = []

    for item, count in delta.items():
        out.extend([item] * count)

    return out


def _queue_delta(src, dst, owner="", handler=""):
    """
    Consumption-aware queue differencing.

    Identical consume/re-add patterns must not disappear. For example:

        before = [Ping]
        execute Ping()
        after  = [Ping]

    means one Ping was consumed and one Ping was emitted. Therefore the
    transition's handler message is removed from the source queue first,
    followed by a multiset comparison.
    """
    removed = []
    added = []

    owner = normalize_name(owner)
    handler_base = _message_base(handler)

    for rebec in sorted(
        set(_rebec_names(src))
        | set(_rebec_names(dst))
    ):
        before = list(
            _queue_signatures(src, rebec)
        )
        after = list(
            _queue_signatures(dst, rebec)
        )

        remaining_before = list(before)
        consumed = None

        if rebec == owner and handler_base:
            for index, item in enumerate(
                remaining_before
            ):
                raw, label, sender = item

                if (
                    _message_base(label)
                    == handler_base
                    or _message_base(raw)
                    == handler_base
                ):
                    consumed = (
                        remaining_before.pop(index)
                    )

                    removed.append(
                        QMsg(
                            rebec,
                            raw,
                            label,
                            sender,
                        )
                    )
                    break

        if consumed is None:
            for raw, label, sender in (
                _positive_delta(
                    before,
                    after,
                )
            ):
                removed.append(
                    QMsg(
                        rebec,
                        raw,
                        label,
                        sender,
                    )
                )

            for raw, label, sender in (
                _positive_delta(
                    after,
                    before,
                )
            ):
                added.append(
                    QMsg(
                        rebec,
                        raw,
                        label,
                        sender,
                    )
                )

            continue

        for raw, label, sender in (
            _positive_delta(
                remaining_before,
                after,
            )
        ):
            removed.append(
                QMsg(
                    rebec,
                    raw,
                    label,
                    sender,
                )
            )

        for raw, label, sender in (
            _positive_delta(
                after,
                remaining_before,
            )
        ):
            added.append(
                QMsg(
                    rebec,
                    raw,
                    label,
                    sender,
                )
            )

    return removed, added


def _build_events(data):
    events = []
    outgoing = defaultdict(list)

    for transition in get_transitions(data):
        source = transition.get("source")
        destination = transition.get(
            "destination"
        )

        owner = transition_owner(
            transition
        )

        handler = transition_message(
            transition
        )

        removed, added = _queue_delta(
            get_state_by_id(data, source),
            get_state_by_id(
                data,
                destination,
            ),
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


def _consumed_by_owner(event: Event):
    return [
        message
        for message in event.removed
        if message.recipient == event.owner
    ]


def _messages_added_by_owner(event: Event):
    return [
        message
        for message in event.added
        if message.sender == event.owner
    ]


def _messages_with_label(
    messages,
    label,
):
    return [
        message
        for message in messages
        if message.label == label
    ]


def _discover_hub_and_protocol(events):
    """
    Discover the central hub by behavior rather than actor name.

    A hub Ping transition consumes one message and emits exactly two messages
    of one common output kind to two distinct recipients. The sender of the
    consumed message is one of those recipients.
    """
    candidates = defaultdict(
        lambda: {
            "count": 0,
            "events": [],
        }
    )

    for event in events:
        consumed = _consumed_by_owner(
            event
        )

        if len(consumed) != 1:
            continue

        added = _messages_added_by_owner(
            event
        )

        by_label = defaultdict(list)
        for message in added:
            by_label[message.label].append(
                message
            )

        for output_label, outputs in (
            by_label.items()
        ):
            if len(outputs) != 2:
                continue

            recipients = {
                message.recipient
                for message in outputs
            }

            if len(recipients) != 2:
                continue

            consumed_sender = consumed[0].sender

            if (
                consumed_sender
                and consumed_sender
                not in recipients
            ):
                continue

            key = (
                event.owner,
                consumed[0].label,
                output_label,
            )

            candidates[key]["count"] += 1
            candidates[key]["events"].append(
                event
            )

    if not candidates:
        return None

    (
        hub,
        ping_kind,
        pong_kind,
    ), details = max(
        candidates.items(),
        key=lambda item: (
            item[1]["count"],
            item[0][0],
        ),
    )

    return {
        "hub": hub,
        "ping_kind": ping_kind,
        "pong_kind": pong_kind,
        "candidate_event_count": (
            details["count"]
        ),
    }


def _hub_ping_events(
    events,
    hub,
    ping_kind,
):
    result = []

    for event in events:
        if event.owner != hub:
            continue

        consumed = _messages_with_label(
            _consumed_by_owner(event),
            ping_kind,
        )

        if consumed:
            result.append(event)

    return result


def _discover_clients(
    hub_events,
    pong_kind,
    hub,
):
    clients = set()

    for event in hub_events:
        consumed = _consumed_by_owner(
            event
        )

        for message in consumed:
            if (
                message.sender
                and message.sender != hub
            ):
                clients.add(
                    message.sender
                )

        for message in _messages_with_label(
            _messages_added_by_owner(event),
            pong_kind,
        ):
            if message.recipient != hub:
                clients.add(
                    message.recipient
                )

    return sorted(clients)


def _ping_outputs_to_hub(
    event,
    ping_kind,
    hub,
):
    return [
        message
        for message in (
            _messages_added_by_owner(event)
        )
        if (
            message.label == ping_kind
            and message.recipient == hub
        )
    ]


def _pong_outputs(
    event,
    pong_kind,
):
    return _messages_with_label(
        _messages_added_by_owner(event),
        pong_kind,
    )


def _nonprotocol_consumed_labels(
    event,
    protocol_kinds,
):
    return [
        message.label
        for message in (
            _consumed_by_owner(event)
        )
        if message.label not in protocol_kinds
    ]


def _nonprotocol_self_added(
    event,
    protocol_kinds,
):
    return [
        message
        for message in (
            _messages_added_by_owner(event)
        )
        if (
            message.recipient == event.owner
            and message.label
            not in protocol_kinds
        )
    ]


def _analyze_client_trigger_chain(
    client,
    events,
    ping_kind,
    pong_kind,
    hub,
):
    protocol_kinds = {
        ping_kind,
        pong_kind,
    }

    client_events = [
        event
        for event in events
        if event.owner == client
    ]

    startup_pairs = []
    periodic_events = []

    # Startup:
    #   consume non-protocol trigger
    #   emit Ping to hub
    #   seed one non-protocol self message.
    for event in client_events:
        ping_out = _ping_outputs_to_hub(
            event,
            ping_kind,
            hub,
        )

        if len(ping_out) != 1:
            continue

        consumed_nonprotocol = (
            _nonprotocol_consumed_labels(
                event,
                protocol_kinds,
            )
        )

        if not consumed_nonprotocol:
            continue

        seeded = _nonprotocol_self_added(
            event,
            protocol_kinds,
        )

        if len(seeded) != 1:
            continue

        startup_pairs.append(
            {
                "event": event,
                "seed_label": seeded[0].label,
                "startup_handler": (
                    _message_base(
                        event.handler
                    )
                ),
            }
        )

    # Periodic opportunity:
    #   consume the seeded trigger
    #   emit one Ping to hub
    #   do not re-seed the same trigger.
    for pair in startup_pairs:
        seed_label = pair["seed_label"]

        for event in client_events:
            consumed_labels = (
                _nonprotocol_consumed_labels(
                    event,
                    protocol_kinds,
                )
            )

            if seed_label not in consumed_labels:
                continue

            ping_out = _ping_outputs_to_hub(
                event,
                ping_kind,
                hub,
            )

            if len(ping_out) != 1:
                continue

            recursively_seeded = [
                message
                for message in (
                    _nonprotocol_self_added(
                        event,
                        protocol_kinds,
                    )
                )
                if (
                    message.label
                    == seed_label
                )
            ]

            periodic_events.append(
                {
                    "event": event,
                    "seed_label": seed_label,
                    "recursive_seed_count": (
                        len(recursively_seeded)
                    ),
                }
            )

    startup_ok = bool(
        startup_pairs
    )

    periodic_ok = any(
        item["recursive_seed_count"] == 0
        for item in periodic_events
    )

    return {
        "startup_ok": startup_ok,
        "periodic_ok": periodic_ok,
        "startup_event_count": len(
            startup_pairs
        ),
        "periodic_event_count": len(
            periodic_events
        ),
        "startup_events": [
            item["event"].as_dict()
            for item in startup_pairs[:10]
        ],
        "periodic_events": [
            item["event"].as_dict()
            for item in periodic_events[:10]
        ],
    }


def _analyze_client_feedback(
    client,
    events,
    ping_kind,
    pong_kind,
    hub,
):
    pong_events = []

    for event in events:
        if event.owner != client:
            continue

        consumed_pong = (
            _messages_with_label(
                _consumed_by_owner(event),
                pong_kind,
            )
        )

        if consumed_pong:
            pong_events.append(event)

    forward_events = []
    drop_events = []
    bad_events = []

    for event in pong_events:
        ping_out = _ping_outputs_to_hub(
            event,
            ping_kind,
            hub,
        )

        other_protocol_out = [
            message
            for message in (
                _messages_added_by_owner(
                    event
                )
            )
            if (
                message.label
                in {ping_kind, pong_kind}
                and not (
                    message.label
                    == ping_kind
                    and message.recipient
                    == hub
                )
            )
        ]

        if len(ping_out) == 1 and not (
            other_protocol_out
        ):
            forward_events.append(
                event
            )

        elif (
            len(ping_out) == 0
            and not other_protocol_out
        ):
            drop_events.append(
                event
            )

        else:
            bad_events.append(
                event
            )

    return {
        "forward_observed": bool(
            forward_events
        ),
        "drop_observed": bool(
            drop_events
        ),
        "safe": not bad_events,
        "pong_event_count": len(
            pong_events
        ),
        "forward_event_count": len(
            forward_events
        ),
        "drop_event_count": len(
            drop_events
        ),
        "bad_events": [
            event.as_dict()
            for event in bad_events[:20]
        ],
    }


def _analyze_hub_event(
    event,
    ping_kind,
    pong_kind,
    clients,
):
    consumed = _messages_with_label(
        _consumed_by_owner(event),
        ping_kind,
    )

    pongs = _pong_outputs(
        event,
        pong_kind,
    )

    if len(consumed) != 1:
        return {
            "valid_input": False,
        }

    sender = consumed[0].sender
    recipients = [
        message.recipient
        for message in pongs
    ]

    direct_count = recipients.count(
        sender
    )

    secondaries = [
        recipient
        for recipient in recipients
        if recipient != sender
    ]

    direct_ok = (
        bool(sender)
        and direct_count == 1
    )

    secondary_ok = (
        len(pongs) == 2
        and len(secondaries) == 1
        and secondaries[0] in clients
        and secondaries[0] != sender
        and len(set(recipients)) == 2
    )

    return {
        "valid_input": True,
        "sender": sender,
        "recipients": recipients,
        "direct_ok": direct_ok,
        "secondary_ok": secondary_ok,
        "secondary": (
            secondaries[0]
            if len(secondaries) == 1
            else None
        ),
    }


def _all_queues_empty(
    state,
):
    for rebec in _rebec_names(state):
        if get_queue(state, rebec):
            return False

    return True


def _test(
    test_id,
    passed,
    observed,
    description,
    evidence,
):
    status = (
        TestStatus.PASS
        if passed
        else (
            TestStatus.FAIL
            if observed
            else TestStatus.NOT_OBSERVED
        )
    )

    return SemanticTestResult(
        test_id=test_id,
        status=status,
        description=description,
        evidence=evidence,
    )


class StarTopologyUntimedBoundedEvaluator(
    BaseSemanticEvaluator
):
    benchmark_id = BENCHMARK_ID

    def __init__(
        self,
        parsed_result,
        example_id=BENCHMARK_ID,
    ):
        super().__init__(
            parsed_result=parsed_result,
            example_id=example_id,
        )

    def evaluate(self, data):
        states = get_states(data)
        transitions = get_transitions(data)
        events, outgoing = _build_events(
            data
        )

        discovery = (
            _discover_hub_and_protocol(
                events
            )
        )

        hub = (
            discovery["hub"]
            if discovery
            else None
        )

        ping_kind = (
            discovery["ping_kind"]
            if discovery
            else None
        )

        pong_kind = (
            discovery["pong_kind"]
            if discovery
            else None
        )

        if discovery:
            hub_events = _hub_ping_events(
                events,
                hub,
                ping_kind,
            )
            clients = _discover_clients(
                hub_events,
                pong_kind,
                hub,
            )
        else:
            hub_events = []
            clients = []

        topology_complete = (
            hub is not None
            and len(clients)
            == EXPECTED_CLIENTS
        )

        # -------------------------
        # Client behavior
        # -------------------------

        trigger_by_client = {}
        feedback_by_client = {}

        if discovery:
            for client in clients:
                trigger_by_client[client] = (
                    _analyze_client_trigger_chain(
                        client,
                        events,
                        ping_kind,
                        pong_kind,
                        hub,
                    )
                )

                feedback_by_client[client] = (
                    _analyze_client_feedback(
                        client,
                        events,
                        ping_kind,
                        pong_kind,
                        hub,
                    )
                )

        startup_ok = (
            topology_complete
            and all(
                trigger_by_client[
                    client
                ]["startup_ok"]
                for client in clients
            )
        )

        periodic_ok = (
            topology_complete
            and all(
                trigger_by_client[
                    client
                ]["periodic_ok"]
                for client in clients
            )
        )

        feedback_forward_ok = (
            topology_complete
            and all(
                feedback_by_client[
                    client
                ]["forward_observed"]
                for client in clients
            )
        )

        feedback_drop_ok = (
            topology_complete
            and all(
                feedback_by_client[
                    client
                ]["drop_observed"]
                and feedback_by_client[
                    client
                ]["safe"]
                for client in clients
            )
        )

        # -------------------------
        # Hub behavior
        # -------------------------

        hub_analysis = [
            _analyze_hub_event(
                event,
                ping_kind,
                pong_kind,
                clients,
            )
            for event in hub_events
        ]

        valid_hub_analysis = [
            item
            for item in hub_analysis
            if item.get("valid_input")
        ]

        direct_bad = [
            item
            for item in valid_hub_analysis
            if not item["direct_ok"]
        ]

        secondary_bad = [
            item
            for item in valid_hub_analysis
            if not item["secondary_ok"]
        ]

        direct_reply_ok = (
            bool(valid_hub_analysis)
            and not direct_bad
        )

        secondary_reply_ok = (
            bool(valid_hub_analysis)
            and not secondary_bad
        )

        secondary_targets_by_sender = (
            defaultdict(set)
        )

        for item in valid_hub_analysis:
            sender = item["sender"]
            secondary = item["secondary"]

            if sender and secondary:
                secondary_targets_by_sender[
                    sender
                ].add(secondary)

        nondeterministic_choice_by_sender = {
            client: (
                len(
                    secondary_targets_by_sender[
                        client
                    ]
                ) >= 2
            )
            for client in clients
        }

        nondeterminism_observed = (
            topology_complete
            and all(
                nondeterministic_choice_by_sender[
                    client
                ]
                for client in clients
            )
        )

        # -------------------------
        # Routing safety
        # -------------------------

        bad_ping_routing = []
        bad_pong_origin = []

        if discovery:
            for event in events:
                owner_added = (
                    _messages_added_by_owner(
                        event
                    )
                )

                for message in owner_added:
                    if (
                        message.label
                        == ping_kind
                        and event.owner
                        in clients
                        and message.recipient
                        != hub
                    ):
                        bad_ping_routing.append(
                            event
                        )

                    if (
                        message.label
                        == pong_kind
                        and event.owner != hub
                    ):
                        bad_pong_origin.append(
                            event
                        )

        centralized_ping_routing = (
            topology_complete
            and not bad_ping_routing
            and any(
                _ping_outputs_to_hub(
                    event,
                    ping_kind,
                    hub,
                )
                for event in events
                if event.owner in clients
            )
        )

        hub_only_pong_origin = (
            discovery is not None
            and not bad_pong_origin
            and bool(valid_hub_analysis)
        )

        eligible_secondary_target = (
            bool(valid_hub_analysis)
            and not secondary_bad
        )

        # -------------------------
        # Quiescence
        # -------------------------

        terminal_state_ids = []

        for state in states:
            state_id = _sid(state)

            if state_id is None:
                continue

            if outgoing.get(state_id):
                continue

            if _all_queues_empty(state):
                terminal_state_ids.append(
                    state_id
                )

        quiescence_observed = bool(
            terminal_state_ids
        )

        # -------------------------
        # Tests
        # -------------------------

        tests = []

        tests.append(_test(
            "STB-XA1",
            startup_ok,
            topology_complete
            and any(
                item["startup_ok"]
                for item in (
                    trigger_by_client.values()
                )
            ),
            (
                "Each client must have startup behavior that emits one Ping "
                "to the hub and seeds one bounded periodic opportunity."
            ),
            {
                "trigger_by_client": trigger_by_client,
            },
        ))

        tests.append(_test(
            "STB-XA2",
            periodic_ok,
            topology_complete
            and any(
                item["periodic_event_count"]
                > 0
                for item in (
                    trigger_by_client.values()
                )
            ),
            (
                "Each client's periodic opportunity must emit one Ping to "
                "the hub without recursively scheduling another periodic "
                "opportunity."
            ),
            {
                "trigger_by_client": trigger_by_client,
            },
        ))

        tests.append(_test(
            "STB-XA3",
            feedback_forward_ok,
            topology_complete
            and any(
                item["forward_observed"]
                for item in (
                    feedback_by_client.values()
                )
            ),
            (
                "Each client must have reachable Pong handling that emits "
                "exactly one Ping to the hub."
            ),
            {
                "feedback_by_client": feedback_by_client,
            },
        ))

        tests.append(_test(
            "STB-XA4",
            feedback_drop_ok,
            topology_complete
            and any(
                item["drop_observed"]
                for item in (
                    feedback_by_client.values()
                )
            ),
            (
                "Each client must also have reachable Pong handling with "
                "no Ping output, and no Pong transition may emit more than "
                "one Ping."
            ),
            {
                "feedback_by_client": feedback_by_client,
            },
        ))

        tests.append(_test(
            "STB-XA5",
            direct_reply_ok,
            bool(valid_hub_analysis),
            (
                "Every observed hub Ping handling must emit exactly one "
                "direct Pong to the Ping sender."
            ),
            {
                "hub_event_count": len(
                    valid_hub_analysis
                ),
                "bad_direct_reply_events": (
                    direct_bad[:30]
                ),
            },
        ))

        tests.append(_test(
            "STB-XA6",
            secondary_reply_ok,
            bool(valid_hub_analysis),
            (
                "Every observed hub Ping handling must emit exactly one "
                "additional Pong to a client distinct from the sender."
            ),
            {
                "hub_event_count": len(
                    valid_hub_analysis
                ),
                "bad_secondary_reply_events": (
                    secondary_bad[:30]
                ),
            },
        ))

        tests.append(_test(
            "STB-XI1",
            topology_complete,
            (
                hub is not None
                and len(clients)
                >= EXPECTED_CLIENTS
            ),
            (
                "Exactly five logical clients and one logical hub must be "
                "discovered."
            ),
            {
                "hub": hub,
                "clients": clients,
                "client_count": len(
                    clients
                ),
            },
        ))

        tests.append(_test(
            "STB-XI2",
            centralized_ping_routing,
            (
                topology_complete
                and bool(events)
            ),
            (
                "All client-generated Ping protocol messages must target "
                "the same hub."
            ),
            {
                "bad_ping_routing_events": [
                    event.as_dict()
                    for event in (
                        bad_ping_routing[:30]
                    )
                ],
            },
        ))

        tests.append(_test(
            "STB-XI3",
            hub_only_pong_origin,
            bool(valid_hub_analysis),
            (
                "All protocol Pong outputs must originate from the "
                "discovered hub."
            ),
            {
                "bad_pong_origin_events": [
                    event.as_dict()
                    for event in (
                        bad_pong_origin[:30]
                    )
                ],
            },
        ))

        tests.append(_test(
            "STB-XI4",
            eligible_secondary_target,
            bool(valid_hub_analysis),
            (
                "Every secondary Pong recipient must be one of the five "
                "clients and different from the consumed Ping sender."
            ),
            {
                "bad_secondary_reply_events": (
                    secondary_bad[:30]
                ),
            },
        ))

        tests.append(_test(
            "STB-XI5",
            nondeterminism_observed,
            nondeterminism_observed,
            (
                "For every client sender, at least two distinct eligible "
                "secondary targets should be observed, providing positive "
                "evidence that secondary routing is not globally fixed."
            ),
            {
                "secondary_targets_by_sender": {
                    sender: sorted(targets)
                    for sender, targets in (
                        secondary_targets_by_sender.items()
                    )
                },
                "nondeterministic_choice_by_sender": (
                    nondeterministic_choice_by_sender
                ),
            },
        ))

        tests.append(_test(
            "STB-XSYS1",
            startup_ok,
            topology_complete,
            (
                "Startup Ping behavior must be reachable for all five "
                "clients."
            ),
            {
                "startup_ok_by_client": {
                    client: (
                        trigger_by_client[
                            client
                        ]["startup_ok"]
                    )
                    for client in clients
                },
            },
        ))

        tests.append(_test(
            "STB-XSYS2",
            startup_ok and periodic_ok,
            topology_complete
            and any(
                item["periodic_event_count"]
                > 0
                for item in (
                    trigger_by_client.values()
                )
            ),
            (
                "The startup-seeded bounded periodic trigger must be "
                "reachable and terminate after one Ping for all clients."
            ),
            {
                "periodic_ok_by_client": {
                    client: (
                        trigger_by_client[
                            client
                        ]["periodic_ok"]
                    )
                    for client in clients
                },
            },
        ))

        tests.append(_test(
            "STB-XSYS3",
            (
                feedback_forward_ok
                and feedback_drop_ok
            ),
            topology_complete
            and any(
                item["pong_event_count"]
                > 0
                for item in (
                    feedback_by_client.values()
                )
            ),
            (
                "Both first-Pong feedback and later-Pong no-output behavior "
                "must be reachable for all clients."
            ),
            {
                "feedback_by_client": feedback_by_client,
            },
        ))

        tests.append(_test(
            "STB-XSYS4",
            quiescence_observed,
            quiescence_observed,
            (
                "At least one reachable terminal state must have empty "
                "message queues."
            ),
            {
                "terminal_quiescent_state_count": (
                    len(terminal_state_ids)
                ),
                "terminal_quiescent_state_ids_sample": (
                    terminal_state_ids[:100]
                ),
            },
        ))

        prior_tests = list(tests)

        all_prior_pass = all(
            test.status == TestStatus.PASS
            for test in prior_tests
        )

        any_prior_fail = any(
            test.status == TestStatus.FAIL
            for test in prior_tests
        )

        tests.append(_test(
            "STB-XSYS5",
            all_prior_pass,
            (
                all_prior_pass
                or any_prior_fail
            ),
            (
                "The complete bounded untimed five-client star-topology "
                "semantic contract must be preserved."
            ),
            {
                "all_prior_pass": all_prior_pass,
                "any_prior_fail": any_prior_fail,
                "prior_statuses": {
                    test.test_id: (
                        test.status.value
                    )
                    for test in prior_tests
                },
            },
        ))

        detected_issues = []

        for test in tests:
            if test.status == TestStatus.FAIL:
                detected_issues.append(
                    f"{test.test_id}_VIOLATION"
                )
            elif (
                test.status
                == TestStatus.NOT_OBSERVED
            ):
                detected_issues.append(
                    f"{test.test_id}_NOT_OBSERVED"
                )

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=detected_issues,
            metadata={
                "semantic_backend": "statespace",
                "evaluator_version": (
                    "v1_consumption_aware_bounded_star"
                ),
                "semantic_scope": (
                    "scenario-bounded observational equivalence "
                    "for the verification-oriented bounded untimed "
                    "five-client star abstraction"
                ),
                "timing_semantics_checked": False,
                "random_probability_distribution_checked": False,
                "state_count": len(states),
                "transition_count": len(
                    transitions
                ),
                "discovered_hub": hub,
                "discovered_clients": clients,
                "discovered_client_count": len(
                    clients
                ),
                "ping_message_kind": ping_kind,
                "pong_message_kind": pong_kind,
                "hub_protocol_event_count": len(
                    valid_hub_analysis
                ),
                "trigger_by_client": trigger_by_client,
                "feedback_by_client": feedback_by_client,
                "secondary_targets_by_sender": {
                    sender: sorted(targets)
                    for sender, targets in (
                        secondary_targets_by_sender.items()
                    )
                },
                "nondeterministic_choice_by_sender": (
                    nondeterministic_choice_by_sender
                ),
                "terminal_quiescent_state_count": (
                    len(terminal_state_ids)
                ),
                "terminal_quiescent_state_ids_sample": (
                    terminal_state_ids[:100]
                ),
                "missing_positive_evidence_policy": (
                    "NOT_OBSERVED"
                ),
                "target_name_hard_coding": False,
                "explicit_registration_required": False,
            },
        )


def evaluate_star_topology_untimed_bounded(
    data: dict[str, Any],
) -> dict[str, Any]:
    return (
        StarTopologyUntimedBoundedEvaluator(
            data
        )
        .evaluate(data)
        .to_dict()
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate the bounded untimed five-client star topology "
            "from normalized full RMC state-space JSON."
        )
    )

    parser.add_argument(
        "parsed_result"
    )

    parser.add_argument(
        "--output",
        "-o",
    )

    args = parser.parse_args()

    try:
        data = json.loads(
            Path(
                args.parsed_result
            ).read_text(
                encoding="utf-8"
            )
        )

        result = (
            evaluate_star_topology_untimed_bounded(
                data
            )
        )

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
            (
                "StarTopologyUntimedBounded evaluator "
                f"infrastructure error: {exc}"
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
