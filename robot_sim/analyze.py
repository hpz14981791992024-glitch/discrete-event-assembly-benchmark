"""Summarize the matched MuJoCo reaching experiment."""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import numpy as np


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="write the summary to a new JSON file")
    args = parser.parse_args()
    with (args.results / "episodes.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    pairs = {}
    for row in rows:
        scenario = int(row["scenario"])
        group = pairs.setdefault(scenario, {})
        if row["policy"] in group:
            raise ValueError(f"duplicate scenario and policy: {scenario}, {row['policy']}")
        group[row["policy"]] = row
    for scenario, pair in pairs.items():
        if set(pair) != {"direct", "checked_waypoints"}:
            raise ValueError(f"incomplete scenario: {scenario}")
        for key in ("target_x", "target_y", "obstacle_x", "obstacle_y"):
            if pair["direct"][key] != pair["checked_waypoints"][key]:
                raise ValueError(f"mismatched scene for scenario {scenario}: {key}")
    if not pairs:
        raise ValueError("no scenarios")
    ordered = [pairs[key] for key in sorted(pairs)]
    differences = np.array([int(p["checked_waypoints"]["success"] == "True") -
                            int(p["direct"]["success"] == "True") for p in ordered])
    rng = np.random.default_rng(20261029)
    samples = rng.choice(differences, size=(2000, len(differences)), replace=True).mean(axis=1)
    low, high = np.quantile(samples, [0.025, 0.975])
    result = {"paired_scenarios": len(pairs), "bootstrap_resamples": 2000,
              "bootstrap_seed": 20261029,
              "checked_minus_direct_success_rate": float(differences.mean()),
              "ci95": [float(low), float(high)], "policies": {}}
    for policy in ("direct", "checked_waypoints"):
        group = [p[policy] for p in ordered]
        result["policies"][policy] = {
            "statuses": dict(Counter(row["status"] for row in group)),
            "successes": sum(row["success"] == "True" for row in group),
            "contact_episodes": sum(int(row["contact_steps"]) > 0 for row in group),
            "median_planning_elapsed_ms": float(np.median([float(row["planning_elapsed_ms"]) for row in group])),
        }
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(output)
    print(output, end="")


if __name__ == "__main__":
    main()
