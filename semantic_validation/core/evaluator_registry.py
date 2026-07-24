from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BenchmarkSemanticConfig:
    """
    Paths and metadata required for semantic validation
    of one benchmark.
    """

    benchmark_id: str
    manifest_benchmark: str
    spec_path: Path
    evaluator_path: Path


BENCHMARK_REGISTRY: dict[str, BenchmarkSemanticConfig] = {
    "simple_counter": BenchmarkSemanticConfig(
        benchmark_id="simple_counter",
        manifest_benchmark="simpleCounter",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "phase2_simple"
            / "simple_counter"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "simple_counter_evaluator.py"
        ),
    ),
    "simple_ping_pong": BenchmarkSemanticConfig(
        benchmark_id="simple_ping_pong",
        manifest_benchmark="simplePingPong",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "phase2_simple"
            / "simple_ping_pong"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "simple_ping_pong_evaluator.py"
        ),
    ),
}


BENCHMARK_ALIASES: dict[str, str] = {
    "simplecounter": "simple_counter",
    "simple-counter": "simple_counter",
    "simple_counter": "simple_counter",
    "simplepingpong": "simple_ping_pong",
    "simple-ping-pong": "simple_ping_pong",
    "simple_ping_pong": "simple_ping_pong",
}


def normalize_benchmark_id(benchmark_id: str) -> str:
    """
    Normalize benchmark names accepted from the command line.
    """

    normalized = benchmark_id.strip().lower()

    return BENCHMARK_ALIASES.get(
        normalized,
        normalized,
    )


def get_benchmark_config(
    benchmark_id: str,
) -> BenchmarkSemanticConfig:
    """
    Return the semantic-validation configuration for a benchmark.
    """

    normalized_id = normalize_benchmark_id(
        benchmark_id,
    )

    if normalized_id not in BENCHMARK_REGISTRY:
        available = ", ".join(sorted(BENCHMARK_REGISTRY))

        raise ValueError(
            f"Unsupported benchmark: {benchmark_id}. "
            f"Available benchmarks: {available}"
        )

    config = BENCHMARK_REGISTRY[normalized_id]

    if not config.spec_path.is_file():
        raise FileNotFoundError(
            f"Semantic specification not found: " f"{config.spec_path}"
        )

    if not config.evaluator_path.is_file():
        raise FileNotFoundError(
            f"Semantic evaluator not found: " f"{config.evaluator_path}"
        )

    return config


def get_evaluator_path(
    example_id: str,
) -> Path:
    """
    Backward-compatible evaluator lookup.
    """

    return get_benchmark_config(example_id).evaluator_path


def get_spec_path(
    example_id: str,
) -> Path:
    """
    Return the semantic specification path for a benchmark.
    """

    return get_benchmark_config(example_id).spec_path


def available_benchmarks() -> list[str]:
    """
    Return registered benchmark IDs.
    """

    return sorted(BENCHMARK_REGISTRY)
