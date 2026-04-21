import unittest
from unittest.mock import patch

import app
from app import Seat, export_arrangement_pdf


class PdfGuardTests(unittest.TestCase):
    def test_export_raises_clear_error_when_reportlab_missing(self):
        with patch.object(app, "REPORTLAB_AVAILABLE", False):
            with self.assertRaises(RuntimeError) as ctx:
                export_arrangement_pdf(
                    output_path="out.pdf",
                    classroom_name="9.A",
                    mode="manual",
                    score=0.0,
                    seats=[Seat(id=1, row_index=0, col_index=0, label="A1", is_active=True)],
                    assignments={1: None},
                    student_names_by_id={},
                    analysis=None,
                )
        self.assertIn("reportlab", str(ctx.exception).lower())


if __name__ == "__main__":
    unittest.main()
