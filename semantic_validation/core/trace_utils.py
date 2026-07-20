from __future__ import annotations

from typing import Any


def find_state_by_id(
    states: list[dict],
    state_id: int,
) -> dict | None:
    """
    Find a state by its numeric ID.
    """

    for state in states:
        if state.get("id") == state_id:
            return state

    return None


def get_rebec_state_var(
    state: dict,
    rebec_name: str,
    variable_name: str,
) -> Any:
    """
    Return a state variable value for a rebec.
    """

    return (
        state
        .get("rebecs", {})
        .get(rebec_name, {})
        .get("state_variables", {})
        .get(variable_name)
    )


def get_rebec_queue(
    state: dict,
    rebec_name: str,
) -> list[dict]:
    """
    Return the message queue of a rebec.
    """

    return (
        state
        .get("rebecs", {})
        .get(rebec_name, {})
        .get("queue", [])
    )


def transition_sequence(
    parsed_result: dict,
) -> list[str]:
    """
    Return the ordered list of executed message servers.
    """

    return [
        transition.get("message_server")
        for transition
        in parsed_result.get("transitions", [])
        if transition.get("message_server") is not None
    ]
