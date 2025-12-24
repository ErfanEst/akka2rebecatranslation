# experiments/day1_minimal_grid.py
"""
Day 1: MINIMAL prompt - 32 parameter configurations
Tests: 4 temps × 4 top_p × 2 freq_penalty = 32 configs

Research questions:
1. Does temperature affect translation quality? (4 levels)
2. Does nucleus sampling (top_p) help code generation? (4 levels)
3. Does frequency penalty improve/hurt structured output? (2 levels)
4. How do these parameters interact?

Expected runtime: ~20-30 minutes
"""
from experiments.base_model_v2 import BaseModelV2
from experiments.parameter_grid import get_all_configs, get_config_name
from prompts.system_prompts import MINIMAL


def main():
    prompt_name = "minimal"
    configs = get_all_configs()

    print("\n" + "=" * 80)
    print(f"DAY 1: {prompt_name.upper()} PROMPT - 32 PARAMETER CONFIGURATIONS")
    print("=" * 80)
    print(f"Parameters:")
    print(f"  Temperature: [0.0, 0.1, 0.3, 0.5]")
    print(f"  Top-p: [0.5, 0.8, 0.9, 1.0]")
    print(f"  Frequency penalty: [0.0, 0.5]")
    print(f"  Presence penalty: 0.0 (fixed)")
    print(f"\nTotal configs: {len(configs)}")
    print(
        f"Estimated runtime: ~{len(configs) * 0.5:.0f}-{len(configs) * 0.7:.0f} minutes"
    )
    print("=" * 80 + "\n")

    results = []

    for i, param_config in enumerate(configs, 1):
        config_name = get_config_name(param_config)
        exp_name = f"day1_{prompt_name}/{config_name}"

        print(f"\n{'#'*80}")
        print(f"CONFIG {i}/{len(configs)}: {config_name}")
        print(f"{'#'*80}")

        full_config = {
            "experiment_name": exp_name,
            "model": "gpt-4",
            "system_prompt": MINIMAL,
            "max_retries": 5,
            "description": f"Day1: {prompt_name} - {config_name}",
            **param_config,  # Merge parameter config
        }

        model = BaseModelV2(full_config)
        result = model.run_on_directory("data/input_akka_codes")
        results.append(result)

    # Summary
    print("\n\n" + "=" * 80)
    print("DAY 1 COMPLETE!")
    print("=" * 80)

    successful = 0
    for i, param_config in enumerate(configs):
        config_name = get_config_name(param_config)
        r = results[i][0] if results[i] else None
        if r:
            if r["success"]:
                successful += 1
                print(f"✓ SUCCESS | {config_name}")
            else:
                last_error = (
                    r["attempts"][-1]["error"][:80] if r["attempts"] else "Unknown"
                )
                print(f"✗ FAILED  | {config_name} | {last_error}...")

    print("\n" + "=" * 80)
    print(f"SUMMARY: {successful}/{len(configs)} configs succeeded")
    print("=" * 80)
    print(f"Results location: experiments/results/day1_{prompt_name}/")
    print("\nNext steps:")
    print("1. Analyze successful configs:")
    print(f"   grep -r '\"success\": true' experiments/results/day1_{prompt_name}/")
    print("2. View prompt logs:")
    print(f"   ls experiments/results/day1_{prompt_name}/*/prompt_logs/")
    print("3. Compare parameter effects:")
    print(f"   python -m experiments.analyze_day1")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
