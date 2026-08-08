from __future__ import annotations

import json
import sys
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

from semantic_validation.core.trace_utils import (
    find_state_by_id,
    get_rebec_queue,
    get_rebec_state_var,
    transition_sequence,
)


def load_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_simple_ping_pong(
    parsed_result: dict,
) -> dict[str, Any]:

    evaluator = BaseSemanticEvaluator(
        parsed_result=parsed_result,
        example_id="simple_ping_pong",
    )

    states = evaluator.states
    transitions = evaluator.transitions

    if not states:
        raise ValueError("No states found in parsed RMC result.")

    # =========================================================
    # ACTOR LEVEL
    # =========================================================

    # ---------------------------------------------------------
    # PING-A1
    # StartMessage must lead to PingMessage being queued for Pong
    # ---------------------------------------------------------

    ping_a1_passed = False

    for transition in transitions:

        if (
            transition["message_server"] == "STARTMESSAGE"
            and transition["owner"] == "ping"
        ):

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if destination_state:

                pong_queue = get_rebec_queue(
                    destination_state,
                    "pong",
                )

                ping_a1_passed = any(
                    message["message"] == "PingMessage()"
                    and message["sender"] == "ping"
                    for message in pong_queue
                )

            break

    evaluator.add_result(
        "PING-A1",
        ping_a1_passed,
        (
            "StartMessage causes PingMessage to be sent to Pong."
            if ping_a1_passed
            else "Expected PingMessage after StartMessage was not observed."
        ),
    )

    # ---------------------------------------------------------
    # PING-A2
    # PongMessage before threshold increments count and continues
    # ---------------------------------------------------------

    ping_a2_passed = False

    for transition in transitions:

        if (
            transition["message_server"] == "PONGMESSAGE"
            and transition["owner"] == "ping"
        ):

            source_state = find_state_by_id(
                states,
                transition["source"],
            )

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if not source_state or not destination_state:
                continue

            old_count = get_rebec_state_var(
                source_state,
                "ping",
                "Ping.count",
            )

            new_count = get_rebec_state_var(
                destination_state,
                "ping",
                "Ping.count",
            )

            pong_queue = get_rebec_queue(
                destination_state,
                "pong",
            )

            if (
                old_count is not None
                and old_count < 9
                and new_count == old_count + 1
                and any(message["message"] == "PingMessage()" for message in pong_queue)
            ):
                ping_a2_passed = True
                break

    evaluator.add_result(
        "PING-A2",
        ping_a2_passed,
        (
            "PongMessage before threshold increments count "
            "and continues with PingMessage."
            if ping_a2_passed
            else "Continuation behavior before threshold failed."
        ),
    )

    # ---------------------------------------------------------
    # PING-A3
    # At count=8, processing PongMessage should produce count=9
    # and continue with PingMessage
    # ---------------------------------------------------------

    ping_a3_passed = False

    for transition in transitions:

        if (
            transition["message_server"] == "PONGMESSAGE"
            and transition["owner"] == "ping"
        ):

            source_state = find_state_by_id(
                states,
                transition["source"],
            )

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if not source_state or not destination_state:
                continue

            old_count = get_rebec_state_var(
                source_state,
                "ping",
                "Ping.count",
            )

            new_count = get_rebec_state_var(
                destination_state,
                "ping",
                "Ping.count",
            )

            pong_queue = get_rebec_queue(
                destination_state,
                "pong",
            )

            if (
                old_count == 8
                and new_count == 9
                and any(message["message"] == "PingMessage()" for message in pong_queue)
            ):
                ping_a3_passed = True
                break

    evaluator.add_result(
        "PING-A3",
        ping_a3_passed,
        (
            "9th PongMessage remains in continuation branch."
            if ping_a3_passed
            else "Boundary continuation behavior failed."
        ),
    )

    # ---------------------------------------------------------
    # PING-A4
    # At count=9, PongMessage should produce count=10
    # and StopMessage
    # ---------------------------------------------------------

    ping_a4_passed = False

    for transition in transitions:

        if (
            transition["message_server"] == "PONGMESSAGE"
            and transition["owner"] == "ping"
        ):

            source_state = find_state_by_id(
                states,
                transition["source"],
            )

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if not source_state or not destination_state:
                continue

            old_count = get_rebec_state_var(
                source_state,
                "ping",
                "Ping.count",
            )

            new_count = get_rebec_state_var(
                destination_state,
                "ping",
                "Ping.count",
            )

            pong_queue = get_rebec_queue(
                destination_state,
                "pong",
            )

            if (
                old_count == 9
                and new_count == 10
                and any(message["message"] == "StopMessage()" for message in pong_queue)
            ):
                ping_a4_passed = True
                break

    evaluator.add_result(
        "PING-A4",
        ping_a4_passed,
        (
            "10th PongMessage causes StopMessage."
            if ping_a4_passed
            else "Termination threshold behavior failed."
        ),
    )

    # ---------------------------------------------------------
    # PING-A5
    # After the 10th PongMessage, Ping must send StopMessage and
    # produce no further observable protocol behavior.
    # ---------------------------------------------------------

    final_state = states[-1]

    ping_termination_transition_index: int | None = None

    for index, transition in enumerate(transitions):

        if (
            transition["message_server"] == "PONGMESSAGE"
            and transition["owner"] == "ping"
        ):

            source_state = find_state_by_id(
                states,
                transition["source"],
            )

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if not source_state or not destination_state:
                continue

            old_count = get_rebec_state_var(
                source_state,
                "ping",
                "Ping.count",
            )

            new_count = get_rebec_state_var(
                destination_state,
                "ping",
                "Ping.count",
            )

            pong_queue = get_rebec_queue(
                destination_state,
                "pong",
            )

            stop_message_sent = any(
                message["message"] == "StopMessage()" and message["sender"] == "ping"
                for message in pong_queue
            )

            if old_count == 9 and new_count == 10 and stop_message_sent:
                ping_termination_transition_index = index
                break

    ping_has_no_later_transition = (
        ping_termination_transition_index is not None
        and all(
            transition["owner"] != "ping"
            for transition in transitions[ping_termination_transition_index + 1 :]
        )
    )

    ping_a5_passed = (
        ping_termination_transition_index is not None and ping_has_no_later_transition
    )

    evaluator.add_result(
        "PING-A5",
        ping_a5_passed,
        (
            "After sending StopMessage, Ping produces no further protocol behavior."
            if ping_a5_passed
            else (
                "Ping did not reach observable termination after the "
                "10th PongMessage."
            )
        ),
    )

    # ---------------------------------------------------------
    # PONG-A1
    # PingMessage must cause PongMessage to be sent back to Ping
    # ---------------------------------------------------------

    pong_a1_passed = False

    for transition in transitions:

        if (
            transition["message_server"] == "PINGMESSAGE"
            and transition["owner"] == "pong"
        ):

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if destination_state:

                ping_queue = get_rebec_queue(
                    destination_state,
                    "ping",
                )

                pong_a1_passed = any(
                    message["message"] == "PongMessage()"
                    and message["sender"] == "pong"
                    for message in ping_queue
                )

            if pong_a1_passed:
                break

    evaluator.add_result(
        "PONG-A1",
        pong_a1_passed,
        (
            "PingMessage causes Pong to send PongMessage back to Ping."
            if pong_a1_passed
            else "Expected PongMessage response was not observed."
        ),
    )

    # ---------------------------------------------------------
    # PONG-A2
    # Pong must reply to all 10 PingMessage executions
    # ---------------------------------------------------------

    ping_requests_to_pong = 0
    valid_pong_responses = 0

    for transition in transitions:

        if (
            transition["message_server"] == "PINGMESSAGE"
            and transition["owner"] == "pong"
        ):

            ping_requests_to_pong += 1

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if destination_state:

                ping_queue = get_rebec_queue(
                    destination_state,
                    "ping",
                )

                if any(
                    message["message"] == "PongMessage()"
                    and message["sender"] == "pong"
                    for message in ping_queue
                ):
                    valid_pong_responses += 1

    pong_a2_passed = ping_requests_to_pong == 10 and valid_pong_responses == 10

    evaluator.add_result(
        "PONG-A2",
        pong_a2_passed,
        (
            "Pong correctly replies to all 10 PingMessages."
            if pong_a2_passed
            else (
                f"Observed {valid_pong_responses} valid responses "
                f"for {ping_requests_to_pong} PingMessages."
            )
        ),
    )

    # ---------------------------------------------------------
    # PONG-A3
    # StopMessage must leave Pong observably terminated:
    # no outgoing messages, empty queues, and no later transition.
    # ---------------------------------------------------------

    pong_a3_passed = False

    for index, transition in enumerate(transitions):

        if (
            transition["message_server"] == "STOPMESSAGE"
            and transition["owner"] == "pong"
        ):

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if destination_state:

                ping_queue_after_stop = get_rebec_queue(
                    destination_state,
                    "ping",
                )

                pong_queue_after_stop = get_rebec_queue(
                    destination_state,
                    "pong",
                )

                no_later_transition = index == len(transitions) - 1

                pong_a3_passed = (
                    len(ping_queue_after_stop) == 0
                    and len(pong_queue_after_stop) == 0
                    and no_later_transition
                )

            break

    evaluator.add_result(
        "PONG-A3",
        pong_a3_passed,
        (
            "After StopMessage, Pong produces no further message or transition."
            if pong_a3_passed
            else "Pong stop behavior did not reach observable quiescence."
        ),
    )

    # =========================================================
    # INTERACTION LEVEL
    # =========================================================

    sequence = transition_sequence(parsed_result)

    # ---------------------------------------------------------
    # PP-I1
    # START -> PING -> PONG
    # ---------------------------------------------------------

    expected_start = [
        "STARTMESSAGE",
        "PINGMESSAGE",
        "PONGMESSAGE",
    ]

    pp_i1_passed = sequence[:3] == expected_start

    evaluator.add_result(
        "PP-I1",
        pp_i1_passed,
        (
            "Initial Ping-Pong interaction sequence is correct."
            if pp_i1_passed
            else f"Unexpected initial sequence: {sequence[:3]}"
        ),
    )

    # ---------------------------------------------------------
    # PP-I2
    # PingMessage / PongMessage must alternate
    # ---------------------------------------------------------

    protocol_messages = [
        msg
        for msg in sequence
        if msg
        in (
            "PINGMESSAGE",
            "PONGMESSAGE",
        )
    ]

    expected_protocol = []

    for _ in range(10):
        expected_protocol.extend(
            [
                "PINGMESSAGE",
                "PONGMESSAGE",
            ]
        )

    pp_i2_passed = protocol_messages == expected_protocol

    evaluator.add_result(
        "PP-I2",
        pp_i2_passed,
        (
            "PingMessage and PongMessage alternate correctly."
            if pp_i2_passed
            else "Protocol alternation differs from expected sequence."
        ),
    )

    # ---------------------------------------------------------
    # PP-I3
    # Exactly 10 PongMessage executions
    # ---------------------------------------------------------

    pong_message_count = sequence.count("PONGMESSAGE")

    evaluator.add_result(
        "PP-I3",
        pong_message_count == 10,
        (
            f"Exactly 10 PongMessage executions observed."
            if pong_message_count == 10
            else (
                f"Expected 10 PongMessage executions, "
                f"observed {pong_message_count}."
            )
        ),
    )

    # ---------------------------------------------------------
    # PP-I4
    # Protocol must end with StopMessage
    # ---------------------------------------------------------

    pp_i4_passed = len(sequence) > 0 and sequence[-1] == "STOPMESSAGE"

    evaluator.add_result(
        "PP-I4",
        pp_i4_passed,
        (
            "Protocol ends with StopMessage."
            if pp_i4_passed
            else "Final transition is not StopMessage."
        ),
    )

    # ---------------------------------------------------------
    # PP-I5
    # The completed interaction must reach observable quiescence.
    # This is representation-independent: no variable named
    # active, inactive, or stopped is required.
    # ---------------------------------------------------------

    ping_queue_final = get_rebec_queue(
        final_state,
        "ping",
    )

    pong_queue_final = get_rebec_queue(
        final_state,
        "pong",
    )

    pp_i5_passed = (
        ping_a5_passed
        and pong_a3_passed
        and len(ping_queue_final) == 0
        and len(pong_queue_final) == 0
        and len(sequence) > 0
        and sequence[-1] == "STOPMESSAGE"
    )

    evaluator.add_result(
        "PP-I5",
        pp_i5_passed,
        (
            "The completed interaction reaches terminal quiescence."
            if pp_i5_passed
            else (
                "The protocol did not reach representation-independent "
                "terminal quiescence."
            )
        ),
    )

    # =========================================================
    # SYSTEM LEVEL
    # =========================================================

    initial_state = states[0]

    # ---------------------------------------------------------
    # PP-SYS1
    # Both Ping and Pong must exist in the initial system state
    # ---------------------------------------------------------

    initial_rebecs = initial_state.get(
        "rebecs",
        {},
    )

    pp_sys1_passed = (
        "ping" in initial_rebecs
        and "pong" in initial_rebecs
        and len(initial_rebecs) == 2
    )

    evaluator.add_result(
        "PP-SYS1",
        pp_sys1_passed,
        (
            "Exactly one Ping and one Pong actor are created."
            if pp_sys1_passed
            else (
                "Expected Ping and Pong actors were not "
                f"found correctly. Found: {list(initial_rebecs.keys())}"
            )
        ),
    )

    # ---------------------------------------------------------
    # PP-SYS2
    # Effective wiring:
    # executing Ping's StartMessage must place PingMessage
    # in Pong's queue
    # ---------------------------------------------------------

    pp_sys2_passed = False

    for transition in transitions:

        if (
            transition["message_server"] == "STARTMESSAGE"
            and transition["owner"] == "ping"
        ):

            destination_state = find_state_by_id(
                states,
                transition["destination"],
            )

            if destination_state:

                pong_queue = get_rebec_queue(
                    destination_state,
                    "pong",
                )

                pp_sys2_passed = any(
                    message["message"] == "PingMessage()"
                    and message["sender"] == "ping"
                    for message in pong_queue
                )

            break

    evaluator.add_result(
        "PP-SYS2",
        pp_sys2_passed,
        (
            "Ping is effectively wired to Pong."
            if pp_sys2_passed
            else (
                "Ping did not deliver PingMessage to Pong; "
                "actor wiring may be incorrect."
            )
        ),
    )

    # ---------------------------------------------------------
    # PP-SYS3
    # StartMessage must exist initially
    # ---------------------------------------------------------

    initial_ping_queue = get_rebec_queue(
        initial_state,
        "ping",
    )

    pp_sys3_passed = any(
        message["message"] == "StartMessage()" for message in initial_ping_queue
    )

    evaluator.add_result(
        "PP-SYS3",
        pp_sys3_passed,
        (
            "Startup trigger exists in Ping initial queue."
            if pp_sys3_passed
            else "No initial StartMessage found."
        ),
    )

    # ---------------------------------------------------------
    # PP-SYS4
    # Automatic execution:
    # first transition must execute startup trigger
    # ---------------------------------------------------------

    pp_sys4_passed = len(sequence) > 0 and sequence[0] == "STARTMESSAGE"

    evaluator.add_result(
        "PP-SYS4",
        pp_sys4_passed,
        (
            "System begins automatically with StartMessage."
            if pp_sys4_passed
            else "Automatic startup was not observed."
        ),
    )

    # ---------------------------------------------------------
    # PP-SYS5
    # Complete execution must cover startup, ten Ping-Pong rounds,
    # StopMessage, and a final quiescent state.
    # ---------------------------------------------------------

    pp_sys5_passed = (
        len(sequence) > 0
        and sequence[0] == "STARTMESSAGE"
        and sequence.count("PINGMESSAGE") == 10
        and sequence.count("PONGMESSAGE") == 10
        and sequence[-1] == "STOPMESSAGE"
        and ping_a5_passed
        and pong_a3_passed
        and len(ping_queue_final) == 0
        and len(pong_queue_final) == 0
    )

    evaluator.add_result(
        "PP-SYS5",
        pp_sys5_passed,
        (
            "Complete execution reaches observable terminal quiescence."
            if pp_sys5_passed
            else (
                "The complete Ping-Pong execution did not reach the "
                "expected quiescent terminal state."
            )
        ),
    )

    # =========================================================
    # SUMMARY
    # =========================================================

    return evaluator.build_summary()


def main():

    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Simple Ping-Pong semantic properties " "from parsed RMC output."
        )
    )

    parser.add_argument(
        "parsed_result",
        help="Parsed RMC JSON result",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Optional semantic result JSON file",
    )

    args = parser.parse_args()

    parsed_result = load_json(args.parsed_result)

    semantic_result = evaluate_simple_ping_pong(parsed_result)

    output = json.dumps(
        semantic_result,
        indent=2,
        ensure_ascii=False,
    )

    if args.output:

        output_path = Path(args.output)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output_path.write_text(
            output,
            encoding="utf-8",
        )

        print(f"Semantic evaluation written to: " f"{output_path}")

    else:

        print(output)


if __name__ == "__main__":
    main()
