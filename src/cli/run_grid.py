#!/usr/bin/env python3
"""Run every selected prompt across a temperature/top-p Cartesian grid."""

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
    TEMPERATURES,
    TOP_P_VALUES,
    get_config_name,
)
from semantic_validation.core.evaluator_registry import available_benchmarks  # noqa: E402
from src.artifacts.workspace import WorkspaceManager, safe_identifier  # noqa: E402
from src.cli.run_pipeline import (  # noqa: E402
    PROMPT_STRATEGIES,
    result_exit_code,
    result_summary,
    run_pipeline,
)


@dataclass(frozen=True)
class GridSetting:
    index: int
    prompt_strategy: str
    temperature: float
    top_p: float

    @property
    def parameter_name(self) -> str:
        return get_config_name(
            {"temperature": self.temperature, "top_p": self.top_p}
        )

    @property
    def setting_id(self) -> str:
        return f"{self.prompt_strategy}/{self.parameter_name}"


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


def temperature_value(value: str) -> float:
    return bounded_float(value, name="temperature", minimum=0.0, maximum=2.0)


def top_p_value(value: str) -> float:
    return bounded_float(value, name="top_p", minimum=0.0, maximum=1.0)


def unique(values: Iterable[Any]) -> list[Any]:
    return list(dict.fromkeys(values))


def build_settings(
    prompt_strategies: Iterable[str],
    temperatures: Iterable[float],
    top_p_values: Iterable[float],
) -> list[GridSetting]:
    prompts = unique(prompt_strategies)
    temps = unique(temperatures)
    top_ps = unique(top_p_values)
    settings: list[GridSetting] = []
    for prompt_strategy in prompts:
        for temperature in temps:
            for top_p in top_ps:
                settings.append(
                    GridSetting(
                        index=len(settings) + 1,
                        prompt_strategy=prompt_strategy,
                        temperature=temperature,
                        top_p=top_p,
                    )
                )
    return settings


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
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument(
        "--prompt-strategies",
        nargs="+",
        choices=sorted(PROMPT_STRATEGIES),
        default=list(PROMPT_STRATEGIES),
        help="Prompts to run; defaults to all available strategies.",
    )
    parser.add_argument(
        "--temperatures",
        nargs="+",
        type=temperature_value,
        default=list(TEMPERATURES),
    )
    parser.add_argument(
        "--top-p-values",
        nargs="+",
        type=top_p_value,
        default=list(TOP_P_VALUES),
    )
    parser.add_argument("--frequency-penalty", type=float, default=0.0)
    parser.add_argument("--presence-penalty", type=float, default=0.0)
    parser.add_argument("--initial-prompt-file", type=Path)
    parser.add_argument("--retry-prompt-file", type=Path)
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
    model_dir = f"model_{safe_identifier(model)}"
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
        "schema_version": "1.0",
        "input": str(input_path),
        "candidate_id": args.candidate_id,
        "model": args.model,
        "workspace_root": str(grid_root),
        "prompt_strategies": unique(args.prompt_strategies),
        "temperatures": unique(args.temperatures),
        "top_p_values": unique(args.top_p_values),
        "total_settings": len(settings),
        "max_attempts_per_candidate": args.max_attempts,
        "benchmark": args.benchmark,
        "syntax_only": args.syntax_only,
        "settings": [
            {
                "index": setting.index,
                "setting_id": setting.setting_id,
                "prompt_strategy": setting.prompt_strategy,
                "temperature": setting.temperature,
                "top_p": setting.top_p,
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
        "schema_version": "1.0",
        "started_at": started_at,
        "finished_at": finished_at,
        "model": manifest["model"],
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
    if not os.getenv("OPENAI_API_KEY", ""):
        raise ValueError("OPENAI_API_KEY is required to run the grid.")

    rmc_jar = args.rmc_jar.expanduser().resolve()
    java_bin = args.java_bin.expanduser().resolve()
    if not rmc_jar.is_file():
        raise FileNotFoundError(f"RMC JAR not found: {rmc_jar}")
    if not java_bin.is_file():
        raise FileNotFoundError(f"Java executable not found: {java_bin}")
    for prompt_file in (args.initial_prompt_file, args.retry_prompt_file):
        if prompt_file and not prompt_file.expanduser().is_file():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    if args.benchmark and shutil.which(args.gpp_bin) is None:
        raise FileNotFoundError(f"C++ compiler not found on PATH: {args.gpp_bin}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = build_settings(
        args.prompt_strategies, args.temperatures, args.top_p_values
    )
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
        setting_args.prompt_strategy = setting.prompt_strategy
        setting_args.temperature = setting.temperature
        setting_args.top_p = setting.top_p
        # build_candidate_pipeline expects this scalar option. Grid prompts always
        # come from the named strategies, so no system-prompt override is used.
        setting_args.system_prompt_file = None

        base_result: dict[str, Any] = {
            "index": setting.index,
            "setting_id": setting.setting_id,
            "model": args.model,
            "prompt_strategy": setting.prompt_strategy,
            "temperature": setting.temperature,
            "top_p": setting.top_p,
            "workspace": str(workspace),
            "started_at": setting_started_at,
        }
        try:
            results, batch_errors = run_pipeline(
                setting_args,
                extra_metadata={
                    "grid_setting_id": setting.setting_id,
                    "grid_workspace_root": str(grid_root),
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
