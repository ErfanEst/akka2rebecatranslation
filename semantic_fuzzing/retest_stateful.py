"""Retest frozen successful translations with seeded protocol inputs; never calls an LLM."""

import argparse
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import sys

from .pipeline import FuzzingConfig, FuzzingPipeline, read_json, write_json

ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "semantic_fuzzing/benchmarks/stateful"
VERSION = "stateful-random-v1"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def freeze_translation(entry, translations_root):
    source = SUITE / entry["source"]
    archive = translations_root / entry["id"] / "translation" / f"{source.stem}_result.json"
    result = read_json(archive)
    code = result.get("final_code")
    if result.get("success") is not True or not isinstance(code, str) or not code.strip():
        raise ValueError(f"{archive}: successful final_code is required")
    source_hash, candidate_hash = digest(source.read_bytes()), digest(code.encode("utf-8"))
    # Resolve relative to the archive, so copying the run directory is supported.
    evidence = []
    for path in sorted((archive.parent / "semantic_checks").glob("*/fuzzing/result.json")):
        document = read_json(path)
        inputs = document.get("inputs", [])
        if (any(Path(i["path"]).suffix == ".scala" and i["sha256"] == source_hash for i in inputs)
                and any(Path(i["path"]).suffix == ".rebeca" and i["sha256"] == candidate_hash for i in inputs)
                and document.get("status") == "BOUNDED_MATCH"):
            evidence.append(str(path))
    if not evidence:
        raise ValueError(f"{entry['id']}: no matching source/candidate hashes in archived validation. "
                         "Use the original complete translation run and unchanged Scala source.")
    return code, {"archive": str(archive), "archive_sha256": digest(archive.read_bytes()),
                  "source_sha256": source_hash, "candidate_sha256": candidate_hash,
                  "baseline_status": result.get("semantic_status"), "baseline_evidence": evidence}


def scenario_steps(case_id, seed, count):
    if count < 8:
        raise ValueError("messages must be at least 8")
    rng = random.Random(f"{VERSION}:{case_id}:{seed}")
    if case_id == "ACSU-09":
        prefix, choices = ["Swap", "Swap"], ["Swap", "Noop"]
    elif case_id == "ACSU-10":
        prefix, choices = ["Foo", "Foo", "Bar", "Bar"], ["Foo", "Bar"]
    elif case_id == "ACSU-25":
        prefix, choices = ["Data", "RouteStateOn", "Data", "RouteStateOff", "Data"], ["Data", "RouteStateOn", "RouteStateOff"]
    elif case_id == "FSM-01":
        prefix, choices = ["Open", "Add", "Open", "Reset", "Close", "Close", "Add"], ["Open", "Add", "Close", "Reset"]
    else:
        raise ValueError(f"Unknown stateful case: {case_id}")
    messages = prefix + [rng.choice(choices) for _ in range(count - len(prefix))]
    return [{"receiver": "client" if message == "Noop" else "worker",
             "sender": "client", "message": message,
             "arguments": [{"literal": rng.randint(-7, 7)}] if message in {"Data", "Open", "Add"} else []}
            for message in messages]


def make_spec(case_id, seeds, messages):
    return {"schema_version": "1.0", "planner": VERSION,
            "seeded_sequence_templates": {
                str(seed): [{"name": f"{case_id}_seed_{seed}",
                             "steps": scenario_steps(case_id, seed, messages)}] for seed in seeds}}


