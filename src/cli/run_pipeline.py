#!/usr/bin/env python3
"""Run the workspace-based Akka-to-Rebeca validation pipeline."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from prompts import phase2_prompts, retry_prompts
from semantic_validation.core.evaluator_registry import available_benchmarks
from src.artifacts.report_writer import ReportWriter
from src.artifacts.result_models import PipelineStatus
from src.artifacts.workspace import WorkspaceManager
from src.llm.llm_client import OpenAILangChainClient
from src.llm.output_cleaner import OutputCleaner
from src.llm.prompt_builder import PromptBuilder
from src.pipeline.batch_pipeline import BatchPipeline
from src.pipeline.candidate_pipeline import CandidatePipeline
from src.pipeline.retry_manager import RetryManager
from src.pipeline.translation_pipeline import TranslationPipeline
from src.semantic.semantic_validator import SemanticValidator
from src.syntax.rmc_compiler import RmcCompiler
from src.syntax.syntax_validator import SyntaxValidator


PROMPT_STRATEGIES = {
    "minimal": phase2_prompts.MINIMAL,
    "basic": phase2_prompts.BASIC,
    "detailed_rules": phase2_prompts.DETAILED_RULES,
    "v1_advanced": phase2_prompts.VERSION_1_ADVANCED,
    "v2_advanced": phase2_prompts.VERSION_2_ADVANCED,
    "few_shot_1": phase2_prompts.FEW_SHOT_1,
    "few_shot_2": phase2_prompts.FEW_SHOT_2,
    "few_shot_3": phase2_prompts.FEW_SHOT_3,
}


def default_workspace() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "workspace" / timestamp


def read_optional(path: Path | None, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path else fallback


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Translate Akka to Rebeca with compiler-feedback retries, RMC 2.14 "
            "syntax validation, isolated artifacts, and optional semantic evaluation."
        )
    )
    parser.add_argument("input", type=Path, help="Akka .txt/.scala file or directory")
    parser.add_argument("--workspace-root", type=Path, default=default_workspace())
    parser.add_argument("--candidate-id", help="Override ID for a single input file")
    parser.add_argument(
        "--model", default=os.getenv("OPENAI_MODEL", "gpt-5.1-2025-11-13")
    )
    parser.add_argument("--max-attempts", type=int, default=5)
    parser.add_argument("--temperature", type=float, default=0.1)
    parser.add_argument("--top-p", type=float, default=1.0)
    parser.add_argument("--frequency-penalty", type=float, default=0.0)
    parser.add_argument("--presence-penalty", type=float, default=0.0)
    parser.add_argument(
        "--prompt-strategy", choices=sorted(PROMPT_STRATEGIES), default="basic"
    )
    parser.add_argument("--system-prompt-file", type=Path)
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
        help="Stop after the first syntax-valid candidate.",
    )
    return parser


def build_candidate_pipeline(args: argparse.Namespace) -> CandidatePipeline:
    system_prompt = read_optional(
        args.system_prompt_file, PROMPT_STRATEGIES[args.prompt_strategy]
    )
    initial_template = read_optional(args.initial_prompt_file, "{akka_code}")
    retry_template = read_optional(args.retry_prompt_file, retry_prompts.DETAILED)

    llm_client = OpenAILangChainClient(
        model=args.model,
        api_key=os.getenv("OPENAI_API_KEY", ""),
        temperature=args.temperature,
        top_p=args.top_p,
        frequency_penalty=args.frequency_penalty,
        presence_penalty=args.presence_penalty,
    )
    compiler = RmcCompiler(
        jar_path=args.rmc_jar,
        java_bin=args.java_bin,
        extension=args.rmc_extension,
        timeout_seconds=args.rmc_timeout,
    )
    compiler.preflight()
    syntax_validator = SyntaxValidator(compiler)
    report_writer = ReportWriter()
    translation = TranslationPipeline(
        llm_client=llm_client,
        prompt_builder=PromptBuilder(
            system_prompt=system_prompt,
            initial_template=initial_template,
            retry_template=retry_template,
            strategy=args.prompt_strategy,
        ),
        output_cleaner=OutputCleaner(),
        syntax_validator=syntax_validator,
        retry_manager=RetryManager(args.max_attempts),
        report_writer=report_writer,
    )
    semantic = None
    if args.benchmark:
        if shutil.which(args.gpp_bin) is None:
            raise FileNotFoundError(f"C++ compiler not found on PATH: {args.gpp_bin}")
        semantic = SemanticValidator(
            project_root=PROJECT_ROOT,
            gpp_bin=args.gpp_bin,
            compile_timeout=args.compile_timeout,
            model_checker_timeout=args.model_checker_timeout,
            evaluator_timeout=args.evaluator_timeout,
        )
    return CandidatePipeline(
        translation_pipeline=translation,
        workspace_manager=WorkspaceManager(args.workspace_root),
        max_attempts=args.max_attempts,
        semantic_validator=semantic,
        report_writer=report_writer,
    )


def run_pipeline(
    args: argparse.Namespace,
    *,
    extra_metadata: dict[str, object] | None = None,
) -> tuple[list, list[dict[str, str]]]:
    """Execute one pipeline setting without printing or exiting.

    Keeping this orchestration callable lets the grid runner reuse precisely the
    same candidate and batch behavior as the single-setting CLI.
    """
    pipeline = build_candidate_pipeline(args)
    input_path = args.input.expanduser().resolve()
    run_metadata = {
        "model": args.model,
        "prompt_strategy": args.prompt_strategy,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "frequency_penalty": args.frequency_penalty,
        "presence_penalty": args.presence_penalty,
        "rmc_jar": str(args.rmc_jar.expanduser().resolve()),
        "rmc_extension": args.rmc_extension,
    }
    run_metadata.update(extra_metadata or {})

    batch_errors: list[dict[str, str]] = []
    if input_path.is_file():
        results = [
            pipeline.run(
                input_path,
                candidate_id=args.candidate_id,
                benchmark=args.benchmark,
                metadata=run_metadata,
            )
        ]
    elif input_path.is_dir():
        if args.candidate_id:
            raise ValueError("--candidate-id is valid only for a single file.")
        batch = BatchPipeline(pipeline)
        sources = batch.discover(input_path)
        if not sources:
            raise ValueError(f"No .txt or .scala files found under {input_path}")
        results = batch.run(
            sources,
            benchmark=args.benchmark,
            relative_to=input_path,
            metadata=run_metadata,
        )
        batch_errors = batch.errors
    else:
        raise FileNotFoundError(f"Input path not found: {input_path}")
    return results, batch_errors


def result_summary(results: list, batch_errors: list[dict[str, str]]) -> dict:
    return {
        "candidates": [
            {
                "candidate_id": result.candidate_id,
                "status": result.overall_status.value,
                "report": str(Path(result.workspace_path) / "candidate_result.json"),
            }
            for result in results
        ],
        "infrastructure_errors": batch_errors,
    }


def result_exit_code(results: list, batch_errors: list[dict[str, str]]) -> int:
    successful = {PipelineStatus.SYNTAX_PASS, PipelineStatus.SEMANTIC_PASS}
    has_infra_error = bool(batch_errors) or any(
        result.overall_status == PipelineStatus.INFRA_ERROR for result in results
    )
    if has_infra_error:
        return 1
    if results and all(result.overall_status in successful for result in results):
        return 0
    return 2


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        results, batch_errors = run_pipeline(args)
        print(
            json.dumps(
                result_summary(results, batch_errors),
                indent=2,
                ensure_ascii=False,
            )
        )
        return result_exit_code(results, batch_errors)
    except Exception as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
