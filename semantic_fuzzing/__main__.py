"""python -m semantic_fuzzing: check existing translations or translate and check."""

import argparse
from pathlib import Path
import sys

from .pipeline import FuzzingConfig, FuzzingPipeline, read_json, write_json

EXIT_CODES = {"BOUNDED_MATCH": 0, "MISMATCH": 1, "INCONCLUSIVE": 2, "ERROR": 3}


def resolve(base: Path, value: str) -> Path:
    return (base / value).resolve()


def check_job(pipeline: FuzzingPipeline, job: dict, base: Path, output: Path) -> dict:
    sources = [resolve(base, path) for path in job["akka_sources"]]
    if ("candidate" in job) == ("translation_result" in job):
        raise ValueError("Specify exactly one candidate or translation_result per job")
    mutants = [{**item, "source": resolve(base, item["source"])}
               for item in job.get("mutants", [])]
    if "translation_result" in job:
        result = read_json(resolve(base, job["translation_result"]))
        code = result.get("final_code")
        if result.get("success") is not True or not isinstance(code, str) or not code.strip():
            raise ValueError("Translation result must contain success=true and nonempty final_code")
        # Materialize archived code outside the original result/benchmark files.
        output.mkdir(parents=True, exist_ok=False)
        candidate = output / "archived_candidate.rebeca"
        candidate.write_text(code, encoding="utf-8")
        output = output / "fuzzing"
    else:
        candidate = resolve(base, job["candidate"])
    return pipeline.check(sources, candidate, output, mutants)


def main() -> int:
    parser = argparse.ArgumentParser(description="Akka-to-Rebeca semantic fuzzing integration")
    parser.add_argument("--config", required=True, type=Path,
                        help="Fuzzing/toolchain JSON; paths are relative to this file")
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("check", help="Check a candidate against its original Akka source")
    check.add_argument("--akka-source", action="append", required=True)
    candidates = check.add_mutually_exclusive_group(required=True)
    candidates.add_argument("--candidate")
    candidates.add_argument("--translation-result")
    check.add_argument("--mutant", action="append", default=[])
    check.add_argument("--output", required=True, type=Path)
    batch = commands.add_parser("batch", help="Check explicitly paired archived translations")
    batch.add_argument("--manifest", required=True, type=Path)
    batch.add_argument("--output", required=True, type=Path)
    translate = commands.add_parser("translate", help="Translate with existing prompts/retries and fuzz validation")
    translate.add_argument("--akka-source", required=True, type=Path)
    translate.add_argument("--translation-config", required=True, type=Path,
                           help="Existing BaseModelV2 configuration as JSON")
    args = parser.parse_args()
    try:
        pipeline = FuzzingPipeline(FuzzingConfig.from_file(args.config))
        pipeline.config.validate()
        if args.command == "translate":
            from .translator import FuzzingTranslator
            translator = FuzzingTranslator(pipeline, read_json(args.translation_config))
            result = translator.run_on_file(str(args.akka_source))
            print(f"Semantic status: {result['semantic_status']}; results: {translator.output_dir}")
            return EXIT_CODES.get(result["semantic_status"], 3)
        if args.command == "check":
            job = {"akka_sources": args.akka_source,
                   "mutants": [{"source": path} for path in args.mutant]}
            if args.candidate:
                job["candidate"] = args.candidate
            else:
                job["translation_result"] = args.translation_result
            result = check_job(pipeline, job, Path.cwd(), args.output)
            print(f"{result['status']}: {result['reason']}\nResults: {result['output_dir']}")
            return EXIT_CODES[result["status"]]
        jobs = read_json(args.manifest)["jobs"]
        if not isinstance(jobs, list) or not jobs:
            raise ValueError("Manifest jobs must be a nonempty array")
        args.output.mkdir(parents=True, exist_ok=False)
        results = []
        for index, job in enumerate(jobs, 1):
            try:
                result = check_job(pipeline, job, args.manifest.resolve().parent,
                                   args.output / f"job_{index:04d}")
                record = {"job": index, "status": result["status"],
                          "result_file": str(Path(result["output_dir"]) / "result.json")}
            except (OSError, ValueError, KeyError, TypeError) as exc:
                record = {"job": index, "status": "ERROR", "reason": str(exc)}
            results.append(record)
            write_json(args.output / "batch_summary.json", {"results": results})
            print(f"Job {index}: {record['status']}", flush=True)
        return max(EXIT_CODES[result["status"]] for result in results)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
