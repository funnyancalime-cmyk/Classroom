#!/usr/bin/env python3
"""
Jednoduchý lokální benchmark režimu smart.

Použití:
  python scripts/benchmark_smart.py --rows 5 --cols 6 --students 26 --iterations 5
"""

from __future__ import annotations

import argparse
import random
import statistics
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import Seat, SeatingEngine, Student


def build_synthetic_case(rows: int, cols: int, student_count: int):
    seats: list[Seat] = []
    sid = 1
    for r in range(rows):
        for c in range(cols):
            seats.append(Seat(id=sid, row_index=r, col_index=c, label=f"{chr(65 + r)}{c + 1}", is_active=True))
            sid += 1

    students = [Student(id=1000 + i, display_name=f"Student {i+1}", is_active=True) for i in range(student_count)]

    # Lehce syntetická historická data, aby smart mód měl co optimalizovat.
    pair_scores = {}
    seat_scores = {}
    for s in students:
        for seat in random.sample(seats, k=min(5, len(seats))):
            seat_scores[(s.id, seat.id)] = (random.uniform(-1.2, 1.5), random.randint(1, 8))
    for _ in range(student_count * 3):
        a, b = sorted(random.sample([s.id for s in students], 2))
        proximity = random.choice(["side", "front_back", "diagonal"])
        pair_scores[(a, b, proximity)] = (random.uniform(-1.0, 1.4), random.randint(1, 8))

    return seats, students, pair_scores, seat_scores


def run_once(rows: int, cols: int, student_count: int):
    seats, students, pair_scores, seat_scores = build_synthetic_case(rows, cols, student_count)
    engine = SeatingEngine(seats=seats, students=students, pair_scores=pair_scores, seat_scores=seat_scores, locked={})
    search_iterations = engine.recommend_iterations(student_count=len(students), active_seat_count=len(seats))

    t0 = time.perf_counter()
    arrangement, score = engine.best_of_random_search(iterations=search_iterations)
    elapsed = time.perf_counter() - t0
    assigned = sum(1 for v in arrangement.values() if v is not None)
    return elapsed, score, assigned, search_iterations


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=5)
    parser.add_argument("--cols", type=int, default=6)
    parser.add_argument("--students", type=int, default=26)
    parser.add_argument("--iterations", type=int, default=5, help="Počet opakování benchmarku.")
    parser.add_argument("--seed", type=int, default=None, help="Volitelný seed pro reprodukovatelnost.")
    args = parser.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    timings = []
    scores = []
    recommended = None
    assigned = None

    for _ in range(args.iterations):
        elapsed, score, assigned, recommended = run_once(args.rows, args.cols, args.students)
        timings.append(elapsed)
        scores.append(score)

    print("=== SMART BENCHMARK ===")
    print(f"Třída: {args.rows}x{args.cols}, studenti: {args.students}")
    print(f"Doporučené iterace: {recommended}")
    print(f"Obsazených míst: {assigned}")
    print(f"Opakování: {args.iterations}")
    print(f"Čas avg: {statistics.mean(timings):.4f}s | min: {min(timings):.4f}s | max: {max(timings):.4f}s")
    print(f"Skóre avg: {statistics.mean(scores):.3f}")


if __name__ == "__main__":
    main()
