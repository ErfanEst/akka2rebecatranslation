# experiments/day2_vanilla_grid.py
"""
Day 2: Full Factorial - Vanilla LLM Test
Tests all combinations of temperature × prompt style WITHOUT Rebeca handbook.

Grid: 5 temperatures × 7 prompt styles = 35 experiments
Runtime: ~6-7 hours
"""
from experiments.base_model_v2 import BaseModelV2
from prompts.system_prompts import (
    MINIMAL,
    BASIC,
    DETAILED_RULES,
    VERSION_1_ADVANCED,
    VERSION_2_ADVANCED,
    FEW_SHOT_1,
    FEW_SHOT_2,
    FEW_SHOT_3,
)

# Temperature levels to test
TEMPS = [0.0, 0.1, 0.3, 0.5, 0.7]

# System prompt variations
SYSTEM_PROMPTS = [
    ("minimal", MINIMAL),
    ("basic", BASIC),
    ("detailed", DETAILED_RULES),
    ("version1_advanced", VERSION_1_ADVANCED),
    ("version2_advanced", VERSION_2_ADVANCED),
    ("fewshot1", FEW_SHOT_1),
    ("fewshot2", FEW_SHOT_2),
    ("fewshot3", FEW_SHOT_3),
]


def main():
    total_experiments = len(TEMPS) * len(SYSTEM_PROMPTS)
    print("\n" + "=" * 80)
    print("DAY 2: FULL FACTORIAL GRID - VANILLA")
    print("=" * 80)
    print(f"Temperatures: {TEMPS}")
    print(f"Prompt styles: {len(SYSTEM_PROMPTS)}")
    print(f"Total experiments: {total_experiments}")
    print(
        f"Estimated runtime: ~{total_experiments * 5} minutes (~{total_experiments * 5 / 60:.1f} hours)"
    )
    print("=" * 80 + "\n")

    experiment_count = 0

    for temp in TEMPS:
        for name, prompt in SYSTEM_PROMPTS:
            experiment_count += 1

            exp_name = f"day2_vanilla/temp_{str(temp).replace('.','_')}_{name}"

            print("\n" + "=" * 80)
            print(f"EXPERIMENT {experiment_count}/{total_experiments}: {exp_name}")
            print("=" * 80 + "\n")

            config = {
                "experiment_name": exp_name,
                "model": "gpt-4",
                "temperature": temp,
                "max_retries": 5,
                "system_prompt": prompt,
                "description": f"Vanilla: temp={temp}, prompt={name}",
            }

            model = BaseModelV2(config)
            model.run_on_directory("data/input_akka_codes")

    print("\n" + "=" * 80)
    print("DAY 2 GRID COMPLETE!")
    print("=" * 80)
    print(f"Total experiments completed: {experiment_count}")
    print(f"Results location: experiments/results/day2_vanilla/")
    print("\nNext steps:")
    print("1. Run comparison analysis:")
    print("   python -m experiments.analyze_day2")
    print("2. View individual results:")
    print("   ls experiments/results/day2_vanilla/")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