def save_summary(output, report):
    write_json(output / "summary.json", report)
    lines = ["# Frozen Translation Retest", "", "No LLM calls. Bounded testing is not an equivalence proof.", "",
             "| ID | Status | Completed / requested | Unique planned / generated inputs |",
             "|---|---|---|---|"]
    for row in report["cases"]:
        lines.append(f"| {row['id']} | {row['status']} | {row.get('completed_cases', 0)} / {report['case_count']} | {row['unique_planned_inputs']} / {row.get('unique_generated_inputs', '-')} |")
    lines += ["", "## Details", ""]
    lines += [f"- {r['id']}: {r.get('reason', '')}; {r.get('result_file', '')}" for r in report["cases"]]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def verify_generated_inputs(result, spec):
    hashes = {}
    for case in result.get("campaign", {}).get("cases", []):
        path = Path(case["case_directory"]) / "scenario.json"
        if not path.is_file() and result["status"] != "BOUNDED_MATCH":
            continue
        actual = read_json(path)["messages"]
        expected = spec["seeded_sequence_templates"][str(case["seed"])][0]["steps"]
        expected = [{"sender": s["sender"], "receiver": s["receiver"], "message": s["message"],
                     "args": [a["literal"] for a in s["arguments"]]} for s in expected]
        if actual != expected:
            raise ValueError(f"Generated scenario differs from frozen plan: {path}")
        hashes[str(case["seed"])] = digest(json.dumps(actual, sort_keys=True).encode())
    if result["status"] == "BOUNDED_MATCH" and len(hashes) != len(spec["seeded_sequence_templates"]):
        raise ValueError("Successful result did not execute every planned seed")
    return hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--translations-root", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=ROOT / "semantic_fuzzing/runtime.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cases", type=int, default=50)
    parser.add_argument("--start-seed", type=int, default=20000)
    parser.add_argument("--messages", type=int, default=16)
    parser.add_argument("--case", action="append", choices=("ACSU-09", "ACSU-10", "ACSU-25", "FSM-01"))
    parser.add_argument("--plan-only", action="store_true", help="Verify archives and write scenarios without running tools")
    args = parser.parse_args(argv)
    try:
        if args.cases < 1 or args.start_seed < 0 or args.messages < 8:
            raise ValueError("cases >= 1, start-seed >= 0 and messages >= 8 are required")
        if args.output.exists():
            raise ValueError("Output exists; choose a fresh directory")
        base = FuzzingConfig.from_file(args.config)
        generator = base.fuzzing_repo / "scripts/generate_random_scenario.py"
        if "seeded_sequence_templates" not in generator.read_text(encoding="utf-8"):
            raise ValueError("Update semantic-differential-fuzzing: seeded sequence support is missing")
        if not args.plan_only:
            base.validate()
        entries = [e for e in read_json(SUITE / "manifest.json")["cases"]
                   if not args.case or e["id"] in args.case]
        # Check every archive before starting potentially expensive execution.
        frozen = [freeze_translation(e, args.translations_root.resolve()) for e in entries]
        output = args.output.resolve()
        output.mkdir(parents=True, exist_ok=False)
        report = {"planner": VERSION, "llm_calls": 0, "case_count": args.cases,
                  "start_seed": args.start_seed, "messages": args.messages,
                  "semantic_equivalence": "NOT_ESTABLISHED", "cases": []}
        seeds = range(args.start_seed, args.start_seed + args.cases)
        for entry, (code, provenance) in zip(entries, frozen):
            run = output / entry["id"]
            run.mkdir()
            spec = make_spec(entry["id"], seeds, args.messages)
            write_json(run / "generation_spec.json", spec)
            (run / "candidate.rebeca").write_text(code, encoding="utf-8")
            plans = spec["seeded_sequence_templates"]
            hashes = {seed: digest(json.dumps(t[0]["steps"], sort_keys=True).encode()) for seed, t in plans.items()}
            row = {"id": entry["id"], "status": "PLANNED", **provenance,
                   "unique_planned_inputs": len(set(hashes.values())), "scenario_sha256_by_seed": hashes}
            report["cases"].append(row)
            save_summary(output, report)
        for entry, row in zip(entries, report["cases"]):
            if args.plan_only:
                continue
            run = output / entry["id"]
            config = replace(base, case_count=args.cases, start_seed=args.start_seed,
                             message_count=args.messages, trace_bound=max(base.trace_bound, args.messages * 2 + 8),
                             generation_spec=run / "generation_spec.json", first_case_scenario=None,
                             coverage_mode="random", value_coverage="random", initial_priority_branches=[])
            row["status"] = "RUNNING"
            save_summary(output, report)
            print(f"{entry['id']}: frozen translation; {row['unique_planned_inputs']} unique planned inputs; no API", flush=True)
            try:
                result = FuzzingPipeline(config).check([SUITE / entry["source"]], run / "candidate.rebeca", run / "validation")
                actual_hashes = verify_generated_inputs(result, read_json(run / "generation_spec.json"))
                row.update(status=result["status"], reason=result.get("reason"),
                           unique_generated_inputs=len(set(actual_hashes.values())),
                           generated_scenario_sha256_by_seed=actual_hashes,
                           completed_cases=result.get("campaign", {}).get("completed_case_count", 0),
                           result_file=str(run / "validation/result.json"))
            except (OSError, ValueError) as exc:
                row.update(status="ERROR", reason=str(exc))
            save_summary(output, report)
            print(f"{entry['id']}: {row['status']}", flush=True)
        print(f"Summary: {output / 'summary.md'}")
        return 0 if args.plan_only or all(r["status"] == "BOUNDED_MATCH" for r in report["cases"]) else 1
    except KeyboardInterrupt:
        print("Interrupted. Partial results are retained; use a fresh output for another run.", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
