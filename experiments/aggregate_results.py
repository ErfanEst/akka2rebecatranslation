# experiments/aggregate_results.py
import os
import json
import glob


def aggregate_phase(phase_name):
    base_path = f"experiments/results/{phase_name}"

    if not os.path.exists(base_path):
        print(f"Skipping {phase_name} (path not found)")
        return

    print(f"\nProcessing Phase: {phase_name}")
    print("=" * 60)

    # List all prompt directories (e.g., minimal, basic, v1_advanced...)
    prompt_dirs = [
        d for d in os.listdir(base_path) if os.path.isdir(os.path.join(base_path, d))
    ]

    for prompt in prompt_dirs:
        prompt_path = os.path.join(base_path, prompt)
        print(f"  > Aggregating prompt: {prompt}")

        aggregated_data = []

        # Walk through config directories (temp0_0_topp0_5, etc.)
        config_dirs = [
            d
            for d in os.listdir(prompt_path)
            if os.path.isdir(os.path.join(prompt_path, d))
        ]

        for config in config_dirs:
            config_path = os.path.join(prompt_path, config)

            # Find all JSON result files (one per source code file translated)
            json_files = glob.glob(os.path.join(config_path, "*_result.json"))

            for jf in json_files:
                try:
                    with open(jf, "r") as f:
                        data = json.load(f)
                        # Inject metadata
                        data["config_name"] = config
                        data["prompt_name"] = prompt
                        data["phase"] = phase_name
                        aggregated_data.append(data)
                except Exception as e:
                    print(f"    ! Error reading {jf}: {e}")

        # Save aggregated file
        output_file = os.path.join(prompt_path, "aggregated_results.json")
        with open(output_file, "w") as out:
            json.dump(aggregated_data, out, indent=2)

        print(f"    ✓ Saved {len(aggregated_data)} records to: {output_file}")


def main():
    phases = ["phase3_intermediate"]
    for phase in phases:
        aggregate_phase(phase)


if __name__ == "__main__":
    main()
