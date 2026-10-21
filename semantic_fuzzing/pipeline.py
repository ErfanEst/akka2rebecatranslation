"""Prepare raw Akka/Rebeca inputs and delegate semantic checks to the fuzz engine."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


@dataclass
class FuzzingConfig:
    fuzzing_repo: Path
    rmc_jar: Path
    sbt: str = "sbt"
    java: str = "java"
    cxx: str = "g++"
    case_count: int = 3
    message_count: int = 10
    start_seed: int = 1
    trace_bound: int = 40
    run_millis: int = 1000
    model_timeout_seconds: int = 120
    stage_timeout_seconds: int = 600
    campaign_timeout_seconds: int = 3600
    coverage_mode: str = "message"
    value_coverage: str = "boundary"
    bootstrap_sender_policy: str = "abstract-external"
    generation_spec: Path | None = None
    first_case_scenario: Path | None = None
    initial_priority_branches: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: Path) -> FuzzingConfig:
        path = path.resolve()
        raw = read_json(path)
        for key in ("fuzzing_repo", "rmc_jar", "generation_spec", "first_case_scenario"):
            if raw.get(key) is not None:
                raw[key] = (path.parent / raw[key]).resolve()
        for key in ("sbt", "java", "cxx"):
            if key in raw and "/" in raw[key]:
                raw[key] = str((path.parent / raw[key]).resolve())
        return cls(**raw)

    def validate(self) -> None:
        for key in ("case_count", "trace_bound", "model_timeout_seconds",
                    "stage_timeout_seconds", "campaign_timeout_seconds"):
            if getattr(self, key) <= 0:
                raise ValueError(f"{key} must be positive")
        if self.message_count < 0 or self.run_millis < 0:
            raise ValueError("message_count and run_millis must be nonnegative")
        for key, choices in {
            "coverage_mode": {"random", "message", "sender-message"},
            "value_coverage": {"random", "boundary"},
            "bootstrap_sender_policy": {"exact", "abstract-external"},
        }.items():
            if getattr(self, key) not in choices:
                raise ValueError(f"Invalid {key}")
        for path in (self.rmc_jar, self.generation_spec, self.first_case_scenario):
            if path is not None and not Path(path).is_file():
                raise ValueError(f"Missing input: {path}")
        for executable in (self.sbt, self.java, self.cxx):
            if shutil.which(executable) is None:
                raise ValueError(f"Executable not found: {executable}")
        for relative in ("scripts/run_semantic_differential_campaign.py",
                         "akka-interface-extractor/build.sbt", "akka-runner/build.sbt"):
            if not (self.fuzzing_repo / relative).is_file():
                raise ValueError(f"Invalid fuzzing checkout: missing {relative}")


class StageError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage


class SyntaxRejected(StageError):
    pass


def save_report(output: Path, report: dict) -> None:
    write_json(output / "result.json", report)
    lines = ["# Validation Report", "", f"Result: {report['status']}",
             f"Semantic status: {report['semantic_status']}",
             f"Reason: {report.get('reason', '')}", "",
             "## Syntax / Type Checking", ""]
    lines.extend(f"- {name}: {status}" for name, status in report["syntax_checks"].items())
    lines.extend(["", "## Differential Fuzzing", "",
                  f"Requested cases: {report['config']['case_count']}",
                  f"Trace bound: {report['config']['trace_bound']}", ""])
    for case in report.get("campaign", {}).get("cases", []):
        for model in case.get("model_results", []):
            lines.append(f"- Seed {case.get('seed', '?')}, {model.get('name', model.get('kind'))}: "
                         f"{model.get('trace_status', 'NOT_CHECKED')}; "
                         f"events={model.get('observed_event_count', 0)}; "
                         f"mismatch={model.get('mismatch_kind', 'none')}")
    lines.extend(["", "A bounded match is not a proof of semantic equivalence.",
                  "Full configuration, input hashes and evidence: result.json.",
                  "Command lines and diagnostics: logs/.", ""])
    (output / "report.md").write_text("\n".join(lines), encoding="utf-8")


def run_stage(stage: str, command: list[str], cwd: Path, logs: Path,
              timeout: int, allow_failure: bool = False) -> int:
    """A campaign spawns Java/C++ children; terminate its whole group on timeout."""
    write_json(logs / f"{stage}.command.json", {"argv": command, "cwd": str(cwd)})
    with (logs / f"{stage}.stdout.log").open("w") as out, (
        logs / f"{stage}.stderr.log"
    ).open("w") as err:
        process = subprocess.Popen(command, cwd=cwd, stdout=out, stderr=err,
                                   start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise StageError(stage, f"{stage} interrupted or exceeded {timeout}s")
    if code and not allow_failure:
        raise StageError(stage, f"{stage} exited {code}; see {logs / (stage + '.stderr.log')}")
    return code


def campaign_verdict(summary: dict, expected_cases: int) -> tuple[str, str]:
    """Do not equate a completed campaign or zero counterexamples with a pass."""
    cases = summary.get("cases", [])
    candidates = [model for case in cases for model in case.get("model_results", [])
                  if model.get("kind") == "candidate"]
    for model in candidates:
        if model.get("trusted_semantic_result") and (
            model.get("trace_status") == "TRACE_PREFIX_MISMATCH"
            or model.get("rmc_verdict", {}).get("status") == "QUEUE_OVERFLOW"
        ):
            return "MISMATCH", "A trusted candidate counterexample was found."
    if summary.get("campaign_status") in {"IN_PROGRESS", "COMPLETED_WITH_ERRORS"} or any(
        model.get("pipeline_status") == "INFRA_ERROR"
        for case in cases for model in case.get("model_results", [])
    ):
        return "ERROR", "The campaign contains execution errors; inspect its logs."
    if len(cases) != expected_cases or len(candidates) != expected_cases:
        return "INCONCLUSIVE", "Not all requested cases produced a candidate result."
    if summary.get("campaign_status") not in {"COMPLETED", "COMPLETED_WITH_UNMET_EXPECTATIONS"}:
        return "INCONCLUSIVE", "The campaign did not report a recognized completed status."
    if any(sum(model.get("kind") == "candidate" for model in case.get("model_results", [])) != 1
           for case in cases):
        return "INCONCLUSIVE", "Every case must contain exactly one candidate result."
    if any(case.get("status") not in {"COMPLETED", "COMPLETED_WITH_UNMET_EXPECTATIONS"}
           for case in cases):
        return "INCONCLUSIVE", "At least one case did not complete."
    if all(model.get("pipeline_status") == "EXECUTED"
           and model.get("trusted_trace_result") is True
           and model.get("trace_status") == "TRACE_PREFIX_MATCH"
           and model.get("observed_event_count", 0) > 0
           for model in candidates):
        return "BOUNDED_MATCH", "All requested candidate traces matched within the configured bounds."
    return "INCONCLUSIVE", "Untrusted, incomplete, or empty traces cannot establish a bounded match."


def sbt_quote(value: Path) -> str:
    return '"' + str(value).replace('\\', '\\\\').replace('"', '\\"') + '"'


class FuzzingPipeline:
    def __init__(self, config: FuzzingConfig):
        self.config = config

    def check(self, akka_sources: list[Path], candidate: Path, output: Path,
              mutants: list[dict] | None = None) -> dict:
        cfg = self.config
        cfg.validate()
        output = output.resolve()
        sources = [Path(path).resolve() for path in akka_sources]
        models = [{"name": "candidate", "kind": "candidate", "source": candidate}]
        for index, mutant in enumerate(mutants or []):
            models.append({**mutant, "name": f"mutant_{index + 1}", "kind": "mutant"})
        if not sources or any(not path.is_file() for path in sources):
            raise ValueError("At least one existing Akka source is required")
        if len({path.stem for path in sources}) != len(sources):
            raise ValueError("Akka source basenames must be unique")
        if any(not Path(model["source"]).is_file() for model in models):
            raise ValueError("Candidate and mutant sources must exist")
        output.mkdir(parents=True, exist_ok=False)
        logs = output / "logs"
        logs.mkdir()
        report = {"schema_version": 2, "status": "IN_PROGRESS", "success": False,
                  "started_at": datetime.now(timezone.utc).isoformat(),
                  "syntax_checks": {}, "semantic_status": "NOT_RUN",
                  "semantic_equivalence": "NOT_ESTABLISHED", "output_dir": str(output),
                  "config": json.loads(json.dumps(asdict(cfg), default=str)),
                  "inputs": [], "campaign_summary_file": None}
        try:
            for path in sources + [Path(model["source"]).resolve() for model in models]:
                report["inputs"].append({"path": str(path),
                                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            git = subprocess.run(["git", "-C", str(cfg.fuzzing_repo), "rev-parse", "HEAD"],
                                 capture_output=True, text=True)
            report["fuzzing_commit"] = git.stdout.strip() if git.returncode == 0 else None
            source_dir = output / "sources"
            source_dir.mkdir()
            copied = []
            for path in sources:
                target = source_dir / (path.stem + ".scala")
                shutil.copy2(path, target)
                copied.append(target)
            # RMC's frontend is the syntax/type gate, before any semantic work.
            manifest = []
            for model in models:
                name = model["name"]
                source = output / f"{name}.rebeca"
                shutil.copy2(model["source"], source)
                generated = output / "generated" / name
                report["syntax_checks"][name] = "ERROR"
                run_stage(f"rmc_{name}", [cfg.java, "-jar", str(cfg.rmc_jar.resolve()),
                          "-s", str(source), "-o", str(generated), "-e", "CORE_REBECA",
                          "-x", "statespace.xml"], output, logs, cfg.stage_timeout_seconds)
                # A zero exit code alone is not acceptance by this RMC release.
                if not (generated / "CoreRebecaModelChecker.cpp").is_file():
                    diagnostics = "\n".join(
                        (logs / f"rmc_{name}.{stream}.log").read_text(encoding="utf-8")[-4000:]
                        for stream in ("stdout", "stderr")
                    )
                    report["syntax_checks"][name] = "REJECTED"
                    raise SyntaxRejected(f"rmc_{name}", "RMC frontend did not accept the model:\n" + diagnostics)
                report["syntax_checks"][name] = "PASSED"
                manifest.append({"name": name, "kind": model["kind"],
                                 "generated_dir": str(generated), "expected_trace_status": "ANY",
                                 **{key: model[key] for key in ("activation_policy", "activation_targets")
                                    if key in model}})
            write_json(output / "result.json", report)
            report["semantic_status"] = "IN_PROGRESS"
            # Build copies isolate instrumentation and sbt targets from both checkouts.
            for project in ("akka-interface-extractor", "akka-runner"):
                original = cfg.fuzzing_repo / project
                target = output / project
                target.mkdir()
                shutil.copy2(original / "build.sbt", target / "build.sbt")
                shutil.copytree(original / "project", target / "project",
                                ignore=shutil.ignore_patterns("target", ".bloop"))
                shutil.copytree(original / "src", target / "src")
            interface = output / "interface.json"
            instrumented = output / "instrumented"
            extract = "runMain fuzzextractor.AkkaInterfaceExtractor --output " + sbt_quote(interface)
            instrument = "runMain fuzzextractor.AkkaStateInstrumenter --output-dir " + sbt_quote(instrumented)
            arguments = " " + " ".join(sbt_quote(path) for path in copied)
            run_stage("extract_and_instrument", [cfg.sbt, extract + arguments, instrument + arguments],
                      output / "akka-interface-extractor", logs, cfg.stage_timeout_seconds)
            document = read_json(interface)
            if not document.get("actor_instances") or not document.get("actor_types"):
                raise StageError("extract_and_instrument", "No supported static actors were extracted")
            models_file = output / "models.json"
            write_json(models_file, {"models": manifest})
            command = [sys.executable, str(cfg.fuzzing_repo.resolve() / "scripts/run_semantic_differential_campaign.py"),
                       "--interface", str(interface), "--akka-source-dir", str(instrumented),
                       "--akka-runner-dir", str(output / "akka-runner"),
                       "--models-file", str(models_file), "--output-dir", str(output / "campaign")]
            for key in ("case_count", "message_count", "start_seed", "trace_bound", "run_millis",
                        "model_timeout_seconds", "coverage_mode", "value_coverage",
                        "bootstrap_sender_policy", "sbt", "cxx"):
                command.extend(["--" + key.replace("_", "-"), str(getattr(cfg, key))])
            for key in ("generation_spec", "first_case_scenario"):
                if getattr(cfg, key) is not None:
                    target = output / (key + ".json")
                    shutil.copy2(getattr(cfg, key), target)
                    command.extend(["--" + key.replace("_", "-"), str(target)])
            for branch in cfg.initial_priority_branches:
                command.extend(["--initial-priority-branch", json.dumps(branch)])
            code = run_stage("campaign", command, output, logs, cfg.campaign_timeout_seconds,
                             allow_failure=True)
            summary_file = output / "campaign/campaign_summary.json"
            if not summary_file.is_file():
                raise StageError("campaign", f"No campaign summary was produced (exit {code})")
            summary = read_json(summary_file)
            report["campaign_summary_file"] = str(summary_file)
            report["campaign"] = summary
            report["status"], report["reason"] = campaign_verdict(summary, cfg.case_count)
            if code and report["status"] == "BOUNDED_MATCH":
                report.update(status="ERROR", reason=f"Campaign exited {code}")
        except SyntaxRejected as exc:
            report.update(status="SYNTAX_ERROR", reason=str(exc), stage=exc.stage)
        except (StageError, OSError, ValueError, KeyError) as exc:
            report.update(status="ERROR", reason=str(exc), stage=getattr(exc, "stage", "setup"))
        if report["semantic_status"] != "NOT_RUN":
            report["semantic_status"] = report["status"]
        report["success"] = report["status"] == "BOUNDED_MATCH"
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        save_report(output, report)
        return report
