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
    semantic_input: str = "trace"


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
    "simple_producer_consumer": BenchmarkSemanticConfig(
        benchmark_id="simple_producer_consumer",
        manifest_benchmark="simpleProducerConsumer",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "phase2_simple"
            / "simple_producer_consumer"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "simple_producer_consumer_evaluator.py"
        ),
    ),
    "buffer_producer_consumer": BenchmarkSemanticConfig(
        benchmark_id="buffer_producer_consumer",
        manifest_benchmark="bufferProducerConsumer",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "phase2_simple"
            / "buffer_producer_consumer"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "buffer_producer_consumer_evaluator.py"
        ),
    ),
    "buffer_producer_consumer_v2": BenchmarkSemanticConfig(
        benchmark_id="buffer_producer_consumer_v2",
        manifest_benchmark="bufferProducerConsumer",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "phase2_simple"
            / "buffer_producer_consumer_v2"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "buffer_producer_consumer_v2_evaluator.py"
        ),
    ),
    "clockwise_ring_ping_pong": BenchmarkSemanticConfig(
        benchmark_id="clockwise_ring_ping_pong",
        manifest_benchmark="clockwiseRingPingPong",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "clockwise_ring_ping_pong_evaluator"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "clockwise_ring_ping_pong_evaluator_v3.py"
        ),
        semantic_input="statespace",
    ),
    "all_pings_to_one_pong": BenchmarkSemanticConfig(
        benchmark_id="all_pings_to_one_pong",
        manifest_benchmark="allPingsToOnePong",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "all_pings_to_one_pong"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "all_pings_to_one_pong_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "infinite_ping_pong": BenchmarkSemanticConfig(
        benchmark_id="infinite_ping_pong",
        manifest_benchmark="infinitePingPong",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "infinite_ping_pong"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "infinite_ping_pong_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "mesh_ping_pong": BenchmarkSemanticConfig(
        benchmark_id="mesh_ping_pong",
        manifest_benchmark="meshPingPong",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "mesh_ping_pong"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "mesh_ping_pong_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "odd_even_ring": BenchmarkSemanticConfig(
        benchmark_id="odd_even_ring",
        manifest_benchmark="oddEvenRing",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "odd_even_ring"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "odd_even_ring_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "odd_even_ring_4": BenchmarkSemanticConfig(
        benchmark_id="odd_even_ring_4",
        manifest_benchmark="oddEvenRing4",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "odd_even_ring_4"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "odd_even_ring_4_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "ping_pong_periodic_untimed": BenchmarkSemanticConfig(
        benchmark_id="ping_pong_periodic_untimed",
        manifest_benchmark="pingPongPeriodicUntimed",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "ping_pong_periodic_untimed"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "ping_pong_periodic_untimed_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "ping_pong_periodic_untimed_finite": BenchmarkSemanticConfig(
        benchmark_id="ping_pong_periodic_untimed_finite",
        manifest_benchmark="pingPongPeriodicUntimedFinite",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "ping_pong_periodic_untimed_finite"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "ping_pong_periodic_untimed_finite_evaluator.py"
        ),
        semantic_input="statespace",
    ),
    "star_topology_untimed_bounded": BenchmarkSemanticConfig(
        benchmark_id="star_topology_untimed_bounded",
        manifest_benchmark="starTopologyUntimedBounded",
        spec_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "specs"
            / "intermediate"
            / "star_topology_untimed_bounded"
            / "semantic_spec.json"
        ),
        evaluator_path=(
            PROJECT_ROOT
            / "semantic_validation"
            / "evaluators"
            / "star_topology_untimed_bounded_evaluator.py"
        ),
        semantic_input="statespace",
    ),
}


BENCHMARK_ALIASES: dict[str, str] = {
    "simplecounter": "simple_counter",
    "simple-counter": "simple_counter",
    "simple_counter": "simple_counter",
    "simplepingpong": "simple_ping_pong",
    "simple-ping-pong": "simple_ping_pong",
    "simple_ping_pong": "simple_ping_pong",
    "simpleproducerconsumer": "simple_producer_consumer",
    "simple-producer-consumer": "simple_producer_consumer",
    "simple_producer_consumer": "simple_producer_consumer",
    "bufferproducerconsumer": "buffer_producer_consumer",
    "buffer-producer-consumer": "buffer_producer_consumer",
    "buffer_producer_consumer": "buffer_producer_consumer",
    "bufferproducerconsumerv2": "buffer_producer_consumer_v2",
    "buffer-producer-consumer-v2": "buffer_producer_consumer_v2",
    "buffer_producer_consumer_v2": "buffer_producer_consumer_v2",
    "clockwiseringpingpong": "clockwise_ring_ping_pong",
    "clockwise-ring-ping-pong": "clockwise_ring_ping_pong",
    "clockwise_ring_ping_pong": "clockwise_ring_ping_pong",
    "allpingstoonepong": "all_pings_to_one_pong",
    "all-pings-to-one-pong": "all_pings_to_one_pong",
    "all_pings_to_one_pong": "all_pings_to_one_pong",
    "infinitepingpong": "infinite_ping_pong",
    "infinite-ping-pong": "infinite_ping_pong",
    "infinite_ping_pong": "infinite_ping_pong",
    "infiniteexample": "infinite_ping_pong",
    "meshpingpong": "mesh_ping_pong",
    "mesh-ping-pong": "mesh_ping_pong",
    "mesh_ping_pong": "mesh_ping_pong",
    "meshpingpongexample": "mesh_ping_pong",
    "oddevenring": "odd_even_ring",
    "odd-even-ring": "odd_even_ring",
    "odd_even_ring": "odd_even_ring",
    "oddevenactorsexample": "odd_even_ring",
    "oddevenring4": "odd_even_ring_4",
    "odd-even-ring-4": "odd_even_ring_4",
    "odd_even_ring_4": "odd_even_ring_4",
    "pingpongperiodicuntimed": "ping_pong_periodic_untimed",
    "ping-pong-periodic-untimed": "ping_pong_periodic_untimed",
    "ping_pong_periodic_untimed": "ping_pong_periodic_untimed",
    "pingpongperiodicuntimedfinite": "ping_pong_periodic_untimed_finite",
    "ping-pong-periodic-untimed-finite": "ping_pong_periodic_untimed_finite",
    "ping_pong_periodic_untimed_finite": "ping_pong_periodic_untimed_finite",
    "startopologyuntimedbounded": "star_topology_untimed_bounded",
    "star-topology-untimed-bounded": "star_topology_untimed_bounded",
    "star_topology_untimed_bounded": "star_topology_untimed_bounded",
}


def normalize_benchmark_id(
    benchmark_id: str,
) -> str:
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
