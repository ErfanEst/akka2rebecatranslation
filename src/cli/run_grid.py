#!/usr/bin/env python3
"""Run provider/model/prompt/parameter experiment matrices."""

from __future__ import annotations

import argparse
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
    parse_reasoning_effort,
)
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


def build_settings(
    prompt_strategies: Iterable[str],
    temperatures: Iterable[float | None],
    top_p_values: Iterable[float | None],
    model_targets: Iterable[ModelTarget] | None = None,
    reasoning_efforts: Iterable[str | None] = (None,),
) -> list[GridSetting]:
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
                        settings.append(
                            GridSetting(
                                index=len(settings) + 1,
                                prompt_strategy=prompt_strategy,
                                temperature=temperature,
                                top_p=top_p,
                                provider=target.provider,
                                model=target.model,
                                reasoning_effort=reasoning_effort,
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
    parser.add_argument("--max-attempts", type=int, default=5)
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
    parser.add_argument("--semantic-retry-prompt-file", type=Path)
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
    return parser


def setting_workspace(grid_root: Path, model: str, setting: GridSetting) -> Path:
    selected_model = setting.model or model
    model_dir = f"model_{safe_identifier(selected_model)}"
    if setting.model:
        return (
            grid_root
            / f"provider_{safe_identifier(setting.provider)}"
            / model_dir
            / safe_identifier(setting.prompt_strategy)
            / setting.parameter_name
        )
    return (
        grid_root
        / model_dir
        / safe_identifier(setting.prompt_strategy)
        / setting.parameter_name
    )


def plan_payload(
    args: argparse.Namespace, settings: list[GridSetting], grid_root: Path
) -> dict[str, Any]:
    input_path = args.input.expanduser().resolve()
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
        "total_settings": len(settings),
        "max_attempts_per_candidate": args.max_attempts,
        "benchmark": args.benchmark,
        "syntax_only": args.syntax_only,
        "settings": [
            {
                "index": setting.index,
                "setting_id": setting.setting_id,
                "prompt_strategy": setting.prompt_strategy,
                "provider": setting.provider or getattr(args, "provider", "auto"),
                "model": setting.model or args.model,
                "temperature": setting.temperature,
                "top_p": setting.top_p,
                "reasoning_effort": setting.reasoning_effort,
                "workspace": str(
                    setting_workspace(grid_root, args.model, setting)
                ),
            }
            for setting in settings
        ],
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
    if args.max_semantic_repairs < 0:
        raise ValueError("--max-semantic-repairs cannot be negative")
    if args.max_semantic_repairs and not args.benchmark:
        raise ValueError("--max-semantic-repairs requires --benchmark")
    if "retrieved_few_shot_v1" in args.prompt_strategies:
        if not args.retrieval_corpus:
            raise ValueError(
                "retrieved_few_shot_v1 requires --retrieval-corpus"
            )
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
            ),
        )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        targets = model_targets_from_args(args)
    except ValueError as exc:
        print(f"Grid error: {exc}", file=sys.stderr)
        return 1
    settings = build_settings(
        args.prompt_strategies,
        args.temperatures,
        args.top_p_values,
        model_targets=targets,
        reasoning_efforts=args.reasoning_efforts,
    )
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
            "Choose a new --workspace-root; no existing artifact was overwritten.",
            file=sys.stderr,
        )
        return 1

    started_at = utc_now()
    manifest["created_at"] = started_at
    WorkspaceManager.write_json(grid_root / "grid_manifest.json", manifest)
    setting_results: list[dict[str, Any]] = []

    for setting in settings:
        workspace = setting_workspace(grid_root, args.model, setting)
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
        setting_results.append(base_result)
        WorkspaceManager.write_json(
            grid_root / "grid_result.json",
            aggregate_payload(
                manifest,
                setting_results,
                started_at=started_at,
                finished_at=None,
            ),
        )

    finished_at = utc_now()
    aggregate = aggregate_payload(
        manifest,
        setting_results,
        started_at=started_at,
        finished_at=finished_at,
    )
    WorkspaceManager.write_json(grid_root / "grid_result.json", aggregate)
    print(
        json.dumps(
            {
                "grid_report": str(grid_root / "grid_result.json"),
                "total_settings": len(settings),
                "setting_status_counts": aggregate["setting_status_counts"],
                "candidate_status_counts": aggregate["candidate_status_counts"],
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return grid_exit_code(setting_results)


if __name__ == "__main__":
    raise SystemExit(main())
