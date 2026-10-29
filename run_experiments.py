"""Run the synthetic discrete-event assembly benchmark.

Usage:
    python run_experiments.py --output-dir results
"""

from __future__ import annotations

import argparse
import csv
import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

from simulator import (
    ABLATION_METHODS,
    MAX_PREDISPATCH_REPAIRS,
    MAX_RUNTIME_RECOVERY_ATTEMPTS,
    METHODS,
    build_scenarios,
    run_benchmark,
)


def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def installed_package_version(package: str) -> str | None:
    try:
        return version(package)
    except PackageNotFoundError:
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("results"))
    parser.add_argument("--seeds", type=int, default=20)
    parser.add_argument("--episodes-per-stratum", type=int, default=10)
    parser.add_argument("--semantic-error-rate", type=float, default=0.20)
    parser.add_argument("--sensitivity-seeds", type=int, default=10)
    parser.add_argument("--skip-sensitivity", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    main_scenarios = build_scenarios(
        seeds=range(1, args.seeds + 1),
        episodes_per_stratum=args.episodes_per_stratum,
        semantic_error_rate=args.semantic_error_rate,
        include_disturbances=True,
    )
    main_records = run_benchmark(main_scenarios)
    write_csv(output_dir / "episodes_main.csv", main_records)
    ablation_records = run_benchmark(main_scenarios, methods=ABLATION_METHODS)
    write_csv(output_dir / "episodes_component_ablation.csv", ablation_records)

    manifest = {
        "benchmark": "synthetic discrete-event assembly benchmark",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "methods": list(METHODS),
        "runtime": {
            "python_version": sys.version,
            "platform": platform.platform(),
            "machine": platform.machine(),
            "analysis_dependencies": {
                "numpy": installed_package_version("numpy"),
                "matplotlib": installed_package_version("matplotlib"),
            },
        },
        "source_sha256": {
            source.as_posix(): sha256(source)
            for source in (
                Path("simulator.py"),
                Path("run_experiments.py"),
                Path("analyze_results.py"),
                Path("audit_results.py"),
                Path("generate_qualitative_trace.py"),
                Path("test_simulator.py"),
                Path("figures/make_figure1_composite.py"),
                Path("figures/make_publication_figures.py"),
                Path("figures/audit_panel_alignment.py"),
                Path("make_release_manifest.py"),
            )
            if source.exists()
        },
        "main": {
            "evaluation_seeds": list(range(1, args.seeds + 1)),
            "episodes_per_stratum": args.episodes_per_stratum,
            "base_semantic_error_rate": args.semantic_error_rate,
            "candidate_profile_increment": 0.10,
            "disturbance_semantic_error_rate": args.semantic_error_rate,
            "max_predispatch_repairs": MAX_PREDISPATCH_REPAIRS,
            "max_runtime_recovery_attempts": MAX_RUNTIME_RECOVERY_ATTEMPTS,
            "scenario_count": len(main_scenarios),
            "record_count": len(main_records),
        },
        "component_ablation": {
            "scenario_count": len(main_scenarios),
            "record_count": len(ablation_records),
            "methods": list(ABLATION_METHODS),
            "initial_predispatch_check": {
                "disabled": ["structured_no_verify", "repair_only"],
                "enabled": ["checker_only", "vcrisp"],
            },
            "runtime_suffix_verification": {
                "disabled": ["structured_no_verify", "checker_only"],
                "enabled": ["repair_only", "vcrisp"],
            },
        },
        "scope": {
            "is_physical_robot_experiment": False,
            "uses_real_llm_or_vlm": False,
            "uses_geometric_tamp_or_collision_checker": False,
            "claim_boundary": (
                "Results evaluate an abstract policy architecture under declared "
                "synthetic constraints, disturbances, and candidate-plan errors. "
                "The pre-dispatch checker shares modeled semantics with the "
                "dispatch guard."
            ),
        },
    }

    if not args.skip_sensitivity:
        sensitivity_rows: List[Dict[str, object]] = []
        for rate_index, rate in enumerate((0.05, 0.10, 0.20, 0.30)):
            scenarios = build_scenarios(
                seeds=range(100 + rate_index * 20, 100 + rate_index * 20 + args.sensitivity_seeds),
                episodes_per_stratum=args.episodes_per_stratum,
                semantic_error_rate=rate,
                include_disturbances=False,
                candidate_profile_increment=0.0,
            )
            sensitivity_rows.extend(run_benchmark(scenarios))
        write_csv(output_dir / "episodes_sensitivity.csv", sensitivity_rows)
        manifest["sensitivity"] = {
            "rates": [0.05, 0.10, 0.20, 0.30],
            "evaluation_seeds_per_rate": args.sensitivity_seeds,
            "candidate_profile_increment": 0.0,
            "record_count": len(sensitivity_rows),
        }

    with (output_dir / "run_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)

    print(
        "main records:",
        len(main_records),
        "scenarios:",
        len(main_scenarios),
        "methods:",
        len(METHODS),
    )


if __name__ == "__main__":
    main()
