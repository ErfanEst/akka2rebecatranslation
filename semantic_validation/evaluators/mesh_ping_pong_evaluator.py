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
from semantic_validation.core.evaluator_models import SemanticEvaluationResult, SemanticTestResult, TestStatus
from semantic_validation.core.trace_utils import (
    get_queue, get_state_by_id, get_states, get_transitions,
    normalize_name, transition_message, transition_owner,
)

BENCHMARK_ID = "mesh_ping_pong"
EXPECTED_PINGS = 6
EXPECTED_PONGS = 6


@dataclass(frozen=True)
class QMsg:
    recipient: str
    raw: str
    name: str
    sender: str

    def as_dict(self) -> dict[str, str]:
        return {"recipient": self.recipient, "raw_message": self.raw,
                "message_name": self.name, "sender": self.sender}


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
            "source_state_id": self.source, "destination_state_id": self.destination,
            "owner": self.owner, "message_server": self.handler,
            "removed_messages": [m.as_dict() for m in self.removed],
            "added_messages": [m.as_dict() for m in self.added],
        }


def sid(state: dict[str, Any] | None) -> Any:
    if not state:
        return None
    return state.get("id") if state.get("id") is not None else state.get("state_id")


def initial_ids(data: dict[str, Any]) -> list[Any]:
    ids = [sid(s) for s in get_states(data) if sid(s) is not None]
    dests = {t.get("destination") for t in get_transitions(data)}
    roots = [x for x in ids if x not in dests]
    return roots or ([0] if 0 in ids else ids[:1])


def rebec_names(state: dict[str, Any] | None) -> list[str]:
    if not state:
        return []
    rebecs = state.get("rebecs", {})
    if isinstance(rebecs, dict):
        return [normalize_name(x) for x in rebecs]
    result = []
    for r in rebecs if isinstance(rebecs, list) else []:
        if isinstance(r, dict):
            value = r.get("name") or r.get("id") or r.get("rebec")
            if value is not None:
                result.append(normalize_name(str(value)))
    return result


def all_rebecs(data: dict[str, Any]) -> list[str]:
    names = set()
    for s in get_states(data):
        names.update(rebec_names(s))
    return sorted(names)


def raw_msg(m: dict[str, Any]) -> str:
    return str(m.get("message") or m.get("name") or
               m.get("message_name") or m.get("message_server") or "").strip()


def msg_name(m: dict[str, Any]) -> str:
    raw = raw_msg(m)
    return normalize_name(raw.split("(", 1)[0])


def sender(m: dict[str, Any]) -> str:
    return normalize_name(str(m.get("sender") or ""))


def qsignatures(state: dict[str, Any] | None, rebec: str):
    return [(raw_msg(m), msg_name(m), sender(m)) for m in get_queue(state, rebec)]


def positive_delta(a, b):
    c = Counter(a) - Counter(b)
    out = []
    for item, n in c.items():
        out.extend([item] * n)
    return out


def queue_delta(src: dict[str, Any] | None, dst: dict[str, Any] | None):
    removed, added = [], []
    for r in sorted(set(rebec_names(src)) | set(rebec_names(dst))):
        a, b = qsignatures(src, r), qsignatures(dst, r)
        for raw, name, snd in positive_delta(a, b):
            removed.append(QMsg(r, raw, name, snd))
        for raw, name, snd in positive_delta(b, a):
            added.append(QMsg(r, raw, name, snd))
    return removed, added


def build_events(data: dict[str, Any]):
    events, outgoing = [], defaultdict(list)
    for t in get_transitions(data):
        s, d = t.get("source"), t.get("destination")
        removed, added = queue_delta(get_state_by_id(data, s), get_state_by_id(data, d))
        e = Event(s, d, transition_owner(t), transition_message(t), removed, added)
        events.append(e)
        outgoing[s].append(e)
    return events, outgoing


def cross_added(e: Event) -> list[QMsg]:
    return [m for m in e.added if m.sender and m.recipient and m.sender != m.recipient]


