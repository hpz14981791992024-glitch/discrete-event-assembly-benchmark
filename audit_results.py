"""Integrity audit for the locally generated synthetic benchmark logs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from simulator import ABLATION_METHODS, METHODS


def bool_value(value: str) -> bool:
    return value.lower() in {"true", "1"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit_pairing(path: Path, expected_methods: tuple[str, ...] = METHODS) -> dict:
    """Validate one result file has exactly one row per method and scenario."""

    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    by_scenario = defaultdict(list)
    pair_counts = Counter()
    for row in rows:
        scenario_id = row["scenario_id"]
        method = row["method"]
        by_scenario[scenario_id].append(method)
        pair_counts[(scenario_id, method)] += 1

    expected_method_set = set(expected_methods)
    incomplete = {
        scenario_id: sorted(set(methods) ^ expected_method_set)
        for scenario_id, methods in by_scenario.items()
        if set(methods) != expected_method_set or len(methods) != len(expected_methods)
    }
    duplicates = [
        {"scenario_id": scenario_id, "method": method, "count": count}
        for (scenario_id, method), count in pair_counts.items()
        if count != 1
    ]
    return {
        "source": str(path),
        "record_count": len(rows),
        "scenario_count": len(by_scenario),
        "expected_methods": list(expected_methods),
        "incomplete_scenarios": incomplete,
        "duplicate_method_scenario_records": duplicates,
        "audit_passed": not incomplete and not duplicates,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args()

    main_path = args.results_dir / "episodes_main.csv"
    main_report = audit_pairing(main_path)
    with main_path.open(newline="", encoding="utf-8") as handle:
        main_rows = list(csv.DictReader(handle))
    vcrisp_rows = [row for row in main_rows if row["method"] == "vcrisp"]
    main_report["vcrisp"] = {
        "episodes": len(vcrisp_rows),
        "successes": sum(bool_value(row["success"]) for row in vcrisp_rows),
        "modeled_constraint_rejections": sum(
            int(row["modeled_constraint_rejections"]) for row in vcrisp_rows
        ),
    }
    sensitivity_path = args.results_dir / "episodes_sensitivity.csv"
    sensitivity_report = audit_pairing(sensitivity_path) if sensitivity_path.exists() else None
    ablation_path = args.results_dir / "episodes_component_ablation.csv"
    ablation_report = (
        audit_pairing(ablation_path, expected_methods=ABLATION_METHODS)
        if ablation_path.exists()
        else None
    )
    manifest_path = args.results_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hash_mismatches = []
    for source_name, expected_hash in manifest.get("source_sha256", {}).items():
        source_path = Path(source_name)
        observed_hash = sha256(source_path) if source_path.exists() else None
        if observed_hash != expected_hash:
            hash_mismatches.append(
                {
                    "source": source_name,
                    "expected_sha256": expected_hash,
                    "observed_sha256": observed_hash,
                }
            )
    report = {
        "main": main_report,
        "sensitivity": sensitivity_report,
        "component_ablation": ablation_report,
        "source_hash_mismatches": hash_mismatches,
        "audit_passed": main_report["audit_passed"]
        and (sensitivity_report is None or sensitivity_report["audit_passed"])
        and (ablation_report is None or ablation_report["audit_passed"]),
        "source_hashes_match_manifest": not hash_mismatches,
    }
    report["audit_passed"] = report["audit_passed"] and report["source_hashes_match_manifest"]
    output_path = args.results_dir / "analysis" / "integrity_audit.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if not report["audit_passed"]:
        raise SystemExit("integrity audit failed")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
