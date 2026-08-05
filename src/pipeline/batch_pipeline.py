"""Batch isolation: one candidate failure never stops the remaining files."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from src.artifacts.result_models import CandidateResult
from src.artifacts.workspace import WorkspaceManager, safe_identifier

from .candidate_pipeline import CandidatePipeline


class BatchPipeline:
    SUPPORTED_SUFFIXES = {".txt", ".scala"}

    def __init__(self, candidate_pipeline: CandidatePipeline) -> None:
        self.candidate_pipeline = candidate_pipeline
        self.errors: list[dict[str, str]] = []

    @classmethod
    def discover(cls, input_dir: str | Path) -> list[Path]:
        root = Path(input_dir).expanduser().resolve()
        if not root.is_dir():
            raise NotADirectoryError(f"Input directory not found: {root}")
        return sorted(
            path
            for path in root.rglob("*")
            if path.is_file() and path.suffix.lower() in cls.SUPPORTED_SUFFIXES
        )

    def run(
        self,
        sources: Iterable[str | Path],
        *,
        benchmark: str | None = None,
        relative_to: str | Path | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> list[CandidateResult]:
        base = Path(relative_to).resolve() if relative_to else None
        results: list[CandidateResult] = []
        self.errors = []
        for raw_source in sources:
            source = Path(raw_source).resolve()
            relative = source.relative_to(base) if base else source.name
            relative_stem = Path(relative).with_suffix("")
            identifier = safe_identifier("__".join(relative_stem.parts))
            try:
                result = self.candidate_pipeline.run(
                    source,
                    candidate_id=identifier,
                    benchmark=benchmark,
                    metadata=metadata,
                )
                results.append(result)
            except Exception as exc:
                self.errors.append(
                    {
                        "candidate_id": identifier,
                        "source": str(source),
                        "error": str(exc),
                    }
                )

        counts = Counter(result.overall_status.value for result in results)
        summary = {
            "total_candidates": len(results),
            "status_counts": dict(sorted(counts.items())),
            "candidates": [
                {
                    "candidate_id": result.candidate_id,
                    "status": result.overall_status.value,
                    "report": str(Path(result.workspace_path) / "candidate_result.json"),
                }
                for result in results
            ],
            "infrastructure_errors": self.errors,
        }
        WorkspaceManager.write_json(
            self.candidate_pipeline.workspace_manager.root / "batch_result.json",
            summary,
        )
        return results
