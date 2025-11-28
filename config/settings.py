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
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "default")

    # Model Settings
    DEFAULT_MODEL: str = "gpt-4"
    TEMPERATURE: float = 0.7

    # Application Settings
    DEBUG: bool = True


# Create global settings instance
settings = Settings()
