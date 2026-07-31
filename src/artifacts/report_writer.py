"""Structured JSON report persistence."""

from __future__ import annotations

from pathlib import Path

from .result_models import AttemptResult, CandidateResult
from .workspace import WorkspaceManager


class ReportWriter:
    def write_attempt(self, result: AttemptResult, path: Path) -> Path:
        WorkspaceManager.write_json(path, result.to_dict())
        return path

    def write_candidate(self, result: CandidateResult, path: Path) -> Path:
        WorkspaceManager.write_json(path, result.to_dict())
        return path
