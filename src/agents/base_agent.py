# src/agents/base_agent.py
"""
Base agent implementations for workflow nodes.
Each agent is a function that takes state and returns updates.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage
from src.state.workflow_state import WorkflowState
from config.settings import settings

# Initialize LLM once (reuse across nodes)
llm = ChatOpenAI(
    model=settings.DEFAULT_MODEL,
    temperature=settings.TEMPERATURE,
    api_key=settings.OPENAI_API_KEY,
)


def input_processor(state: WorkflowState) -> dict:
    """
    Node 1: Process user input.

    Takes raw input and prepares it for the workflow.
    Returns updates to merge into state.
    """
    input_text = state.get("input_text", "")

    # Add user message to conversation
    messages = list(state.get("messages", []))
    messages.append(HumanMessage(content=input_text))

    return {
        "messages": messages,
        "current_step": "input_processed",
        "iteration_count": state.get("iteration_count", 0) + 1,
    }


def llm_processor(state: WorkflowState) -> dict:
    """
    Node 2: Send to LLM for processing.

    Takes the conversation history and gets AI response.
    """
    messages = state.get("messages", [])

    try:
        # Call LLM
        response = llm.invoke(messages)

        # Add AI response to messages
        updated_messages = list(messages)
        updated_messages.append(AIMessage(content=response.content))

        return {
            "messages": updated_messages,
            "current_step": "llm_processed",
            "final_output": response.content,
            "error": None,
        }
    except Exception as e:
        return {"current_step": "error", "error": str(e)}


def output_formatter(state: WorkflowState) -> dict:
    """
    Node 3: Format final output.

    Takes processed results and formats them nicely.
    """
    final_output = state.get("final_output", "")

    formatted = f"=== Result ===\n{final_output}\n=============="
    print(formatted)

    return {"current_step": "completed", "final_output": formatted}