def cross_removed(e: Event) -> list[QMsg]:
    return [m for m in e.removed if m.sender and m.recipient == e.owner and m.sender != e.owner]


def broadcast_targets(e: Event) -> list[str]:
    return [m.recipient for m in cross_added(e) if m.sender == e.owner]


def is_broadcast(e: Event) -> bool:
    targets = broadcast_targets(e)
    return len(targets) == 2 and len(set(targets)) == 2


def is_reply(e: Event) -> bool:
    consumed = cross_removed(e)
    if len(consumed) != 1:
        return False
    src = consumed[0].sender
    outs = [m for m in cross_added(e) if m.sender == e.owner]
    return len(outs) == 1 and outs[0].recipient == src


def discover_roles(events: list[Event]):
    bcount, rcount = defaultdict(int), defaultdict(int)
    for e in events:
        if is_broadcast(e):
            bcount[e.owner] += 1
        if is_reply(e):
            rcount[e.owner] += 1

    pings = sorted(bcount, key=lambda x: (-bcount[x], rcount.get(x, 0), x))[:EXPECTED_PINGS]
    pongs = sorted(
        [x for x in rcount if x not in set(pings)],
        key=lambda x: (-rcount[x], bcount.get(x, 0), x)
    )[:EXPECTED_PONGS]
    return pings, pongs


def discover_neighbors(events: list[Event], pings: set[str], pongs: set[str]):
    neighbors = {p: set() for p in pings}
    broadcasts = defaultdict(list)
    bad = []
    canonical = {}

    for e in events:
        if e.owner not in pings or not is_broadcast(e):
            continue
        targets = set(broadcast_targets(e))
        broadcasts[e.owner].append(e)
        if len(targets) != 2 or not targets <= pongs:
            bad.append(e)
            continue
        canonical.setdefault(e.owner, targets)
        if canonical[e.owner] != targets:
            bad.append(e)
        neighbors[e.owner] = set(canonical[e.owner])

    return neighbors, dict(broadcasts), bad


def discover_replies(events: list[Event], pings: set[str], pongs: set[str]):
    replies = defaultdict(list)
    bad = []
    for e in events:
        if e.owner not in pongs:
            continue
        consumed = [m for m in cross_removed(e) if m.sender in pings]
        if not consumed:
            continue
        outs = [m for m in cross_added(e) if m.sender == e.owner]
        if len(consumed) == 1 and len(outs) == 1 and outs[0].recipient == consumed[0].sender:
            replies[consumed[0].sender].append(e)
        else:
            bad.append(e)
    return dict(replies), bad


def pong_input(e: Event, pongs: set[str]) -> bool:
    return any(m.sender in pongs and m.recipient == e.owner for m in e.removed)


def autonomous_input(e: Event, pongs: set[str]) -> bool:
    if pong_input(e, pongs):
        return False
    return not e.removed or all(m.sender == e.owner or m.sender not in pongs for m in e.removed)


def bfs_witness(outgoing, starts, predicate, block=None):
    q = deque((s, []) for s in starts)
    seen = set()
    while q:
        state, path = q.popleft()
        if state in seen:
            continue
        seen.add(state)
        for e in outgoing.get(state, []):
            if predicate(e):
                return path + [e]
            if block is not None and block(e):
                continue
            q.append((e.destination, path + [e]))
    return None


def startup_witness(data, outgoing, ping, pongs):
    return bfs_witness(
        outgoing, initial_ids(data),
        lambda e: e.owner == ping and is_broadcast(e) and autonomous_input(e, pongs)
    )


def periodic_witness(outgoing, ping, pongs, startup):
    if not startup:
        return None
    return bfs_witness(
        outgoing, [startup[-1].destination],
        lambda e: e.owner == ping and is_broadcast(e) and autonomous_input(e, pongs),
        block=lambda e: pong_input(e, pongs)
    )


def reply_rebroadcast_witness(outgoing, ping, pongs, replies, expected_neighbors):
    for reply in replies:
        found = bfs_witness(
            outgoing, [reply.destination],
            lambda e: (
                e.owner == ping and is_broadcast(e)
                and set(broadcast_targets(e)) == expected_neighbors
            ),
            block=lambda e: e.owner == ping and pong_input(e, pongs)
        )
        if found:
            return [reply] + found
    return None


