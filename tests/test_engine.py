import unittest

from app import Seat, SeatingEngine, Student


class SeatingEngineTests(unittest.TestCase):
    def setUp(self):
        # 2x2 grid:
        # A B
        # C D
        self.seats = [
            Seat(id=1, row_index=0, col_index=0, label="A", is_active=True),
            Seat(id=2, row_index=0, col_index=1, label="B", is_active=True),
            Seat(id=3, row_index=1, col_index=0, label="C", is_active=True),
            Seat(id=4, row_index=1, col_index=1, label="D", is_active=True),
        ]
        self.students = [
            Student(id=10, display_name="Alice", is_active=True),
            Student(id=11, display_name="Bob", is_active=True),
            Student(id=12, display_name="Cyril", is_active=True),
        ]

    def test_random_arrangement_respects_locks_and_uniqueness(self):
        engine = SeatingEngine(
            seats=self.seats,
            students=self.students,
            pair_scores={},
            seat_scores={},
            locked={1: 10},
        )

        arrangement = engine.random_arrangement()
        self.assertEqual(arrangement[1], 10)

        assigned_students = [sid for sid in arrangement.values() if sid is not None]
        self.assertEqual(len(assigned_students), len(set(assigned_students)))

    def test_analyze_arrangement_counts_pair_only_once(self):
        # Seat term for student 10 on seat 1:
        # avg=2.0, obs=3 => 2.0 * (1 + 0.3) = 2.6
        seat_scores = {(10, 1): (2.0, 3)}
        # Pair term for (10, 11, side):
        # avg=1.0, obs=2 => 1.0 * (1 + 0.3) = 1.3
        pair_scores = {(10, 11, "side"): (1.0, 2)}
        engine = SeatingEngine(
            seats=self.seats,
            students=self.students,
            pair_scores=pair_scores,
            seat_scores=seat_scores,
            locked={},
        )

        # Neighbors on top row are side-neighbors (1 <-> 2)
        arrangement = {1: 10, 2: 11, 3: None, 4: None}
        analysis = engine.analyze_arrangement(arrangement)

        self.assertAlmostEqual(analysis["seat_total"], 2.6, places=5)
        self.assertAlmostEqual(analysis["pair_total"], 1.3, places=5)
        self.assertAlmostEqual(analysis["total"], 3.9, places=5)
        self.assertEqual(len(analysis["pair_terms"]), 1)

    def test_best_of_random_search_returns_valid_mapping(self):
        engine = SeatingEngine(
            seats=self.seats,
            students=self.students,
            pair_scores={},
            seat_scores={},
            locked={2: 11},
        )
        arrangement, score = engine.best_of_random_search(iterations=20)

        self.assertIsInstance(arrangement, dict)
        self.assertIn(2, arrangement)
        self.assertEqual(arrangement[2], 11)
        self.assertIsInstance(score, float)

    def test_recommend_iterations_is_bounded_and_scales(self):
        self.assertEqual(SeatingEngine.recommend_iterations(0, 0), 600)
        self.assertGreater(SeatingEngine.recommend_iterations(10, 10), 600)
        self.assertEqual(SeatingEngine.recommend_iterations(100, 120), 5000)

    def test_improve_by_swaps_does_not_reduce_score_and_respects_locks(self):
        pair_scores = {(10, 11, "side"): (2.0, 3)}
        engine = SeatingEngine(
            seats=self.seats,
            students=self.students,
            pair_scores=pair_scores,
            seat_scores={},
            locked={1: 10},
        )
        # Base arrangement keeps locked seat 1 occupied by student 10.
        base = {1: 10, 2: 12, 3: 11, 4: None}
        base_score = engine.score_arrangement(base)
        improved, improved_score = engine.improve_by_swaps(base, base_score, rounds=2)

        self.assertEqual(improved[1], 10)
        self.assertGreaterEqual(improved_score, base_score)


if __name__ == "__main__":
    unittest.main()
