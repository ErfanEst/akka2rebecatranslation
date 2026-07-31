"""Determine syntax validity from RMC execution and generated C++ artifacts."""

from __future__ import annotations

from pathlib import Path

from src.artifacts.result_models import SyntaxResult
from src.artifacts.workspace import WorkspaceManager

from .rmc_compiler import RmcCompiler


class SyntaxValidator:
    def __init__(self, compiler: RmcCompiler) -> None:
        self.compiler = compiler

    def validate(self, candidate_path: Path, attempt_root: Path) -> SyntaxResult:
        stdout_path = attempt_root / "rmc_stdout.log"
        stderr_path = attempt_root / "rmc_stderr.log"

        try:
            command_result = self.compiler.compile(candidate_path, attempt_root)
        except Exception as exc:
            WorkspaceManager.write_text(stdout_path, "")
            WorkspaceManager.write_text(stderr_path, str(exc))
            return SyntaxResult(
                executed=False,
                execution_success=False,
                passed=False,
                error_category="SETUP_ERROR",
                error_message=str(exc),
                stdout_path=str(stdout_path),
                stderr_path=str(stderr_path),
            )

        WorkspaceManager.write_text(stdout_path, command_result.stdout)
        WorkspaceManager.write_text(stderr_path, command_result.stderr)

        generated_cpp = attempt_root / "generated_cpp"
        cpp_files = list(generated_cpp.glob("*.cpp")) if generated_cpp.is_dir() else []
        execution_success = (
            command_result.return_code is not None and not command_result.timed_out
        )
        passed = command_result.return_code == 0 and bool(cpp_files)

        error_message = command_result.error
        error_category = None
        if command_result.timed_out:
            error_category = "TIMEOUT"
        elif command_result.return_code is None:
            error_category = "EXECUTION_ERROR"
        elif command_result.return_code != 0:
            error_category = "COMPILER_REJECTED"
        elif not cpp_files:
            error_category = "NO_GENERATED_CPP"
        if not passed and not error_message:
            error_message = (
                command_result.stderr.strip()
                or command_result.stdout.strip()
                or (
                    "RMC returned success but generated no C++ files."
                    if command_result.return_code == 0
                    else f"RMC exited with code {command_result.return_code}."
                )
            )

        return SyntaxResult(
            executed=True,
            execution_success=execution_success,
            passed=passed,
            duration_seconds=command_result.duration_seconds,
            return_code=command_result.return_code,
            command=command_result.command,
            error_category=error_category,
            error_message=error_message,
            stdout_path=str(stdout_path),
            stderr_path=str(stderr_path),
            generated_cpp_path=str(generated_cpp) if generated_cpp.exists() else None,
        )
