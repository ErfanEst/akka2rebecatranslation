# experiments/parameter_grid.py
"""
Shared parameter grid for experiments.
16-config grid: 4 temps × 4 top_p (no frequency/presence penalty for GPT-5.1-Codex)

Based on code generation research:
- Temperature: low range for code precision [0.0-0.5]
- Top-p: nucleus sampling exploration [0.5-1.0]
- Frequency/presence penalty: REMOVED (unsupported by GPT-5.1-Codex models)
"""
from typing import List, Dict


# Core parameter ranges (16 total combinations)
TEMPERATURES = [0.0, 0.1, 0.3, 0.5]  # 4 values
TOP_P_VALUES = [0.5, 0.8, 0.9, 1.0]  # 4 values

# Total: 4 × 4 = 16 configs


def get_all_configs() -> List[Dict[str, float]]:
    """Generate all 16 parameter configurations (no frequency/presence penalty)"""
    configs = []
    for temp in TEMPERATURES:
        for top_p in TOP_P_VALUES:
            configs.append({"temperature": temp, "top_p": top_p})

    return configs


def get_config_name(config: Dict[str, float]) -> str:
    """Generate standardized config name (no freq penalty)"""
    temp_str = str(config["temperature"]).replace(".", "_")
    topp_str = str(config["top_p"]).replace(".", "_")
    return f"temp{temp_str}_topp{topp_str}"


def print_grid_info():
    """Print parameter grid information."""
    configs = get_all_configs()
    print(f"Parameter Grid:")
    print(f"  Temperatures: {TEMPERATURES}")
    print(f"  Top-p: {TOP_P_VALUES}")
    print(f"  (No frequency/presence penalty - unsupported by GPT-5.1-Codex)")
    print(f"\nTotal configurations: {len(configs)}")
    return configs


if __name__ == "__main__":
    print_grid_info()
