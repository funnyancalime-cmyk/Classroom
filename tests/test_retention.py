import tempfile
import unittest
from pathlib import Path

from app import Database


class RetentionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp_path = Path(self.tmp.name)
        self.tmp.close()
        self.db = Database(self.tmp_path)
        self.classroom_id = self.db.create_classroom("9.A", 1, 1)

    def tearDown(self):
        try:
            self.db.close()
        finally:
            self.tmp_path.unlink(missing_ok=True)

    def test_delete_arrangements_older_than(self):
        with self.db.conn:
            self.db.conn.execute(
                "INSERT INTO arrangements(classroom_id, created_at, mode, overall_rating, notes_json) VALUES (?, ?, ?, ?, ?)",
                (self.classroom_id, "2024-01-01T10:00:00", "manual", None, "{}"),
            )
            self.db.conn.execute(
                "INSERT INTO arrangements(classroom_id, created_at, mode, overall_rating, notes_json) VALUES (?, ?, ?, ?, ?)",
                (self.classroom_id, "2026-01-01T10:00:00", "manual", None, "{}"),
            )

        deleted = self.db.delete_arrangements_older_than("2025-01-01T00:00:00")
        self.assertEqual(deleted, 1)
        rows = self.db.conn.execute("SELECT COUNT(*) AS cnt FROM arrangements").fetchone()
        self.assertEqual(int(rows["cnt"]), 1)


if __name__ == "__main__":
    unittest.main()
