# experiments/day6_complex_examples_gpt5_advanced_version_1/day6_grid.py
"""
Day 6: VERSION_1_ADVANCED on TWO complex examples.
1. Producer-Consumer (Queue logic)
2. Counter Multicast (Shared state & Sender reference)

Model: GPT-5.1-2025-11-13
Prompt: VERSION_1_ADVANCED
"""
from experiments.base_model_v2 import BaseModelV2
from experiments.parameter_grid import get_all_configs, get_config_name
from prompts.system_prompts import VERSION_1_ADVANCED


def main():
    model_name = "gpt-5.1-2025-11-13"
    # Descriptive prompt name for logging
    prompt_name = "v1_advanced_complex"
    configs = get_all_configs()

    print("\n" + "=" * 80)
    print(f"DAY 6: {prompt_name.upper()} - 16 CONFIGS x FILES")
    print("=" * 80)
    print(f"Model: {model_name}")
    print(f"Prompt: VERSION_1_ADVANCED")
    print(f"Files: Running on all files in 'data/input_akka_codes'")
    print(f"Total configs: {len(configs)}")
    print("=" * 80 + "\n")

    results = []

    for i, param_config in enumerate(configs, 1):
        config_name = get_config_name(param_config)
        # Use the requested specific experiment name
        exp_name = f"day6_complex_examples_gpt5_advanced_version_1/{config_name}"

        print(f"\n{'#'*80}")
        print(f"CONFIG {i}/{len(configs)}: {config_name}")
        print(f"{'#'*80}")

        full_config = {
            "experiment_name": exp_name,
            "model": model_name,
            "system_prompt": VERSION_1_ADVANCED,
            "max_retries": 5,
            "description": f"Day6: Complex Examples V1 Adv - {config_name}",
            **param_config,
        }

        model = BaseModelV2(full_config)
        # This will process ALL .txt files in the directory
        dir_results = model.run_on_directory("data/input_akka_codes")
        results.append(dir_results)

    # Summary
    print("\n\n" + "=" * 80)
    print("DAY 6 COMPLETE!")
    print("=" * 80)

    total_files_processed = 0
    total_successes = 0

    for i, param_config in enumerate(configs):
        config_name = get_config_name(param_config)
        config_results = results[i]

        # Count successes per config
        successes = sum(1 for r in config_results if r["success"])
        total = len(config_results)

        total_files_processed += total
        total_successes += successes

        status = "✓" if successes == total else "✗"
        # Print breakdown (e.g., 3/3 files succeeded)
        print(f"{status} {config_name} | {successes}/{total} files succeeded")

    print("\n" + "=" * 80)
    print(
        f"OVERALL SUMMARY: {total_successes}/{total_files_processed} total translations succeeded"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