def topology_check(pings: set[str], pongs: set[str], neighbors):
    pong_degree = {p: 0 for p in pongs}
    adj = defaultdict(set)

    for ping in pings:
        for pong in neighbors.get(ping, set()):
            if pong in pongs:
                pong_degree[pong] += 1
                adj[ping].add(pong)
                adj[pong].add(ping)

    degree_ok = (
        len(pings) == EXPECTED_PINGS and len(pongs) == EXPECTED_PONGS
        and all(len(neighbors.get(p, set())) == 2 for p in pings)
        and all(pong_degree[p] == 2 for p in pongs)
    )

    nodes = pings | pongs
    if not nodes:
        return False, False, pong_degree

    q, seen = deque([next(iter(nodes))]), set()
    while q:
        x = q.popleft()
        if x in seen:
            continue
        seen.add(x)
        q.extend(adj[x] - seen)

    connected = seen == nodes
    return degree_ok and connected, connected, pong_degree


def concurrency(outgoing, actors: set[str]):
    for state, events in outgoing.items():
        owners = sorted({e.owner for e in events if e.owner in actors})
        if len(owners) >= 2:
            return state, owners
    return None, []


def path_json(path):
    return [e.as_dict() for e in (path or [])[:40]]


def result(test_id, passed, observed, description, evidence):
    status = TestStatus.PASS if passed else (TestStatus.FAIL if observed else TestStatus.NOT_OBSERVED)
    return SemanticTestResult(test_id=test_id, status=status, description=description, evidence=evidence)


