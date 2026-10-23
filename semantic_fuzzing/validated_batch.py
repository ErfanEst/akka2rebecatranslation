"""Translate and test the documented, independently validated research kernels."""

import argparse
import hashlib
from pathlib import Path
import sys

from .pipeline import FuzzingConfig, read_json, write_json
from .research_batch import ROOT, prepare_config, run_translation, save_summary, summarize_result


DIRECTORY = ROOT / "semantic_fuzzing/benchmarks/validated"


def make_config(base, entry, cases, seed, directory=DIRECTORY):
    config = prepare_config(base, cases, seed, message_count=entry.get("message_count", 4), trace_bound=24)
    config["generation_spec"] = str((directory / entry["generation_spec"]).resolve())
    return config


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "semantic_fuzzing/runtime.json")
    parser.add_argument("--translation-config", type=Path)
    parser.add_argument("--suite", choices=("validated", "stateful"), default="validated")
    parser.add_argument("--cases", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=10000)
    parser.add_argument("--group", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check-fixtures", action="store_true",
                        help="No LLM: test hand-written Rebeca fixtures against real Akka")
    args = parser.parse_args(argv)
    try:
        directory = DIRECTORY if args.suite == "validated" else DIRECTORY.parent / "stateful"
        manifest = read_json(directory / "manifest.json")
        entries = manifest["cases"]
        if args.group < 1 or (args.group - 1) * 5 >= len(entries):
            raise ValueError("Group outside validated manifest")
        if args.cases < 1 or args.start_seed < 0:
            raise ValueError("cases must be positive and seed nonnegative")
        entries = entries[(args.group - 1) * 5:args.group * 5]
        base = FuzzingConfig.from_file(args.config)
        base.validate()
        if args.output.exists():
            raise ValueError("Output exists; use a fresh directory")
        if not args.check_fixtures:
            from .__main__ import prepare_credentials
            prepare_credentials()
            default_translation = ("translation.stateful-medium.json" if args.suite == "stateful"
                                   else "translation.gpt-5.6-sol-medium.json")
            translation = read_json(args.translation_config or ROOT / "semantic_fuzzing" / default_translation)
        output = args.output.resolve()
        output.mkdir(parents=True)
        report = {"case_count": args.cases, "start_seed": args.start_seed,
                  "source_mode": manifest["source_mode"],
                  "validation_mode": "HAND_WRITTEN_FIXTURES" if args.check_fixtures else "LIVE_TRANSLATION",
                  "cases": [{"id": e["id"], "name": e["name"], "status": "PENDING"} for e in entries]}
        save_summary(output, report)
        for entry, row in zip(entries, report["cases"]):
            run = output / entry["id"]
            run.mkdir()
            logs = run / "logs"
            logs.mkdir()
            config = make_config(base, entry, args.cases, args.start_seed, directory)
            write_json(run / "fuzzing.json", config)
            source = directory / entry["source"]
            row["source_sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
            row["spec_sha256"] = hashlib.sha256((directory / entry["generation_spec"]).read_bytes()).hexdigest()
            command = [sys.executable, "-u", "-m", "semantic_fuzzing", "--config", str(run / "fuzzing.json")]
            if args.check_fixtures:
                command += ["check", "--akka-source", str(source), "--candidate",
                            str(directory / entry["fixture"]), "--output", str(run / "validation")]
            else:
                write_json(run / "translation.json", translation)
                command += ["translate", "--akka-source", str(source), "--translation-config",
                            str(run / "translation.json"), "--output", str(run / "translation")]
            print(f"{entry['id']} {entry['name']}: requested cases={args.cases}; logs={logs}", flush=True)
            try:
                code = run_translation(command, logs)
                if args.check_fixtures:
                    path = run / "validation/result.json"
                    evidence = read_json(path)
                    cases = evidence.get("campaign", {}).get("cases", [])
                    row.update(status=evidence["status"], syntax=evidence["syntax_checks"].get("candidate"),
                               semantic=evidence["semantic_status"], attempts=0,
                               completed_cases=len(cases),
                               matched_cases=sum(any(m.get("kind") == "candidate"
                                                     and m.get("trusted_trace_result") is True
                                                     and m.get("trace_status") == "TRACE_PREFIX_MATCH"
                                                     and m.get("observed_event_count", 0) > 0
                                                     for m in case.get("model_results", [])) for case in cases),
                               result_file=str(path), reason=evidence.get("reason"))
                else:
                    row.update(summarize_result(run / "translation" / f"{source.stem}_result.json"))
                if code and row["status"] == "BOUNDED_MATCH":
                    row.update(status="ERROR", reason=f"Process exited {code}")
            except (OSError, ValueError, KeyError) as exc:
                row.update(status="ERROR", reason=str(exc))
            save_summary(output, report)
            print(f"{entry['id']}: {row['status']}", flush=True)
        return 0 if all(r["status"] == "BOUNDED_MATCH" for r in report["cases"]) else 1
    except KeyboardInterrupt:
        print("Interrupted; partial summary is preserved. Use a fresh output directory to rerun.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
