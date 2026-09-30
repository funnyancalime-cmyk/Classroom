import tempfile
import unittest
from pathlib import Path

from app import Database


class StudentInsightsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_path = Path(self.tmp.name)
        self.tmp.close()
        self.db = Database(self.tmp_path)

        self.classroom_id = self.db.create_classroom("9.A", 1, 2)
        self.db.add_student(self.classroom_id, "Alice")
        self.db.add_student(self.classroom_id, "Bob")

        self.students = self.db.list_students(self.classroom_id)
        self.seats = self.db.list_seats(self.classroom_id)
        self.alice_id = next(s.id for s in self.students if s.display_name == "Alice")
        self.bob_id = next(s.id for s in self.students if s.display_name == "Bob")

    def tearDown(self):
        try:
            self.db.close()
        finally:
            self.tmp_path.unlink(missing_ok=True)

    def test_pair_insights_include_other_student_and_sort_by_score(self):
        self.db._upsert_avg("pair_scores", (self.classroom_id, min(self.alice_id, self.bob_id), max(self.alice_id, self.bob_id), "side"), 1.0)
        self.db._upsert_avg("pair_scores", (self.classroom_id, min(self.alice_id, self.bob_id), max(self.alice_id, self.bob_id), "front_back"), -0.5)

        rows = self.db.get_student_pair_insights(self.classroom_id, self.alice_id, limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["other_student_id"], self.bob_id)
        self.assertGreaterEqual(rows[0]["avg_score"], rows[1]["avg_score"])

    def test_seat_insights_return_labels_and_scores(self):
        seat_a, seat_b = self.seats[0], self.seats[1]
        self.db._upsert_avg("seat_scores", (self.classroom_id, self.alice_id, seat_a.id), -1.0)
        self.db._upsert_avg("seat_scores", (self.classroom_id, self.alice_id, seat_b.id), 1.5)

        rows = self.db.get_student_seat_insights(self.classroom_id, self.alice_id, limit=10)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["seat_label"], seat_b.label)
        self.assertEqual(rows[1]["seat_label"], seat_a.label)
        self.assertGreater(rows[0]["avg_score"], rows[1]["avg_score"])


if __name__ == "__main__":
    unittest.main()
