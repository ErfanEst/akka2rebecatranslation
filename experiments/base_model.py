# experiments/base_model.py
"""
Base model: Simple translation with error feedback loop.
Uses existing project infrastructure.
"""
import json
import time
from pathlib import Path
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import settings
from src.processors.file_handler import (
    read_akka_file,
    write_rebeca_file,
    get_akka_files,
)
from src.processors.jar_executor import execute_validator_jar


class BaseModel:
    def __init__(self):
        self.llm = ChatOpenAI(
            model=settings.DEFAULT_MODEL,
            temperature=settings.TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )
        self.output_dir = Path("experiments/base_results")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def clean_output(self, text: str) -> str:
        """Remove markdown blocks and extra text, keep only Rebeca code."""
        text = text.strip()

        # Remove markdown code blocks
        text = text.replace("``````", "")

        # Find first line with Rebeca keywords
        lines = text.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if any(
                kw in stripped
                for kw in ["reactiveclass", "main", "env", "package", "import"]
            ):
                start_idx = i
                break

        # Find last line with closing brace
        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped.endswith("}") or stripped.endswith(";"):
                end_idx = i + 1
                break

        return "\n".join(lines[start_idx:end_idx]).strip()

    def validate_code(self, rebeca_code: str, filename: str = "test") -> dict:
        """Validate Rebeca code using JAR compiler."""
        try:
            # Write to benchmark directory (used by JAR)
            rebeca_file = f"benchmark/{filename}.rebeca"
            write_rebeca_file(rebeca_code, rebeca_file)

            # Run JAR validator (uses your jar_executor)
            success, jar_output = execute_validator_jar()

            # Read validation result from validation_output
            validation_file = f"validation_output/{filename}.txt"
            try:
                with open(validation_file, "r") as f:
                    result = f.read().strip()

                if result == "1":
                    return {"success": True, "error": None}
                else:
                    return {"success": False, "error": result}

            except FileNotFoundError:
                return {"success": False, "error": "Validation file not found"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def show_changes(self, old_code: str, new_code: str):
        """Show what changed between two code versions."""
        print(f"🔄 Changes Made:")
        print(f"{'─'*70}")

        old_lines = old_code.split("\n")
        new_lines = new_code.split("\n")

        # Simple diff: count lines added/removed/changed
        added = len(new_lines) - len(old_lines)

        # Find some specific changes
        changes = []

        # Check length change
        if added > 0:
            changes.append(f"  • Added {added} lines")
        elif added < 0:
            changes.append(f"  • Removed {abs(added)} lines")
        else:
            changes.append(f"  • Same number of lines (modifications only)")

        # Check for specific keyword changes
        old_keywords = {
            "reactiveclass": old_code.count("reactiveclass"),
            "msgsrv": old_code.count("msgsrv"),
            "knownrebecs": old_code.count("knownrebecs"),
            "statevars": old_code.count("statevars"),
        }

        new_keywords = {
            "reactiveclass": new_code.count("reactiveclass"),
            "msgsrv": new_code.count("msgsrv"),
            "knownrebecs": new_code.count("knownrebecs"),
            "statevars": new_code.count("statevars"),
        }

        for keyword, old_count in old_keywords.items():
            new_count = new_keywords[keyword]
            if old_count != new_count:
                changes.append(f"  • {keyword}: {old_count} → {new_count}")

        # Show character-level difference
        if len(old_code) != len(new_code):
            diff = len(new_code) - len(old_code)
            sign = "+" if diff > 0 else ""
            changes.append(
                f"  • Code size: {len(old_code)} → {len(new_code)} ({sign}{diff} chars)"
            )

        if changes:
            for change in changes:
                print(change)
        else:
            print("  • Minor syntax/formatting changes")

        print(f"{'─'*70}\n")

    def translate(self, akka_code: str, max_retries: int = 5) -> dict:
        """
        Translate Akka code to Rebeca with error feedback loop.

        Args:
            akka_code: Input Akka source code
            max_retries: Maximum number of retry attempts (default 5)

        Returns:
            dict with success status, attempts, and history
        """
        attempts = []

        for attempt in range(max_retries):
            print(f"\n{'='*70}")
            print(f"ATTEMPT {attempt + 1}/{max_retries}")
            print(f"{'='*70}")

            if attempt == 0:
                # First attempt: Initial translation
                print("📝 Requesting initial translation from LLM...")
                prompt = f"""Translate the following Akka code into fully equivalent Rebeca code.

Input Akka code:
{akka_code}

Your output must contain only valid Rebeca code with no explanations, comments, or extra text."""

            else:
                # Retry: Include previous code and errors
                previous_code = attempts[-1]["rebeca_code"]
                previous_error = attempts[-1]["error"]

                print("🔄 Requesting corrected translation from LLM...")
                print(f"\n📋 Previous errors to fix:")
                print(f"{'─'*70}")
                # Show first 500 chars of error
                error_preview = previous_error[:500] + (
                    "..." if len(previous_error) > 500 else ""
                )
                print(error_preview)
                print(f"{'─'*70}\n")

                prompt = f"""The following Rebeca code has compilation errors:

Rebeca code:
{previous_code}

Compilation errors:
{previous_error}

Please provide the corrected Rebeca code. Output only valid Rebeca code with no explanations, comments, or extra text."""

            try:
                # Call LLM
                print("🤖 Calling LLM...")
                response = self.llm.invoke(
                    [
                        SystemMessage(
                            content="You are an expert in Akka and Rebeca programming languages."
                        ),
                        HumanMessage(content=prompt),
                    ]
                )

                # Clean output
                rebeca_code = self.clean_output(response.content)

                # Show generated code
                print(f"\n📄 Generated Rebeca Code ({len(rebeca_code)} characters):")
                print(f"{'─'*70}")
                print(rebeca_code)
                print(f"{'─'*70}\n")

                # Show what changed (for retries)
                if attempt > 0:
                    self.show_changes(attempts[-1]["rebeca_code"], rebeca_code)

                # Validate
                print("⚙️  Validating with JAR compiler...")
                validation = self.validate_code(rebeca_code, f"attempt_{attempt+1}")

                # Record attempt
                attempt_record = {
                    "attempt_number": attempt + 1,
                    "rebeca_code": rebeca_code,
                    "validation_success": validation["success"],
                    "error": validation["error"],
                    "timestamp": datetime.now().isoformat(),
                }

                attempts.append(attempt_record)

                if validation["success"]:
                    print(f"\n{'🎉'*20}")
                    print(
                        f"✓ SUCCESS: Code compiled successfully on attempt {attempt + 1}!"
                    )
                    print(f"{'🎉'*20}\n")
                    return {
                        "success": True,
                        "total_attempts": attempt + 1,
                        "final_code": rebeca_code,
                        "attempts": attempts,
                    }
                else:
                    print(f"\n❌ COMPILATION FAILED")
                    print(f"{'─'*70}")
                    error_preview = validation["error"][:300] + (
                        "..." if len(validation["error"]) > 300 else ""
                    )
                    print(error_preview)
                    print(f"{'─'*70}\n")

            except Exception as e:
                print(f"\n❌ LLM ERROR: {str(e)}\n")
                attempt_record = {
                    "attempt_number": attempt + 1,
                    "rebeca_code": "",
                    "validation_success": False,
                    "error": f"LLM Error: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }
                attempts.append(attempt_record)

        # All attempts failed
        print(f"\n{'❌'*20}")
        print(f"ALL {max_retries} ATTEMPTS FAILED")
        print(f"{'❌'*20}\n")
        return {
            "success": False,
            "total_attempts": max_retries,
            "final_code": attempts[-1]["rebeca_code"] if attempts else "",
            "attempts": attempts,
        }

    def run_on_file(self, akka_file: str, max_retries: int = 5) -> dict:
        """Run base model on a single Akka file."""
        print(f"\n{'#'*70}")
        print(f"BASE MODEL TRANSLATION")
        print(f"File: {Path(akka_file).name}")
        print(f"Max retries: {max_retries}")
        print(f"{'#'*70}")

        # Read Akka code using your file_handler
        akka_code = read_akka_file(akka_file)
        print(f"\n📖 Read {len(akka_code)} characters of Akka code")

        # Run translation
        start_time = time.time()
        result = self.translate(akka_code, max_retries)
        elapsed_time = time.time() - start_time

        # Add metadata
        result["file_name"] = Path(akka_file).name
        result["elapsed_time"] = elapsed_time
        result["timestamp"] = datetime.now().isoformat()

        # Save detailed results
        result_file = self.output_dir / f"{Path(akka_file).stem}_result.json"
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)

        # Save final code if successful
        if result["success"]:
            final_code_file = self.output_dir / f"{Path(akka_file).stem}_final.rebeca"
            with open(final_code_file, "w") as f:
                f.write(result["final_code"])

        # Print summary
        print(f"\n{'='*70}")
        print(f"FINAL RESULTS")
        print(f"{'='*70}")
        print(f"Status: {'✓ SUCCESS' if result['success'] else '✗ FAILED'}")
        print(f"Attempts: {result['total_attempts']}/{max_retries}")
        print(f"Time: {elapsed_time:.2f}s")
        print(f"Results saved to: {result_file}")
        if result["success"]:
            print(f"Final code saved to: {Path(akka_file).stem}_final.rebeca")
        print(f"{'='*70}\n")

        return result

    def run_on_directory(
        self, input_dir: str = "input_akka_codes", max_retries: int = 5
    ) -> list:
        """Run base model on all files in directory."""
        # Use your get_akka_files function
        akka_files = get_akka_files(input_dir)

        if not akka_files:
            print(f"No files found in {input_dir}")
            return []

        print(f"\n{'#'*70}")
        print(f"RUNNING BASE MODEL ON {len(akka_files)} FILES")
        print(f"{'#'*70}\n")

        all_results = []

        for i, akka_file in enumerate(akka_files, 1):
            print(f"\n{'*'*70}")
            print(f"FILE {i}/{len(akka_files)}")
            print(f"{'*'*70}")
            result = self.run_on_file(akka_file, max_retries)
            all_results.append(result)

        # Generate summary report
        self.generate_summary(all_results)

        return all_results

    def generate_summary(self, results: list):
        """Generate summary report."""
        summary_file = self.output_dir / "summary.txt"

        total = len(results)
        successful = sum(1 for r in results if r["success"])
        failed = total - successful

        avg_attempts_all = (
            sum(r["total_attempts"] for r in results) / total if total > 0 else 0
        )
        avg_attempts_success = (
            sum(r["total_attempts"] for r in results if r["success"]) / successful
            if successful > 0
            else 0
        )
        avg_time = sum(r["elapsed_time"] for r in results) / total if total > 0 else 0

        with open(summary_file, "w") as f:
            f.write("=" * 70 + "\n")
            f.write("BASE MODEL SUMMARY REPORT\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 70 + "\n\n")

            f.write("OVERALL STATISTICS\n")
            f.write("-" * 70 + "\n")
            f.write(f"Total files: {total}\n")
            f.write(f"Successful: {successful} ({successful/total*100:.1f}%)\n")
            f.write(f"Failed: {failed} ({failed/total*100:.1f}%)\n")
            f.write(f"Avg attempts (all): {avg_attempts_all:.2f}\n")
            f.write(f"Avg attempts (successful): {avg_attempts_success:.2f}\n")
            f.write(f"Avg time: {avg_time:.2f}s\n\n")

            f.write("INDIVIDUAL FILE RESULTS\n")
            f.write("-" * 70 + "\n")
            for result in results:
                status = "✓ SUCCESS" if result["success"] else "✗ FAILED"
                f.write(f"\n{result['file_name']}\n")
                f.write(f"  Status: {status}\n")
                f.write(f"  Attempts: {result['total_attempts']}\n")
                f.write(f"  Time: {result['elapsed_time']:.2f}s\n")

                if not result["success"] and result["attempts"]:
                    last_error = result["attempts"][-1]["error"]
                    f.write(f"  Last error: {last_error[:200]}...\n")

        print(f"\n{'='*70}")
        print(f"📊 SUMMARY REPORT")
        print(f"{'='*70}")
        print(f"Total files: {total}")
        print(f"Successful: {successful} ({successful/total*100:.1f}%)")
        print(f"Failed: {failed} ({failed/total*100:.1f}%)")
        print(f"Avg attempts: {avg_attempts_all:.2f}")
        print(f"Avg time: {avg_time:.2f}s")
        print(f"\nSummary saved to: {summary_file}")
        print(f"{'='*70}\n")


def main():
    """Main entry point."""
    model = BaseModel()

    # Run on all files in input directory
    model.run_on_directory("input_akka_codes", max_retries=5)


if __name__ == "__main__":
    main()
