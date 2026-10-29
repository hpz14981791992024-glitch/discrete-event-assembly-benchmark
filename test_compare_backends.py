"""Checks for missing, duplicate, and differing paired episode records."""

import csv
import tempfile
import unittest
from pathlib import Path

from compare_backends import FILES, compare


def write_rows(directory, rows):
    directory.mkdir(exist_ok=True)
    for name in FILES:
        with (directory / name).open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["scenario_id", "method", "success", "planning_cpu_ms", "verification_cpu_ms"])
            writer.writeheader()
            writer.writerows(rows)


class ComparisonTests(unittest.TestCase):
    def test_timing_is_excluded_but_outcome_differences_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            ref, candidate = Path(temp) / "ref", Path(temp) / "candidate"
            row = {"scenario_id": "1", "method": "vcrisp", "success": "True", "planning_cpu_ms": "1", "verification_cpu_ms": "2"}
            write_rows(ref, [row])
            write_rows(candidate, [{**row, "planning_cpu_ms": "99"}])
            self.assertTrue(compare(ref, candidate)["passed"])
            write_rows(candidate, [{**row, "success": "False"}])
            self.assertFalse(compare(ref, candidate)["passed"])

    def test_missing_and_duplicate_records_are_detected(self):
        with tempfile.TemporaryDirectory() as temp:
            ref, candidate = Path(temp) / "ref", Path(temp) / "candidate"
            row = {"scenario_id": "1", "method": "vcrisp", "success": "True", "planning_cpu_ms": "1", "verification_cpu_ms": "2"}
            write_rows(ref, [row])
            write_rows(candidate, [])
            self.assertFalse(compare(ref, candidate)["passed"])
            write_rows(candidate, [row, row])
            with self.assertRaisesRegex(ValueError, "duplicate record"):
                compare(ref, candidate)


if __name__ == "__main__":
    unittest.main()
