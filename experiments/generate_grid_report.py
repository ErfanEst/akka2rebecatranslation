#!/usr/bin/env python3
"""Regenerate grid_report.md from an existing grid_result.json."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.grid_markdown_report import write_grid_markdown_report  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("grid_root", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    report = write_grid_markdown_report(args.grid_root, output_path=args.output)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
