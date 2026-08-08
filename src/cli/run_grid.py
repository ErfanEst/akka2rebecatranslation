#!/usr/bin/env python3
"""Run provider/model/prompt/parameter experiment matrices."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import traceback
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from experiments.parameter_grid import (  # noqa: E402
    get_config_name,
)
from semantic_validation.core.evaluator_registry import available_benchmarks  # noqa: E402
from src.artifacts.workspace import WorkspaceManager, safe_identifier  # noqa: E402
from src.llm.llm_client import normalize_provider, validate_generation_config  # noqa: E402
from src.llm.model_config import (  # noqa: E402
    GenerationConfig,
    ModelTarget,
    parse_model_target,
    parse_optional_float,
    parse_optional_int,
    parse_prompt_cache_retention,
    parse_reasoning_effort,
)
from src.llm.pricing import (  # noqa: E402
    DEFAULT_PRICING_PATH,
    PricingCatalog,
)
from src.usage_cost import combine_usage_cost_summaries  # noqa: E402
from src.reporting import write_grid_markdown_report  # noqa: E402
from src.cli.run_pipeline import (  # noqa: E402
    DEFAULT_GRID_PROMPT_STRATEGIES,
    PROMPT_STRATEGIES,
    result_exit_code,
    result_summary,
    run_pipeline,
)


@dataclass(frozen=True)
class GridSetting:
    index: int
    prompt_strategy: str
    temperature: float | None
    top_p: float | None
    provider: str = ""
    model: str = ""
    reasoning_effort: str | None = None
    replicate_index: int = 1
    replicate_count: int = 1

    @property
    def parameter_name(self) -> str:
        if self.temperature is not None and self.top_p is not None:
            name = get_config_name(
                {"temperature": self.temperature, "top_p": self.top_p}
            )
        else:
            temperature = (
                "auto" if self.temperature is None else str(self.temperature).replace(".", "_")
            )
            top_p = "auto" if self.top_p is None else str(self.top_p).replace(".", "_")
            name = f"temp{temperature}_topp{top_p}"
        if self.reasoning_effort is not None:
            name += f"_reasoning{safe_identifier(self.reasoning_effort)}"
        return name

    @property
    def setting_id(self) -> str:
        local_id = f"{self.prompt_strategy}/{self.parameter_name}"
        if self.replicate_count > 1:
            local_id += f"/replicate_{self.replicate_index:02d}"
        if not self.model:
            return local_id
        return f"{self.provider}/{self.model}/{local_id}"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_workspace() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "workspace" / f"grid_{timestamp}"


def bounded_float(
    value: str, *, name: str, minimum: float, maximum: float
) -> float:
    parsed = float(value)
    if not minimum <= parsed <= maximum:
        raise argparse.ArgumentTypeError(
            f"{name} must be between {minimum} and {maximum}; received {value}"
        )
    return parsed


def temperature_value(value: str) -> float | None:
    parsed = parse_optional_float(value)
    if parsed is None:
        return None
    return bounded_float(value, name="temperature", minimum=0.0, maximum=2.0)


def top_p_value(value: str) -> float | None:
    parsed = parse_optional_float(value)
    if parsed is None:
        return None
    return bounded_float(value, name="top_p", minimum=0.0, maximum=1.0)


def unique(values: Iterable[Any]) -> list[Any]:
    return list(dict.fromkeys(values))


def setting_prompt_cache_key(
    args: argparse.Namespace, setting: GridSetting
) -> str | None:
    """Build a stable, prompt-version-aware cache key for one grid family."""

    prefix = getattr(args, "prompt_cache_key_prefix", None)
    if not prefix:
        return None
    model = setting.model or args.model
    provider = setting.provider or getattr(args, "provider", "auto")
    system_prompt = PROMPT_STRATEGIES[setting.prompt_strategy]
    prompt_digest = hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16]
    readable = ":".join(
        (
            safe_identifier(prefix),
            safe_identifier(provider),
            safe_identifier(model),
            safe_identifier(setting.prompt_strategy),
        )
    )
    return f"{readable}:{prompt_digest}"


def build_settings(
    prompt_strategies: Iterable[str],
    temperatures: Iterable[float | None],
    top_p_values: Iterable[float | None],
    model_targets: Iterable[ModelTarget] | None = None,
    reasoning_efforts: Iterable[str | None] = (None,),
    repetitions: int = 1,
) -> list[GridSetting]:
    if repetitions < 1:
        raise ValueError("repetitions must be at least 1")
    prompts = unique(prompt_strategies)
    temps = unique(temperatures)
    top_ps = unique(top_p_values)
    targets = unique(model_targets or [ModelTarget(provider="", model="")])
    efforts = unique(reasoning_efforts)
    settings: list[GridSetting] = []
    for target in targets:
        for prompt_strategy in prompts:
            for temperature in temps:
                for top_p in top_ps:
                    for reasoning_effort in efforts:
                        for replicate_index in range(1, repetitions + 1):
                            settings.append(
                                GridSetting(
                                    index=len(settings) + 1,
                                    prompt_strategy=prompt_strategy,
                                    temperature=temperature,
                                    top_p=top_p,
                                    provider=target.provider,
                                    model=target.model,
                                    reasoning_effort=reasoning_effort,
                                    replicate_index=replicate_index,
                                    replicate_count=repetitions,
                                )
                            )
    return settings


def model_targets_from_args(args: argparse.Namespace) -> list[ModelTarget]:
    raw_targets = getattr(args, "model_targets", None)
    default_provider = getattr(args, "provider", "auto")
    if raw_targets:
        parsed = [
            parse_model_target(value, default_provider=default_provider)
            for value in raw_targets
        ]
    else:
        parsed = [ModelTarget(provider=default_provider, model=args.model)]
    resolved = unique(
        ModelTarget(
            provider=normalize_provider(target.provider, target.model),
            model=target.model,
        )
        for target in parsed
    )
    supported = {"openai", "deepseek", "anthropic", "openai_compatible"}
    unknown = sorted({target.provider for target in resolved} - supported)
    if unknown:
        raise ValueError("Unknown providers: " + ", ".join(unknown))
    return resolved


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full Akka-to-Rebeca pipeline for every selected prompt "
            "strategy and every temperature × top_p combination."
        )
    )
    parser.add_argument("input", type=Path, help="Akka .txt/.scala file or directory")
    parser.add_argument("--workspace-root", type=Path, default=default_workspace())
    parser.add_argument("--candidate-id", help="Override ID for a single input file")
    parser.add_argument(
        "--model", default=os.getenv("OPENAI_MODEL", "gpt-5.1-2025-11-13")
    )
    parser.add_argument(
        "--provider",
        choices=("auto", "openai", "deepseek", "anthropic", "openai_compatible"),
        default=os.getenv("LLM_PROVIDER", "auto"),
    )
    parser.add_argument(
        "--model-targets",
        nargs="+",
        metavar="PROVIDER:MODEL",
        help=(
            "Optional multi-model axis, e.g. openai:gpt-5.6-sol "
            "deepseek:deepseek-reasoner anthropic:claude-sonnet-4-5."
        ),
    )
    parser.add_argument("--api-base-url")
    parser.add_argument(
        "--pricing-file",
        type=Path,
        default=DEFAULT_PRICING_PATH,
        help="Versioned price snapshot used to estimate every LLM request cost.",
    )
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help=(
            "Independent samples per parameter setting. Use more than one to "
            "measure nondeterminism; the default 1 preserves historical grids."
        ),
    )
    parser.add_argument(
        "--prompt-strategies",
        nargs="+",
        choices=sorted(PROMPT_STRATEGIES),
        default=list(DEFAULT_GRID_PROMPT_STRATEGIES),
        help="Prompts to run; defaults to all available strategies.",
    )
    parser.add_argument(
        "--temperatures",
        nargs="+",
        type=temperature_value,
        default=[None],
        metavar="FLOAT|auto",
    )
    parser.add_argument(
        "--top-p-values",
        nargs="+",
        type=top_p_value,
        default=[None],
        metavar="FLOAT|auto",
    )
    parser.add_argument(
        "--reasoning-efforts",
        nargs="+",
        type=parse_reasoning_effort,
        default=[None],
        metavar="EFFORT|auto",
    )
    parser.add_argument(
        "--prompt-cache-key-prefix",
        help=(
            "Enable stable OpenAI cache routing. A distinct key is derived for "
            "each model and prompt strategy, including a system-prompt hash."
        ),
    )
    parser.add_argument(
        "--prompt-cache-retention",
        type=parse_prompt_cache_retention,
        default=None,
        metavar="auto|in_memory|24h",
        help=(
            "OpenAI pre-GPT-5.6 retention policy. Use 24h for the GPT-5.1 grid "
            "and auto for GPT-5.6."
        ),
    )
    parser.add_argument(
        "--frequency-penalty", type=parse_optional_float, default=None
    )
    parser.add_argument(
        "--presence-penalty", type=parse_optional_float, default=None
    )
    parser.add_argument(
        "--max-output-tokens", type=parse_optional_int, default=None
    )
    parser.add_argument("--initial-prompt-file", type=Path)
    parser.add_argument("--retry-prompt-file", type=Path)
    parser.add_argument("--codegen-retry-prompt-file", type=Path)
    parser.add_argument("--semantic-retry-prompt-file", type=Path)
    parser.add_argument("--max-codegen-repairs", type=int, default=0)
    parser.add_argument("--max-semantic-repairs", type=int, default=0)
    parser.add_argument("--retrieval-corpus", type=Path)
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument("--near-duplicate-threshold", type=float, default=0.9)
    parser.add_argument(
        "--rmc-jar",
        type=Path,
        default=Path("/home/erfan/Thesis/tools/rmc-2.14.jar"),
    )
    parser.add_argument(
        "--java-bin",
        type=Path,
        default=Path("/usr/lib/jvm/java-17-openjdk-amd64/bin/java"),
    )
    parser.add_argument("--rmc-extension", default="CORE_REBECA")
    parser.add_argument("--rmc-timeout", type=int, default=120)
    parser.add_argument("--gpp-bin", default="g++")
    parser.add_argument("--compile-timeout", type=int, default=120)
    parser.add_argument("--model-checker-timeout", type=int, default=300)
    parser.add_argument("--evaluator-timeout", type=int, default=120)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--benchmark", choices=available_benchmarks())
    mode.add_argument(
        "--syntax-only",
        action="store_true",
        help="Stop each setting after its first syntax-valid candidate.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the complete grid plan without creating files or calling the model.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help=(
            "Resume a compatible grid workspace, skipping settings that already "
            "have a complete setting_result.json."
        ),
    )
    return parser


def setting_workspace(grid_root: Path, model: str, setting: GridSetting) -> Path:
    selected_model = setting.model or model
    model_dir = f"model_{safe_identifier(selected_model)}"
    if setting.model:
        workspace = (
            grid_root
            / f"provider_{safe_identifier(setting.provider)}"
            / model_dir
            / safe_identifier(setting.prompt_strategy)
            / setting.parameter_name
        )
    else:
        workspace = (
            grid_root
            / model_dir
            / safe_identifier(setting.prompt_strategy)
            / setting.parameter_name
        )
    if setting.replicate_count > 1:
        workspace /= f"replicate_{setting.replicate_index:02d}"
    return workspace


def plan_payload(
    args: argparse.Namespace, settings: list[GridSetting], grid_root: Path
) -> dict[str, Any]:
    input_path = args.input.expanduser().resolve()
    cache_keys_seen: set[str] = set()
    setting_payloads: list[dict[str, Any]] = []
    for setting in settings:
        cache_key = setting_prompt_cache_key(args, setting)
        if cache_key is None:
            cache_role = "DISABLED"
        elif cache_key in cache_keys_seen:
            cache_role = "REUSE_CANDIDATE"
        else:
            cache_role = "WARMUP_CANDIDATE"
            cache_keys_seen.add(cache_key)
        setting_payloads.append(
            {
                "index": setting.index,
                "setting_id": setting.setting_id,
                "prompt_strategy": setting.prompt_strategy,
                "provider": setting.provider or getattr(args, "provider", "auto"),
                "model": setting.model or args.model,
                "temperature": setting.temperature,
                "top_p": setting.top_p,
                "reasoning_effort": setting.reasoning_effort,
                "replicate_index": setting.replicate_index,
                "replicate_count": setting.replicate_count,
                "prompt_cache_key": cache_key,
                "prompt_cache_role": cache_role,
                "workspace": str(setting_workspace(grid_root, args.model, setting)),
            }
        )
    return {
        "schema_version": "2.0",
        "input": str(input_path),
        "candidate_id": args.candidate_id,
        "model": args.model,
        "provider": getattr(args, "provider", "auto"),
        "model_targets": unique(
            f"{setting.provider}:{setting.model}"
            for setting in settings
            if setting.model
        ),
        "workspace_root": str(grid_root),
        "prompt_strategies": unique(args.prompt_strategies),
        "temperatures": unique(args.temperatures),
        "top_p_values": unique(args.top_p_values),
        "reasoning_efforts": unique(getattr(args, "reasoning_efforts", [None])),
        "repetitions": getattr(args, "repetitions", 1),
        "prompt_cache": {
            "enabled": bool(getattr(args, "prompt_cache_key_prefix", None)),
            "key_prefix": getattr(args, "prompt_cache_key_prefix", None),
            "retention": getattr(args, "prompt_cache_retention", None),
            "first_request_per_key": "WARMUP_CANDIDATE",
            "hit_measurement": "provider_reported_cached_tokens",
        },
        "total_settings": len(settings),
        "max_attempts_per_candidate": args.max_attempts,
        "max_codegen_repairs": getattr(args, "max_codegen_repairs", 0),
        "max_semantic_repairs": getattr(args, "max_semantic_repairs", 0),
        "benchmark": args.benchmark,
        "syntax_only": args.syntax_only,
        "pricing_snapshot": PricingCatalog.from_path(
            getattr(args, "pricing_file", DEFAULT_PRICING_PATH)
        ).snapshot,
        "settings": setting_payloads,
    }


def aggregate_payload(
    manifest: dict[str, Any],
    setting_results: list[dict[str, Any]],
    *,
    started_at: str,
    finished_at: str | None,
) -> dict[str, Any]:
    candidate_statuses = Counter(
        candidate["status"]
        for result in setting_results
        for candidate in result.get("candidates", [])
    )
    setting_statuses = Counter(result["status"] for result in setting_results)
    overall_usage_cost = combine_usage_cost_summaries(
        result.get("usage_and_cost", {}) for result in setting_results
    )
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for result in setting_results:
        key = (result.get("provider", "unknown"), result.get("model", "unknown"))
        grouped.setdefault(key, []).append(result.get("usage_and_cost", {}))
    usage_cost_by_model = [
        {
            "provider": provider,
            "model": model,
            **combine_usage_cost_summaries(summaries),
        }
        for (provider, model), summaries in sorted(grouped.items())
    ]
    outcome_index = [
        {
            "setting_id": result.get("setting_id"),
            "provider": result.get("provider"),
            "model": result.get("model"),
            "prompt_strategy": result.get("prompt_strategy"),
            "temperature": result.get("temperature"),
            "top_p": result.get("top_p"),
            "reasoning_effort": result.get("reasoning_effort"),
            "replicate_index": result.get("replicate_index", 1),
            "candidate_id": candidate.get("candidate_id"),
            "status": candidate.get("status"),
            "attempts_used": candidate.get("attempts_used"),
            "syntax_pass": candidate.get("syntax_pass"),
            "syntax_valid_attempt": candidate.get("syntax_valid_attempt"),
            "first_pass_codegen_status": candidate.get(
                "first_pass_codegen_status", "NOT_RUN"
            ),
            "final_codegen_status": candidate.get(
                "final_codegen_status", "NOT_RUN"
            ),
            "semantic_status": candidate.get("semantic_status", "NOT_RUN"),
            "report": candidate.get("report"),
        }
        for result in setting_results
        for candidate in result.get("candidates", [])
    ]
    semantic_passes = [
        outcome for outcome in outcome_index if outcome["status"] == "SEMANTIC_PASS"
    ]
    return {
        "schema_version": "2.0",
        "started_at": started_at,
        "finished_at": finished_at,
        "model": manifest["model"],
        "provider": manifest.get("provider", "auto"),
        "model_targets": manifest.get("model_targets", []),
        "input": manifest["input"],
        "workspace_root": manifest["workspace_root"],
        "total_settings": manifest["total_settings"],
        "completed_settings": len(setting_results),
        "setting_status_counts": dict(sorted(setting_statuses.items())),
        "candidate_status_counts": dict(sorted(candidate_statuses.items())),
        "usage_and_cost": overall_usage_cost,
        "usage_and_cost_by_model": usage_cost_by_model,
        "outcome_index": outcome_index,
        "semantic_passes": semantic_passes,
        "pricing_snapshot": manifest.get("pricing_snapshot"),
        "prompt_cache": manifest.get("prompt_cache", {}),
        "markdown_report": str(Path(manifest["workspace_root"]) / "grid_report.md"),
        "settings": setting_results,
    }


def grid_exit_code(setting_results: list[dict[str, Any]]) -> int:
    if any(result.get("exit_code") == 1 for result in setting_results):
        return 1
    if setting_results and all(
        result.get("exit_code") == 0 for result in setting_results
    ):
        return 0
    return 2


def preflight_grid(args: argparse.Namespace, input_path: Path) -> None:
    """Fail once before a large grid when shared prerequisites are unavailable."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input path not found: {input_path}")
    if input_path.is_dir() and args.candidate_id:
        raise ValueError("--candidate-id is valid only for a single input file.")
    if args.max_attempts < 1:
        raise ValueError("--max-attempts must be at least 1.")
    if args.max_codegen_repairs < 0:
        raise ValueError("--max-codegen-repairs cannot be negative")
    if args.max_codegen_repairs and not args.benchmark:
        raise ValueError("--max-codegen-repairs requires --benchmark")
    if args.max_semantic_repairs < 0:
        raise ValueError("--max-semantic-repairs cannot be negative")
    if args.max_semantic_repairs and not args.benchmark:
        raise ValueError("--max-semantic-repairs requires --benchmark")
    if "retrieved_few_shot_v1" in args.prompt_strategies:
        if not args.retrieval_corpus:
            raise ValueError(
                "retrieved_few_shot_v1 requires --retrieval-corpus"
            )
    PricingCatalog.from_path(args.pricing_file)
    targets = model_targets_from_args(args)
    key_names = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "openai_compatible": "LLM_API_KEY",
    }
    missing_keys = sorted({
        key_names[target.provider]
        for target in targets
        if not os.getenv(key_names[target.provider], "")
    })
    if missing_keys:
        raise ValueError("Missing provider API keys: " + ", ".join(missing_keys))
    if any(target.provider == "openai_compatible" for target in targets):
        if not args.api_base_url and not os.getenv("LLM_BASE_URL", ""):
            raise ValueError(
                "openai_compatible requires --api-base-url or LLM_BASE_URL"
            )

    for target in targets:
        for temperature in unique(args.temperatures):
            for top_p in unique(args.top_p_values):
                for reasoning_effort in unique(args.reasoning_efforts):
                    validate_generation_config(
                        target.provider,
                        target.model,
                        GenerationConfig(
                            temperature=temperature,
                            top_p=top_p,
                            frequency_penalty=args.frequency_penalty,
                            presence_penalty=args.presence_penalty,
                            max_tokens=args.max_output_tokens,
                            reasoning_effort=reasoning_effort,
                            prompt_cache_key=setting_prompt_cache_key(
                                args,
                                GridSetting(
                                    index=0,
                                    prompt_strategy=args.prompt_strategies[0],
                                    temperature=temperature,
                                    top_p=top_p,
                                    provider=target.provider,
                                    model=target.model,
                                    reasoning_effort=reasoning_effort,
                                ),
                            ),
                            prompt_cache_retention=args.prompt_cache_retention,
                        ),
                    )

    rmc_jar = args.rmc_jar.expanduser().resolve()
    java_bin = args.java_bin.expanduser().resolve()
    if not rmc_jar.is_file():
        raise FileNotFoundError(f"RMC JAR not found: {rmc_jar}")
    if not java_bin.is_file():
        raise FileNotFoundError(f"Java executable not found: {java_bin}")
    for prompt_file in (
        args.initial_prompt_file,
        args.retry_prompt_file,
        args.codegen_retry_prompt_file,
        args.semantic_retry_prompt_file,
    ):
        if prompt_file and not prompt_file.expanduser().is_file():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    if args.benchmark and shutil.which(args.gpp_bin) is None:
        raise FileNotFoundError(f"C++ compiler not found on PATH: {args.gpp_bin}")


