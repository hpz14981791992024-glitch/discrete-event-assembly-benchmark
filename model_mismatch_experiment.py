"""Controlled checker/dispatch-guard mismatch experiments.

Run from the repository root: python3 model_mismatch_experiment.py --output-dir PATH
The output directory must be new or empty. Existing benchmark data are untouched.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import simulator
from simulator import Action, Metrics, World


MUTATIONS = {
    "fixture": "fixture_not_verified",
    "tool": "fasten_requires_driver",
    "quality": "quality_not_passed",
}


@dataclass(frozen=True)
class Case:
    case_id: str
    mutation: str
    violated: bool
    world: World
    candidate: Action


def cases() -> list[Case]:
    """Build matched invalid and valid cases, without stochastic injection."""
    output = []
    for complexity in ("standard", "extended"):
        for violated in (False, True):
            output.append(Case(
                f"fixture-{complexity}-{'invalid' if violated else 'valid'}",
                "fixture", violated,
                World(complexity=complexity, holding="cover", fixture_verified=not violated),
                Action("install", "cover"),
            ))
    for complexity in ("basic", "standard", "extended"):
        for violated in (False, True):
            output.append(Case(
                f"tool-{complexity}-{'invalid' if violated else 'valid'}",
                "tool", violated,
                World(complexity=complexity, fixture_verified=True, cover_installed=True,
                      current_tool="gripper" if violated else "driver"),
                Action("fasten", "cover", "driver"),
            ))
            output.append(Case(
                f"quality-{complexity}-{'invalid' if violated else 'valid'}",
                "quality", violated,
                World(complexity=complexity, fixture_verified=True, cover_installed=True,
                      fastened=True, current_tool="driver", quality_pass=not violated,
                      label_applied=complexity == "extended"),
                Action("transfer", "assembly"),
            ))
    return output


def checker(world: World, action: Action, suppressed_reason: str | None) -> str | None:
    reason = simulator.check_action_python(world, action)
    return None if reason == suppressed_reason else reason


def verify(plan: list[Action], world: World, metrics: Metrics, mutation: str | None):
    suppressed = MUTATIONS[mutation] if mutation else None
    with patch.object(simulator, "check_action", side_effect=lambda w, a: checker(w, a, suppressed)):
        return simulator.verify_and_repair(plan, world, world.complexity, metrics)


def execute_guarded(world: World, action: Action):
    # Both checkers are selected only for the duration of each call. The
    # dispatch guard always runs the original Python predicate.
    with patch.object(simulator, "check_action", side_effect=simulator.check_action_python):
        return simulator.execute_action(world, action)


def run_case(case: Case, mismatched: bool) -> dict:
    world = copy.deepcopy(case.world)
    metrics = Metrics()
    mutation = case.mutation if mismatched else None
    original_reason = simulator.check_action_python(world, case.candidate)
    checker_reason = checker(world, case.candidate, MUTATIONS[mutation] if mutation else None)
    initial_plan = verify([case.candidate], world, metrics, mutation)
    retained = bool(initial_plan and initial_plan[0] == case.candidate)
    plan = initial_plan
    trace = []
    attempts = 0
    recovery = 0
    rejections = 0
    virtual_cost = 0.0
    terminal = ""
    cursor = 0
    while plan is not None and cursor < len(plan):
        action = plan[cursor]
        attempts += 1
        ok, reason, disturbance = execute_guarded(world, action)
        trace.append({"action": asdict(action), "accepted": ok, "reason": reason})
        if ok:
            virtual_cost += simulator.ACTION_COST[action.kind]
            cursor += 1
            continue
        if disturbance:
            raise RuntimeError("This controlled experiment does not schedule disturbances")
        rejections += 1
        if recovery >= simulator.MAX_RUNTIME_RECOVERY_ATTEMPTS:
            terminal = "recovery_budget_exhausted"
            break
        recovery += 1
        plan = verify(simulator.remaining_plan(world, world.complexity), world, metrics, mutation)
        if plan is None:
            terminal = "verification_exhausted"
            break
        cursor = 0
    if initial_plan is None:
        terminal = "initial_verification_exhausted"
    success = simulator.goal_satisfied(world)
    if not terminal:
        terminal = "goal_reached" if success else "goal_incomplete"
    return {
        "case_id": case.case_id,
        "mutation": case.mutation,
        "complexity": case.world.complexity,
        "violated": case.violated,
        "condition": "mismatch" if mismatched else "matched",
        "guard_initial_reason": original_reason,
        "checker_initial_reason": checker_reason,
        "initial_plan_authorized": initial_plan is not None,
        "original_action_retained_first": retained,
        "guard_rejections": rejections,
        "recovery_attempts": recovery,
        "dispatch_attempts": attempts,
        "predispatch_repair_triggers": metrics.predispatch_repair_triggers,
        "success": success,
        "terminal": terminal,
        "virtual_action_cost": virtual_cost,
        "initial_state_json": json.dumps(asdict(case.world), sort_keys=True),
        "candidate_json": json.dumps(asdict(case.candidate), sort_keys=True),
        "authorized_plan_json": json.dumps(simulator.serialize_plan(initial_plan) if initial_plan else None, sort_keys=True),
        "dispatch_trace_json": json.dumps(trace, sort_keys=True),
    }


def summarize(rows: list[dict]) -> list[dict]:
    output = []
    for mutation in MUTATIONS:
        for violated in (False, True):
            for condition in ("matched", "mismatch"):
                group = [r for r in rows if r["mutation"] == mutation
                         and r["violated"] == violated and r["condition"] == condition]
                output.append({
                    "mutation": mutation, "violated": violated, "condition": condition,
                    "cases": len(group),
                    "initial_guard_invalid": sum(r["guard_initial_reason"] is not None for r in group),
                    "checker_misses_initial_invalid": sum(
                        r["guard_initial_reason"] is not None and r["checker_initial_reason"] is None
                        for r in group),
                    "invalid_first_action_retained": sum(
                        r["guard_initial_reason"] is not None and r["original_action_retained_first"]
                        for r in group),
                    "guard_rejections": sum(r["guard_rejections"] for r in group),
                    "successes": sum(r["success"] for r in group),
                })
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    destination = args.output_dir
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        parser.error("output directory must be new or empty")
    destination.mkdir(parents=True, exist_ok=True)
    rows = [run_case(case, condition) for case in cases() for condition in (False, True)]
    write_csv(destination / "episodes.csv", rows)
    write_csv(destination / "summary.csv", summarize(rows))
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "description": "Hand-constructed deterministic checker/guard model mismatch cases",
        "cases": len(cases()), "records": len(rows),
        "mutation_reasons": MUTATIONS, "random_seed": None,
        "python": sys.version, "platform": platform.platform(),
        "source_sha256": {str(p): sha256(p) for p in
                          (Path("simulator.py"), Path("model_mismatch_experiment.py"),
                           Path("test_model_mismatch_experiment.py"))},
        "notes": ["Matched and mismatched conditions share each initial state and candidate.",
                  "Only the checker suppresses a single modeled reason; guard stays unchanged.",
                  "Each case is deterministic and hand constructed, not a random replicate.",
                  "Guard rejections occur before modeled state changes and are not physical violations."],
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summarize(rows), indent=2))


if __name__ == "__main__":
    main()
