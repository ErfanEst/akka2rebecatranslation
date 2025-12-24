# experiments/day4_detailed_rules_gpt51/day4_detailed_rules_gpt51_grid.py
"""
Day 4: DETAILED_RULES prompt with GPT-5.1 - 16 parameter configurations
Using gpt-5.1-2025-11-13 with comprehensive translation rules

Parameters: temperature x top_p only (no frequency/presence penalty)
Expected: Better accuracy than BASIC due to explicit Rebeca syntax rules
"""
from experiments.base_model_v2 import BaseModelV2
from experiments.parameter_grid import get_all_configs, get_config_name
from prompts.system_prompts import DETAILED_RULES


def main():
    model_name = "gpt-5.1-2025-11-13"
    prompt_name = "detailed_rules"
    configs = get_all_configs()

    print("\n" + "=" * 80)
    print(f"DAY 4: {prompt_name.upper()} PROMPT - GPT-5.1 - 16 CONFIGS")
    print("=" * 80)
    print(f"Model: {model_name}")
    print(f"Prompt: DETAILED_RULES (explicit Akka→Rebeca translation rules)")
    print(f"Parameters:")
    print(f"  Temperature: [0.0, 0.1, 0.3, 0.5]")
    print(f"  Top-p: [0.5, 0.8, 0.9, 1.0]")
    print(f"  (No frequency/presence penalty)")
    print(f"\nTotal configs: {len(configs)}")
    print(
        f"Estimated runtime: ~{len(configs) * 0.5:.0f}-{len(configs) * 0.7:.0f} minutes"
    )
    print("=" * 80 + "\n")

    results = []

    for i, param_config in enumerate(configs, 1):
        config_name = get_config_name(param_config)
        exp_name = f"day4_detailed_rules_gpt51/{config_name}"

        print(f"\n{'#'*80}")
        print(f"CONFIG {i}/{len(configs)}: {config_name}")
        print(f"{'#'*80}")

        full_config = {
            "experiment_name": exp_name,
            "model": model_name,
            "system_prompt": DETAILED_RULES,
            "max_retries": 5,
            "description": f"Day4: {prompt_name} GPT-5.1 - {config_name}",
            **param_config,
        }

        model = BaseModelV2(full_config)
        result = model.run_on_directory("data/input_akka_codes")
        results.append(result)

    # Summary
    print("\n\n" + "=" * 80)
    print("DAY 4 COMPLETE!")
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
    print(f"Day 1 (MINIMAL, GPT-4o): 0/32 succeeded")
    print(f"Day 2 (BASIC, GPT-4o): 0/32 succeeded")
    print(f"Day 3 (BASIC, GPT-5.1): ?/16 succeeded")
    print(f"Day 4 (DETAILED_RULES, GPT-5.1): {successful}/{len(configs)} succeeded")
    print("=" * 80)
    print(f"Results location: experiments/results/day4_detailed_rules_gpt51/")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
