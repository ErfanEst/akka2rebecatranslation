#!/usr/bin/env python3
"""Validate an existing Rebeca candidate without constructing an LLM client."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from semantic_validation.core.evaluator_registry import available_benchmarks
from src.artifacts.workspace import WorkspaceManager
from src.semantic.semantic_validator import SemanticValidator
from src.syntax.rmc_compiler import RmcCompiler
from src.syntax.syntax_validator import SyntaxValidator


def default_workspace() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "workspace" / f"offline_validation_{timestamp}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate an existing Rebeca model without any LLM request."
    )
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--benchmark", choices=available_benchmarks(), required=True)
    parser.add_argument("--workspace-root", type=Path, default=default_workspace())
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
    return parser


def validate(args: argparse.Namespace) -> tuple[dict[str, object], int]:
    candidate = args.candidate.expanduser().resolve()
    if not candidate.is_file():
        raise FileNotFoundError(f"Rebeca candidate not found: {candidate}")
    if shutil.which(args.gpp_bin) is None:
        raise FileNotFoundError(f"C++ compiler not found on PATH: {args.gpp_bin}")

    workspace = args.workspace_root.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=False)
    attempt_root = workspace / "attempt_1"
    attempt_root.mkdir()
    local_candidate = attempt_root / "candidate.rebeca"
    shutil.copy2(candidate, local_candidate)

    compiler = RmcCompiler(
        jar_path=args.rmc_jar,
        java_bin=args.java_bin,
        extension=args.rmc_extension,
        timeout_seconds=args.rmc_timeout,
    )
    compiler.preflight()
    syntax = SyntaxValidator(compiler).validate(local_candidate, attempt_root)

    if syntax.passed:
        semantic = SemanticValidator(
            project_root=PROJECT_ROOT,
            gpp_bin=args.gpp_bin,
            compile_timeout=args.compile_timeout,
            model_checker_timeout=args.model_checker_timeout,
            evaluator_timeout=args.evaluator_timeout,
        ).validate(
            syntax_result=syntax,
            attempt_root=attempt_root,
            benchmark=args.benchmark,
        )
        final_status = semantic.status
    else:
        semantic = None
        final_status = "SYNTAX_FAIL"

    payload: dict[str, object] = {
        "schema_version": "offline_candidate_validation_v1",
        "candidate": str(candidate),
        "workspace": str(workspace),
        "benchmark": args.benchmark,
        "llm_request_count": 0,
        "syntax": syntax.to_dict(),
        "semantic": semantic.to_dict() if semantic else {"status": "NOT_RUN"},
        "final_status": final_status,
    }
    report_path = workspace / "offline_validation_result.json"
    WorkspaceManager.write_json(report_path, payload)
    payload["report"] = str(report_path)

    if final_status in {"SEMANTIC_PASS", "SYNTAX_PASS"}:
        exit_code = 0
    elif final_status == "INFRA_ERROR":
        exit_code = 1
    else:
        exit_code = 2
    return payload, exit_code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload, exit_code = validate(args)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return exit_code
    except Exception as exc:
        print(f"Validation error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
