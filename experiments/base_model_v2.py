# experiments/base_model_v2.py
"""
Configurable translation engine for systematic experimentation.
Version 2.0 - Thesis edition with full prompt logging
"""
import json
import time
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from config.settings import settings
from src.processors.file_handler import (
    read_akka_file,
    write_rebeca_file,
    get_akka_files,
)
from src.processors.jar_executor import execute_validator_jar


class BaseModelV2:
    """
    Configurable LLM-based Akka-to-Rebeca translator.

    Designed for systematic experimentation with:
    - Configurable temperature, model, prompts
    - Detailed attempt tracking
    - Error history and metrics
    - Full prompt logging for analysis
    - Reproducible experiments
    """

    def __init__(self, config: Dict = None):
        """
        Initialize with experimental configuration.

        Args:
            config: Dictionary with experiment parameters:
                - experiment_name: str - Unique experiment identifier
                - model: str - LLM model name (default: gpt-4)
                - temperature: float - 0.0-1.0 (default: 0.1)
                - max_retries: int - Maximum retry attempts (default: 5)
                - system_prompt: str - System prompt text
                - initial_prompt_template: str - First translation prompt
                - retry_prompt_template: str - Error feedback prompt
                - description: str - Experiment description
        """
        config = config or {}

        # Store full config
        self.config = config

        # Extract parameters
        self.experiment_name = config.get("experiment_name", "default")
        self.model_name = config.get("model", settings.DEFAULT_MODEL)
        self.temperature = config.get("temperature", settings.TEMPERATURE)
        self.max_retries = config.get("max_retries", settings.MAX_RETRIES)
        self.description = config.get("description", "")

        # Initialize LLM
        self.llm = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature,
            api_key=settings.OPENAI_API_KEY,
        )

        # Prompts
        self.system_prompt = config.get("system_prompt", self._default_system_prompt())
        self.initial_prompt_template = config.get(
            "initial_prompt_template", self._default_initial_prompt()
        )
        self.retry_prompt_template = config.get(
            "retry_prompt_template", self._default_retry_prompt()
        )

        # Output directory
        self.output_dir = Path(f"experiments/results/{self.experiment_name}")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Metrics tracking
        self.total_api_calls = 0
        self.total_tokens_used = 0

    def _default_system_prompt(self) -> str:
        """Default minimal system prompt."""
        return "You are an expert in Akka and Rebeca programming languages."

    def _default_initial_prompt(self) -> str:
        """Default initial translation prompt."""
        return """Translate the following Akka code into Rebeca code.

Input Akka code:
{akka_code}

Output only valid Rebeca code with no explanations or markdown formatting."""

    def _default_retry_prompt(self) -> str:
        """Default retry prompt with error feedback."""
        return """The following Rebeca code has compilation errors:

Code:
{previous_code}

Errors:
{errors}

Provide corrected Rebeca code. Output only the code with no explanations."""

    def clean_output(self, text: str) -> str:
        """
        Extract clean Rebeca code from LLM output.

        Removes:
        - Markdown code blocks
        - Explanatory text before/after code
        - Extra whitespace
        """
        text = text.strip()

        # Remove markdown blocks
        text = text.replace("``````", "").strip()

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

    def validate_code(self, rebeca_code: str, filename: str = "test") -> Dict:
        """
        Validate Rebeca code using JAR compiler.
        Uses experiment-specific directories to prevent overwrites.

        Flow:
        1. Write to temp location (benchmarks/temp.rebeca)
        2. JAR processes it → creates validation_output/temp.txt
        3. Copy both to experiment-specific archive
        4. Keep temp files for JAR to use on next run

        Args:
            rebeca_code: Rebeca code to validate
            filename: Descriptive name (e.g., "simple_ping_pong_attempt_1")

        Returns:
            dict: {"success": bool, "error": Optional[str]}
        """
        try:
            # Create experiment-specific archive directories
            exp_benchmark_dir = Path(f"benchmarks/{self.experiment_name}")
            exp_validation_dir = Path(f"validation_output/{self.experiment_name}")

            exp_benchmark_dir.mkdir(parents=True, exist_ok=True)
            exp_validation_dir.mkdir(parents=True, exist_ok=True)

            # STEP 1: Write to JAR's working location (temp file)
            temp_rebeca_file = "benchmarks/temp.rebeca"
            write_rebeca_file(rebeca_code, temp_rebeca_file)

            # STEP 2: Run JAR (processes benchmarks/*.rebeca, outputs to validation_output/*.txt)
            success, jar_output = execute_validator_jar()

            # STEP 3: Read result from JAR's output location
            temp_validation_file = "validation_output/temp.txt"

            try:
                with open(temp_validation_file, "r") as f:
                    result = f.read().strip()

                # STEP 4: Archive to experiment-specific directory with good name
                # Copy Rebeca code
                archive_rebeca_path = exp_benchmark_dir / f"{filename}.rebeca"
                shutil.copy2(temp_rebeca_file, archive_rebeca_path)

                # Copy validation result
                archive_validation_path = exp_validation_dir / f"{filename}.txt"
                shutil.copy2(temp_validation_file, archive_validation_path)

                print(f"  📁 Archived to: {self.experiment_name}/{filename}.*")

                # STEP 5: Return validation result
                if result == "1":
                    return {"success": True, "error": None}
                else:
                    return {"success": False, "error": result}

            except FileNotFoundError:
                return {"success": False, "error": "Validation file not found"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _save_prompt_log(
        self,
        attempt_num: int,
        file_id: str,
        system_prompt: str,
        user_prompt: str,
        llm_response: str,
    ):
        """Save detailed prompt log for analysis."""
        log_dir = self.output_dir / "prompt_logs"
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"{file_id}_attempt_{attempt_num}_prompts.txt"

        with open(log_file, "w", encoding="utf-8") as f:
            f.write("=" * 80 + "\n")
            f.write(f"ATTEMPT {attempt_num} - PROMPT LOG\n")
            f.write(f"Experiment: {self.experiment_name}\n")
            f.write(f"File: {file_id}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write("=" * 80 + "\n\n")

            f.write("SYSTEM PROMPT:\n")
            f.write("-" * 80 + "\n")
            f.write(system_prompt)
            f.write("\n\n")

            f.write("USER PROMPT:\n")
            f.write("-" * 80 + "\n")
            f.write(user_prompt)
            f.write("\n\n")

            f.write("LLM RESPONSE:\n")
            f.write("-" * 80 + "\n")
            f.write(llm_response)
            f.write("\n\n")
            f.write("=" * 80 + "\n")

    def translate(self, akka_code: str, file_id: str = "test") -> Dict:
        """
        Translate Akka code to Rebeca with retry loop.

        Args:
            akka_code: Input Akka source code
            file_id: Identifier for this translation (for temp files)

        Returns:
            dict: Complete translation result with all attempts
        """
        attempts = []

        for attempt_num in range(self.max_retries):
            print(f"\n{'='*70}")
            print(f"ATTEMPT {attempt_num + 1}/{self.max_retries}")
            print(f"{'='*70}")

            # Build prompt
            if attempt_num == 0:
                # Initial translation
                prompt_text = self.initial_prompt_template.format(akka_code=akka_code)
            else:
                # Retry with error feedback
                previous_code = attempts[-1]["rebeca_code"]
                previous_error = attempts[-1]["error"]
                prompt_text = self.retry_prompt_template.format(
                    previous_code=previous_code, errors=previous_error
                )

            # Call LLM
            try:
                messages = [
                    SystemMessage(content=self.system_prompt),
                    HumanMessage(content=prompt_text),
                ]

                # LOG PROMPTS TO CONSOLE
                print(f"\n{'─'*70}")
                print("📤 SYSTEM PROMPT:")
                print(f"{'─'*70}")
                system_preview = self.system_prompt[:300] + (
                    "..." if len(self.system_prompt) > 300 else ""
                )
                print(system_preview)
                print(f"\n{'─'*70}")
                print("📤 USER PROMPT:")
                print(f"{'─'*70}")
                user_preview = prompt_text[:500] + (
                    "..." if len(prompt_text) > 500 else ""
                )
                print(user_preview)
                print(f"{'─'*70}\n")

                response = self.llm.invoke(messages)
                self.total_api_calls += 1

                # LOG RESPONSE TO CONSOLE
                print(f"{'─'*70}")
                print("📥 LLM RESPONSE:")
                print(f"{'─'*70}")
                response_preview = response.content[:400] + (
                    "..." if len(response.content) > 400 else ""
                )
                print(response_preview)
                print(f"{'─'*70}\n")

                # SAVE PROMPTS TO FILE
                self._save_prompt_log(
                    attempt_num=attempt_num + 1,
                    file_id=file_id,
                    system_prompt=self.system_prompt,
                    user_prompt=prompt_text,
                    llm_response=response.content,
                )

                # Clean output
                rebeca_code = self.clean_output(response.content)

                # Validate
                validation = self.validate_code(
                    rebeca_code, f"{file_id}_attempt_{attempt_num+1}"
                )

                # Record attempt
                attempt_record = {
                    "attempt_number": attempt_num + 1,
                    "rebeca_code": rebeca_code,
                    "validation_success": validation["success"],
                    "error": validation["error"],
                    "timestamp": datetime.now().isoformat(),
                    "code_length": len(rebeca_code),
                }

                attempts.append(attempt_record)

                # Check success
                if validation["success"]:
                    print(f"\n{'🎉'*20}")
                    print(f"✓ SUCCESS on attempt {attempt_num + 1}!")
                    print(f"{'🎉'*20}\n")
                    return {
                        "success": True,
                        "total_attempts": attempt_num + 1,
                        "final_code": rebeca_code,
                        "attempts": attempts,
                    }
                else:
                    error_preview = validation["error"][:200]
                    print(f"\n✗ COMPILATION FAILED")
                    print(f"Error: {error_preview}...")

            except Exception as e:
                print(f"\n✗ LLM ERROR: {str(e)}")
                attempt_record = {
                    "attempt_number": attempt_num + 1,
                    "rebeca_code": "",
                    "validation_success": False,
                    "error": f"LLM Error: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                    "code_length": 0,
                }
                attempts.append(attempt_record)

        # All attempts failed
        print(f"\n{'❌'*20}")
        print(f"✗ ALL {self.max_retries} ATTEMPTS FAILED")
        print(f"{'❌'*20}\n")
        return {
            "success": False,
            "total_attempts": self.max_retries,
            "final_code": attempts[-1]["rebeca_code"] if attempts else "",
            "attempts": attempts,
        }

    def run_on_file(self, akka_file: str) -> Dict:
        """
        Run translation on a single Akka file.

        Args:
            akka_file: Path to Akka source file

        Returns:
            dict: Complete results including metadata
        """
        file_path = Path(akka_file)
        file_id = file_path.stem

        print(f"✓ Read Akka file: {akka_file}")

        # Read Akka code
        akka_code = read_akka_file(akka_file)

        # Run translation
        start_time = time.time()
        result = self.translate(akka_code, file_id)
        elapsed_time = time.time() - start_time

        # Add metadata
        result["file_name"] = file_path.name
        result["file_id"] = file_id
        result["elapsed_time"] = elapsed_time
        result["config"] = {
            "experiment_name": self.experiment_name,
            "model": self.model_name,
            "temperature": self.temperature,
            "max_retries": self.max_retries,
        }
        result["timestamp"] = datetime.now().isoformat()

        # Save detailed result
        result_file = self.output_dir / f"{file_id}_result.json"
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)

        # Save final code if successful
        if result["success"]:
            final_code_file = self.output_dir / f"{file_id}_final.rebeca"
            with open(final_code_file, "w") as f:
                f.write(result["final_code"])

        return result

    def run_on_directory(self, input_dir: str = "data/input_akka_codes") -> List[Dict]:
        """
        Run translation on all Akka files in directory.

        Args:
            input_dir: Directory containing Akka source files

        Returns:
            list: Results for all files
        """
        akka_files = get_akka_files(input_dir)

        if not akka_files:
            print(f"⚠ No files found in {input_dir}")
            return []

        print(f"\nFound {len(akka_files)} Akka files to process")

        print(f"\n{'#'*70}")
        print(f"EXPERIMENT: {self.experiment_name}")
        print(f"Model: {self.model_name} | Temp: {self.temperature}")
        print(f"Files: {len(akka_files)} | Max retries: {self.max_retries}")
        print(f"{'#'*70}\n")

        all_results = []
        for i, akka_file in enumerate(akka_files, 1):
            print(f"\n{'*'*70}")
            print(f"FILE {i}/{len(akka_files)}: {Path(akka_file).name}")
            print(f"{'*'*70}")

            result = self.run_on_file(akka_file)
            all_results.append(result)

        # Save summary
        self._save_summary(all_results)

        return all_results

    def _save_summary(self, results: List[Dict]):
        """Save experiment summary."""
        summary_file = self.output_dir / "summary.json"

        total = len(results)
        successful = sum(1 for r in results if r["success"])

        summary = {
            "experiment_name": self.experiment_name,
            "description": self.description,
            "config": {
                "model": self.model_name,
                "temperature": self.temperature,
                "max_retries": self.max_retries,
            },
            "results": {
                "total_files": total,
                "successful": successful,
                "failed": total - successful,
                "success_rate": (successful / total * 100) if total > 0 else 0,
                "avg_attempts": (
                    sum(r["total_attempts"] for r in results) / total
                    if total > 0
                    else 0
                ),
                "avg_time": (
                    sum(r["elapsed_time"] for r in results) / total if total > 0 else 0
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }

        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'='*70}")
        print("EXPERIMENT SUMMARY")
        print(f"{'='*70}")
        print(
            f"Success: {successful}/{total} ({summary['results']['success_rate']:.1f}%)"
        )
        print(f"Avg attempts: {summary['results']['avg_attempts']:.2f}")
        print(f"Avg time: {summary['results']['avg_time']:.2f}s")
        print(f"Results saved to: {self.output_dir}")
        print(f"{'='*70}\n")