def validate_setting_configs(
    args: argparse.Namespace, settings: list[GridSetting]
) -> None:
    """Validate model-specific axes without requiring keys, files, or a workspace."""

    for setting in settings:
        validate_generation_config(
            setting.provider,
            setting.model,
            GenerationConfig(
                temperature=setting.temperature,
                top_p=setting.top_p,
                frequency_penalty=args.frequency_penalty,
                presence_penalty=args.presence_penalty,
                max_tokens=args.max_output_tokens,
                reasoning_effort=setting.reasoning_effort,
                prompt_cache_key=setting_prompt_cache_key(args, setting),
                prompt_cache_retention=args.prompt_cache_retention,
            ),
        )


def _read_json_object(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _resume_contract(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the immutable experiment fields that must match on resume."""

    contract = {
        key: manifest.get(key)
        for key in (
            "input",
            "candidate_id",
            "model",
            "provider",
            "model_targets",
            "prompt_strategies",
            "temperatures",
            "top_p_values",
            "reasoning_efforts",
            "total_settings",
            "max_attempts_per_candidate",
            "max_codegen_repairs",
            "max_semantic_repairs",
            "benchmark",
            "syntax_only",
            "prompt_cache",
        )
    }
    contract["repetitions"] = manifest.get("repetitions", 1)
    return contract | {
        "setting_ids": [
            setting.get("setting_id") for setting in manifest.get("settings", [])
        ]
    }


def _load_resume_state(
    grid_root: Path, planned_manifest: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    existing_manifest = _read_json_object(grid_root / "grid_manifest.json")
    if existing_manifest is None:
        raise ValueError(
            f"--resume requires a readable grid_manifest.json under {grid_root}"
        )
    if _resume_contract(existing_manifest) != _resume_contract(planned_manifest):
        raise ValueError(
            "The requested grid axes or execution contract do not match the "
            "existing grid_manifest.json; use the original command or a new workspace."
        )

    completed: dict[str, dict[str, Any]] = {}
    for setting in planned_manifest.get("settings", []):
        setting_id = setting.get("setting_id")
        workspace = Path(str(setting.get("workspace", "")))
        result = _read_json_object(workspace / "setting_result.json")
        if result is not None and result.get("setting_id") == setting_id:
            completed[str(setting_id)] = result
    return existing_manifest, completed


def _preserve_interrupted_workspace(workspace: Path) -> Path | None:
    """Move an incomplete setting aside before retrying it during resume."""

    if not workspace.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archived = workspace.with_name(f"{workspace.name}__interrupted_{timestamp}")
    counter = 1
    while archived.exists():
        archived = workspace.with_name(
            f"{workspace.name}__interrupted_{timestamp}_{counter:02d}"
        )
        counter += 1
    workspace.rename(archived)
    return archived


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        targets = model_targets_from_args(args)
    except ValueError as exc:
        print(f"Grid error: {exc}", file=sys.stderr)
        return 1
    try:
        settings = build_settings(
            args.prompt_strategies,
            args.temperatures,
            args.top_p_values,
            model_targets=targets,
            reasoning_efforts=args.reasoning_efforts,
            repetitions=args.repetitions,
        )
    except ValueError as exc:
        print(f"Grid error: {exc}", file=sys.stderr)
        return 1
    try:
        validate_setting_configs(args, settings)
    except ValueError as exc:
        print(f"Grid error: {exc}", file=sys.stderr)
        return 1
    grid_root = args.workspace_root.expanduser().resolve()
    manifest = plan_payload(args, settings, grid_root)

    if args.dry_run:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
        return 0

    input_path = args.input.expanduser().resolve()
    completed_results: dict[str, dict[str, Any]] = {}
    if args.resume:
        try:
            manifest, completed_results = _load_resume_state(grid_root, manifest)
        except Exception as exc:
            print(f"Grid error: {exc}", file=sys.stderr)
            return 1
        pending = [
            setting for setting in settings if setting.setting_id not in completed_results
        ]
        if pending:
            try:
                preflight_grid(args, input_path)
            except Exception as exc:
                print(f"Grid error: {exc}", file=sys.stderr)
                return 1
        started_at = str(manifest.get("created_at") or utc_now())
    else:
        try:
            preflight_grid(args, input_path)
        except Exception as exc:
            print(f"Grid error: {exc}", file=sys.stderr)
            return 1
        try:
            grid_root.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            print(
                f"Grid error: workspace already exists: {grid_root}. "
                "Choose a new --workspace-root or pass --resume; no existing "
                "artifact was overwritten.",
                file=sys.stderr,
            )
            return 1
        started_at = utc_now()
        manifest["created_at"] = started_at
        WorkspaceManager.write_json(grid_root / "grid_manifest.json", manifest)

    result_by_setting_id = dict(completed_results)
    planned_settings = {
        item["setting_id"]: item for item in manifest.get("settings", [])
    }

    for setting in settings:
        if setting.setting_id in result_by_setting_id:
            print(
                f"[{setting.index}/{len(settings)}] {setting.setting_id} [resume: skipped]",
                file=sys.stderr,
                flush=True,
            )
            continue
        workspace = setting_workspace(grid_root, args.model, setting)
        archived = _preserve_interrupted_workspace(workspace)
        if archived is not None:
            print(
                f"Preserved incomplete setting workspace at {archived}",
                file=sys.stderr,
                flush=True,
            )
        workspace.mkdir(parents=True, exist_ok=False)
        print(
            f"[{setting.index}/{len(settings)}] {setting.setting_id}",
            file=sys.stderr,
            flush=True,
        )
        setting_started_at = utc_now()
        setting_args = argparse.Namespace(**vars(args))
        setting_args.workspace_root = workspace
        setting_args.provider = setting.provider
        setting_args.model = setting.model
        setting_args.prompt_strategy = setting.prompt_strategy
        setting_args.temperature = setting.temperature
        setting_args.top_p = setting.top_p
        setting_args.reasoning_effort = setting.reasoning_effort
        setting_args.prompt_cache_key = setting_prompt_cache_key(args, setting)
        setting_args.prompt_cache_retention = args.prompt_cache_retention
        # build_candidate_pipeline expects this scalar option. Grid prompts always
        # come from the named strategies, so no system-prompt override is used.
        setting_args.system_prompt_file = None

        generation_config = GenerationConfig(
            temperature=setting.temperature,
            top_p=setting.top_p,
            frequency_penalty=args.frequency_penalty,
            presence_penalty=args.presence_penalty,
            max_tokens=args.max_output_tokens,
            reasoning_effort=setting.reasoning_effort,
            prompt_cache_key=setting_args.prompt_cache_key,
            prompt_cache_retention=args.prompt_cache_retention,
        )
        _, effective_parameters = validate_generation_config(
            setting.provider, setting.model, generation_config
        )

        base_result: dict[str, Any] = {
            "index": setting.index,
            "setting_id": setting.setting_id,
            "provider": setting.provider,
            "model": setting.model,
            "model_target": f"{setting.provider}:{setting.model}",
            "prompt_strategy": setting.prompt_strategy,
            "temperature": setting.temperature,
            "top_p": setting.top_p,
            "reasoning_effort": setting.reasoning_effort,
            "replicate_index": setting.replicate_index,
            "replicate_count": setting.replicate_count,
            "prompt_cache_key": setting_args.prompt_cache_key,
            "prompt_cache_retention": args.prompt_cache_retention,
            "prompt_cache_role": planned_settings.get(setting.setting_id, {}).get(
                "prompt_cache_role", "DISABLED"
            ),
            "requested_parameters": generation_config.requested_parameters(),
            "effective_parameters": effective_parameters,
            "workspace": str(workspace),
            "started_at": setting_started_at,
        }
        try:
            results, batch_errors = run_pipeline(
                setting_args,
                extra_metadata={
                    "grid_setting_id": setting.setting_id,
                    "grid_workspace_root": str(grid_root),
                    "grid_model_target": f"{setting.provider}:{setting.model}",
                },
            )
            exit_code = result_exit_code(results, batch_errors)
            base_result.update(result_summary(results, batch_errors))
            base_result.update(
                {
                    "status": {
                        0: "COMPLETED_SUCCESS",
                        1: "INFRA_ERROR",
                        2: "COMPLETED_WITH_VALIDATION_FAILURES",
                    }[exit_code],
                    "exit_code": exit_code,
                }
            )
        except Exception as exc:
            error_log = workspace / "setting_error.log"
            WorkspaceManager.write_text(error_log, traceback.format_exc())
            base_result.update(
                {
                    "status": "INFRA_ERROR",
                    "exit_code": 1,
                    "candidates": [],
                    "infrastructure_errors": [
                        {
                            "error_type": type(exc).__name__,
                            "error": str(exc),
                            "log": str(error_log),
                        }
                    ],
                }
            )

        base_result["finished_at"] = utc_now()
        WorkspaceManager.write_json(workspace / "setting_result.json", base_result)
        result_by_setting_id[setting.setting_id] = base_result
        setting_results = [
            result_by_setting_id[item.setting_id]
            for item in settings
            if item.setting_id in result_by_setting_id
        ]
        partial_aggregate = aggregate_payload(
            manifest,
            setting_results,
            started_at=started_at,
            finished_at=None,
        )
        WorkspaceManager.write_json(grid_root / "grid_result.json", partial_aggregate)
        write_grid_markdown_report(grid_root)

    finished_at = utc_now()
    setting_results = [
        result_by_setting_id[item.setting_id]
        for item in settings
        if item.setting_id in result_by_setting_id
    ]
    aggregate = aggregate_payload(
        manifest,
        setting_results,
        started_at=started_at,
        finished_at=finished_at,
    )
    WorkspaceManager.write_json(grid_root / "grid_result.json", aggregate)
    write_grid_markdown_report(grid_root)
    print(
        json.dumps(
            {
                "grid_report": str(grid_root / "grid_result.json"),
                "total_settings": len(settings),
                "setting_status_counts": aggregate["setting_status_counts"],
                "candidate_status_counts": aggregate["candidate_status_counts"],
                "usage_and_cost": aggregate["usage_and_cost"],
                "usage_and_cost_by_model": aggregate["usage_and_cost_by_model"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return grid_exit_code(setting_results)


if __name__ == "__main__":
    raise SystemExit(main())
