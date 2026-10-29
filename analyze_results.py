"""Aggregate benchmark logs, calculate paired bootstrap intervals, and plot figures.

The analysis intentionally reports simulation units, not physical seconds or
real-robot throughput. CPU timings are local machine measurements only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

import matplotlib
import numpy as np

# The benchmark is expected to run unattended on local and CI hosts.
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulator import METHODS


NUMERIC_COLUMNS = {
    "seed": int,
    "semantic_error_rate": float,
    "success": lambda value: int(value.lower() in {"true", "1"}),
    "human_intervention": int,
    "modeled_constraint_rejections": int,
    "predispatch_repair_triggers": int,
    "verified_suffix_repairs": int,
    "current_state_recipe_rebuilds": int,
    "recovery_attempts": int,
    "disturbance_detected": int,
    "detected_and_completed": lambda value: None if value == "" else int(value),
    "completion_after_detection": lambda value: None if value == "" else int(value),
    "virtual_makespan": float,
    "virtual_time_to_completion_after_detection": lambda value: None if value == "" else float(value),
    "fault_time": lambda value: None if value == "" else float(value),
    "planning_cpu_ms": float,
    "verification_cpu_ms": float,
    "planner_actions_emitted": int,
    "actions_dispatched": int,
}

DISPLAY_NAMES = {
    "rule_script": "Rule script",
    "classical_global": "Oracle-state symbolic",
    "semantic_direct": "Perturbed candidate direct",
    "structured_no_verify": "Structured no-verify",
    "vcrisp": "V-CRISP",
}


def read_csv(path: Path) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for key, converter in NUMERIC_COLUMNS.items():
                row[key] = converter(row[key])
            rows.append(row)
    return rows


def write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def safe_mean(values: Iterable[Optional[float]]) -> Optional[float]:
    collected = [value for value in values if value is not None]
    return mean(collected) if collected else None


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def paired_bootstrap_difference(
    rows: Sequence[Mapping[str, object]],
    method: str,
    baseline: str,
    metric: str,
    iterations: int = 2000,
    seed: int = 20261027,
) -> Tuple[Optional[float], Optional[float], Optional[float], int]:
    """Return mean paired difference and percentile CI against a baseline."""

    by_key: Dict[Tuple[str, str], Mapping[str, object]] = {
        (str(row["method"]), str(row["scenario_id"])): row for row in rows
    }
    paired: List[float] = []
    scenario_ids = sorted({str(row["scenario_id"]) for row in rows})
    for scenario_id in scenario_ids:
        a = by_key.get((method, scenario_id))
        b = by_key.get((baseline, scenario_id))
        if a is None or b is None:
            continue
        if metric == "successful_virtual_makespan":
            if not bool(a["success"]) or not bool(b["success"]):
                continue
            paired.append(float(a["virtual_makespan"]) - float(b["virtual_makespan"]))
        elif a[metric] is not None and b[metric] is not None:
            paired.append(float(a[metric]) - float(b[metric]))
    if not paired:
        return None, None, None, 0
    values = np.asarray(paired, dtype=float)
    rng = np.random.default_rng(seed + sum(map(ord, metric + method + baseline)))
    # Vectorized sampling preserves the paired-unit bootstrap while keeping the
    # full 2,000-resample protocol practical for the complete experiment.
    indices = rng.integers(0, len(values), size=(iterations, len(values)))
    boot = values[indices].mean(axis=1)
    return (
        float(values.mean()),
        float(np.quantile(boot, 0.025)),
        float(np.quantile(boot, 0.975)),
        len(paired),
    )


def aggregate_main(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    table_rows: List[Dict[str, object]] = []
    for method in METHODS:
        group = [row for row in rows if row["method"] == method]
        disturbance_group = [row for row in group if row["disturbance"] != "none"]
        action_count = sum(int(row["actions_dispatched"]) for row in group)
        rejection_attempts = sum(int(row["modeled_constraint_rejections"]) for row in group)
        table_rows.append(
            {
                "method": method,
                "episodes": len(group),
                "task_success_rate": mean(float(row["success"]) for row in group),
                "modeled_constraint_rejection_rate": rejection_attempts / action_count if action_count else 0.0,
                "predispatch_repair_triggers_per_episode": mean(
                    float(row["predispatch_repair_triggers"]) for row in group
                ),
                "simulated_escalation_rate": mean(float(row["human_intervention"]) for row in group),
                "mean_successful_virtual_makespan": safe_mean(
                    float(row["virtual_makespan"]) for row in group if bool(row["success"])
                ),
                "mean_planning_cpu_ms": safe_mean(float(row["planning_cpu_ms"]) for row in group),
                "mean_verification_cpu_ms": safe_mean(float(row["verification_cpu_ms"]) for row in group),
                "event_recorded_and_completed_rate": safe_mean(
                    row["detected_and_completed"] for row in disturbance_group
                ),
                "completion_after_event_recording_rate": safe_mean(
                    row["completion_after_detection"] for row in disturbance_group
                ),
                "mean_virtual_time_to_completion_after_event_recording": safe_mean(
                    row["virtual_time_to_completion_after_detection"] for row in disturbance_group
                ),
                "mean_verified_suffix_repairs": safe_mean(
                    float(row["verified_suffix_repairs"]) for row in group
                ),
                "mean_current_state_recipe_rebuilds": safe_mean(
                    float(row["current_state_recipe_rebuilds"]) for row in group
                ),
            }
        )
    return table_rows


def aggregate_by_disturbance(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    output: List[Dict[str, object]] = []
    for disturbance in sorted({str(row["disturbance"]) for row in rows if row["disturbance"] != "none"}):
        for method in METHODS:
            group = [
                row
                for row in rows
                if row["method"] == method and row["disturbance"] == disturbance
            ]
            if not group:
                continue
            output.append(
                {
                    "disturbance": disturbance,
                    "method": method,
                    "episodes": len(group),
                    "event_recording_rate": mean(float(row["disturbance_detected"]) for row in group),
                    "event_recorded_and_completed_rate": safe_mean(
                        row["detected_and_completed"] for row in group
                    ),
                    "completion_after_event_recording_rate": safe_mean(
                        row["completion_after_detection"] for row in group
                    ),
                    "mean_virtual_time_to_completion_after_event_recording": safe_mean(
                        row["virtual_time_to_completion_after_detection"] for row in group
                    ),
                    "simulated_escalation_rate": mean(float(row["human_intervention"]) for row in group),
                }
            )
    return output


def ablation_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    mapping = {
        "semantic_direct": "Perturbed candidate direct (no schema, no verifier, no recovery)",
        "structured_no_verify": "Structured no-verify (schema + current-state rebuild)",
        "classical_global": "Oracle-state symbolic (current-state rebuild)",
        "vcrisp": "V-CRISP (pre-dispatch verifier + verified suffix repair)",
    }
    main = {row["method"]: row for row in aggregate_main(rows)}
    result = []
    for method, name in mapping.items():
        row = main[method]
        result.append(
            {
                "configuration": name,
                "structured_output": int(method in {"structured_no_verify", "vcrisp"}),
                "pre_dispatch_verifier": int(method == "vcrisp"),
                "event_recorder": int(method in {"classical_global", "structured_no_verify", "vcrisp"}),
                "verified_suffix_repair": int(method == "vcrisp"),
                "task_success_rate": row["task_success_rate"],
                "modeled_constraint_rejection_rate": row["modeled_constraint_rejection_rate"],
                "event_recorded_and_completed_rate": row["event_recorded_and_completed_rate"],
                "completion_after_event_recording_rate": row[
                    "completion_after_event_recording_rate"
                ],
                "mean_successful_virtual_makespan": row["mean_successful_virtual_makespan"],
            }
        )
    return result


def sensitivity_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    output = []
    for rate in sorted({float(row["semantic_error_rate"]) for row in rows}):
        for method in METHODS:
            group = [
                row
                for row in rows
                if float(row["semantic_error_rate"]) == rate and row["method"] == method
            ]
            if not group:
                continue
            output.append(
                {
                    "semantic_error_rate": rate,
                    "method": method,
                    "episodes": len(group),
                    "task_success_rate": mean(float(row["success"]) for row in group),
                    "simulated_escalation_rate": mean(float(row["human_intervention"]) for row in group),
                }
            )
    return output


def runtime_rows(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    """Report local CPU costs by recipe complexity, not physical control latency."""

    output: List[Dict[str, object]] = []
    recipe_steps = {"basic": 6, "standard": 8, "extended": 10}
    for complexity in ("basic", "standard", "extended"):
        for method in METHODS:
            group = [
                row
                for row in rows
                if row["complexity"] == complexity and row["method"] == method
            ]
            if not group:
                continue
            total_cpu = [
                float(row["planning_cpu_ms"]) + float(row["verification_cpu_ms"])
                for row in group
            ]
            output.append(
                {
                    "complexity": complexity,
                    "nominal_recipe_steps": recipe_steps[complexity],
                    "method": method,
                    "episodes": len(group),
                    "mean_planning_cpu_ms": safe_mean(float(row["planning_cpu_ms"]) for row in group),
                    "mean_verification_cpu_ms": safe_mean(float(row["verification_cpu_ms"]) for row in group),
                    "p95_total_decision_cpu_ms": percentile(total_cpu, 0.95),
                    "mean_successful_virtual_makespan": safe_mean(
                        float(row["virtual_makespan"]) for row in group if bool(row["success"])
                    ),
                    "timeout_rate": 0.0,
                }
            )
    return output


def paired_comparisons(rows: Sequence[Mapping[str, object]]) -> List[Dict[str, object]]:
    output: List[Dict[str, object]] = []
    for subset_name, subset in (
        ("all", list(rows)),
        ("disturbance", [row for row in rows if row["disturbance"] != "none"]),
    ):
        for metric in (
            "success",
            "modeled_constraint_rejections",
            "predispatch_repair_triggers",
            "human_intervention",
            "successful_virtual_makespan",
            "verified_suffix_repairs",
            "current_state_recipe_rebuilds",
        ):
            estimate, low, high, n = paired_bootstrap_difference(
                subset, "vcrisp", "structured_no_verify", metric
            )
            output.append(
                {
                    "subset": subset_name,
                    "comparison": "vcrisp_minus_structured_no_verify",
                    "metric": metric,
                    "paired_episodes": n,
                    "mean_difference": estimate,
                    "ci95_low": low,
                    "ci95_high": high,
                }
            )
    return output


def plot_sensitivity(rows: Sequence[Mapping[str, object]], output_path: Path) -> None:
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    for method in METHODS:
        group = [row for row in rows if row["method"] == method]
        rates = sorted({float(row["semantic_error_rate"]) for row in group})
        values = [
            mean(float(row["task_success_rate"]) for row in group if float(row["semantic_error_rate"]) == rate)
            for rate in rates
        ]
        ax.plot(rates, values, marker="o", linewidth=1.8, label=DISPLAY_NAMES[method])
    ax.set_xlabel("Base semantic candidate-error rate")
    ax.set_ylabel("Task success rate")
    ax.set_ylim(-0.03, 1.03)
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(output_path, dpi=240)
    plt.close(fig)


def plot_failure_distribution(rows: Sequence[Mapping[str, object]], output_path: Path) -> None:
    methods = list(METHODS)
    def category(reason: str) -> str:
        if reason in {"fasten_requires_driver", "tool_incompatible", "label_requires_gripper"}:
            return "Tool constraint"
        if reason in {"inspection_precondition_failed", "quality_not_passed"}:
            return "Process / quality constraint"
        if reason == "unknown_target":
            return "Unknown target / schema"
        if reason in {
            "grasp_failure",
            "inspection_reject",
            "low_confidence",
            "pose_shift",
            "station_blockage",
            "tool_unavailable",
        }:
            return "Injected disturbance"
        return "Other"

    categories = sorted(
        {
            category(str(row["terminal_reason"]))
            for row in rows
            if row["terminal_reason"] != "goal_reached"
        }
    )
    if not categories:
        categories = ["no_failures"]
    counts = {
        method: [
            sum(
                1
                for row in rows
                if row["method"] == method
                and row["terminal_reason"] != "goal_reached"
                and category(str(row["terminal_reason"])) == category_name
            )
            for category_name in categories
        ]
        for method in methods
    }
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    bottoms = [0] * len(methods)
    for index, category in enumerate(categories):
        values = [counts[method][index] for method in methods]
        ax.bar([DISPLAY_NAMES[m] for m in methods], values, bottom=bottoms, label=category)
        bottoms = [a + b for a, b in zip(bottoms, values)]
    ax.set_ylabel("Terminal episodes")
    ax.tick_params(axis="x", rotation=25)
    ax.legend(fontsize=7, bbox_to_anchor=(1.02, 1), loc="upper left")
    fig.tight_layout()
    fig.savefig(output_path, dpi=240)
    plt.close(fig)


def write_report(
    path: Path,
    summary: Sequence[Mapping[str, object]],
    paired: Sequence[Mapping[str, object]],
    manifest: Mapping[str, object],
) -> None:
    by_method = {str(row["method"]): row for row in summary}
    vcrisp = by_method["vcrisp"]
    structured = by_method["structured_no_verify"]
    with path.open("w", encoding="utf-8") as handle:
        handle.write("# Synthetic Benchmark Results\n\n")
        handle.write("## Scope\n\n")
        handle.write(
            "These values were generated by a locally executed, synthetic discrete-event "
            "assembly benchmark. They are not measurements from physical "
            "robots, a factory deployment, a geometric task-and-motion planner, or a real "
            "large language model / vision-language model.\n\n"
        )
        handle.write("## Execution\n\n")
        main = manifest["main"]
        handle.write(
            f"The main run used {main['scenario_count']} paired scenario instances and "
            f"{main['record_count']} method-episode records across {len(METHODS)} methods. "
            "Each method saw the same initial state and disturbance schedule for a given "
            "scenario. The three candidate-consuming methods shared the same deterministic "
            "candidate-error draw; the rule and oracle-state symbolic baselines do not consume "
            "that candidate interface.\n\n"
        )
        handle.write("## Primary Summary\n\n")
        handle.write(
            f"V-CRISP achieved a task success rate of {float(vcrisp['task_success_rate']):.3f} "
            f"and a modeled-constraint rejection-attempt rate of "
            f"{float(vcrisp['modeled_constraint_rejection_rate']):.3f} per dispatched action in this "
            "synthetic benchmark. The matched structured-without-verification configuration "
            f"had task success {float(structured['task_success_rate']):.3f} and modeled-constraint "
            f"rejection-attempt rate {float(structured['modeled_constraint_rejection_rate']):.3f}.\n\n"
        )
        handle.write("## Paired Bootstrap Contrasts\n\n")
        for row in paired:
            estimate = row["mean_difference"]
            low = row["ci95_low"]
            high = row["ci95_high"]
            handle.write(
                f"- `{row['subset']}` / `{row['metric']}`: V-CRISP minus structured no-verify "
                f"= {float(estimate):.4f} (95% paired bootstrap CI {float(low):.4f}, "
                f"{float(high):.4f}; n={row['paired_episodes']}).\n"
            )
        handle.write("\n## Interpretation Boundary\n\n")
        handle.write(
            "The comparisons support only the benchmark-specific claim that, under the "
            "declared state transitions and injected error model, pre-dispatch checking and "
            "verified suffix repair changed measured episode outcomes. The pre-dispatch checker "
            "shares its modeled action semantics with the dispatch guard; these results do not "
            "establish independent safety verification, real-world robot safety, perception "
            "robustness, LLM generalization, or industrial deployment performance.\n"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    args = parser.parse_args()
    results_dir = args.results_dir
    analysis_dir = results_dir / "analysis"
    figures_dir = analysis_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)

    main_rows = read_csv(results_dir / "episodes_main.csv")
    sensitivity_input = results_dir / "episodes_sensitivity.csv"
    sensitivity_input_rows = read_csv(sensitivity_input) if sensitivity_input.exists() else []
    manifest = json.loads((results_dir / "run_manifest.json").read_text(encoding="utf-8"))

    summary = aggregate_main(main_rows)
    disturbance = aggregate_by_disturbance(main_rows)
    ablations = ablation_rows(main_rows)
    paired = paired_comparisons(main_rows)
    sensitivity = sensitivity_rows(sensitivity_input_rows)
    runtime = runtime_rows(main_rows)

    write_csv(analysis_dir / "table_overall.csv", summary)
    write_csv(analysis_dir / "table_robustness.csv", disturbance)
    write_csv(analysis_dir / "table_ablation.csv", ablations)
    write_csv(analysis_dir / "paired_bootstrap.csv", paired)
    if sensitivity:
        write_csv(analysis_dir / "table_sensitivity.csv", sensitivity)
        plot_sensitivity(sensitivity, figures_dir / "sensitivity_curve.png")
    write_csv(analysis_dir / "table_runtime_scalability.csv", runtime)
    plot_failure_distribution(main_rows, figures_dir / "failure_distribution.png")
    write_report(analysis_dir / "results_report.md", summary, paired, manifest)

    print("analysis written to", analysis_dir)


if __name__ == "__main__":
    main()
