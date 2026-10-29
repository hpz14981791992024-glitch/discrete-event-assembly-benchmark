"""Generate a purpose-built synthetic Figure 2 mechanism trace.

The selected scenario has both a wrong-order candidate plan and an
inspection-rejection disturbance. The script searches a fixed seed range to
avoid manually choosing an undocumented random draw. It is illustrative and is
not a representative sample from the primary experiment distribution.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from simulator import Scenario, candidate_error_for, run_episode


def action_label(action: dict) -> str:
    tool = action.get("declared_tool")
    suffix = f" ({tool})" if tool else ""
    return f"{action['kind']}:{action['target']}{suffix}"


def meaningful_trace(trace: list[dict]) -> list[str]:
    labels: list[str] = []
    for event in trace:
        stage = event["stage"]
        if stage == "candidate_plan":
            labels.append("Candidate plan\nwrong action order")
        elif stage == "predispatch_repair":
            reason = event["reason"]
            if reason == "inspection_precondition_failed":
                labels.append("Verifier inserts\nmissing prerequisite")
            else:
                labels.append(f"Verifier blocks\n{reason}")
        elif stage == "verification_authorized":
            labels.append("Verified\nauthorization")
        elif stage == "dispatch" and event["outcome"] == "failure":
            labels.append("Event logger records\ninspection rejection")
        elif stage == "runtime_repair":
            labels.append("Verified suffix repair\nrework, refasten, reinspect")
        elif stage == "terminal":
            labels.append(f"Terminal\n{event['outcome']}")
    return labels


def plot(labels: list[str], output_path: Path) -> None:
    width = max(8.4, 1.42 * len(labels))
    fig, ax = plt.subplots(figsize=(width, 2.9))
    ax.axis("off")
    colors = ["#dbeafe", "#fee2e2", "#dcfce7", "#fef3c7", "#e0e7ff", "#dcfce7"]
    for index, label in enumerate(labels):
        x = index / max(1, len(labels) - 1)
        ax.text(
            x,
            0.53,
            label,
            ha="center",
            va="center",
            fontsize=8.3,
            bbox={"boxstyle": "round,pad=0.55", "facecolor": colors[index % len(colors)], "edgecolor": "#475569"},
            transform=ax.transAxes,
        )
        if index < len(labels) - 1:
            ax.annotate(
                "",
                xy=((index + 0.84) / max(1, len(labels) - 1), 0.53),
                xytext=((index + 0.16) / max(1, len(labels) - 1), 0.53),
                xycoords=ax.transAxes,
                arrowprops={"arrowstyle": "->", "color": "#475569", "lw": 1.1},
            )
    ax.set_title("Synthetic extended-recipe trace: verification and recovery", fontsize=11, pad=9)
    fig.tight_layout()
    fig.savefig(output_path, dpi=240, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("results/analysis"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    figures_dir = args.output_dir / "figures"
    figures_dir.mkdir(exist_ok=True)

    selected = None
    for seed in range(1, 10000):
        candidate = Scenario(
            scenario_id=f"qualitative-{seed}",
            seed=seed,
            scenario_kind="qualitative",
            complexity="extended",
            disturbance="inspection_reject",
            semantic_error_rate=1.0,
        )
        if candidate_error_for(candidate) == "wrong_order":
            selected = candidate
            break
    if selected is None:
        raise RuntimeError("Could not select the fixed qualitative scenario")

    record = run_episode("vcrisp", selected, include_trace=True)
    trace = json.loads(str(record.pop("trace_json")))
    payload = {
        "scope": (
            "Synthetic discrete-event trace; not a physical robot or LLM/VLM execution."
        ),
        "scenario": {
            "scenario_id": selected.scenario_id,
            "seed": selected.seed,
            "complexity": selected.complexity,
            "disturbance": selected.disturbance,
            "semantic_error_rate": selected.semantic_error_rate,
        },
        "record": record,
        "trace": trace,
    }
    (args.output_dir / "qualitative_trace.json").write_text(
        json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
    )
    plot(meaningful_trace(trace), figures_dir / "qualitative_recovery_trace.png")
    print("selected", selected.scenario_id, "with seed", selected.seed)


if __name__ == "__main__":
    main()
