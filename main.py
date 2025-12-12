# main.py
"""
Main entry point for Akka-to-Rebeca translation system.
Processes Akka code files and translates them to Rebeca with validation.
"""
import sys
from pathlib import Path
from src.graphs.translation_workflow import translation_graph
from src.state.translation_state import TranslationState
from src.processors.file_handler import get_akka_files


def process_single_file(akka_file: str, max_retries: int = 3) -> dict:
    """
    Process a single Akka file through the translation workflow.

    Args:
        akka_file: Path to Akka .txt file
        max_retries: Maximum number of retry attempts on validation failure

    Returns:
        Final state after processing
    """
    print(f"\n{'='*60}")
    print(f"Processing: {akka_file}")
    print(f"{'='*60}")

    # Initial state
    initial_state: TranslationState = {
        "akka_file_path": akka_file,
        "akka_code": "",
        "rebeca_code": "",
        "rebeca_file_path": "",
        "validation_result": "",
        "validation_output": "",
        "retry_count": 0,
        "max_retries": max_retries,
        "error_history": [],
        "current_step": "starting",
        "error": None,
    }

    # Execute workflow
    config = {"configurable": {"thread_id": f"translation-{Path(akka_file).stem}"}}
    final_state = translation_graph.invoke(initial_state, config)

    # Print results
    print(f"\n--- Results for {Path(akka_file).name} ---")
    print(f"Status: {final_state['current_step']}")
    print(f"Rebeca file: {final_state.get('rebeca_file_path', 'N/A')}")
    print(f"Validation: {final_state.get('validation_result', 'N/A')}")
    print(f"Attempts: {final_state.get('retry_count', 0) + 1}")

    if final_state.get("error"):
        print(f"Error: {final_state['error']}")
        print(f"\nError History:")
        for err in final_state.get("error_history", []):
            print(f"  {err}")
    else:
        print(f"Output: {final_state.get('validation_output', 'N/A')}")

    return final_state


def main():
    """
    Main execution: Process all Akka files or a specific file.
    """
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="Akka to Rebeca Translation")
    parser.add_argument("file", nargs="?", help="Specific Akka file to process")
    parser.add_argument(
        "--max-retries", type=int, default=3, help="Maximum retry attempts (default: 3)"
    )
    args = parser.parse_args()

    # Check if specific file provided
    if args.file:
        akka_file = args.file
        if not Path(akka_file).exists():
            print(f"Error: File not found: {akka_file}")
            return

        akka_files = [akka_file]
    else:
        # Process all files in input directory
        akka_files = get_akka_files("input_akka_codes")

        if not akka_files:
            print("No Akka .txt files found in input_akka_codes/")
            print("Please add your Akka code files to input_akka_codes/ directory")
            return

    print(f"\nStarting Akka-to-Rebeca Translation")
    print(f"Total files to process: {len(akka_files)}")
    print(f"Max retries per file: {args.max_retries}")

    # Process each file
    results = []
    for akka_file in akka_files:
        result = process_single_file(akka_file, args.max_retries)
        results.append(
            {
                "file": akka_file,
                "success": result.get("validation_result") == "success",
                "attempts": result.get("retry_count", 0) + 1,
                "error": result.get("error"),
            }
        )

    # Summary
    print(f"\n{'='*60}")
    print("TRANSLATION SUMMARY")
    print(f"{'='*60}")

    successful = sum(1 for r in results if r["success"])
    failed = len(results) - successful

    print(f"Total processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")

    if successful > 0:
        print("\nSuccessful translations:")
        for r in results:
            if r["success"]:
                print(f"  ✓ {Path(r['file']).name} (attempts: {r['attempts']})")

    if failed > 0:
        print("\nFailed translations:")
        for r in results:
            if not r["success"]:
                print(
                    f"  ✗ {Path(r['file']).name} (attempts: {r['attempts']}): {r['error']}"
                )


if __name__ == "__main__":
    main()
