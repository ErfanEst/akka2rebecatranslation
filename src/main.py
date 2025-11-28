# main.py
"""
Main entry point for the LangGraph application.
Run this file to execute the workflow.
"""
from src.graphs.main_workflow import graph
from src.state.workflow_state import WorkflowState


def main():
    """Execute the main workflow"""

    # Initial state
    initial_state: WorkflowState = {
        "messages": [],
        "input_text": "What is LangGraph and why should I use it?",
        "current_step": "starting",
        "processed_data": None,
        "final_output": "",
        "error": None,
        "iteration_count": 0,
    }

    # Configuration for stateful execution
    config = {"configurable": {"thread_id": "demo-thread-1"}}

    print("Starting LangGraph workflow...")
    print(f"Input: {initial_state['input_text']}\n")

    # Execute workflow
    final_state = graph.invoke(initial_state, config)

    print("\nWorkflow completed!")
    print(f"Final step: {final_state['current_step']}")

    if final_state.get("error"):
        print(f"Error occurred: {final_state['error']}")


if __name__ == "__main__":
    main()
