# experiments/phase3_intermediate/run_detailed_rules.py
"""
Phase 3: Intermediate Examples - DETAILED_RULES Prompt
Runs the 16-config grid on the 4 intermediate examples.
"""
from experiments.base_model_v2 import BaseModelV2
from experiments.parameter_grid import get_all_configs, get_config_name
import prompts.phase2_prompts as p2_prompts

def main():
    model_name = "gpt-5.1-2025-11-13"
    prompt_name = "detailed_rules"
    input_dir = "data/input_akka_codes/intermediate_examples"
    configs = get_all_configs()

    print("\n" + "=" * 80)
    print(f"PHASE 3: {prompt_name.upper()} PROMPT - 16 CONFIGS x 4 FILES")
    print("=" * 80)
    print(f"Model: {model_name}")
    print(f"Prompt: {prompt_name.upper()}")
    print(f"Input Directory: {input_dir}")
    print(f"Total configs: {len(configs)}")
    print("=" * 80 + "\n")

    results = []

    for i, param_config in enumerate(configs, 1):
        config_name = get_config_name(param_config)
        exp_name = f"phase3_intermediate/{prompt_name}/{config_name}"

        print(f"\n{'#'*80}")
        print(f"CONFIG {i}/{len(configs)}: {config_name}")
        print(f"{'#'*80}")

        full_config = {
            "experiment_name": exp_name,
            "model": model_name,
            "system_prompt": p2_prompts.DETAILED_RULES,
            "max_retries": 5,
            "description": f"Phase3 Intermediate: {prompt_name} - {config_name}",
            **param_config,
        }

        model = BaseModelV2(full_config)
        dir_results = model.run_on_directory(input_dir)
        results.append(dir_results)

    # Summary
    print("\n\n" + "=" * 80)
    print(f"PHASE 3 {prompt_name.upper()} COMPLETE!")
    print("=" * 80)

    total_files_processed = 0
    total_successes = 0

    for i, param_config in enumerate(configs):
        config_name = get_config_name(param_config)
        config_results = results[i]
        successes = sum(1 for r in config_results if r["success"])
        total = len(config_results)
        total_files_processed += total
        total_successes += successes
        status = "✓" if successes == total else "✗"
        print(f"{status} {config_name} | {successes}/{total} files succeeded")

    print("\n" + "=" * 80)
    print(f"OVERALL SUMMARY: {total_successes}/{total_files_processed} total translations succeeded")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
