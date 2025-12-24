# experiments/day7_v2_advanced/day7_grid.py
"""
Day 7: VERSION_2_ADVANCED on all 3 examples.
Comparing V2 prompt performance against the V1 baseline (Day 6).

Model: GPT-5.1-2025-11-13
Prompt: VERSION_2_ADVANCED
"""
from experiments.base_model_v2 import BaseModelV2
from experiments.parameter_grid import get_all_configs, get_config_name
from prompts.system_prompts import VERSION_2_ADVANCED


def main():
    model_name = "gpt-5.1-2025-11-13"
    prompt_name = "v2_advanced_comparison"
    configs = get_all_configs()

    print("\n" + "=" * 80)
    print(f"DAY 7: {prompt_name.upper()} - 16 CONFIGS x 3 FILES")
    print("=" * 80)
    print(f"Model: {model_name}")
    print(f"Prompt: VERSION_2_ADVANCED")
    print(f"Objective: Compare V2 vs V1 (Day 6)")
    print(f"Total configs: {len(configs)}")
    print("=" * 80 + "\n")

    results = []

    for i, param_config in enumerate(configs, 1):
        config_name = get_config_name(param_config)
        exp_name = f"day7_v2_advanced/{config_name}"

        print(f"\n{'#'*80}")
        print(f"CONFIG {i}/{len(configs)}: {config_name}")
        print(f"{'#'*80}")

        full_config = {
            "experiment_name": exp_name,
            "model": model_name,
            "system_prompt": VERSION_2_ADVANCED,
            "max_retries": 5,
            "description": f"Day7: V2 Advanced - {config_name}",
            **param_config,
        }

        model = BaseModelV2(full_config)
        # Runs on all 3 files: ping_pong, producer_consumer, counter_multicast
        dir_results = model.run_on_directory("data/input_akka_codes")
        results.append(dir_results)

    # Summary
    print("\n\n" + "=" * 80)
    print("DAY 7 COMPLETE!")
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
    print(
        f"OVERALL SUMMARY: {total_successes}/{total_files_processed} total translations succeeded"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
