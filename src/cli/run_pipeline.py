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

from prompts import phase2_prompts, researched_prompts
from semantic_validation.core.evaluator_registry import available_benchmarks
from src.artifacts.report_writer import ReportWriter
from src.artifacts.result_models import PipelineStatus
from src.artifacts.workspace import WorkspaceManager
from src.llm.llm_client import OpenAILangChainClient
from src.llm.example_retriever import VerifiedExampleRetriever
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
    "minimal_v2": researched_prompts.MINIMAL_V2,
    "handbook_zero_shot_v1": researched_prompts.HANDBOOK_ZERO_SHOT_V1,
    "retrieved_few_shot_v1": researched_prompts.RETRIEVED_FEW_SHOT_V1,
}

# Keep the historical default grid stable at 8 x 4 x 4 = 128 settings.
# New strategies are opt-in through --prompt-strategies so old experiments and
# their tests remain exactly reproducible.
DEFAULT_GRID_PROMPT_STRATEGIES = (
    "minimal",
    "basic",
    "detailed_rules",
    "v1_advanced",
    "v2_advanced",
    "few_shot_1",
    "few_shot_2",
    "few_shot_3",
)


def default_workspace() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return PROJECT_ROOT / "workspace" / timestamp


def read_optional(path: Path | None, fallback: str) -> str:
    return path.read_text(encoding="utf-8") if path else fallback


def initial_template_for(strategy: str) -> str:
    if strategy == "retrieved_few_shot_v1":
        return researched_prompts.RETRIEVED_FEW_SHOT_INITIAL_V1
    if strategy in researched_prompts.CONTEXT_AWARE_STRATEGIES:
        return researched_prompts.INITIAL_WITH_CONTEXT_V1
    return "{akka_code}"


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
    parser.add_argument(
        "--max-attempts",
        type=int,
        default=5,
        help=(
            "Maximum compiler-feedback attempts for initial generation and for "
            "each enabled semantic-repair cycle."
        ),
    )
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
    parser.add_argument("--semantic-retry-prompt-file", type=Path)
    parser.add_argument(
        "--max-semantic-repairs",
        type=int,
        default=0,
        help=(
            "Maximum oracle-assisted semantic repairs after a first-pass semantic "
            "failure. Default 0 preserves unbiased baseline runs."
        ),
    )
    parser.add_argument(
        "--retrieval-corpus",
        type=Path,
        help="JSON file or directory of verified, metadata-labelled few-shot examples.",
    )
    parser.add_argument("--retrieval-top-k", type=int, default=3)
    parser.add_argument(
        "--near-duplicate-threshold",
        type=float,
        default=0.9,
        help="Lexical Jaccard threshold used as an additional leakage guard.",
    )
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
    max_semantic_repairs = getattr(args, "max_semantic_repairs", 0)
    retrieval_corpus = getattr(args, "retrieval_corpus", None)
    retrieval_top_k = getattr(args, "retrieval_top_k", 3)
    near_duplicate_threshold = getattr(args, "near_duplicate_threshold", 0.9)
    semantic_retry_prompt_file = getattr(args, "semantic_retry_prompt_file", None)
    if max_semantic_repairs < 0:
        raise ValueError("--max-semantic-repairs cannot be negative")
    if max_semantic_repairs and not args.benchmark:
        raise ValueError("--max-semantic-repairs requires --benchmark")
    if args.prompt_strategy == "retrieved_few_shot_v1" and not retrieval_corpus:
        raise ValueError(
            "retrieved_few_shot_v1 requires --retrieval-corpus with verified examples"
        )
    if not 0.0 <= near_duplicate_threshold <= 1.0:
        raise ValueError("--near-duplicate-threshold must be between 0 and 1")

    system_prompt = read_optional(
        args.system_prompt_file, PROMPT_STRATEGIES[args.prompt_strategy]
    )
    initial_template = read_optional(
        args.initial_prompt_file, initial_template_for(args.prompt_strategy)
    )
    retry_template = read_optional(
        args.retry_prompt_file, researched_prompts.SYNTAX_REPAIR_V1
    )
    semantic_retry_template = read_optional(
        semantic_retry_prompt_file, researched_prompts.SEMANTIC_REPAIR_V1
    )

    example_retriever = None
    if args.prompt_strategy == "retrieved_few_shot_v1":
        example_retriever = VerifiedExampleRetriever.from_path(
            retrieval_corpus,
            top_k=retrieval_top_k,
            extension=args.rmc_extension,
            near_duplicate_threshold=near_duplicate_threshold,
        )

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
            semantic_retry_template=semantic_retry_template,
            strategy=args.prompt_strategy,
            version=researched_prompts.PROMPT_VERSIONS.get(
                args.prompt_strategy, "v1"
            ),
            rmc_extension=args.rmc_extension,
            default_semantic_contract=researched_prompts.DEFAULT_SEMANTIC_CONTRACT,
        ),
        output_cleaner=OutputCleaner(),
        syntax_validator=syntax_validator,
        retry_manager=RetryManager(args.max_attempts),
        example_retriever=example_retriever,
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
        max_semantic_repairs=max_semantic_repairs,
        semantic_validator=semantic,
        report_writer=report_writer,
    )


def run_pipeline(
    args: argparse.Namespace,
    *,
    extra_metadata: dict[str, object] | None = None,
) -> tuple[list, list[dict[str, str]]]:
    pipeline = build_candidate_pipeline(args)
    input_path = args.input.expanduser().resolve()
    retrieval_corpus = getattr(args, "retrieval_corpus", None)
    run_metadata = {
        "model": args.model,
        "prompt_strategy": args.prompt_strategy,
        "prompt_version": researched_prompts.PROMPT_VERSIONS.get(
            args.prompt_strategy, "v1"
        ),
        "retry_prompt": "syntax_repair_v1",
        "semantic_retry_prompt": "semantic_repair_v1",
        "max_semantic_repairs": getattr(args, "max_semantic_repairs", 0),
        "retry_budget": {
            "initial_generation_and_syntax": args.max_attempts,
            "per_semantic_repair_cycle": args.max_attempts,
        },
        "temperature": args.temperature,
        "top_p": args.top_p,
        "frequency_penalty": args.frequency_penalty,
        "presence_penalty": args.presence_penalty,
        "rmc_jar": str(args.rmc_jar.expanduser().resolve()),
        "rmc_extension": args.rmc_extension,
        "retrieval": {
            "enabled": args.prompt_strategy == "retrieved_few_shot_v1",
            "corpus": str(retrieval_corpus.resolve())
            if retrieval_corpus
            else None,
            "top_k": getattr(args, "retrieval_top_k", 3),
            "near_duplicate_threshold": getattr(
                args, "near_duplicate_threshold", 0.9
            ),
        },
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
                "first_pass_semantic_status": result.metadata.get(
                    "semantic_evaluation", {}
                ).get("first_pass_status", "NOT_RUN"),
                "repair_assisted_semantic_pass": result.metadata.get(
                    "semantic_evaluation", {}
                ).get("repair_assisted_semantic_pass", False),
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
                result_summary(results, batch_errors), indent=2, ensure_ascii=False
            )
        )
        return result_exit_code(results, batch_errors)
    except Exception as exc:
        print(f"Pipeline error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
