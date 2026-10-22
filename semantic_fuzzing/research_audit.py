"""Audit every archived research source with the real interface extractor."""

import argparse
import hashlib
from pathlib import Path
import shutil

from .pipeline import FuzzingConfig, read_json, run_stage, sbt_quote, StageError, write_json
from .research_batch import BUNDLE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    config = FuzzingConfig.from_file(args.config)
    config.validate()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=args.resume)
    project = output / "extractor"
    original = config.fuzzing_repo / "akka-interface-extractor"
    if not project.exists():
        shutil.copytree(original, project,
                        ignore=shutil.ignore_patterns("target", ".bloop", ".metals"))
    runner = output / "runner"
    if not runner.exists():
        shutil.copytree(config.fuzzing_repo / "akka-runner", runner,
                        ignore=shutil.ignore_patterns("target", ".bloop", ".metals"))
    logs = output / "logs"
    logs.mkdir(exist_ok=args.resume)
    notes = read_json(BUNDLE / "compatibility_fa.json")
    report = {"method": "REAL_EXTRACTOR_AND_SOURCE_REVIEW", "live_api_executed": False,
              "full_pipeline_executed": False, "cases": []}
    cache = {}
    if args.resume:
        for row in read_json(output / "audit.json")["cases"]:
            cache[row["source_sha256"]] = row["extraction"]
    for manifest in sorted((BUNDLE / "originals/benchmarks").glob("*/case.json")):
        case = read_json(manifest)
        source = manifest.parent / case["bundled_source"]["path"]
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != case["bundled_source"]["sha256"]:
            raise ValueError(f"Source hash mismatch: {source}")
        if digest not in cache:
            interface = output / f"{case['id']}.interface.json"
            command = "runMain fuzzextractor.AkkaInterfaceExtractor --output " + sbt_quote(interface)
            command += " " + sbt_quote(source.resolve())
            try:
                run_stage(case["id"], [config.sbt, command], project, logs,
                          config.stage_timeout_seconds)
                document = read_json(interface)
                cache[digest] = {
                    "extractor_status": "COMPLETED",
                    "actor_types": len(document.get("actor_types", [])),
                    "actor_instances": len(document.get("actor_instances", [])),
                    "warnings": document.get("warnings", []),
                    "interface_file": str(interface),
                }
            except (StageError, OSError, ValueError) as exc:
                cache[digest] = {"extractor_status": "ERROR", "reason": str(exc)}
        evidence = cache[digest]
        if evidence.get("interface_file"):
            document = read_json(Path(evidence["interface_file"]))
            evidence["message_types"] = len(document.get("message_types", {}))
        structural = (evidence.get("actor_types", 0) > 0
                      and evidence.get("actor_instances", 0) > 0)
        if structural and evidence.get("message_types", 0) and "compilation" not in evidence:
            try:
                run_stage(case["id"] + "-compile",
                          [config.sbt, f"-Dfuzz.akka.source.dir={source.parent.resolve()}", "compile"],
                          runner, logs, config.stage_timeout_seconds)
                evidence["compilation"] = "PASSED"
            except (StageError, OSError) as exc:
                evidence["compilation"] = "FAILED"
                evidence["compilation_error"] = str(exc)
        status = "BLOCKED_AT_EXTRACTION"
        if structural:
            status = ("BLOCKED_NO_MESSAGES" if not evidence.get("message_types", 0)
                      else "BLOCKED_AT_COMPILATION" if evidence.get("compilation") == "FAILED"
                      else "NEEDS_SEMANTIC_VALIDATION")
        row = {"id": case["id"], "name": case["name"], "source_sha256": digest,
               "source": str(source.relative_to(BUNDLE)),
               "extraction": evidence,
               "status": status,
               "reason_fa": notes[case["id"]],
               "source_review": case["adaptation_and_risks"]}
        report["cases"].append(row)
        write_json(output / "audit.json", report)
        print(f"{row['id']}: {row['status']}; types={evidence.get('actor_types', 0)}, "
              f"instances={evidence.get('actor_instances', 0)}", flush=True)
    report["unique_sources"] = len(cache)
    write_json(output / "audit.json", report)


if __name__ == "__main__":
    main()
