# src/state/translation_state.py
"""
State definition for Akka-to-Rebeca translation workflow with retry logic.
"""
from typing import TypedDict, List


class TranslationState(TypedDict):
    """
    State for the translation workflow with error feedback loop.
    """

    # Input phase
    akka_file_path: str  # Path to input .txt file
    akka_code: str  # Raw Akka code content

    # Translation phase
    rebeca_code: str  # Translated Rebeca code
    rebeca_file_path: str  # Path where .rebec will be saved

    # Validation phase
    validation_result: str  # "success" or "error"
    validation_output: str  # Output from JAR (1 or error message)

    # Error feedback loop
    retry_count: int  # Number of retry attempts
    max_retries: int  # Maximum allowed retries
    error_history: List[str]  # History of all errors encountered

    # Metadata
    current_step: str  # Current workflow step
    error: str | None  # Current error
