from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------
# Project root setup
# ---------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Make project modules such as config.settings importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

from config.settings import settings

RMC_JAR = Path("/home/erfan/Thesis/tools/rmc-2.14.jar")
JAVA_17 = Path("/usr/lib/jvm/java-17-openjdk-amd64/bin/java")

# Resolve validator JAR from centralized settings.
VALIDATOR_JAR = Path(settings.VALIDATOR_JAR_PATH)

if not VALIDATOR_JAR.is_absolute():
    VALIDATOR_JAR = PROJECT_ROOT / VALIDATOR_JAR


PARSER_SCRIPT = PROJECT_ROOT / "semantic_validation" / "rebeca" / "rmc_result_parser.py"

from semantic_validation.core.evaluator_registry import (
    get_evaluator_path,
)


def run_command(
    command: list[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """
    Run a command and return the completed process.

    Raises RuntimeError if the command fails.
    """

    result = subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"\nCommand failed:\n"
            f"{' '.join(command)}\n\n"
            f"STDOUT:\n{result.stdout}\n\n"
            f"STDERR:\n{result.stderr}"
        )

    return result


def run_syntax_validation(
    model_path: Path,
    temp_dir: Path,
) -> dict:
    """
    Validate the Rebeca candidate using the existing compiler JAR.

    Important:
    The current RebecaCompilerMain expects fixed directories:

        benchmarks/
        validation_output/

    Therefore, the model is copied into an isolated temporary
    benchmarks directory and the compiler is executed from there.
    """

    if not VALIDATOR_JAR.exists():
        raise FileNotFoundError(f"Validator JAR not found: {VALIDATOR_JAR}")

    syntax_root = temp_dir / "syntax_validation"

    benchmark_dir = syntax_root / "benchmarks"

    validation_dir = syntax_root / "validation_output"

    benchmark_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    validation_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    local_model = benchmark_dir / model_path.name

    shutil.copy2(
        model_path,
        local_model,
    )

    # Execute compiler.
    result = run_command(
        [
            str(JAVA_17),
            "-jar",
            str(VALIDATOR_JAR),
        ],
        cwd=syntax_root,
    )

    validation_file = validation_dir / f"{model_path.stem}.txt"

    if not validation_file.exists():
        raise RuntimeError(
            "Syntax validator did not generate "
            f"expected result file: {validation_file}"
        )

    validation_text = validation_file.read_text(encoding="utf-8").strip()

    syntax_pass = validation_text == "1"

    return {
        "syntax_pass": syntax_pass,
        "validation_output": validation_text,
        "compiler_stdout": result.stdout.strip(),
        "compiler_stderr": result.stderr.strip(),
    }


def run_semantic_validation(
    model_path: Path,
    example: str,
    output_dir: Path,
) -> dict:

    model_path = model_path.resolve()
    output_dir = output_dir.resolve()

    if not model_path.exists():
        raise FileNotFoundError(f"Rebeca model not found: {model_path}")

    if not RMC_JAR.exists():
        raise FileNotFoundError(f"RMC JAR not found: {RMC_JAR}")

    if not JAVA_17.exists():
        raise FileNotFoundError(f"Java 17 not found: {JAVA_17}")

    evaluator_script = get_evaluator_path(example)

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    with tempfile.TemporaryDirectory(prefix="semantic_validation_") as temp_dir_str:

        temp_dir = Path(temp_dir_str)

        # =====================================================
        # Stage 1: Syntax validation
        # =====================================================

        print("[1/6] Running Rebeca syntax validation...")

        syntax_result = run_syntax_validation(
            model_path=model_path,
            temp_dir=temp_dir,
        )

        if not syntax_result["syntax_pass"]:

            print("      FAIL")

            final_result = {
                "model": str(model_path),
                "example": example,
                "syntax": {
                    "passed": False,
                    "details": (syntax_result["validation_output"]),
                },
                "semantic": {
                    "executed": False,
                    "passed": False,
                    "reason": (
                        "Semantic validation skipped "
                        "because syntax validation failed."
                    ),
                },
                "final_pass": False,
            }

            report_path = output_dir / f"{model_path.stem}_final_result.json"

            report_path.write_text(
                json.dumps(
                    final_result,
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            return final_result

        print("      PASS")

        # Copy model to isolated RMC working directory.
        rmc_work_dir = temp_dir / "rmc"

        rmc_work_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        local_model = rmc_work_dir / model_path.name

        shutil.copy2(
            model_path,
            local_model,
        )

        # =====================================================
        # Stage 2: RMC code generation
        # =====================================================

        print("[2/6] Running RMC code generation...")

        run_command(
            [
                str(JAVA_17),
                "-jar",
                str(RMC_JAR),
                "-s",
                local_model.name,
                "-e",
                "CORE_REBECA",
                "--tracegenerator",
            ],
            cwd=rmc_work_dir,
        )

        rmc_output_dir = rmc_work_dir / "rmc-output"

        if not rmc_output_dir.exists():
            raise RuntimeError("RMC did not generate " "rmc-output directory.")

        print("      PASS")

        # =====================================================
        # Stage 3: Compile generated C++
        # =====================================================

        print("[3/6] Compiling generated model checker...")

        cpp_files = [str(path.name) for path in rmc_output_dir.glob("*.cpp")]

        if not cpp_files:
            raise RuntimeError("No generated C++ files found.")

        run_command(
            [
                "g++",
                "-std=c++11",
                *cpp_files,
                "-o",
                "model_checker",
            ],
            cwd=rmc_output_dir,
        )

        model_checker = rmc_output_dir / "model_checker"

        if not model_checker.exists():
            raise RuntimeError("model_checker executable " "was not created.")

        print("      PASS")

        # =====================================================
        # Stage 4: Execute model checker
        # =====================================================

        print("[4/6] Running model checker...")

        result_xml = rmc_output_dir / "result.xml"

        run_command(
            [
                "./model_checker",
                "-o",
                result_xml.name,
            ],
            cwd=rmc_output_dir,
        )

        if not result_xml.exists():
            raise RuntimeError("RMC result.xml " "was not generated.")

        print("      PASS")

        # =====================================================
        # Stage 5: Parse RMC result
        # =====================================================

        print("[5/6] Parsing RMC result...")

        parsed_json = output_dir / f"{model_path.stem}_parsed.json"

        run_command(
            [
                sys.executable,
                str(PARSER_SCRIPT),
                str(result_xml),
                "-o",
                str(parsed_json),
            ],
            cwd=PROJECT_ROOT,
        )

        print("      PASS")

        # =====================================================
        # Stage 6: Semantic evaluation
        # =====================================================

        print("[6/6] Running semantic evaluator...")

        semantic_result_json = output_dir / (
            f"{model_path.stem}" "_semantic_result.json"
        )

        run_command(
            [
                sys.executable,
                str(evaluator_script),
                str(parsed_json),
                "-o",
                str(semantic_result_json),
            ],
            cwd=PROJECT_ROOT,
        )

        print("      PASS")

    # =========================================================
    # Load semantic result
    # =========================================================

    with semantic_result_json.open(
        "r",
        encoding="utf-8",
    ) as f:

        semantic_result = json.load(f)

    semantic_summary = semantic_result["summary"]

    semantic_pass = semantic_summary["semantic_pass"]

    final_result = {
        "model": str(model_path),
        "example": example,
        "syntax": {
            "passed": True,
            "details": ("Compilation successful"),
        },
        "semantic": {
            "executed": True,
            "passed": semantic_pass,
            "summary": (semantic_summary),
            "result_file": str(semantic_result_json),
        },
        "final_pass": (True and semantic_pass),
    }

    final_report_path = output_dir / f"{model_path.stem}_final_result.json"

    final_report_path.write_text(
        json.dumps(
            final_result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    return final_result


def main():

    parser = argparse.ArgumentParser(
        description=("Run complete Rebeca syntax and " "semantic validation pipeline.")
    )

    parser.add_argument(
        "--model",
        required=True,
        help=("Path to the Rebeca model"),
    )

    parser.add_argument(
        "--example",
        required=True,
        help=("Semantic evaluator example name"),
    )

    parser.add_argument(
        "--output-dir",
        default=("semantic_validation/results"),
        help=("Directory for validation results"),
    )

    args = parser.parse_args()

    try:

        result = run_semantic_validation(
            model_path=Path(args.model),
            example=args.example,
            output_dir=Path(args.output_dir),
        )

        print()
        print("=" * 60)

        print("FINAL TRANSLATION VALIDATION RESULT")

        print("=" * 60)

        print(f"Model: " f"{result['model']}")

        print(f"Example: " f"{result['example']}")

        print()

        print(f"Syntax PASS: " f"{result['syntax']['passed']}")

        print(f"Semantic Executed: " f"{result['semantic']['executed']}")

        print(f"Semantic PASS: " f"{result['semantic']['passed']}")

        if result["semantic"].get("summary"):

            summary = result["semantic"]["summary"]

            print(f"Semantic Tests: " f"{summary['passed']}" f"/{summary['total']}")

        print(f"Final PASS: " f"{result['final_pass']}")

        print("=" * 60)

        if result["final_pass"]:

            sys.exit(0)

        # Validation completed successfully,
        # but translation was incorrect.
        sys.exit(2)

    except Exception as exc:

        print()
        print("=" * 60)

        print("VALIDATION PIPELINE ERROR")

        print("=" * 60)

        print(str(exc))

        sys.exit(1)


if __name__ == "__main__":
    main()
