"""Run numbered research benchmarks in reproducible, sequential groups."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import signal
import subprocess
import sys

from .pipeline import FuzzingConfig, read_json, write_json


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "semantic_fuzzing/benchmarks/research50"


def run_translation(command, logs):
    write_json(logs / "translate.command.json", {"argv": command, "cwd": str(ROOT)})
    with (logs / "translate.stdout.log").open("w") as out, (
        logs / "translate.stderr.log"
    ).open("w") as err:
        process = subprocess.Popen(command, cwd=ROOT, stdout=out, stderr=err)
        try:
            return process.wait()
        except KeyboardInterrupt:
            # Let the CLI's stage runner clean up its Java/C++ process groups.
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise


def select_cases(group, size, bundle=BUNDLE):
    cases = sorted((bundle / "originals/benchmarks").glob("*/case.json"))
    if group < 1 or size < 1 or (group - 1) * size >= len(cases):
        raise ValueError("Group is outside the benchmark list")
    return cases[(group - 1) * size:group * size]


def prepare_config(base, case_count, seed, message_count=6, trace_bound=40):
    config = asdict(base)
    # Session-specific constraints from the runtime example must not leak into
    # unrelated research benchmarks.
    config.update(case_count=case_count, start_seed=seed, coverage_mode="random",
                  value_coverage="random", generation_spec=None,
                  first_case_scenario=None, initial_priority_branches=[],
                  message_count=message_count, trace_bound=trace_bound)
    return json.loads(json.dumps(config, default=str))


def summarize_result(path):
    result = read_json(path)
    completed = matched = 0
    checks = result.get("semantic_checks", [])
    if checks:
        evidence = read_json(Path(checks[-1]["result_file"]))
        cases = evidence.get("campaign", {}).get("cases", [])
        completed = len(cases)
        matched = sum(any(m.get("kind") == "candidate"
                          and m.get("trusted_trace_result") is True
                          and m.get("trace_status") == "TRACE_PREFIX_MATCH"
                          and m.get("observed_event_count", 0) > 0
                          for m in case.get("model_results", [])) for case in cases)
    return {"status": result.get("pipeline_status", "ERROR"),
            "syntax": result.get("syntax_status", "NOT_RUN"),
            "semantic": result.get("semantic_status", "NOT_RUN"),
            "attempts": result.get("total_attempts", 0),
            "completed_cases": completed, "matched_cases": matched,
            "result_file": str(path)}


def save_summary(output, report):
    temporary = output / "summary.json.tmp"
    write_json(temporary, report)
    temporary.replace(output / "summary.json")
    lines = ["# Research Benchmark Batch", "",
             "Counts describe the final translation attempt, not all retries.", "",
             "| ID | Status | Syntax | Matched / requested | Attempts |",
             "|---|---|---|---|---|"]
    for row in report["cases"]:
        lines.append(f"| {row['id']} | {row['status']} | {row.get('syntax', 'NOT_RUN')} | "
                     f"{row.get('matched_cases', 0)} / {report['case_count']} | "
                     f"{row.get('attempts', 0)} |")
    lines += ["", "## Details", ""]
    for row in report["cases"]:
        lines.append(f"- {row['id']}: {row.get('reason', row.get('result_file', ''))}")
        if row.get("result_file"):
            lines.append(f"  Result: {row['result_file']}")
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", type=int, required=True, help="1-10 with default group size")
    parser.add_argument("--group-size", type=int, default=5)
    parser.add_argument("--cases", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=10000)
    parser.add_argument("--message-count", type=int, default=6)
    parser.add_argument("--trace-bound", type=int, default=40)
    parser.add_argument("--config", type=Path, default=ROOT / "semantic_fuzzing/runtime.json")
    parser.add_argument("--translation-config", type=Path,
                        default=ROOT / "semantic_fuzzing/translation.gpt-5.6-sol-medium.json")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dry-run", action="store_true", help="Show readiness; no API or tool execution")
    parser.add_argument("--resume", action="store_true", help="Continue pending cases with identical settings")
    args = parser.parse_args(argv)
    try:
        if args.cases < 1 or args.start_seed < 0 or args.message_count < 1 or args.trace_bound < 1:
            raise ValueError("cases, message-count and trace-bound must be positive; start-seed nonnegative")
        selected = select_cases(args.group, args.group_size)
        compatibility_fa = read_json(BUNDLE / "compatibility_fa.json")
        rows = []
        for path in selected:
            case = read_json(path)
            original = path.parent / case["bundled_source"]["path"]
            if hashlib.sha256(original.read_bytes()).hexdigest() != case["bundled_source"]["sha256"]:
                raise ValueError(f"Original source hash mismatch: {case['id']}")
            rows.append({"id": case["id"], "name": case["name"],
                         "status": "PENDING", "compatibility": "REVIEW_REQUIRED",
                         "compatibility_reason": case["adaptation_and_risks"],
                         "compatibility_reason_fa": compatibility_fa[case["id"]],
                         "source": str(original.resolve()),
                         "provenance": case["provenance"]})
        for row in rows:
            print(f"{row['id']} | {row['name']} | {row['compatibility']}\n"
                  f"  Selected symbols in research: {row['provenance']['selected_symbols']}\n"
                  f"  {row['compatibility_reason_fa']}\n"
                  f"  Review before execution: {row['compatibility_reason']}", flush=True)
        print("Input is the COMPLETE original source file. Research selections are not extracted.\n"
              "Extra test-suite code, missing dependencies, unsupported data or actor topology may fail.\n"
              "Warnings do not skip translation. Semantic fuzzing runs only after syntax acceptance.", flush=True)
        if args.dry_run:
            print(f"Requested scenarios per runnable example: {args.cases}; seeds start at {args.start_seed}")
            return 0
        if args.output is None:
            raise ValueError("--output is required (use a fresh directory for each experiment)")
        base = FuzzingConfig.from_file(args.config)
        translation = read_json(args.translation_config)
        identity = {"group": args.group, "group_size": args.group_size,
                    "case_count": args.cases, "start_seed": args.start_seed,
                    "message_count": args.message_count, "trace_bound": args.trace_bound,
                    "base_config": json.loads(json.dumps(asdict(base), default=str)),
                    "translation_config": translation, "inputs": json.loads(json.dumps(rows)),
                    "source_hashes": {r["id"]: hashlib.sha256(Path(r["source"]).read_bytes()).hexdigest()
                                      for r in rows}}
        output = args.output.resolve()
        if args.resume:
            report = read_json(output / "summary.json")
            if report["identity"] != identity:
                raise ValueError("Resume settings or source content differ; use a new output directory")
        else:
            if output.exists():
                raise ValueError("Output exists; use --resume or a new directory")
            if any(row["status"] == "PENDING" for row in rows):
                base.validate()
                from .__main__ import prepare_credentials
                prepare_credentials()
            output.mkdir(parents=True)
            report = {"identity": identity, "case_count": args.cases, "cases": rows}
            save_summary(output, report)
            write_json(output / "compatibility.json", rows)
            (output / "compatibility.md").write_text(
                "# Compatibility Review\n\n"
                "Advisory source triage, not a compatibility certification. All selected cases are attempted.\n"
                "Complete source files are sent, including surrounding code. No adaptations are applied.\n\n"
                + "\n\n".join(f"## {r['id']} - {r['name']}\n\n"
                                 f"Selected symbols: {r['provenance']['selected_symbols']}\n\n"
                                 f"{r['compatibility_reason_fa']}\n\n"
                                 f"{r['compatibility_reason']}\n\nSource: {r['source']}" for r in rows)
                + "\n", encoding="utf-8")
        for row in report["cases"]:
            if row["status"] != "PENDING":
                print(f"{row['id']}: {row['status']}", flush=True)
                continue
            source = Path(row["source"])
            case_dir = output / row["id"]
            # Never overwrite evidence from an interrupted request. A rerun gets
            # a new attempt directory, and may incur another API charge.
            case_dir.mkdir(exist_ok=True)
            import tempfile
            run = Path(tempfile.mkdtemp(prefix="run-", dir=case_dir))
            logs = run / "logs"
            logs.mkdir()
            config_path = run / "fuzzing.json"
            write_json(config_path, prepare_config(base, args.cases, args.start_seed,
                                                  args.message_count, args.trace_bound))
            translation_path = run / "translation.json"
            write_json(translation_path, translation)
            command = [sys.executable, "-u", "-m", "semantic_fuzzing", "--config", str(config_path),
                       "translate", "--akka-source", str(source),
                       "--translation-config", str(translation_path), "--output", str(run / "translation")]
            print(f"{row['id']}: running {args.cases} scenarios; logs: {logs}", flush=True)
            try:
                code = run_translation(command, logs)
                result_path = run / "translation" / f"{source.stem}_result.json"
                row.update(summarize_result(result_path))
                if code != 0 and row["status"] == "BOUNDED_MATCH":
                    row.update(status="ERROR", reason=f"Translation process exited {code}")
            except (OSError, ValueError, KeyError) as exc:
                row.update(status="ERROR", reason=str(exc), logs=str(logs))
            save_summary(output, report)
            print(f"{row['id']}: {row['status']}", flush=True)
        print(f"Summary: {output / 'summary.md'}")
        return 0 if all(row["status"] == "BOUNDED_MATCH" for row in report["cases"]) else 1
    except KeyboardInterrupt:
        print("Interrupted. Use --resume with identical settings to continue pending cases.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