class MeshPingPongEvaluator(BaseSemanticEvaluator):
    benchmark_id = BENCHMARK_ID

    def __init__(self, parsed_result: dict[str, Any], example_id: str = BENCHMARK_ID):
        super().__init__(parsed_result=parsed_result, example_id=example_id)

    def evaluate(self, data: dict[str, Any]) -> SemanticEvaluationResult:
        states, transitions = get_states(data), get_transitions(data)
        events, outgoing = build_events(data)

        pings, pongs = discover_roles(events)
        pset, qset = set(pings), set(pongs)
        roles_complete = len(pings) == EXPECTED_PINGS and len(pongs) == EXPECTED_PONGS

        neighbors, broadcasts, bad_neighbors = discover_neighbors(events, pset, qset)
        replies, bad_replies = discover_replies(events, pset, qset)

        startups, periodic, rebroadcast = {}, {}, {}
        for ping in pings:
            startups[ping] = startup_witness(data, outgoing, ping, qset)
            periodic[ping] = periodic_witness(outgoing, ping, qset, startups[ping])
            rebroadcast[ping] = reply_rebroadcast_witness(
                outgoing, ping, qset, replies.get(ping, []), neighbors.get(ping, set())
            )

        startup_ok = roles_complete and all(startups.get(p) for p in pings)
        periodic_ok = roles_complete and all(periodic.get(p) for p in pings)
        rebroadcast_ok = roles_complete and all(rebroadcast.get(p) for p in pings)
        neighbor_ok = roles_complete and not bad_neighbors and all(len(neighbors.get(p, set())) == 2 for p in pings)

        cycle_ok, connected, pong_degrees = topology_check(pset, qset, neighbors)
        degree_ok = roles_complete and all(len(neighbors.get(p, set())) == 2 for p in pings) and all(pong_degrees.get(p, 0) == 2 for p in pongs)

        pong_owners_seen = {e.owner for rs in replies.values() for e in rs}
        reply_ok = roles_complete and len(pong_owners_seen) == EXPECTED_PONGS and not bad_replies

        cstate, cowners = concurrency(outgoing, pset | qset)
        concurrency_ok = cstate is not None

        tests = [
            result("MPP-XA1", startup_ok, roles_complete, "Each Ping has an autonomous startup two-neighbor broadcast witness.",
                   {"startup_found": {p: startups.get(p) is not None for p in pings},
                    "witnesses": {p: path_json(startups.get(p)) for p in pings}}),

            result("MPP-XA2", periodic_ok, periodic_ok, "Each Ping has recurring autonomous untimed scheduler activity.",
                   {"periodic_found": {p: periodic.get(p) is not None for p in pings},
                    "witnesses": {p: path_json(periodic.get(p)) for p in pings}}),

            result("MPP-XA3", rebroadcast_ok, rebroadcast_ok, "Each Ping has a Pong-reply to two-neighbor-rebroadcast witness.",
                   {"rebroadcast_found": {p: rebroadcast.get(p) is not None for p in pings},
                    "witnesses": {p: path_json(rebroadcast.get(p)) for p in pings}}),

            result("MPP-XA4", reply_ok, bool(replies) or bool(bad_replies), "Each Pong replies exactly once to the consumed request sender.",
                   {"reply_event_count_by_ping": {p: len(replies.get(p, [])) for p in pings},
                    "bad_reply_events": [e.as_dict() for e in bad_replies[:30]]}),

            result("MPP-XA5", neighbor_ok, bool(broadcasts), "Every observed broadcast from a Ping uses the same two Pong neighbors.",
                   {"neighbors": {p: sorted(neighbors.get(p, set())) for p in pings},
                    "bad_neighbor_events": [e.as_dict() for e in bad_neighbors[:30]]}),

            result("MPP-XI1", roles_complete, bool(events), "Six Ping roles and six Pong roles are behaviorally discovered.",
                   {"pings": pings, "pongs": pongs}),

            result("MPP-XI2", degree_ok, roles_complete, "Every Ping and Pong has degree two in the logical bipartite graph.",
                   {"ping_degrees": {p: len(neighbors.get(p, set())) for p in pings},
                    "pong_degrees": pong_degrees}),

            result("MPP-XI3", cycle_ok, roles_complete, "The 6x6 bipartite topology is connected and 2-regular.",
                   {"connected": connected, "neighbors": {p: sorted(neighbors.get(p, set())) for p in pings}}),

            result("MPP-XI4", startup_ok, roles_complete, "All six Ping roles have autonomous startup witnesses.",
                   {"startup_found": {p: startups.get(p) is not None for p in pings}}),

            result("MPP-XI5", reply_ok, bool(replies) or bool(bad_replies), "Pong replies remain isolated to the original Ping sender.",
                   {"bad_reply_count": len(bad_replies)}),

            result("MPP-XI6", rebroadcast_ok, rebroadcast_ok, "Every Ping has a connected reply-induced two-request fan-out witness.",
                   {"rebroadcast_found": {p: rebroadcast.get(p) is not None for p in pings}}),

            result("MPP-XI7", concurrency_ok, bool(transitions), "At least one state enables progress for two distinct logical actors.",
                   {"branching_state_id": cstate, "enabled_protocol_owners": cowners}),

            result("MPP-XSYS1", roles_complete, bool(states), "The protocol exposes six Ping and six Pong logical roles.",
                   {"observed_rebecs": all_rebecs(data), "logical_pings": pings, "logical_pongs": pongs}),

            result("MPP-XSYS2", startup_ok, roles_complete, "All six Ping roles enter the mesh protocol automatically.",
                   {"initial_state_ids": initial_ids(data), "startup_found": {p: startups.get(p) is not None for p in pings}}),

            result("MPP-XSYS3", periodic_ok, periodic_ok, "All six Ping roles expose autonomous recurring scheduler activity.",
                   {"periodic_found": {p: periodic.get(p) is not None for p in pings}}),

            result("MPP-XSYS4", rebroadcast_ok, rebroadcast_ok, "Reply-induced message amplification is observed.",
                   {"rebroadcast_found": {p: rebroadcast.get(p) is not None for p in pings}}),
        ]

        complete_ok = all([
            roles_complete, degree_ok, cycle_ok, startup_ok, periodic_ok,
            rebroadcast_ok, reply_ok, neighbor_ok, concurrency_ok
        ])

        tests.append(
            result("MPP-XSYS5", complete_ok, roles_complete and startup_ok and reply_ok,
                   "The complete untimed Mesh Ping-Pong contract is preserved.",
                   {
                       "roles_complete": roles_complete, "degree_ok": degree_ok,
                       "topology_cycle_ok": cycle_ok, "startup_complete": startup_ok,
                       "periodic_complete": periodic_ok, "rebroadcast_complete": rebroadcast_ok,
                       "reply_isolation_ok": reply_ok, "neighbor_stable": neighbor_ok,
                       "concurrency_ok": concurrency_ok,
                   })
        )

        issues = []
        if not transitions: issues.append("NO_TRANSITIONS")
        if not roles_complete: issues.append("INCOMPLETE_MESH_ROLE_DISCOVERY")
        if bad_neighbors: issues.append("NEIGHBOR_SET_VIOLATION")
        if bad_replies: issues.append("REPLY_ROUTING_VIOLATION")
        if roles_complete and not degree_ok: issues.append("MESH_DEGREE_VIOLATION")
        if roles_complete and not cycle_ok: issues.append("MESH_CONNECTIVITY_OR_CYCLE_VIOLATION")
        if roles_complete and not startup_ok: issues.append("INCOMPLETE_STARTUP_EVIDENCE")
        if roles_complete and not periodic_ok: issues.append("PERIODIC_TRIGGER_NOT_FULLY_OBSERVED")
        if roles_complete and not rebroadcast_ok: issues.append("REPLY_REBROADCAST_NOT_FULLY_OBSERVED")
        if not concurrency_ok: issues.append("CONCURRENT_PROGRESS_NOT_OBSERVED")
        if any(t.status == TestStatus.NOT_OBSERVED for t in tests):
            issues.append("INCOMPLETE_OBSERVABILITY")

        return SemanticEvaluationResult(
            benchmark=self.benchmark_id,
            semantic_tests=tests,
            detected_issues=issues,
            metadata={
                "semantic_backend": "statespace",
                "evaluation_style": "bounded_witness_plus_invariants",
                "semantic_scope": "scenario-bounded observational equivalence for the untimed message-amplifying 6x6 mesh",
                "timing_mode": "UNTIMED",
                "state_count": len(states),
                "transition_count": len(transitions),
                "initial_state_ids": initial_ids(data),
                "observed_rebecs": all_rebecs(data),
                "logical_pings": pings,
                "logical_pongs": pongs,
                "logical_ping_count": len(pings),
                "logical_pong_count": len(pongs),
                "neighbors": {p: sorted(neighbors.get(p, set())) for p in pings},
                "pong_degrees": pong_degrees,
                "startup_found": {p: startups.get(p) is not None for p in pings},
                "periodic_found": {p: periodic.get(p) is not None for p in pings},
                "reply_rebroadcast_found": {p: rebroadcast.get(p) is not None for p in pings},
                "reply_event_count_by_ping": {p: len(replies.get(p, [])) for p in pings},
                "bad_reply_event_count": len(bad_replies),
                "bad_neighbor_event_count": len(bad_neighbors),
                "topology_connected": connected,
                "topology_cycle_ok": cycle_ok,
                "concurrency_state_id": cstate,
                "concurrency_owners": cowners,
                "state_space_completeness_required": False,
                "missing_positive_evidence_policy": "NOT_OBSERVED",
                "target_name_hard_coding": False,
            },
        )


def evaluate_mesh_ping_pong(data: dict[str, Any]) -> dict[str, Any]:
    return MeshPingPongEvaluator(data).evaluate(data).to_dict()


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("parsed_result")
    parser.add_argument("--output", "-o")
    args = parser.parse_args()

    try:
        data = json.loads(Path(args.parsed_result).read_text(encoding="utf-8"))
        result_data = evaluate_mesh_ping_pong(data)
        text = json.dumps(result_data, indent=2, ensure_ascii=False)
        if args.output:
            p = Path(args.output)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text + "\n", encoding="utf-8")
        else:
            print(text)
        return 0
    except Exception as exc:
        print(f"MeshPingPong evaluator infrastructure error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
