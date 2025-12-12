# src/agents/translator_agent.py
"""
LLM-based Akka-to-Rebeca translation agent.
"""
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from src.state.translation_state import TranslationState
from config.settings import settings
from src.processors.file_handler import (
    read_akka_file,
    write_rebeca_file,
    read_validation_output,
)
from src.processors.jar_executor import execute_validator_jar, parse_validation_result
from pathlib import Path

# Initialize LLM
llm = ChatOpenAI(
    model=settings.DEFAULT_MODEL,
    temperature=settings.TEMPERATURE,
    api_key=settings.OPENAI_API_KEY,
)


def read_akka_code(state: TranslationState) -> dict:
    """Node 1: Read Akka code from input file."""
    file_path = state["akka_file_path"]
    try:
        akka_code = read_akka_file(file_path)
        return {"akka_code": akka_code, "current_step": "akka_read", "error": None}
    except Exception as e:
        return {"current_step": "error", "error": f"Failed to read Akka file: {str(e)}"}


def translate_to_rebeca(state: TranslationState) -> dict:
    """Node 2: Translate Akka code to Rebeca using LLM."""
    akka_code = state["akka_code"]

    system_prompt = """You are an expert in translating Akka actor code to Rebeca modeling language.

Rebeca (Reactive Objects Language) is an actor-based modeling language for concurrent systems.

Key translation rules:
1. Akka actors become Rebeca reactive classes
2. Actor messages become message servers
3. Actor references become known rebecs
4. Message sending (!) becomes message calls
5. Maintain the structure and behavior of the original Akka code

OUTPUT ONLY THE RAW REBECA CODE. NO EXPLANATIONS. NO MARKDOWN. NO COMMENTS."""

    user_prompt = f"""Translate the following Akka code to Rebeca: 
    {akka_code}
Output ONLY the Rebeca code with no explanations, no markdown formatting, no comments."""

    try:
        response = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )

        rebeca_code = response.content.strip()

        # Remove any explanatory text before code
        lines = rebeca_code.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if any(
                keyword in stripped
                for keyword in ["reactiveclass", "main", "env", "package", "import"]
            ):
                start_idx = i
                break

        # Remove any explanatory text after code
        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped.endswith("}") or stripped.endswith(";"):
                end_idx = i + 1
                break

        rebeca_code = "\n".join(lines[start_idx:end_idx])

        # Clean up markdown code blocks
        rebeca_code = rebeca_code.replace("``````", "").strip()

        return {"rebeca_code": rebeca_code, "current_step": "translated", "error": None}
    except Exception as e:
        return {"current_step": "error", "error": f"Translation failed: {str(e)}"}


def write_rebeca_output(state: TranslationState) -> dict:
    """Node 3: Write translated Rebeca code to benchmark directory."""
    rebeca_code = state["rebeca_code"]
    akka_file = state["akka_file_path"]

    base_name = Path(akka_file).stem
    output_path = f"benchmark/{base_name}.rebeca"  # Changed from .rebec to .rebeca

    try:
        write_rebeca_file(rebeca_code, output_path)
        return {
            "rebeca_file_path": output_path,
            "current_step": "written",
            "error": None,
        }
    except Exception as e:
        return {
            "current_step": "error",
            "error": f"Failed to write Rebeca file: {str(e)}",
        }


def validate_rebeca(state: TranslationState) -> dict:
    """Node 4: Execute JAR to validate Rebeca code."""
    rebeca_file = state["rebeca_file_path"]

    try:
        # Execute JAR (it processes the entire benchmark directory)
        success, jar_output = execute_validator_jar()

        # The JAR writes individual .txt files for each .rebeca file
        # Read the specific validation file for this rebeca file
        base_name = Path(rebeca_file).stem
        validation_file = f"validation_output/{base_name}.txt"

        try:
            with open(validation_file, "r") as f:
                validation_content = f.read().strip()

            if validation_content == "1":
                return {
                    "validation_result": "success",
                    "validation_output": "Compilation successful",
                    "current_step": "validated",
                    "error": None,
                }
            else:
                # Content contains error messages in format: "msg, line, charPositionInLine"
                return {
                    "validation_result": "error",
                    "validation_output": validation_content,
                    "current_step": "validation_failed",
                    "error": validation_content,
                }
        except FileNotFoundError:
            return {
                "validation_result": "error",
                "validation_output": f"Validation output file not found: {validation_file}",
                "current_step": "validation_failed",
                "error": f"Validation output file not found: {validation_file}",
            }

    except Exception as e:
        return {
            "validation_result": "error",
            "validation_output": str(e),
            "current_step": "validation_failed",
            "error": f"Validation failed: {str(e)}",
        }


def fix_translation_errors(state: TranslationState) -> dict:
    """Node 5: Fix translation based on validation errors."""
    akka_code = state["akka_code"]
    previous_rebeca_code = state["rebeca_code"]
    validation_errors = state["validation_output"]
    retry_count = state.get("retry_count", 0)
    error_history = state.get("error_history", [])

    error_history.append(f"Attempt {retry_count}: {validation_errors}")

    system_prompt = """You are an expert in translating Akka actor code to Rebeca modeling language.

You previously generated Rebeca code that failed compilation. Your task is to fix the errors.

Rebeca syntax rules:
1. Reactive classes must be properly defined
2. Message servers must have correct signatures
3. Known rebecs must be declared in the knowns section
4. Main rebec must be defined
5. All syntax must follow Rebeca language specifications

OUTPUT ONLY THE RAW REBECA CODE. NO EXPLANATIONS. NO MARKDOWN. NO COMMENTS. NO PREAMBLE."""

    error_context = "\n".join([f"- {err}" for err in error_history])

    user_prompt = f"""Original Akka code:
    {akka_code}
Your previous Rebeca translation had these compilation errors:
{validation_errors}

Error history:
{error_context}

Provide ONLY the corrected Rebeca code. No explanations, no markdown blocks, no comments, no preamble text."""

    try:
        print(f"\n🔄 Retry attempt {retry_count + 1}: Asking LLM to fix errors...")

        response = llm.invoke(
            [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        )

        rebeca_code = response.content.strip()

        # Remove any preamble text
        lines = rebeca_code.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            stripped = line.strip().lower()
            if any(
                keyword in stripped
                for keyword in ["reactiveclass", "main", "env", "package", "import"]
            ):
                start_idx = i
                break

        # Remove any closing text
        end_idx = len(lines)
        for i in range(len(lines) - 1, -1, -1):
            stripped = lines[i].strip()
            if stripped.endswith("}") or stripped.endswith(";"):
                end_idx = i + 1
                break

        rebeca_code = "\n".join(lines[start_idx:end_idx])

        # Clean markdown
        rebeca_code = rebeca_code.replace("``````", "").strip()

        return {
            "rebeca_code": rebeca_code,
            "retry_count": retry_count + 1,
            "error_history": error_history,
            "current_step": "retranslated",
            "error": None,
        }
    except Exception as e:
        return {
            "retry_count": retry_count + 1,
            "error_history": error_history,
            "current_step": "error",
            "error": f"Retry translation failed: {str(e)}",
        }
