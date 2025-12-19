# src/processors/jar_executor.py
"""
Execute Rebeca validator JAR file and process results.
"""
import subprocess
import os
from config.settings import settings


def execute_validator_jar(
    jar_path: str = None, benchmark_dir: str = "benchmarks"
) -> tuple:
    """
    Execute the Rebeca validator JAR file.

    The JAR expects:
    - Arg 1: Input directory containing .rebeca files
    - Arg 2: Output directory for validation .txt files
    """
    if jar_path is None:
        jar_path = settings.VALIDATOR_JAR_PATH

    try:
        # Ensure directories exist
        os.makedirs(benchmark_dir, exist_ok=True)
        os.makedirs("validation_output", exist_ok=True)

        print(f"Running validator JAR: {jar_path}")
        print(f"Input directory: {benchmark_dir}")
        print(f"Output directory: validation_output")

        # Force Java 17
        java_bin = "/usr/lib/jvm/java-17-openjdk-amd64/bin/java"

        # Call JAR with both directories
        result = subprocess.run(
            [java_bin, "-jar", jar_path, benchmark_dir, "validation_output"],
            capture_output=True,
            text=True,
            timeout=60,
        )

        full_output = result.stdout + "\n" + result.stderr

        # Print output for debugging
        if full_output.strip():
            print(f"JAR output:\n{full_output}")

        if result.returncode == 0:
            print("✓ JAR execution completed successfully")
            return True, full_output
        else:
            print(f"✗ JAR execution failed with return code {result.returncode}")
            return False, full_output

    except subprocess.TimeoutExpired:
        return False, "JAR execution timed out after 60 seconds"
    except FileNotFoundError:
        return False, f"JAR file not found: {jar_path}"
    except Exception as e:
        return False, f"Error executing JAR: {str(e)}"


def parse_validation_result(validation_output: str) -> dict:
    """Parse validation output to determine success or failure."""
    # The JAR writes "1" for success, or error lines for failure
    if validation_output.strip() == "1":
        return {"success": True, "message": "Compilation successful"}
    else:
        return {"success": False, "message": validation_output.strip()}
