# experiments/day1_baseline_test.py
"""
Day 1: Baseline vanilla LLM test.
Goal: Get simple_ping_pong working with at least 1 config.
Tests basic infrastructure and identifies baseline errors.
"""
from experiments.base_model_v2 import BaseModelV2
from prompts.system_prompts import MINIMAL, BASIC, DETAILED_RULES

# Test 3 baseline configs
configs = [
    {
        "experiment_name": "day1_baseline/minimal_temp0",
        "model": "gpt-4",
        "temperature": 0.0,
        "max_retries": 5,
        "system_prompt": MINIMAL,
        "description": "Baseline: Minimal prompt, temp=0.0",
    },
    {
        "experiment_name": "day1_baseline/basic_temp0",
        "model": "gpt-4",
        "temperature": 0.0,
        "max_retries": 5,
        "system_prompt": BASIC,
        "description": "Baseline: Basic prompt, temp=0.0",
    },
    {
        "experiment_name": "day1_baseline/detailed_temp05",
        "model": "gpt-4",
        "temperature": 0.5,
        "max_retries": 5,
        "system_prompt": DETAILED_RULES,
        "description": "Baseline: Detailed rules, temp=0.5",
    },
]

print("=" * 80)
print("DAY 1: BASELINE TEST")
print("Testing 3 configurations on simple_ping_pong.txt")
print("=" * 80)

results = []
for config in configs:
    print(f"\n\n{'#'*80}")
    print(f"CONFIG: {config['description']}")
    print(f"{'#'*80}\n")

    model = BaseModelV2(config)
    result = model.run_on_directory("data/input_akka_codes")
    results.append(result)

print("\n\n" + "=" * 80)
print("DAY 1 COMPLETE!")
print("=" * 80)
for i, config in enumerate(configs):
    r = results[i][0] if results[i] else None
    if r:
        status = "✓ SUCCESS" if r["success"] else "✗ FAILED"
        print(f"{status} | {config['description']}")
        if not r["success"]:
            last_error = (
                r["attempts"][-1]["error"][:100] if r["attempts"] else "Unknown"
            )
            print(f"  Last error: {last_error}...")

print("\n" + "=" * 80)
print("NEXT STEPS:")
print("=" * 80)
print("1. Check prompt logs:")
print("   ls experiments/results/day1_baseline/*/prompt_logs/")
print("\n2. View specific attempt prompts:")
print(
    "   cat experiments/results/day1_baseline/minimal_temp0/prompt_logs/simple_ping_pong_attempt_1_prompts.txt"
)
print("\n3. Compare errors across configs:")
print("   cat validation_output/day1_baseline/*/simple_ping_pong_attempt_1.txt")
print("\n4. Analyze error patterns and prepare Day 2 full factorial grid!")
print("=" * 80)
