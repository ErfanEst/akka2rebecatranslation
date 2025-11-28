# src/state/workflow_state.py
"""
State definitions for LangGraph workflows.
State is the shared memory that passes between nodes.
"""
from typing import TypedDict, Annotated, Sequence
from operator import add
from langchain_core.messages import BaseMessage


class WorkflowState(TypedDict):
    """
    Main workflow state structure.

    This is the 'shared notebook' that all nodes can read and write to.
    Keep it minimal, typed, and boring - complexity belongs in nodes, not state.
    """

    # Input data
    messages: Annotated[Sequence[BaseMessage], add]  # Chat messages
    input_text: str  # Raw input from user

    # Processing data
    current_step: str  # Which step are we at?
    processed_data: dict | None  # Intermediate results

    # Output data
    final_output: str  # Final result

    # Metadata
    error: str | None  # Any errors encountered
    iteration_count: int  # How many loops we've done
