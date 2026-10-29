"""Render the quantitative and qualitative figures for the synthetic study.

All panels are derived from the locally generated benchmark logs. The figures
do not depict a physical robot, real LLM/VLM outputs, or geometric trajectories.

Run with the selected Python backend and a path to the figure QA helper:
  PYTHONPATH=/path/to/nature-figure/scripts .venv/bin/python make_publication_figures.py
"""

from __future__ import annotations

import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from audit_panel_alignment import require_matplotlib_panel_alignment


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
ANALYSIS = RESULTS / "analysis"
OUT = ROOT / "figures" / "publication"

METHOD_LABELS = {
    "rule_script": "Rule script",
    "classical_global": "Oracle-state symbolic",
    "semantic_direct": "Perturbed candidate direct",
    "structured_no_verify": "Structured no-verify",
    "vcrisp": "V-CRISP",
}
PALETTE = {
    "ink": "#0f172a",
    "muted": "#64748b",
    "grid": "#cbd5e1",
    "vcrisp": "#2563eb",
    "semantic": "#d97706",
    "rule": "#94a3b8",
    "classical": "#64748b",
    "structured": "#7c3aed",
    "grounding": "#0284c7",
    "disturbance": "#d97706",
    "process": "#65a30d",
    "tool": "#dc2626",
}

mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
        "font.size": 7,
        "axes.labelsize": 7,
        "axes.titlesize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "legend.fontsize": 6,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "axes.linewidth": 0.7,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "xtick.major.width": 0.7,
        "ytick.major.width": 0.7,
    }
)


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def as_bool(value: str) -> bool:
    return value.lower() in {"true", "1"}


def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    if total == 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1.0 + z * z / total
    center = (p + z * z / (2.0 * total)) / denominator
    half = z * math.sqrt(p * (1.0 - p) / total + z * z / (4.0 * total * total)) / denominator
    return max(0.0, center - half), min(1.0, center + half)


def export_figure(fig: mpl.figure.Figure, stem: str, axes: Sequence[plt.Axes]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    layout_json = OUT / f"{stem}.alignment.json"
    overlay_svg = OUT / f"{stem}.alignment.svg"
    require_matplotlib_panel_alignment(
        fig,
        axes=axes,
        panel_ids=[chr(ord("a") + index) for index in range(len(axes))],
        json_out=layout_json,
        overlay_svg=overlay_svg,
        tolerance_pt=1.5,
        gutter_tolerance_pt=1.5,
        require_panel_labels=len(axes) > 1,
        strict=True,
    )
    fig.savefig(OUT / f"{stem}.svg", dpi=600, facecolor="white")
    fig.savefig(OUT / f"{stem}.pdf", dpi=600, facecolor="white")
    fig.savefig(OUT / f"{stem}.png", dpi=600, facecolor="white")
    fig.savefig(OUT / f"{stem}.tiff", dpi=600, facecolor="white")
    plt.close(fig)


def panel_label(ax: plt.Axes, label: str) -> None:
    ax.text(
        -0.14,
        1.04,
        label,
        transform=ax.transAxes,
        fontweight="bold",
        fontsize=8,
        va="bottom",
        ha="left",
        rotation_mode="anchor",
        clip_on=False,
    )


def style_axis(ax: plt.Axes) -> None:
    ax.grid(axis="y", color=PALETTE["grid"], linewidth=0.5, alpha=0.75)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, color=PALETTE["ink"])


def fig2_qualitative_trace() -> None:
    trace_payload = json.loads((ANALYSIS / "qualitative_trace.json").read_text(encoding="utf-8"))
    record = trace_payload["record"]
    labels = [
        "Candidate plan\nwrong action order",
        "Checker repairs\nearly inspection",
        "Corrected prefix\nauthorized",
        "Event logger records\ninspection rejection",
        "Verified suffix repair\nrework, fasten, inspect",
        "Terminal\nsuccess",
    ]
    colors = ["#e0ecff", "#fee2e2", "#dcfce7", "#fef3c7", "#dbeafe", "#dcfce7"]
    fig, ax = plt.subplots(figsize=(7.2, 2.25))
    ax.set_xlim(-0.2, len(labels) - 0.8)
    ax.set_ylim(0.0, 1.0)
    ax.axis("off")
    for index, (label, color) in enumerate(zip(labels, colors)):
        ax.text(
            index,
            0.53,
            label,
            ha="center",
            va="center",
            fontsize=6.5,
            linespacing=1.15,
            bbox={"boxstyle": "round,pad=0.52", "facecolor": color, "edgecolor": "#475569", "linewidth": 0.8},
        )
        if index < len(labels) - 1:
            # Connect above the cards so no stroke passes through live text.
            ax.annotate(
                "",
                xy=(index + 0.72, 0.74),
                xytext=(index + 0.28, 0.74),
                arrowprops={"arrowstyle": "->", "color": "#475569", "lw": 1.0},
            )
    ax.text(
        0.0,
        0.12,
        "Synthetic extended-recipe episode; deterministic seed = " + str(record["seed"])
        + "; no physical robot or language model is involved.",
        ha="left",
        va="center",
        fontsize=5.8,
        color=PALETTE["muted"],
    )
    export_figure(fig, "fig2_qualitative_recovery", [ax])


