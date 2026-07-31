"""Collision-free, candidate-scoped artifact workspaces."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class WorkspaceExistsError(FileExistsError):
    """Raised instead of silently overwriting artifacts from an earlier run."""


def safe_identifier(value: str) -> str:
    identifier = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip()).strip("._")
    if not identifier:
        raise ValueError("Candidate ID must contain at least one safe character.")
    return identifier


@dataclass(frozen=True)
class AttemptWorkspace:
    root: Path

    @property
    def candidate_path(self) -> Path:
        return self.root / "candidate.rebeca"

    @property
    def raw_response_path(self) -> Path:
        return self.root / "llm_response.txt"

    @property
    def prompt_path(self) -> Path:
        return self.root / "prompt.json"

    @property
    def result_path(self) -> Path:
        return self.root / "attempt_result.json"


@dataclass(frozen=True)
class CandidateWorkspace:
    root: Path

    def attempt(self, attempt_number: int) -> AttemptWorkspace:
        if attempt_number < 1:
            raise ValueError("Attempt numbers start at 1.")
        root = self.root / f"attempt_{attempt_number}"
        root.mkdir(parents=False, exist_ok=False)
        return AttemptWorkspace(root=root)

    @property
    def result_path(self) -> Path:
        return self.root / "candidate_result.json"

    @property
    def final_candidate_path(self) -> Path:
        return self.root / "final_candidate.rebeca"


class WorkspaceManager:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def create_candidate(self, candidate_id: str) -> CandidateWorkspace:
        candidate_root = self.root / safe_identifier(candidate_id)
        try:
            candidate_root.mkdir(parents=False, exist_ok=False)
        except FileExistsError as exc:
            raise WorkspaceExistsError(
                f"Candidate workspace already exists: {candidate_root}. "
                "Choose a new workspace root; existing artifacts were not overwritten."
            ) from exc
        return CandidateWorkspace(root=candidate_root)

    @staticmethod
    def write_text(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")

    @staticmethod
    def read_text(path: str | Path) -> str:
        return Path(path).read_text(encoding="utf-8")

    @staticmethod
    def write_json(path: Path, payload: dict[str, Any]) -> None:
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary_path.replace(path)
