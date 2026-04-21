import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class BenchmarkRegressionScriptTests(unittest.TestCase):
    def test_regression_check_passes_for_good_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "bench.csv"
            json_path = tmp_path / "thresholds.json"

            csv_path.write_text(
                "rows,cols,students,recommended_iter,time_avg_s,time_min_s,time_max_s,score_avg\n"
                "4,5,16,2800,0.30,0.30,0.30,10.0\n",
                encoding="utf-8",
            )
            json_path.write_text(
                json.dumps({"scenarios": {"4x5x16": {"max_time_avg_s": 1.0, "min_score_avg": 0.0}}}),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/check_benchmark_regression.py",
                    "--benchmark-csv",
                    str(csv_path),
                    "--thresholds",
                    str(json_path),
                ],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, msg=result.stdout + result.stderr)

    def test_regression_check_fails_when_over_baseline_tolerance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            csv_path = tmp_path / "bench.csv"
            json_path = tmp_path / "thresholds.json"
            baseline_path = tmp_path / "baseline.csv"

            csv_path.write_text(
                "rows,cols,students,recommended_iter,time_avg_s,time_min_s,time_max_s,score_avg\n"
                "4,5,16,2800,1.00,1.00,1.00,10.0\n",
                encoding="utf-8",
            )
            baseline_path.write_text(
                "rows,cols,students,recommended_iter,time_avg_s,time_min_s,time_max_s,score_avg\n"
                "4,5,16,2800,0.50,0.50,0.50,10.0\n",
                encoding="utf-8",
            )
            json_path.write_text(
                json.dumps({"scenarios": {"4x5x16": {"max_time_avg_s": 2.0, "min_score_avg": 0.0}}}),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/check_benchmark_regression.py",
                    "--benchmark-csv",
                    str(csv_path),
                    "--thresholds",
                    str(json_path),
                    "--baseline-csv",
                    str(baseline_path),
                    "--max-regression-pct",
                    "20",
                ],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
