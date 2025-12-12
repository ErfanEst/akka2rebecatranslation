# tests/test_workflow.py
"""
Unit tests for workflow components.
"""
from src.state.workflow_state import WorkflowState
from src.agents.base_agent import input_processor


def test_input_processor():
    """Test that input processor adds message correctly"""

    # Setup test state
    test_state: WorkflowState = {
        "messages": [],
        "input_text": "Test input",
        "current_step": "start",
        "processed_data": None,
        "final_output": "",
        "error": None,
        "iteration_count": 0,
    }

    # Run function
    result = input_processor(test_state)

    # Assert results
    assert result["current_step"] == "input_processed"
    assert result["iteration_count"] == 1
    assert len(result["messages"]) == 1

    print("✓ Input processor test passed!")


if __name__ == "__main__":
    test_input_processor()
