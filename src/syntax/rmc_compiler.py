"""Execute RMC 2.14 and retain every compiler artifact in the attempt workspace."""

from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    return_code: int | None
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "command": self.command,
            "return_code": self.return_code,
            "duration_seconds": self.duration_seconds,
            "timed_out": self.timed_out,
            "error": self.error,
        }


class CommandRunner:
    def run(
        self, command: list[str], *, cwd: Path, timeout_seconds: int
    ) -> CommandResult:
        started = time.monotonic()
        try:
            process = subprocess.run(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
            return CommandResult(
                command=command,
                return_code=process.returncode,
                stdout=process.stdout,
                stderr=process.stderr,
                duration_seconds=time.monotonic() - started,
            )
        except subprocess.TimeoutExpired as exc:
            return CommandResult(
                command=command,
                return_code=None,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
                duration_seconds=time.monotonic() - started,
                timed_out=True,
                error=f"Command timed out after {timeout_seconds} seconds",
            )
        except OSError as exc:
            return CommandResult(
                command=command,
                return_code=None,
                stdout="",
                stderr="",
                duration_seconds=time.monotonic() - started,
                error=str(exc),
            )


class RmcCompiler:
    DEFAULT_JAR = Path("/home/erfan/Thesis/tools/rmc-2.14.jar")
    DEFAULT_JAVA = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin/java")

    def __init__(
        self,
        *,
        jar_path: str | Path = DEFAULT_JAR,
        java_bin: str | Path = DEFAULT_JAVA,
        extension: str = "CORE_REBECA",
        timeout_seconds: int = 120,
        runner: CommandRunner | None = None,
    ) -> None:
        self.jar_path = Path(jar_path).expanduser().resolve()
        self.java_bin = Path(java_bin).expanduser()
        self.extension = extension
        self.timeout_seconds = timeout_seconds
        self.runner = runner or CommandRunner()

    def preflight(self) -> None:
        if not self.jar_path.is_file():
            raise FileNotFoundError(f"RMC JAR not found: {self.jar_path}")
        if not self.java_bin.is_file():
            raise FileNotFoundError(f"Java executable not found: {self.java_bin}")

    def compile(self, candidate_path: Path, attempt_root: Path) -> CommandResult:
        if not candidate_path.is_file():
            raise FileNotFoundError(f"Rebeca candidate not found: {candidate_path}")
        self.preflight()

        command = [
            str(self.java_bin),
            "-jar",
            str(self.jar_path),
            "-s",
            candidate_path.name,
            "-e",
            self.extension,
            "--tracegenerator",
        ]
        result = self.runner.run(
            command, cwd=attempt_root, timeout_seconds=self.timeout_seconds
        )

        generated_by_rmc = attempt_root / "rmc-output"
        generated_cpp = attempt_root / "generated_cpp"
        if generated_by_rmc.exists() and not generated_cpp.exists():
            shutil.move(str(generated_by_rmc), str(generated_cpp))
        return result
