#!/usr/bin/env python3

"""
Generic parser for RMC XML model-checking reports.

This module is benchmark-independent. It extracts:

- model-checking statistics
- checked-property information
- counterexample states
- rebec state variables
- rebec message queues
- state-to-state observations

Benchmark-specific semantic decisions belong in evaluator modules.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


class RMCTraceParseError(RuntimeError):
    """Raised when an RMC XML report cannot be parsed."""


@dataclass
class QueueMessage:
    name: str | None
    sender: str | None
    parameters: dict[str, Any] = field(default_factory=dict)
    raw_text: str | None = None


@dataclass
class RebecState:
    name: str
    state_variables: dict[str, Any] = field(default_factory=dict)
    queue: list[QueueMessage] = field(default_factory=list)


@dataclass
class TraceState:
    state_id: str
    atomic_propositions: list[str] = field(default_factory=list)
    rebecs: dict[str, RebecState] = field(default_factory=dict)


@dataclass
class ParsedRMCReport:
    source_path: str

    total_spent_time: float | None
    reached_states: int | None
    reached_transitions: int | None
    consumed_memory: float | None

    property_type: str | None
    property_name: str | None
    property_result: str | None
    options: list[str]

    trace_states: list[TraceState]

    @property
    def has_trace(self) -> bool:
        return bool(self.trace_states)

    @property
    def is_deadlock(self) -> bool:
        result = (self.property_result or "").strip().lower()
        return result == "deadlock" or "deadlock" in result

    @property
    def is_initial_deadlock(self) -> bool:
        if not self.is_deadlock:
            return False

        if len(self.trace_states) != 1:
            return False

        first_state = self.trace_states[0]

        return all(
            len(rebec.queue) == 0
            for rebec in first_state.rebecs.values()
        )

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["has_trace"] = self.has_trace
        result["is_deadlock"] = self.is_deadlock
        result["is_initial_deadlock"] = self.is_initial_deadlock
        return result


def _text(element: ET.Element | None) -> str | None:
    if element is None or element.text is None:
        return None

    value = element.text.strip()
    return value or None


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None

    try:
        return int(value)
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except ValueError:
        return None


def _convert_scalar(value: str | None, variable_type: str | None) -> Any:
    if value is None:
        return None

    stripped = value.strip()
    normalized_type = (variable_type or "").strip().lower()

    if normalized_type in {
        "byte",
        "short",
        "int",
        "integer",
        "long",
    }:
        try:
            return int(stripped)
        except ValueError:
            return stripped

    if normalized_type in {
        "float",
        "double",
        "real",
    }:
        try:
            return float(stripped)
        except ValueError:
            return stripped

    if normalized_type in {"bool", "boolean"}:
        lowered = stripped.lower()

        if lowered == "true":
            return True

        if lowered == "false":
            return False

    return stripped


def _parse_atomic_propositions(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []

    return [
        item.strip()
        for item in raw_value.split(",")
        if item.strip()
    ]


def _parse_queue_message(element: ET.Element) -> QueueMessage:
    message_name = (
        element.attrib.get("name")
        or element.attrib.get("msgsrv")
        or element.attrib.get("message")
    )

    sender = (
        element.attrib.get("sender")
        or element.attrib.get("sender-name")
        or element.attrib.get("senderName")
    )

    parameters: dict[str, Any] = {}

    for parameter in element.findall(".//parameter"):
        parameter_name = (
            parameter.attrib.get("name")
            or parameter.attrib.get("id")
            or f"parameter_{len(parameters)}"
        )

        parameter_type = parameter.attrib.get("type")
        parameters[parameter_name] = _convert_scalar(
            _text(parameter),
            parameter_type,
        )

    raw_text = _text(element)

    return QueueMessage(
        name=message_name,
        sender=sender,
        parameters=parameters,
        raw_text=raw_text,
    )


def _parse_rebec(element: ET.Element) -> RebecState:
    rebec_name = element.attrib.get("name")

    if not rebec_name:
        raise RMCTraceParseError(
            "Encountered a <rebec> element without a name."
        )

    state_variables: dict[str, Any] = {}

    variables_element = element.find("./statevariables")

    if variables_element is not None:
        for variable in variables_element.findall("./variable"):
            variable_name = variable.attrib.get("name")

            if not variable_name:
                continue

            variable_type = variable.attrib.get("type")

            state_variables[variable_name] = _convert_scalar(
                _text(variable),
                variable_type,
            )

    queue_messages: list[QueueMessage] = []
    queue_element = element.find("./queue")

    if queue_element is not None:
        for child in list(queue_element):
            queue_messages.append(_parse_queue_message(child))

    return RebecState(
        name=rebec_name,
        state_variables=state_variables,
        queue=queue_messages,
    )


def _parse_state(element: ET.Element) -> TraceState:
    state_id = element.attrib.get("id", "unknown")

    rebecs: dict[str, RebecState] = {}

    for rebec_element in element.findall("./rebec"):
        rebec = _parse_rebec(rebec_element)
        rebecs[rebec.name] = rebec

    return TraceState(
        state_id=state_id,
        atomic_propositions=_parse_atomic_propositions(
            element.attrib.get("atomicpropositions")
        ),
        rebecs=rebecs,
    )


def parse_rmc_report(path: str | Path) -> ParsedRMCReport:
    report_path = Path(path)

    if not report_path.is_file():
        raise RMCTraceParseError(
            f"RMC report does not exist: {report_path}"
        )

    try:
        tree = ET.parse(report_path)
    except ET.ParseError as exc:
        raise RMCTraceParseError(
            f"Invalid XML in RMC report {report_path}: {exc}"
        ) from exc
    except OSError as exc:
        raise RMCTraceParseError(
            f"Cannot read RMC report {report_path}: {exc}"
        ) from exc

    root = tree.getroot()

    if root.tag != "model-checking-report":
        raise RMCTraceParseError(
            "Unexpected XML root element: "
            f"{root.tag!r}; expected 'model-checking-report'."
        )

    system_info = root.find("./system-info")

    checked_property = root.find("./checked-property")

    property_options: list[str] = []

    if checked_property is not None:
        for option in checked_property.findall("./options/option"):
            option_text = _text(option)

            if option_text:
                property_options.append(option_text)

    trace_states = [
        _parse_state(state)
        for state in root.findall(
            "./counter-example-trace/state"
        )
    ]

    return ParsedRMCReport(
        source_path=str(report_path.resolve()),
        total_spent_time=_to_float(
            _text(
                system_info.find("./total-spent-time")
                if system_info is not None
                else None
            )
        ),
        reached_states=_to_int(
            _text(
                system_info.find("./reached-states")
                if system_info is not None
                else None
            )
        ),
        reached_transitions=_to_int(
            _text(
                system_info.find("./reached-transitions")
                if system_info is not None
                else None
            )
        ),
        consumed_memory=_to_float(
            _text(
                system_info.find("./consumed-mem")
                if system_info is not None
                else None
            )
        ),
        property_type=_text(
            checked_property.find("./type")
            if checked_property is not None
            else None
        ),
        property_name=_text(
            checked_property.find("./name")
            if checked_property is not None
            else None
        ),
        property_result=_text(
            checked_property.find("./result")
            if checked_property is not None
            else None
        ),
        options=property_options,
        trace_states=trace_states,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Parse an RMC XML report."
    )

    parser.add_argument(
        "--trace",
        required=True,
        help="Path to the RMC XML report.",
    )

    parser.add_argument(
        "--output",
        help="Optional output JSON path.",
    )

    args = parser.parse_args()

    try:
        report = parse_rmc_report(args.trace)
    except RMCTraceParseError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    content = json.dumps(
        report.to_dict(),
        indent=2,
        ensure_ascii=False,
    )

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content + "\n", encoding="utf-8")
    else:
        print(content)

    return 0


if __name__ == "__main__":
    sys.exit(main())
