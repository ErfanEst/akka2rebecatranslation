#!/usr/bin/env python3
"""
collect_semantic_candidates.py

Collects translation experiment results and prepares syntactically valid
Rebeca translations as candidates for semantic validation.

For every experiment:
    - Reads the experiment JSON.
    - Identifies the benchmark, prompt strategy, parameter setting, and model.
    - Records syntax success or failure.
    - Extracts final_code only when syntax validation succeeded.
    - Writes each valid Rebeca candidate into a separate directory.
    - Produces JSON, JSONL, CSV, and summary reports.

This script does NOT execute semantic validation.
It only prepares the candidate manifest consumed by the semantic batch runner.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


LOGGER = logging.getLogger("semantic-candidate-collector")

DEFAULT_BENCHMARK = "simpleCounter"
AGGREGATED_FILE_NAME = "aggregated_results.json"


@dataclass
class CandidateRecord:
    candidate_id: str
    phase: str
    benchmark: str
    file_name: str | None

    prompt_strategy: str
    setting: str
    experiment_name: str | None
    model: str | None

    temperature: float | None
    top_p: float | None
    frequency_penalty: float | None
    presence_penalty: float | None
    max_retries: int | None

    syntax_pass: bool
    total_attempts: int
    final_attempt: int | None
    final_code_length: int
    final_code_sha256: str | None

    semantic_candidate: bool
    semantic_status: str
    overall_status: str

    source_result_path: str
    candidate_directory: str | None
    candidate_code_path: str | None
    metadata_path: str | None

    collection_error: str | None


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Collect syntactically valid Rebeca translations and prepare "
            "them for semantic validation."
        )
    )

    parser.add_argument(
        "--results-root",
        type=Path,
        default=Path("experiments/results/phase2_simple"),
        help=(
            "Root directory containing experiment result JSON files. "
            "Default: experiments/results/phase2_simple"
        ),
    )

    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path(
            "semantic_validation/batch_results/"
            "phase2_simple/simple_counter"
        ),
        help=(
            "Directory in which the semantic candidate manifest and "
            "candidate files are written."
        ),
    )

    parser.add_argument(
        "--benchmark",
        default=DEFAULT_BENCHMARK,
        help="Benchmark file_id to collect. Default: simpleCounter",
    )

    parser.add_argument(
        "--phase",
        default="phase2_simple",
        help="Experiment phase stored in generated reports.",
    )

    parser.add_argument(
        "--clean",
        action="store_true",
        help=(
            "Remove the existing output directory before collecting "
            "candidates."
        ),
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable detailed logging.",
    )

    return parser.parse_args()


def configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="[%(levelname)s] %(message)s",
    )


def normalize_identifier(value: str) -> str:
    """
    Convert arbitrary metadata into a filesystem-safe identifier.
    """

    normalized = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    normalized = normalized.strip("._-")

    return normalized or "unknown"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        json.dump(
            value,
            file,
            ensure_ascii=False,
            indent=2,
        )
        file.write("\n")


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def iter_result_json_files(results_root: Path) -> Iterable[Path]:
    """
    Return individual experiment result files.

    aggregated_results.json is deliberately excluded because it represents
    aggregated reporting rather than one translation experiment.
    """

    for path in sorted(results_root.rglob("*.json")):
        if path.name == AGGREGATED_FILE_NAME:
            continue

        if path.is_file():
            yield path


def infer_prompt_and_setting(
    result_path: Path,
    results_root: Path,
) -> tuple[str, str]:
    """
    Expected layout:

        results_root/
            basic/
                temp0_0_topp0_5/
                    simpleCounter.json

    The function also tolerates one extra nesting level.
    """

    try:
        relative_path = result_path.relative_to(results_root)
    except ValueError:
        return "unknown", "unknown"

    parts = relative_path.parts

    prompt_strategy = parts[0] if len(parts) >= 1 else "unknown"
    setting = parts[1] if len(parts) >= 2 else "unknown"

    return prompt_strategy, setting


def extract_final_attempt(
    result: dict[str, Any],
    final_code: str,
) -> int | None:
    """
    Determine which attempt became final_code.

    Priority:
        1. Last successful attempt whose code equals final_code.
        2. Last successful attempt.
        3. total_attempts, if the experiment reports success.
    """

    attempts = result.get("attempts")

    if isinstance(attempts, list):
        matching_attempts: list[int] = []
        successful_attempts: list[int] = []

        for attempt in attempts:
            if not isinstance(attempt, dict):
                continue

            attempt_number = attempt.get("attempt_number")

            if not isinstance(attempt_number, int):
                continue

            if attempt.get("validation_success") is True:
                successful_attempts.append(attempt_number)

                if attempt.get("rebeca_code") == final_code:
                    matching_attempts.append(attempt_number)

        if matching_attempts:
            return max(matching_attempts)

        if successful_attempts:
            return max(successful_attempts)

    total_attempts = result.get("total_attempts")

    if result.get("success") is True and isinstance(total_attempts, int):
        return total_attempts

    return None


def benchmark_matches(
    result: dict[str, Any],
    result_path: Path,
    benchmark: str,
) -> bool:
    """
    Match using file_id first, then file_name and filename as fallbacks.
    """

    expected = benchmark.casefold()

    file_id = str(result.get("file_id") or "").casefold()

    file_name = str(result.get("file_name") or "")
    file_name_stem = Path(file_name).stem.casefold()

    result_stem = result_path.stem.casefold()

    return expected in {
        file_id,
        file_name_stem,
        result_stem,
    }


def make_candidate_id(
    phase: str,
    benchmark: str,
    prompt_strategy: str,
    setting: str,
    model: str | None,
    source_path: Path,
) -> str:
    """
    Human-readable prefix plus a short stable hash.

    The hash prevents collisions when multiple models or result files exist
    under the same prompt/setting combination.
    """

    logical_identity = "|".join(
        [
            phase,
            benchmark,
            prompt_strategy,
            setting,
            model or "unknown-model",
            str(source_path.resolve()),
        ]
    )

    suffix = hashlib.sha256(
        logical_identity.encode("utf-8")
    ).hexdigest()[:12]

    prefix = "__".join(
        [
            normalize_identifier(prompt_strategy),
            normalize_identifier(setting),
            normalize_identifier(model or "unknown_model"),
        ]
    )

    return f"{prefix}__{suffix}"


def prepare_output_directory(
    output_root: Path,
    clean: bool,
) -> None:
    if clean and output_root.exists():
        LOGGER.warning(
            "Removing existing output directory: %s",
            output_root,
        )
        shutil.rmtree(output_root)

    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "candidates").mkdir(parents=True, exist_ok=True)
    (output_root / "reports").mkdir(parents=True, exist_ok=True)


def collect_single_result(
    result_path: Path,
    results_root: Path,
    output_root: Path,
    phase: str,
    benchmark: str,
) -> CandidateRecord | None:
    try:
        raw_result = load_json(result_path)
    except (OSError, json.JSONDecodeError) as error:
        LOGGER.error(
            "Could not read JSON file %s: %s",
            result_path,
            error,
        )
        return None

    if not isinstance(raw_result, dict):
        LOGGER.warning(
            "Skipping non-object JSON result: %s",
            result_path,
        )
        return None

    if not benchmark_matches(raw_result, result_path, benchmark):
        return None

    prompt_strategy, setting = infer_prompt_and_setting(
        result_path=result_path,
        results_root=results_root,
    )

    config = raw_result.get("config")
    if not isinstance(config, dict):
        config = {}

    model = config.get("model")
    model = str(model) if model is not None else None

    candidate_id = make_candidate_id(
        phase=phase,
        benchmark=benchmark,
        prompt_strategy=prompt_strategy,
        setting=setting,
        model=model,
        source_path=result_path,
    )

    success = raw_result.get("success") is True
    final_code_raw = raw_result.get("final_code")
    final_code = final_code_raw if isinstance(final_code_raw, str) else ""

    total_attempts_raw = raw_result.get("total_attempts")
    total_attempts = (
        total_attempts_raw
        if isinstance(total_attempts_raw, int)
        else 0
    )

    final_attempt = (
        extract_final_attempt(raw_result, final_code)
        if success and final_code.strip()
        else None
    )

    candidate_directory: Path | None = None
    candidate_code_path: Path | None = None
    metadata_path: Path | None = None
    collection_error: str | None = None

    semantic_candidate = success and bool(final_code.strip())

    if success and not final_code.strip():
        collection_error = (
            "Experiment reports success=true but final_code is missing "
            "or empty."
        )
        semantic_candidate = False

    if semantic_candidate:
        candidate_directory = (
            output_root
            / "candidates"
            / normalize_identifier(prompt_strategy)
            / normalize_identifier(setting)
            / candidate_id
        )

        candidate_code_path = candidate_directory / "candidate.rebeca"
        metadata_path = candidate_directory / "candidate_metadata.json"

        write_text(candidate_code_path, final_code.rstrip() + "\n")

        candidate_metadata = {
            "candidate_id": candidate_id,
            "phase": phase,
            "benchmark": benchmark,
            "prompt_strategy": prompt_strategy,
            "setting": setting,
            "model": model,
            "config": config,
            "syntax": {
                "passed": True,
                "total_attempts": total_attempts,
                "final_attempt": final_attempt,
            },
            "source": {
                "result_path": str(result_path.resolve()),
                "file_name": raw_result.get("file_name"),
                "file_id": raw_result.get("file_id"),
                "experiment_timestamp": raw_result.get("timestamp"),
                "elapsed_time": raw_result.get("elapsed_time"),
            },
            "candidate": {
                "code_path": str(candidate_code_path.resolve()),
                "code_length": len(final_code),
                "sha256": sha256_text(final_code),
            },
            "semantic": {
                "status": "PENDING",
                "executed": False,
            },
        }

        write_json(metadata_path, candidate_metadata)

    if not success:
        overall_status = "SYNTAX_FAIL"
        semantic_status = "NOT_RUN"
    elif semantic_candidate:
        overall_status = "SEMANTIC_PENDING"
        semantic_status = "PENDING"
    else:
        overall_status = "COLLECTION_ERROR"
        semantic_status = "NOT_RUN"

    return CandidateRecord(
        candidate_id=candidate_id,
        phase=phase,
        benchmark=benchmark,
        file_name=raw_result.get("file_name"),
        prompt_strategy=prompt_strategy,
        setting=setting,
        experiment_name=config.get("experiment_name"),
        model=model,
        temperature=config.get("temperature"),
        top_p=config.get("top_p"),
        frequency_penalty=config.get("frequency_penalty"),
        presence_penalty=config.get("presence_penalty"),
        max_retries=config.get("max_retries"),
        syntax_pass=success,
        total_attempts=total_attempts,
        final_attempt=final_attempt,
        final_code_length=len(final_code),
        final_code_sha256=(
            sha256_text(final_code)
            if final_code
            else None
        ),
        semantic_candidate=semantic_candidate,
        semantic_status=semantic_status,
        overall_status=overall_status,
        source_result_path=str(result_path.resolve()),
        candidate_directory=(
            str(candidate_directory.resolve())
            if candidate_directory
            else None
        ),
        candidate_code_path=(
            str(candidate_code_path.resolve())
            if candidate_code_path
            else None
        ),
        metadata_path=(
            str(metadata_path.resolve())
            if metadata_path
            else None
        ),
        collection_error=collection_error,
    )


def write_jsonl(
    path: Path,
    records: list[dict[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(
                json.dumps(
                    record,
                    ensure_ascii=False,
                    sort_keys=False,
                )
            )
            file.write("\n")


def write_csv_report(
    path: Path,
    records: list[CandidateRecord],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    field_names = list(CandidateRecord.__dataclass_fields__.keys())

    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=field_names,
        )

        writer.writeheader()

        for record in records:
            writer.writerow(asdict(record))


def build_prompt_summary(
    records: list[CandidateRecord],
) -> list[dict[str, Any]]:
    prompt_names = sorted(
        {record.prompt_strategy for record in records}
    )

    summary: list[dict[str, Any]] = []

    for prompt_name in prompt_names:
        prompt_records = [
            record
            for record in records
            if record.prompt_strategy == prompt_name
        ]

        total = len(prompt_records)
        syntax_passed = sum(
            record.syntax_pass for record in prompt_records
        )
        syntax_failed = total - syntax_passed

        candidate_count = sum(
            record.semantic_candidate
            for record in prompt_records
        )

        syntax_pass_rate = (
            round(syntax_passed / total, 6)
            if total
            else 0.0
        )

        summary.append(
            {
                "prompt_strategy": prompt_name,
                "total_experiments": total,
                "syntax_passed": syntax_passed,
                "syntax_failed": syntax_failed,
                "syntax_pass_rate": syntax_pass_rate,
                "semantic_candidates": candidate_count,
            }
        )

    return summary


def build_summary(
    records: list[CandidateRecord],
    scanned_json_files: int,
    results_root: Path,
    output_root: Path,
    phase: str,
    benchmark: str,
) -> dict[str, Any]:
    total = len(records)

    syntax_passed = sum(
        record.syntax_pass for record in records
    )

    syntax_failed = sum(
        not record.syntax_pass for record in records
    )

    semantic_candidates = sum(
        record.semantic_candidate for record in records
    )

    collection_errors = sum(
        record.collection_error is not None
        for record in records
    )

    return {
        "phase": phase,
        "benchmark": benchmark,
        "results_root": str(results_root.resolve()),
        "output_root": str(output_root.resolve()),
        "scanned_json_files": scanned_json_files,
        "matched_experiments": total,
        "syntax_passed": syntax_passed,
        "syntax_failed": syntax_failed,
        "semantic_candidates": semantic_candidates,
        "collection_errors": collection_errors,
        "syntax_pass_rate": (
            round(syntax_passed / total, 6)
            if total
            else 0.0
        ),
        "semantic_execution": {
            "executed": 0,
            "passed": 0,
            "failed": 0,
            "pending": semantic_candidates,
        },
        "by_prompt_strategy": build_prompt_summary(records),
    }


def main() -> int:
    args = parse_arguments()
    configure_logging(args.verbose)

    results_root = args.results_root.expanduser().resolve()
    output_root = args.output_root.expanduser().resolve()

    if not results_root.exists():
        LOGGER.error(
            "Experiment results directory does not exist: %s",
            results_root,
        )
        return 1

    if not results_root.is_dir():
        LOGGER.error(
            "Experiment results path is not a directory: %s",
            results_root,
        )
        return 1

    prepare_output_directory(
        output_root=output_root,
        clean=args.clean,
    )

    result_files = list(iter_result_json_files(results_root))

    LOGGER.info(
        "Scanning %d individual JSON result file(s).",
        len(result_files),
    )

    records: list[CandidateRecord] = []

    for result_path in result_files:
        record = collect_single_result(
            result_path=result_path,
            results_root=results_root,
            output_root=output_root,
            phase=args.phase,
            benchmark=args.benchmark,
        )

        if record is not None:
            records.append(record)

            status_marker = (
                "CANDIDATE"
                if record.semantic_candidate
                else record.overall_status
            )

            LOGGER.info(
                "%-16s | %-14s | %-22s | %s",
                status_marker,
                record.prompt_strategy,
                record.setting,
                result_path.name,
            )

    records.sort(
        key=lambda item: (
            item.prompt_strategy,
            item.setting,
            item.model or "",
            item.source_result_path,
        )
    )

    record_dicts = [asdict(record) for record in records]

    reports_directory = output_root / "reports"

    manifest_json_path = reports_directory / "candidate_manifest.json"
    manifest_jsonl_path = reports_directory / "candidate_manifest.jsonl"
    manifest_csv_path = reports_directory / "candidate_manifest.csv"
    summary_path = reports_directory / "collection_summary.json"

    write_json(manifest_json_path, record_dicts)
    write_jsonl(manifest_jsonl_path, record_dicts)
    write_csv_report(manifest_csv_path, records)

    summary = build_summary(
        records=records,
        scanned_json_files=len(result_files),
        results_root=results_root,
        output_root=output_root,
        phase=args.phase,
        benchmark=args.benchmark,
    )

    write_json(summary_path, summary)

    print()
    print("=" * 80)
    print("SEMANTIC CANDIDATE COLLECTION COMPLETED")
    print("=" * 80)
    print(f"Benchmark             : {args.benchmark}")
    print(f"JSON files scanned    : {len(result_files)}")
    print(f"Experiments matched   : {summary['matched_experiments']}")
    print(f"Syntax passed         : {summary['syntax_passed']}")
    print(f"Syntax failed         : {summary['syntax_failed']}")
    print(f"Semantic candidates   : {summary['semantic_candidates']}")
    print(f"Collection errors     : {summary['collection_errors']}")
    print("-" * 80)
    print(f"Manifest JSON         : {manifest_json_path}")
    print(f"Manifest JSONL        : {manifest_jsonl_path}")
    print(f"Manifest CSV          : {manifest_csv_path}")
    print(f"Summary               : {summary_path}")
    print("=" * 80)

    if not records:
        LOGGER.warning(
            "No experiment result matched benchmark '%s'.",
            args.benchmark,
        )
        return 2

    if summary["semantic_candidates"] == 0:
        LOGGER.warning(
            "No syntactically valid semantic candidate was found."
        )
        return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
