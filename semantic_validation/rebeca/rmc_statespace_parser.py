from __future__ import annotations

import argparse
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _parse_value(value: str) -> Any:
    value = value.strip()

    if value.lower() == "true":
        return True

    if value.lower() == "false":
        return False

    try:
        return int(value)
    except ValueError:
        pass

    try:
        return float(value)
    except ValueError:
        return value


def parse_rmc_statespace(statespace_file: str | Path) -> dict:
    statespace_file = Path(statespace_file)

    if not statespace_file.exists():
        raise FileNotFoundError(
            f"RMC state-space file not found: {statespace_file}"
        )

    tree = ET.parse(statespace_file)
    root = tree.getroot()

    if root.tag != "transitionsystem":
        raise ValueError(
            f"Expected <transitionsystem> root, got <{root.tag}>"
        )

    states = []
    transitions = []

    for node in root:

        # ---------------- State ----------------
        if node.tag == "state":
            state = {
                "id": int(node.attrib["id"]),
                "atomic_propositions": (
                    node.attrib.get("atomicpropositions", "").strip()
                ),
                "rebecs": {},
            }

            for rebec_node in node.findall("rebec"):
                rebec_name = rebec_node.attrib["name"]

                rebec_data = {
                    "state_variables": {},
                    "queue": [],
                }

                statevars_node = rebec_node.find("statevariables")

                if statevars_node is not None:
                    for variable in statevars_node.findall("variable"):
                        rebec_data["state_variables"][
                            variable.attrib["name"]
                        ] = _parse_value(variable.text or "")

                queue_node = rebec_node.find("queue")

                if queue_node is not None:
                    for message in queue_node.findall("message"):
                        rebec_data["queue"].append(
                            {
                                "sender": message.attrib.get("sender"),
                                "message": (
                                    message.text or ""
                                ).strip(),
                            }
                        )

                state["rebecs"][rebec_name] = rebec_data

            states.append(state)

        # --------------- Transition ---------------
        elif node.tag == "transition":
            messageserver = node.find("messageserver")

            transition = {
                "source": int(node.attrib["source"]),
                "destination": int(node.attrib["destination"]),
            }

            if messageserver is not None:
                transition.update(
                    {
                        "sender": messageserver.attrib.get("sender"),
                        "owner": messageserver.attrib.get("owner"),
                        "message_server": messageserver.attrib.get("title"),
                    }
                )

            transitions.append(transition)

    state_ids = {state["id"] for state in states}

    invalid_transition_refs = []

    for transition in transitions:
        if (
            transition["source"] not in state_ids
            or transition["destination"] not in state_ids
        ):
            invalid_transition_refs.append(
                {
                    "source": transition["source"],
                    "destination": transition["destination"],
                }
            )

    return {
        "system_info": {},
        "checked_property": {},
        "state_space_info": {
            "exported_states": len(states),
            "exported_transitions": len(transitions),
            "invalid_transition_refs": invalid_transition_refs,
        },
        "states": states,
        "transitions": transitions,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Parse an RMC full state-space XML into normalized JSON."
    )

    parser.add_argument(
        "statespace_file",
        help="Path to statespace.xml",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output normalized JSON file",
    )

    args = parser.parse_args()

    parsed = parse_rmc_statespace(args.statespace_file)

    output_json = json.dumps(
        parsed,
        indent=2,
        ensure_ascii=False,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")

        print(f"Parsed RMC state space written to: {output_path}")
    else:
        print(output_json)


if __name__ == "__main__":
    main()
