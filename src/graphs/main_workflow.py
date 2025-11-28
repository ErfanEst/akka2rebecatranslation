# src/graphs/main_workflow.py
"""
Main LangGraph workflow definition.
Connects nodes together and defines the execution flow.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.state.workflow_state import WorkflowState
from src.agents.base_agent import input_processor, llm_processor, output_formatter


def create_workflow() -> StateGraph:
    """
    Build and return the main workflow graph.

    Returns:
        Compiled StateGraph ready to execute
    """

    # Step 1: Create empty graph with our state schema
    workflow = StateGraph(WorkflowState)

    # Step 2: Add nodes (the workers)
    workflow.add_node("process_input", input_processor)
    workflow.add_node("call_llm", llm_processor)
    workflow.add_node("format_output", output_formatter)

    # Step 3: Define edges (the flow)
    workflow.add_edge(START, "process_input")  # Start → process_input
    workflow.add_edge("process_input", "call_llm")  # process_input → call_llm
    workflow.add_edge("call_llm", "format_output")  # call_llm → format_output
    workflow.add_edge("format_output", END)  # format_output → End

    # Step 4: Add checkpointing for state persistence
    memory = MemorySaver()

    # Step 5: Compile into executable app
    app = workflow.compile(checkpointer=memory)

    return app


# Create the workflow instance
graph = create_workflow()
