"""Compare non-timing episode fields between two recorded benchmark runs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


FILES = ("episodes_main.csv", "episodes_component_ablation.csv", "episodes_sensitivity.csv")
IGNORED_FIELDS = {"planning_cpu_ms", "verification_cpu_ms"}


def read_records(path: Path) -> tuple[dict, dict]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        if not fields or len(fields) != len(set(fields)):
            raise ValueError(f"missing or duplicate columns: {path}")
        records = {}
        for row in reader:
            key = (row["scenario_id"], row["method"])
            if key in records:
                raise ValueError(f"duplicate record {key} in {path}")
            records[key] = row
    return records, set(fields)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(reference: Path, candidate: Path) -> dict:
    report = {"ignored_fields": sorted(IGNORED_FIELDS), "files": {}, "passed": True}
    for filename in FILES:
        left_path, right_path = reference / filename, candidate / filename
        left, left_fields = read_records(left_path)
        right, right_fields = read_records(right_path)
        if left_fields != right_fields:
            raise ValueError(f"column mismatch for {filename}")
        left_only, right_only = left.keys() - right.keys(), right.keys() - left.keys()
        common = left.keys() & right.keys()
        compared_fields = sorted(left_fields - IGNORED_FIELDS)
        mismatches = [
            key for key in common
            if any(left[key][field] != right[key][field] for field in compared_fields)
        ]
        entry = {
            "reference_sha256": digest(left_path),
            "candidate_sha256": digest(right_path),
            "reference_records": len(left),
            "candidate_records": len(right),
            "matched_keys": len(common),
            "reference_only": len(left_only),
            "candidate_only": len(right_only),
            "mismatched_records": len(mismatches),
            "mismatch_examples": [list(key) for key in sorted(mismatches)[:5]],
        }
        report["files"][filename] = entry
        report["passed"] &= not (left_only or right_only or mismatches)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compare(args.reference, args.candidate)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    if not report["passed"]:
        raise SystemExit("backend comparison failed")


if __name__ == "__main__":
    main()
