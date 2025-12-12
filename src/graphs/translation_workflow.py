# src/graphs/translation_workflow.py
"""
LangGraph workflow for Akka-to-Rebeca translation with error feedback loop.
"""
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from src.state.translation_state import TranslationState
from src.agents.translator_agent import (
    read_akka_code,
    translate_to_rebeca,
    write_rebeca_output,
    validate_rebeca,
    fix_translation_errors,
)


def should_retry(state: TranslationState) -> str:
    """Routing function: Decide whether to retry or end based on validation."""
    validation_result = state.get("validation_result", "")
    retry_count = state.get("retry_count", 0)
    max_retries = state.get("max_retries", 3)

    # Success case
    if validation_result == "success":
        print("✓ Validation successful! Workflow complete.")
        return "end"

    # Retry case
    if retry_count < max_retries:
        print(f"✗ Validation failed. Retrying... ({retry_count + 1}/{max_retries})")
        return "fix_errors"

    # Max retries reached
    print(f"✗ Max retries ({max_retries}) reached. Stopping.")
    return "end"


def create_translation_workflow():
    """Build the translation workflow graph with error feedback loop."""
    workflow = StateGraph(TranslationState)

    # Add nodes
    workflow.add_node("read_akka", read_akka_code)
    workflow.add_node("translate", translate_to_rebeca)
    workflow.add_node("write_rebeca", write_rebeca_output)
    workflow.add_node("validate", validate_rebeca)
    workflow.add_node("fix_errors", fix_translation_errors)
    workflow.add_node("end", lambda state: state)

    # Define flow
    workflow.add_edge(START, "read_akka")
    workflow.add_edge("read_akka", "translate")
    workflow.add_edge("translate", "write_rebeca")
    workflow.add_edge("write_rebeca", "validate")

    # Conditional routing after validation
    workflow.add_conditional_edges(
        "validate", should_retry, {"fix_errors": "fix_errors", "end": "end"}
    )

    # After fixing errors, write again and validate
    workflow.add_edge("fix_errors", "write_rebeca")
    workflow.add_edge("end", END)

    # Compile
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app


translation_graph = create_translation_workflow()
