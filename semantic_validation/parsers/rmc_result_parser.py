from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


def _parse_value(value: str) -> Any:
    """
    Convert XML text values to basic Python types where possible.
    """
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


def parse_rmc_result(result_file: str | Path) -> dict:
    """
    Parse an RMC model-checking result XML file.

    Returns a normalized structure containing:
      - model checking result
      - state-space statistics
      - states
      - message queues
      - transitions
    """

    result_file = Path(result_file)

    if not result_file.exists():
        raise FileNotFoundError(
            f"RMC result file not found: {result_file}"
        )

    tree = ET.parse(result_file)
    root = tree.getroot()

    # ---------------------------------------------------------
    # System information
    # ---------------------------------------------------------

    system_info_node = root.find("system-info")

    system_info = {}

    if system_info_node is not None:

        for child in system_info_node:
            system_info[child.tag] = _parse_value(
                child.text or ""
            )

    # ---------------------------------------------------------
    # Checked property
    # ---------------------------------------------------------

    checked_property_node = root.find("checked-property")

    checked_property = {}

    if checked_property_node is not None:

        for child in checked_property_node:

            if child.tag == "options":
                checked_property["options"] = [
                    option.text
                    for option in child.findall("option")
                ]

            else:
                checked_property[child.tag] = (
                    child.text.strip()
                    if child.text
                    else ""
                )

    # ---------------------------------------------------------
    # States and transitions
    # ---------------------------------------------------------

    trace_node = root.find("counter-example-trace")

    states = []
    transitions = []

    if trace_node is not None:

        for node in trace_node:

            # -------------------------------------------------
            # State
            # -------------------------------------------------

            if node.tag == "state":

                state = {
                    "id": int(node.attrib["id"]),
                    "atomic_propositions": (
                        node.attrib
                        .get("atomicpropositions", "")
                        .strip()
                    ),
                    "rebecs": {},
                }

                for rebec_node in node.findall("rebec"):

                    rebec_name = rebec_node.attrib["name"]

                    rebec_data = {
                        "state_variables": {},
                        "queue": [],
                    }

                    # State variables
                    statevars_node = rebec_node.find(
                        "statevariables"
                    )

                    if statevars_node is not None:

                        for variable in statevars_node.findall(
                            "variable"
                        ):

                            variable_name = variable.attrib[
                                "name"
                            ]

                            variable_value = _parse_value(
                                variable.text or ""
                            )

                            rebec_data[
                                "state_variables"
                            ][variable_name] = variable_value

                    # Message queue
                    queue_node = rebec_node.find("queue")

                    if queue_node is not None:

                        for message in queue_node.findall(
                            "message"
                        ):

                            rebec_data["queue"].append(
                                {
                                    "sender": message.attrib.get(
                                        "sender"
                                    ),
                                    "message": (
                                        message.text or ""
                                    ).strip(),
                                }
                            )

                    state["rebecs"][rebec_name] = rebec_data

                states.append(state)

            # -------------------------------------------------
            # Transition
            # -------------------------------------------------

            elif node.tag == "transition":

                messageserver = node.find(
                    "messageserver"
                )

                transition = {
                    "source": int(
                        node.attrib["source"]
                    ),
                    "destination": int(
                        node.attrib["destination"]
                    ),
                }

                if messageserver is not None:

                    transition.update(
                        {
                            "sender": messageserver.attrib.get(
                                "sender"
                            ),
                            "owner": messageserver.attrib.get(
                                "owner"
                            ),
                            "message_server": (
                                messageserver.attrib.get(
                                    "title"
                                )
                            ),
                        }
                    )

                transitions.append(transition)

    return {
        "system_info": system_info,
        "checked_property": checked_property,
        "states": states,
        "transitions": transitions,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Parse an RMC result.xml file into normalized JSON."
        )
    )

    parser.add_argument(
        "result_file",
        help="Path to the RMC result.xml file",
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Optional output JSON file",
    )

    args = parser.parse_args()

    parsed = parse_rmc_result(
        args.result_file
    )

    output_json = json.dumps(
        parsed,
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
            output_json,
            encoding="utf-8",
        )

        print(
            f"Parsed RMC result written to: "
            f"{output_path}"
        )

    else:

        print(output_json)


if __name__ == "__main__":
    main()