def sensitivity_summary(rows: Sequence[Mapping[str, str]], method: str) -> List[Tuple[float, float, float, float, int]]:
    result: List[Tuple[float, float, float, float, int]] = []
    rates = sorted({float(row["semantic_error_rate"]) for row in rows})
    for rate in rates:
        group = [row for row in rows if float(row["semantic_error_rate"]) == rate and row["method"] == method]
        total = len(group)
        successes = sum(as_bool(row["success"]) for row in group)
        low, high = wilson_interval(successes, total)
        interventions = sum(int(row["human_intervention"]) for row in group)
        intervention_low, intervention_high = wilson_interval(interventions, total)
        result.append((rate, successes / total, low, high, interventions / total))
        # The intervention interval is recomputed by the caller when needed.
        _ = intervention_low, intervention_high
    return result


def fig3_sensitivity() -> None:
    rows = read_csv(RESULTS / "episodes_sensitivity.csv")
    direct = sensitivity_summary(rows, "semantic_direct")
    vcrisp = sensitivity_summary(rows, "vcrisp")
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.65), sharex=True)

    for ax, metric_name in zip(axes, ("success", "intervention")):
        if metric_name == "success":
            for series, label, color, marker in (
                (direct, "Perturbed candidate direct", PALETTE["semantic"], "o"),
                (vcrisp, "V-CRISP", PALETTE["vcrisp"], "s"),
            ):
                xs = np.array([row[0] for row in series])
                ys = np.array([row[1] for row in series])
                lows = np.array([row[2] for row in series])
                highs = np.array([row[3] for row in series])
                ax.plot(xs, ys, marker=marker, markersize=4.2, linewidth=1.4, color=color, label=label)
                ax.fill_between(xs, lows, highs, color=color, alpha=0.12, linewidth=0)
            ax.set_ylabel("Task success rate")
            ax.set_ylim(0.55, 1.035)
        else:
            for method, label, color, marker in (
                ("semantic_direct", "Perturbed candidate direct", PALETTE["semantic"], "o"),
                ("vcrisp", "V-CRISP", PALETTE["vcrisp"], "s"),
            ):
                rates = sorted({float(row["semantic_error_rate"]) for row in rows})
                values = []
                lows = []
                highs = []
                for rate in rates:
                    group = [
                        row
                        for row in rows
                        if float(row["semantic_error_rate"]) == rate and row["method"] == method
                    ]
                    count = sum(int(row["human_intervention"]) for row in group)
                    low, high = wilson_interval(count, len(group))
                    values.append(count / len(group))
                    lows.append(low)
                    highs.append(high)
                ax.plot(rates, values, marker=marker, markersize=4.2, linewidth=1.4, color=color, label=label)
                ax.fill_between(rates, lows, highs, color=color, alpha=0.12, linewidth=0)
            ax.set_ylabel("Simulated escalation rate")
            ax.set_ylim(-0.015, 0.42)

        ax.set_xlabel("Synthetic candidate-error rate")
        ax.set_xticks([0.05, 0.10, 0.20, 0.30])
        style_axis(ax)
    panel_label(axes[0], "a")
    panel_label(axes[1], "b")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.54, 0.995),
        ncol=2,
        frameon=False,
        handlelength=1.8,
        columnspacing=1.5,
    )
    fig.subplots_adjust(left=0.09, right=0.985, top=0.82, bottom=0.22, wspace=0.35)
    export_figure(fig, "fig3_sensitivity", list(axes))


def failure_category(reason: str) -> str:
    if reason in {"fasten_requires_driver", "tool_incompatible", "label_requires_gripper"}:
        return "Modeled tool"
    if reason in {"inspection_precondition_failed", "quality_not_passed"}:
        return "Modeled process / quality"
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


def fig4_failure_distribution() -> None:
    rows = read_csv(RESULTS / "episodes_main.csv")
    methods = ["rule_script", "classical_global", "semantic_direct", "structured_no_verify", "vcrisp"]
    categories = ["Unknown target / schema", "Injected disturbance", "Modeled process / quality", "Modeled tool"]
    colors = [PALETTE["grounding"], PALETTE["disturbance"], PALETTE["process"], PALETTE["tool"]]
    counts: Dict[str, Counter[str]] = {method: Counter() for method in methods}
    for row in rows:
        if row["terminal_reason"] != "goal_reached":
            counts[row["method"]][failure_category(row["terminal_reason"])] += 1

    fig, ax = plt.subplots(figsize=(7.2, 2.95))
    x = np.arange(len(methods))
    bottom = np.zeros(len(methods))
    for category, color in zip(categories, colors):
        values = np.array([counts[method][category] for method in methods])
        ax.bar(x, values, bottom=bottom, width=0.66, color=color, label=category, edgecolor="white", linewidth=0.35)
        bottom += values
    ax.set_xticks(x, [METHOD_LABELS[method] for method in methods])
    for label in ax.get_xticklabels():
        label.set_rotation(18)
        label.set_rotation_mode("anchor")
        label.set_ha("right")
    ax.set_ylabel("Terminal episodes (n = 4,800 per method)")
    ax.set_ylim(0, 4200)
    ax.set_yticks([0, 1000, 2000, 3000, 4000])
    style_axis(ax)
    for x_text, category, color in zip((0.34, 0.53, 0.71, 0.87), categories, colors):
        fig.text(x_text, 0.965, category, color=color, fontsize=5.8, ha="center", va="top")
    fig.subplots_adjust(left=0.105, right=0.985, top=0.82, bottom=0.30)
    export_figure(fig, "fig4_failure_distribution", [ax])


def main() -> None:
    fig2_qualitative_trace()
    fig3_sensitivity()
    fig4_failure_distribution()
    print("publication figures written to", OUT)


if __name__ == "__main__":
    main()
