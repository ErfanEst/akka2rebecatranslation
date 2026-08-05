"""Determine syntax validity from RMC execution and generated C++ artifacts."""

from __future__ import annotations

import re
from pathlib import Path

from src.artifacts.result_models import SyntaxResult
from src.artifacts.workspace import WorkspaceManager

from .rmc_compiler import RmcCompiler


_SLF4J_WARNING_PATTERNS = (
    re.compile(r'^SLF4J: Failed to load class "org\.slf4j\.impl\.StaticLoggerBinder"\.$'),
    re.compile(r"^SLF4J: Defaulting to no-operation \(NOP\) logger implementation$"),
    re.compile(r"^SLF4J: See https?://www\.slf4j\.org/codes\.html#StaticLoggerBinder for further details\.$"),
)
_COMPILER_DIAGNOSTIC_PATTERN = re.compile(
    r"(?im)^(?:Errors:|line:\s*\d+\s*,\s*column:\s*\d+|line\s+\d+(?::|,))"
)
_JAVA_STACK_FRAME_PATTERN = re.compile(r"^\s*at\s+.+$")
_JAVA_CAUSED_BY_PATTERN = re.compile(r"^\s*Caused by:\s+.+$")
_JAVA_COMMON_FRAMES_PATTERN = re.compile(r"^(\s*)\.\.\.\s+(\d+)\s+more\s*$")


def _expand_java_common_frames(output: str) -> str:
    """Expand Java's ``... N more`` stack-trace abbreviation.

    Java omits the final N frames of a caused exception when they are identical
    to the final N frames of its parent.  Keeping those frames explicit makes
    archived compiler logs and retry prompts self-contained.
    """
    expanded_lines: list[str] = []
    current_frames: list[str] = []
    parent_frames: list[str] = []

    for line in output.splitlines():
        if _JAVA_CAUSED_BY_PATTERN.match(line):
            parent_frames = current_frames
            current_frames = []
            expanded_lines.append(line)
            continue

        if _JAVA_STACK_FRAME_PATTERN.match(line):
            current_frames.append(line)
            expanded_lines.append(line)
            continue

        common_frames = _JAVA_COMMON_FRAMES_PATTERN.match(line)
        if common_frames:
            count = int(common_frames.group(2))
            inherited = parent_frames[-count:] if count <= len(parent_frames) else []
            if inherited:
                expanded_lines.extend(inherited)
                current_frames.extend(inherited)
            else:
                # Keep malformed or incomplete traces honest rather than
                # silently deleting information that cannot be reconstructed.
                expanded_lines.append(line)
            continue

        expanded_lines.append(line)

    return "\n".join(expanded_lines)


def _remove_slf4j_warnings(output: str) -> str:
    """Remove the known logging warning without discarding compiler output."""
    useful_lines = []
    for line in output.splitlines():
        if any(pattern.fullmatch(line.strip()) for pattern in _SLF4J_WARNING_PATTERNS):
            continue
        useful_lines.append(line)
    return "\n".join(useful_lines).strip()


def _compiler_feedback(stdout: str, stderr: str) -> str:
    """Build retry feedback from both RMC streams, with stdout first."""
    parts = []
    for output in (stdout, stderr):
        cleaned = _remove_slf4j_warnings(_expand_java_common_frames(output))
        if cleaned and cleaned not in parts:
            parts.append(cleaned)
    return "\n\n".join(parts)


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

        # Store complete traces: Java's ``... N more`` notation is expanded
        # from the shared parent frames before the logs are archived.
        expanded_stdout = _expand_java_common_frames(command_result.stdout)
        expanded_stderr = _expand_java_common_frames(command_result.stderr)
        WorkspaceManager.write_text(stdout_path, expanded_stdout)
        WorkspaceManager.write_text(stderr_path, expanded_stderr)

        generated_cpp = attempt_root / "generated_cpp"
        cpp_files = list(generated_cpp.glob("*.cpp")) if generated_cpp.is_dir() else []
        execution_success = (
            command_result.return_code is not None and not command_result.timed_out
        )
        passed = command_result.return_code == 0 and bool(cpp_files)

        compiler_feedback = _compiler_feedback(
            command_result.stdout, command_result.stderr
        )
        has_compiler_diagnostics = bool(
            _COMPILER_DIAGNOSTIC_PATTERN.search(compiler_feedback)
        )

        error_message = (
            _expand_java_common_frames(command_result.error)
            if command_result.error
            else None
        )
        error_category = None
        if command_result.timed_out:
            error_category = "TIMEOUT"
        elif command_result.return_code is None:
            error_category = "EXECUTION_ERROR"
        elif command_result.return_code != 0:
            error_category = "COMPILER_REJECTED"
        elif not cpp_files:
            # RMC 2.14 may return zero even when its parser reports errors on
            # stdout. Those are syntax failures, not infrastructure failures.
            error_category = (
                "COMPILER_REJECTED"
                if has_compiler_diagnostics
                else "RMC_INTERNAL_ERROR"
            )
        if not passed and not error_message:
            error_message = (
                compiler_feedback
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
