from __future__ import annotations

from typing import Any


def normalize_name(value: str | None) -> str:
    """
    Normalize rebec and message-server names for comparison.
    """

    return (
        value or ""
    ).replace("_", "").upper()


def get_states(
    parsed_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return all parsed states.
    """

    return parsed_result.get("states", [])


def get_transitions(
    parsed_result: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return all parsed transitions.
    """

    return parsed_result.get("transitions", [])


def get_state_by_id(
    parsed_result: dict[str, Any],
    state_id: int,
) -> dict[str, Any] | None:
    """
    Find a state by ID inside a parsed RMC result.
    """

    for state in get_states(parsed_result):
        if state.get("id") == state_id:
            return state

    return None


def find_state_by_id(
    states: list[dict[str, Any]],
    state_id: int,
) -> dict[str, Any] | None:
    """
    Backward-compatible state lookup using a states list.
    """

    for state in states:
        if state.get("id") == state_id:
            return state

    return None


def transition_message(
    transition: dict[str, Any],
) -> str:
    """
    Return normalized transition message-server name.
    """

    return normalize_name(
        transition.get("message_server")
    )


def transition_owner(
    transition: dict[str, Any],
) -> str:
    """
    Return normalized transition owner name.
    """

    return normalize_name(
        transition.get("owner")
    )


def find_transitions(
    parsed_result: dict[str, Any],
    *,
    owner: str | None = None,
    message_server: str | None = None,
) -> list[dict[str, Any]]:
    """
    Find transitions matching owner and/or message server.
    """

    expected_owner = normalize_name(owner)
    expected_message = normalize_name(
        message_server
    )

    matches: list[dict[str, Any]] = []

    for transition in get_transitions(
        parsed_result
    ):
        if (
            owner is not None
            and transition_owner(transition)
            != expected_owner
        ):
            continue

        if (
            message_server is not None
            and transition_message(transition)
            != expected_message
        ):
            continue

        matches.append(transition)

    return matches


def transition_sequence(
    parsed_result: dict[str, Any],
) -> list[str]:
    """
    Return ordered normalized message-server names.
    """

    return [
        transition_message(transition)
        for transition in get_transitions(
            parsed_result
        )
        if transition.get(
            "message_server"
        ) is not None
    ]


def get_rebec(
    state: dict[str, Any] | None,
    rebec_name: str,
) -> dict[str, Any] | None:
    """
    Return one rebec from a state.

    Supports both dictionary-based and list-based
    rebec structures.
    """

    if not state:
        return None

    expected_name = normalize_name(
        rebec_name
    )

    rebecs = state.get("rebecs", {})

    if isinstance(rebecs, dict):
        for name, rebec in rebecs.items():
            if (
                normalize_name(name)
                == expected_name
            ):
                return rebec

    if isinstance(rebecs, list):
        for rebec in rebecs:
            name = (
                rebec.get("name")
                or rebec.get("id")
                or rebec.get("rebec")
            )

            if (
                normalize_name(name)
                == expected_name
            ):
                return rebec

    return None


def get_variable(
    state: dict[str, Any] | None,
    rebec_name: str,
    variable_name: str,
) -> Any:
    """
    Return one rebec state-variable value.
    """

    rebec = get_rebec(
        state,
        rebec_name,
    )

    if not rebec:
        return None

    variables = (
        rebec.get("state_variables")
        or rebec.get("statevars")
        or rebec.get("variables")
        or {}
    )

    return variables.get(variable_name)


def get_queue(
    state: dict[str, Any] | None,
    rebec_name: str,
) -> list[dict[str, Any]]:
    """
    Return one rebec message queue.
    """

    rebec = get_rebec(
        state,
        rebec_name,
    )

    if not rebec:
        return []

    queue = (
        rebec.get("queue")
        or rebec.get("message_queue")
        or []
    )

    return queue


def get_rebec_state_var(
    state: dict[str, Any],
    rebec_name: str,
    variable_name: str,
) -> Any:
    """
    Backward-compatible wrapper for get_variable().
    """

    return get_variable(
        state,
        rebec_name,
        variable_name,
    )


def get_rebec_queue(
    state: dict[str, Any],
    rebec_name: str,
) -> list[dict[str, Any]]:
    """
    Backward-compatible wrapper for get_queue().
    """

    return get_queue(
        state,
        rebec_name,
    )
