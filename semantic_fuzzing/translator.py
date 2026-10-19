"""An opt-in BaseModelV2 variant whose validation gate is differential fuzzing."""

from pathlib import Path
import tempfile

from experiments.base_model_v2 import BaseModelV2
from .pipeline import FuzzingPipeline


class FuzzingTranslator(BaseModelV2):
    """Reuse existing prompts, LLM calls, retry feedback, and result archives.

    The old compiler validator and benchmark-specific semantic evaluators are
    not used. RMC checks compilation and the full campaign checks semantics.
    """

    def __init__(self, pipeline: FuzzingPipeline, config: dict | None = None):
        config = {"experiment_name": "default", **(config or {})}
        name = Path(str(config["experiment_name"]))
        if name.is_absolute() or ".." in name.parts or str(name) == ".":
            raise ValueError("experiment_name must be a nonempty relative name without '..'")
        if name.parts[0] != "semantic_fuzzing":
            name = Path("semantic_fuzzing") / name
        config["experiment_name"] = name.as_posix()
        pipeline.config.validate()
        super().__init__(config)
        self.pipeline = pipeline
        self.semantic_checks: list[dict] = []
        self.akka_source: Path | None = None

    def translate(self, akka_code: str, file_id: str = "test") -> dict:
        if Path(file_id).name != file_id or file_id in {".", ".."}:
            raise ValueError("file_id must be a basename")
        self.semantic_checks = []
        with tempfile.TemporaryDirectory(prefix="akka-fuzz-input-") as directory:
            self.akka_source = Path(directory) / (file_id + ".scala")
            self.akka_source.write_text(akka_code, encoding="utf-8")
            try:
                result = super().translate(akka_code, file_id)
            finally:
                self.akka_source = None
        result["semantic_backend"] = "semantic-differential-fuzzing"
        result["semantic_equivalence"] = "NOT_ESTABLISHED"
        result["semantic_checks"] = self.semantic_checks
        checks = {check["attempt"]: check for check in self.semantic_checks}
        for attempt in result["attempts"]:
            check = checks.get(f"{file_id}_attempt_{attempt['attempt_number']}")
            attempt["semantic_status"] = check["status"] if check else "NOT_RUN"
        final_status = result["attempts"][-1]["semantic_status"] if result["attempts"] else "NOT_RUN"
        result["semantic_status"] = "ERROR" if final_status == "NOT_RUN" else final_status
        return result

    def validate_code(self, rebeca_code: str, filename: str = "test") -> dict:
        if self.akka_source is None:
            raise RuntimeError("Use translate/run_on_file to supply the original Akka code")
        root = self.output_dir / "semantic_checks"
        root.mkdir(parents=True, exist_ok=True)
        # A fresh run directory prevents old generated files from passing a new attempt.
        run = Path(tempfile.mkdtemp(prefix=f"{filename}-", dir=root))
        candidate = run / "candidate.rebeca"
        candidate.write_text(rebeca_code, encoding="utf-8")
        report = self.pipeline.check([self.akka_source], candidate, run / "fuzzing")
        self.semantic_checks.append({"attempt": filename, "status": report["status"],
                                     "result_file": str((run / "fuzzing/result.json").resolve())})
        error = None
        if not report["success"]:
            evidence = report.get("campaign", {}).get("candidate_counterexamples", [])
            error = f"Semantic fuzzing {report['status']}: {report['reason']}"
            if evidence:
                import json
                error += "\nCounterexample: " + json.dumps(evidence[0])
        return {"success": report["success"], "error": error}
