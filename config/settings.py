# config/settings.py
"""
Application configuration settings.
Loads environment variables and provides centralized config access.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")

    # LangChain Settings
    LANGCHAIN_TRACING: bool = (
        os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    )
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "akka2rebeca-translation")

    # Model Settings
    DEFAULT_MODEL: str = "gpt-4"
    TEMPERATURE: float = 0.1  # Low for consistent code generation

    # Translation Settings
    MAX_RETRIES: int = 3
    INPUT_DIR: str = "input_akka_codes"
    OUTPUT_DIR: str = "benchmarks"
    VALIDATION_DIR: str = "validation-output"

    # JAR Settings
    VALIDATOR_JAR_PATH: str = "compiler-2.25-jar-with-dependencies.jar"

    # Application Settings
    DEBUG: bool = True


# Create global settings instance
settings = Settings()
