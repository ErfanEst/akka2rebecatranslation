from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


EVALUATOR_REGISTRY = {
    "simple_ping_pong": (
        PROJECT_ROOT
        / "semantic_validation"
        / "rebeca"
        / "simple_ping_pong_evaluator.py"
    ),
}


def get_evaluator_path(
    example_id: str,
) -> Path:
    """
    Return evaluator script path for an example.
    """

    if example_id not in EVALUATOR_REGISTRY:
        raise ValueError(
            f"Unsupported example: {example_id}. "
            f"Available examples: "
            f"{list(EVALUATOR_REGISTRY.keys())}"
        )

    evaluator_path = EVALUATOR_REGISTRY[
        example_id
    ]

    if not evaluator_path.exists():
        raise FileNotFoundError(
            f"Evaluator file not found: "
            f"{evaluator_path}"
        )

    return evaluator_path
