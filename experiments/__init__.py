# experiments/__init__.py
"""
Experiments module for systematic LLM configuration testing.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base_model_v2 import BaseModelV2

__all__ = ["BaseModelV2"]


def __getattr__(name: str):
    """Keep the legacy public import without loading provider dependencies eagerly."""
    if name == "BaseModelV2":
        from .base_model_v2 import BaseModelV2

        return BaseModelV2
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
