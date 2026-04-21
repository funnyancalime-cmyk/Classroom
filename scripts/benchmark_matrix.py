#!/usr/bin/env python3
"""
Profilace smart režimu napříč více scénáři tříd.

Příklad:
  python scripts/benchmark_matrix.py --seed 42 --repeats 3
"""

from __future__ import annotations

import argparse
import csv
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.benchmark_smart import run_once


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", type=str, default=None, help="Volitelná cesta pro uložení CSV výstupu.")
    args = parser.parse_args()

    random.seed(args.seed)

    scenarios = [
        (4, 5, 16),
        (5, 6, 26),
        (6, 6, 30),
    ]

    header = ["rows", "cols", "students", "recommended_iter", "time_avg_s", "time_min_s", "time_max_s", "score_avg"]
    print(",".join(header))
    rows_out = []
    for rows, cols, students in scenarios:
        timings = []
        scores = []
        recommended = None
        for _ in range(args.repeats):
            elapsed, score, _, recommended = run_once(rows, cols, students)
            timings.append(elapsed)
            scores.append(score)
        row = [
            rows,
            cols,
            students,
            recommended,
            f"{statistics.mean(timings):.4f}",
            f"{min(timings):.4f}",
            f"{max(timings):.4f}",
            f"{statistics.mean(scores):.3f}",
        ]
        rows_out.append(row)
        print(",".join(str(v) for v in row))

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            writer.writerows(rows_out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
