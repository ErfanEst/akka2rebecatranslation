"""Build auditable, oracle-free feedback for generated C++ failures."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_complete(path: object) -> str:
    if not path:
        return ""
    artifact = Path(str(path))
    if not artifact.is_file():
        return ""
    return artifact.read_text(encoding="utf-8", errors="replace")


class CodegenDiagnosticBuilder:
    """Expose backend compiler evidence without exposing semantic-oracle data."""

    def build(self, semantic_result: Any) -> dict[str, Any]:
        commands = list(getattr(semantic_result, "commands", []) or [])
        compile_commands = [
            dict(command)
            for command in commands
            if isinstance(command, dict) and command.get("stage") == "cpp_compile"
        ]
        logs = []
        for command in compile_commands:
            logs.append(
                {
                    "stage": "cpp_compile",
                    "stdout_path": command.get("stdout_path"),
                    "stderr_path": command.get("stderr_path"),
                    "stdout": _read_complete(command.get("stdout_path")),
                    "stderr": _read_complete(command.get("stderr_path")),
                }
            )
        return {
            "schema_version": "codegen_diagnostic_v1",
            "benchmark_oracle_exposed": False,
            "status": getattr(semantic_result, "status", "CODEGEN_FAIL"),
            "error_stage": getattr(semantic_result, "error_stage", None),
            "error_message": getattr(semantic_result, "error_message", None),
            "commands": compile_commands,
            "logs": logs,
        }

    def format(self, semantic_result: Any) -> str:
        return json.dumps(
            self.build(semantic_result), indent=2, ensure_ascii=False
        )
