# prompts/__init__.py
"""
Prompt library for Akka-to-Rebeca translation experiments.
"""

from .system_prompts import (
    MINIMAL,
    BASIC,
    DETAILED_RULES,
    FEW_SHOT_1,
    FEW_SHOT_3,
)

from .retry_prompts import (
    SIMPLE,
    DETAILED,
)

__all__ = [
    "MINIMAL",
    "BASIC",
    "DETAILED_RULES",
    "FEW_SHOT_1",
    "FEW_SHOT_3",
    "SIMPLE",
    "DETAILED",
]
