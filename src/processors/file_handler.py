"""
File I/O operations for Akka and Rebeca code files.
"""

import os
from pathlib import Path


def read_akka_file(file_path: str) -> str:
    """Read Akka code from .txt file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        print(f"✓ Read Akka file: {file_path}")
        return content
    except Exception as e:
        raise IOError(f"Failed to read Akka file {file_path}: {str(e)}")


def write_rebeca_file(rebeca_code: str, output_path: str) -> str:
    """Write Rebeca code to .rebec file in benchmark directory."""
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(rebeca_code)
        print(f"✓ Wrote Rebeca file: {output_path}")
        return output_path
    except Exception as e:
        raise IOError(f"Failed to write Rebeca file {output_path}: {str(e)}")


def get_akka_files(directory: str = "input_akka_codes") -> list:
    """Get all .txt files from input directory."""
    akka_files = list(Path(directory).glob("*.txt"))
    print(f"Found {len(akka_files)} Akka files to process")
    return [str(f) for f in akka_files]


def read_validation_output(file_name: str) -> str:
    """Read validation output for a specific .rebec file."""
    output_path = f"validation_output/{Path(file_name).stem}_output.txt"
    try:
        with open(output_path, "r", encoding="utf-8") as f:
            result = f.read().strip()
        return result
    except FileNotFoundError:
        return "Validation output file not found"
    except Exception as e:
        return f"Error reading validation: {str(e)}"
