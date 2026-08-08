"""Run semantic validation using both RMC result and full state-space artifacts."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from semantic_validation.core.evaluator_registry import get_benchmark_config
from src.artifacts.result_models import SemanticResult, SyntaxResult
from src.artifacts.workspace import WorkspaceManager
from src.syntax.rmc_compiler import CommandResult, CommandRunner


class SemanticValidator:
    def __init__(
        self,
        *,
        project_root: str | Path,
        gpp_bin: str = "g++",
        compile_timeout: int = 120,
        model_checker_timeout: int = 300,
        evaluator_timeout: int = 120,
        runner: CommandRunner | None = None,
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.gpp_bin = gpp_bin
        self.compile_timeout = compile_timeout
        self.model_checker_timeout = model_checker_timeout
        self.evaluator_timeout = evaluator_timeout
        self.runner = runner or CommandRunner()

        self.trace_parser_script = (
            self.project_root
            / "semantic_validation"
            / "rebeca"
            / "rmc_result_parser.py"
        )
        self.statespace_parser_script = (
            self.project_root
            / "semantic_validation"
            / "rebeca"
            / "rmc_statespace_parser.py"
        )

    def _run_stage(
        self,
        *,
        stage: str,
        command: list[str],
        cwd: Path,
        timeout: int,
        log_dir: Path,
        command_records: list[dict[str, object]],
    ) -> CommandResult:
        result = self.runner.run(command, cwd=cwd, timeout_seconds=timeout)

        stdout_path = log_dir / f"{stage}_stdout.log"
        stderr_path = log_dir / f"{stage}_stderr.log"

        WorkspaceManager.write_text(stdout_path, result.stdout)
        WorkspaceManager.write_text(stderr_path, result.stderr)

        record = result.to_dict()
        record.update(
            {
                "stage": stage,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        )
        command_records.append(record)
        return result

    @staticmethod
    def _failure(
        *,
        started: float,
        stage: str,
        message: str,
        spec_path: Path,
        commands: list[dict[str, object]],
        trace_xml_path: Path | None = None,
        state_space_xml_path: Path | None = None,
        parsed_trace_path: Path | None = None,
        parsed_state_space_path: Path | None = None,
        semantic_input: str | None = None,
    ) -> SemanticResult:
        return SemanticResult(
            executed=True,
            passed=None,
            status="INFRA_ERROR",
            duration_seconds=time.monotonic() - started,
            error_stage=stage,
            error_message=message,
            spec_path=str(spec_path),
            commands=commands,
            trace_xml_path=(
                str(trace_xml_path)
                if trace_xml_path is not None and trace_xml_path.exists()
                else None
            ),
            state_space_xml_path=(
                str(state_space_xml_path)
                if state_space_xml_path is not None and state_space_xml_path.exists()
                else None
            ),
            parsed_trace_path=(
                str(parsed_trace_path)
                if parsed_trace_path is not None and parsed_trace_path.exists()
                else None
            ),
            parsed_state_space_path=(
                str(parsed_state_space_path)
                if parsed_state_space_path is not None and parsed_state_space_path.exists()
                else None
            ),
            semantic_input=semantic_input,
        )

    @staticmethod
    def _command_error(result: CommandResult) -> str:
        return (
            result.error
            or result.stderr.strip()
            or result.stdout.strip()
            or f"Command exited with code {result.return_code}."
        )

    @staticmethod
    def _extract_summary(payload: dict[str, object]) -> dict[str, object]:
        summary = payload.get("summary")
        return summary if isinstance(summary, dict) else payload

    def validate(
        self,
        *,
        syntax_result: SyntaxResult,
        attempt_root: Path,
        benchmark: str,
    ) -> SemanticResult:
        started = time.monotonic()
        config = get_benchmark_config(benchmark)
        commands: list[dict[str, object]] = []

        # Backward-compatible default: existing benchmarks remain trace-based
        # until explicitly audited and moved to full-state-space evaluation.
        semantic_input = getattr(config, "semantic_input", "trace")
        if semantic_input not in {"trace", "statespace"}:
            return self._failure(
                started=started,
                stage="semantic_config",
                message=(
                    f"Unsupported semantic_input={semantic_input!r} for "
                    f"benchmark {benchmark!r}. Expected 'trace' or 'statespace'."
                ),
                spec_path=config.spec_path,
                commands=commands,
                semantic_input=str(semantic_input),
            )

        if not syntax_result.passed or not syntax_result.generated_cpp_path:
            return SemanticResult(
                executed=False,
                passed=None,
                status="NOT_RUN",
                error_message="Semantic validation requires a syntax-valid RMC candidate.",
                spec_path=str(config.spec_path),
                semantic_input=semantic_input,
            )

        generated_cpp = Path(syntax_result.generated_cpp_path)
        semantic_dir = attempt_root / "semantic"
        semantic_dir.mkdir(parents=False, exist_ok=False)

        cpp_files = sorted(generated_cpp.glob("*.cpp"))
        if not cpp_files:
            return self._failure(
                started=started,
                stage="cpp_discovery",
                message=f"No generated C++ files found in {generated_cpp}",
                spec_path=config.spec_path,
                commands=commands,
                semantic_input=semantic_input,
            )

        # ============================================================
        # Stage 1: Compile generated checker with state-space export
        # ============================================================
        model_checker = generated_cpp / "model_checker"
        compile_result = self._run_stage(
            stage="cpp_compile",
            command=[
                self.gpp_bin,
                "-std=c++11",
                "-DEXPORT_STATE_SPACE",
                *[path.name for path in cpp_files],
                "-o",
                model_checker.name,
            ],
            cwd=generated_cpp,
            timeout=self.compile_timeout,
            log_dir=semantic_dir,
            command_records=commands,
        )
        if compile_result.return_code != 0 or not model_checker.is_file():
            return SemanticResult(
                executed=True,
                passed=False,
                status="CODEGEN_FAIL",
                duration_seconds=time.monotonic() - started,
                error_stage="cpp_compilation",
                error_message=self._command_error(compile_result),
                spec_path=str(config.spec_path),
                commands=commands,
                semantic_input=semantic_input,
            )

        # ============================================================
        # Stage 2: Execute checker and preserve BOTH artifacts
        # ============================================================
        trace_xml = generated_cpp / "result.xml"
        state_space_xml = generated_cpp / "statespace.xml"

        checker_command = [
            str(model_checker),
            "-o",
            trace_xml.name,
        ]

        if semantic_input == "statespace":
            checker_command = [
                str(model_checker),
                "-x",
                state_space_xml.name,
                "-o",
                trace_xml.name,
            ]

        checker_result = self._run_stage(
            stage="model_checker",
            command=checker_command,
            cwd=generated_cpp,
            timeout=self.model_checker_timeout,
            log_dir=semantic_dir,
            command_records=commands,
        )
        if checker_result.return_code != 0:
            return self._failure(
                started=started,
                stage="model_checker",
                message=self._command_error(checker_result),
                spec_path=config.spec_path,
                commands=commands,
                trace_xml_path=trace_xml,
                state_space_xml_path=state_space_xml,
                semantic_input=semantic_input,
            )

        if not trace_xml.is_file():
            return self._failure(
                started=started,
                stage="result_xml_missing",
                message=f"RMC result XML was not generated: {trace_xml}",
                spec_path=config.spec_path,
                commands=commands,
                state_space_xml_path=state_space_xml,
                semantic_input=semantic_input,
            )

        if semantic_input == "statespace" and not state_space_xml.is_file():
            return self._failure(
                started=started,
                stage="statespace_xml_missing",
                message=f"RMC state-space XML was not generated: {state_space_xml}",
                spec_path=config.spec_path,
                commands=commands,
                trace_xml_path=trace_xml,
                semantic_input=semantic_input,
            )

        # ============================================================
        # Stage 3: Parse result.xml (counterexample / RMC result)
        # ============================================================
        parsed_trace_json = semantic_dir / "parsed_result.json"
        trace_parser_result = self._run_stage(
            stage="trace_parser",
            command=[
                sys.executable,
                str(self.trace_parser_script),
                str(trace_xml),
                "-o",
                str(parsed_trace_json),
            ],
            cwd=self.project_root,
            timeout=self.evaluator_timeout,
            log_dir=semantic_dir,
            command_records=commands,
        )
        if (
            trace_parser_result.return_code != 0
            or not parsed_trace_json.is_file()
        ):
            return self._failure(
                started=started,
                stage="trace_parser",
                message=self._command_error(trace_parser_result),
                spec_path=config.spec_path,
                commands=commands,
                trace_xml_path=trace_xml,
                state_space_xml_path=state_space_xml,
                semantic_input=semantic_input,
            )

        # ============================================================
        # Stage 4: Parse full statespace.xml only when required
        # ============================================================
        parsed_state_space_json: Path | None = None

        if semantic_input == "statespace":
            parsed_state_space_json = semantic_dir / "parsed_statespace.json"
            statespace_parser_result = self._run_stage(
                stage="statespace_parser",
                command=[
                    sys.executable,
                    str(self.statespace_parser_script),
                    str(state_space_xml),
                    "-o",
                    str(parsed_state_space_json),
                ],
                cwd=self.project_root,
                timeout=self.evaluator_timeout,
                log_dir=semantic_dir,
                command_records=commands,
            )
            if (
                statespace_parser_result.return_code != 0
                or not parsed_state_space_json.is_file()
            ):
                return self._failure(
                    started=started,
                    stage="statespace_parser",
                    message=self._command_error(statespace_parser_result),
                    spec_path=config.spec_path,
                    commands=commands,
                    trace_xml_path=trace_xml,
                    state_space_xml_path=state_space_xml,
                    parsed_trace_path=parsed_trace_json,
                    semantic_input=semantic_input,
                )

            evaluator_input_json = parsed_state_space_json
        else:
            evaluator_input_json = parsed_trace_json

        # ============================================================
        # Stage 6: Benchmark-specific semantic evaluator
        # ============================================================
        semantic_json = semantic_dir / "semantic_result.json"
        evaluator_result = self._run_stage(
            stage="evaluator",
            command=[
                sys.executable,
                str(config.evaluator_path),
                str(evaluator_input_json),
                "-o",
                str(semantic_json),
            ],
            cwd=self.project_root,
            timeout=self.evaluator_timeout,
            log_dir=semantic_dir,
            command_records=commands,
        )
        if evaluator_result.return_code != 0 or not semantic_json.is_file():
            return self._failure(
                started=started,
                stage="evaluator",
                message=self._command_error(evaluator_result),
                spec_path=config.spec_path,
                commands=commands,
                trace_xml_path=trace_xml,
                state_space_xml_path=state_space_xml,
                parsed_trace_path=parsed_trace_json,
                parsed_state_space_path=parsed_state_space_json,
                semantic_input=semantic_input,
            )

        payload = json.loads(semantic_json.read_text(encoding="utf-8"))
        summary = self._extract_summary(payload)

        semantic_pass = bool(summary.get("semantic_pass", False))
        passed_tests = summary.get("passed_tests", summary.get("passed"))
        failed_tests = summary.get("failed_tests", summary.get("failed"))
        not_observed = summary.get(
            "not_observed_tests",
            summary.get("not_observed", 0),
        )
        total_tests = summary.get("total_tests", summary.get("total"))

        # Preserve complete per-test evaluator output when available.
        # Older evaluators may expose failed/not-observed IDs only through
        # semantic_tests rather than through summary.
        semantic_test_results = payload.get("semantic_tests", [])
        if not isinstance(semantic_test_results, list):
            semantic_test_results = []

        failed_ids = summary.get("failed_test_ids")
        if failed_ids is None:
            failed_ids = [
                test.get("test_id")
                for test in semantic_test_results
                if isinstance(test, dict)
                and test.get("passed") is False
                and test.get("test_id")
            ]

        not_observed_ids = summary.get("not_observed_test_ids")
        if not_observed_ids is None:
            not_observed_ids = [
                test.get("test_id")
                for test in semantic_test_results
                if isinstance(test, dict)
                and str(test.get("status", "")).upper() == "NOT_OBSERVED"
                and test.get("test_id")
            ]

        if semantic_pass:
            status = "SEMANTIC_PASS"
        elif not_observed and not failed_tests:
            status = "SEMANTIC_NOT_OBSERVED"
        else:
            status = "SEMANTIC_FAIL"

        return SemanticResult(
            executed=True,
            passed=semantic_pass,
            status=status,
            duration_seconds=time.monotonic() - started,
            passed_tests=(
                int(passed_tests) if passed_tests is not None else None
            ),
            failed_tests=(
                int(failed_tests) if failed_tests is not None else None
            ),
            not_observed_tests=(
                int(not_observed) if not_observed is not None else None
            ),
            total_tests=(
                int(total_tests) if total_tests is not None else None
            ),
            failed_test_ids=list(failed_ids),
            not_observed_test_ids=list(not_observed_ids),
            semantic_test_results=list(semantic_test_results),
            trace_xml_path=str(trace_xml),
            state_space_xml_path=(
                str(state_space_xml)
                if state_space_xml.is_file()
                else None
            ),
            parsed_trace_path=str(parsed_trace_json),
            parsed_state_space_path=(
                str(parsed_state_space_json)
                if parsed_state_space_json is not None
                and parsed_state_space_json.is_file()
                else None
            ),
            # Backward-compatible field: this is the actual JSON consumed
            # by the evaluator for this benchmark.
            parsed_result_path=str(evaluator_input_json),
            semantic_input=semantic_input,
            result_path=str(semantic_json),
            spec_path=str(config.spec_path),
            commands=commands,
        )
