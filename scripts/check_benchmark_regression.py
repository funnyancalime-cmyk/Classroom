#!/usr/bin/env python3
"""
Kontrola benchmark výsledků proti jednoduchým prahům.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-csv", required=True)
    parser.add_argument("--thresholds", default="benchmarks/thresholds.json")
    parser.add_argument("--baseline-csv", default=None, help="Volitelný baseline CSV pro trend porovnání.")
    parser.add_argument(
        "--max-regression-pct",
        type=float,
        default=35.0,
        help="Max povolené zhoršení time_avg_s oproti baseline v procentech.",
    )
    args = parser.parse_args()

    thresholds = json.loads(Path(args.thresholds).read_text(encoding="utf-8"))
    scenario_limits = thresholds.get("scenarios", {})

    rows = list(csv.DictReader(Path(args.benchmark_csv).read_text(encoding="utf-8").splitlines()))
    if not rows:
        print("Benchmark regression check failed: CSV is empty.")
        return 1

    baseline_map = {}
    if args.baseline_csv:
        baseline_rows = list(csv.DictReader(Path(args.baseline_csv).read_text(encoding="utf-8").splitlines()))
        for row in baseline_rows:
            key = f"{row['rows']}x{row['cols']}x{row['students']}"
            baseline_map[key] = float(row["time_avg_s"])

    ok = True
    for row in rows:
        key = f"{row['rows']}x{row['cols']}x{row['students']}"
        limit = scenario_limits.get(key)
        if not limit:
            print(f"WARNING: missing threshold for scenario {key}, skipping.")
            continue

        time_avg = float(row["time_avg_s"])
        score_avg = float(row["score_avg"])
        if time_avg > float(limit["max_time_avg_s"]):
            print(f"FAIL: {key} time_avg_s={time_avg:.4f} exceeds {limit['max_time_avg_s']}")
            ok = False
        if score_avg < float(limit["min_score_avg"]):
            print(f"FAIL: {key} score_avg={score_avg:.4f} below {limit['min_score_avg']}")
            ok = False

        baseline_time = baseline_map.get(key)
        if baseline_time is not None:
            allowed = baseline_time * (1.0 + args.max_regression_pct / 100.0)
            if time_avg > allowed:
                print(
                    f"FAIL: {key} time_avg_s={time_avg:.4f} exceeds baseline tolerance "
                    f"{allowed:.4f} (baseline={baseline_time:.4f}, max_regression_pct={args.max_regression_pct})"
                )
                ok = False

    if ok:
        print("Benchmark regression check OK.")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
