"""Synthetic discrete-event assembly benchmark.

This module intentionally models an abstract production cell. It is not a
robotics simulator, an LLM implementation, or evidence of physical safety.
The benchmark isolates how structured candidate plans, explicit constraints,
and recovery policies behave under matched, synthetic plan errors and events.
"""

from __future__ import annotations

import copy
import json
import random
import time
from dataclasses import asdict, dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


METHODS = (
    "rule_script",
    "classical_global",
    "semantic_direct",
    "structured_no_verify",
    "vcrisp",
)

COMPLEXITIES = ("basic", "standard", "extended")
DISTURBANCES = (
    "none",
    "grasp_failure",
    "pose_shift",
    "station_blockage",
    "tool_unavailable",
    "inspection_reject",
    "low_confidence",
)

ACTION_COST = {
    "observe": 0.8,
    "verify_fixture": 0.6,
    "pick": 1.5,
    "install": 2.0,
    "tool_change": 1.2,
    "fasten": 1.8,
    "inspect": 1.4,
    "label": 1.0,
    "transfer": 0.8,
    "wait": 1.0,
    "rework": 3.0,
}

VALID_ACTIONS = frozenset(ACTION_COST)
VALID_TARGETS = frozenset({"cover", "driver", "gripper", "assembly"})
MAX_PREDISPATCH_REPAIRS = 3
MAX_RUNTIME_RECOVERY_ATTEMPTS = 3


@dataclass(frozen=True)
class Action:
    """A typed action token in the synthetic action vocabulary."""

    kind: str
    target: str
    declared_tool: Optional[str] = None


@dataclass(frozen=True)
class Scenario:
    """One independently reset episode specification."""

    scenario_id: str
    seed: int
    scenario_kind: str
    complexity: str
    disturbance: str
    semantic_error_rate: float


@dataclass
class World:
    """Task-relevant state for a single assembly episode."""

    complexity: str
    pose_known: bool = True
    fixture_verified: bool = False
    current_tool: str = "gripper"
    holding: Optional[str] = None
    cover_installed: bool = False
    fastened: bool = False
    quality_pass: bool = False
    label_applied: bool = False
    transferred: bool = False
    station_blocked_ticks: int = 0
    driver_unavailable_ticks: int = 0
    rework_required: bool = False
    disturbance: str = "none"
    disturbance_fired: bool = False


@dataclass
class Metrics:
    """Per-episode counters retained in raw experiment logs."""

    success: bool = False
    human_intervention: int = 0
    modeled_constraint_rejections: int = 0
    predispatch_repair_triggers: int = 0
    verified_suffix_repairs: int = 0
    current_state_recipe_rebuilds: int = 0
    recovery_attempts: int = 0
    disturbance_detected: int = 0
    detected_and_completed: Optional[int] = None
    completion_after_detection: Optional[int] = None
    virtual_makespan: float = 0.0
    virtual_time_to_completion_after_detection: Optional[float] = None
    fault_time: Optional[float] = None
    planning_cpu_ms: float = 0.0
    verification_cpu_ms: float = 0.0
    planner_actions_emitted: int = 0
    terminal_reason: str = ""
    candidate_error: str = "none"
    actions_dispatched: int = 0


def requires_fixture_check(complexity: str) -> bool:
    return complexity in {"standard", "extended"}


def requires_label(complexity: str) -> bool:
    return complexity == "extended"


def goal_satisfied(world: World) -> bool:
    return (
        world.cover_installed
        and world.fastened
        and world.quality_pass
        and (not requires_label(world.complexity) or world.label_applied)
        and world.transferred
    )


def base_plan(complexity: str) -> List[Action]:
    """Return the nominal recipe for a product-complexity class.

    Basic has six logical operations. Standard adds perception and fixture
    confirmation. Extended adds a label-application step after inspection.
    """

    if complexity == "basic":
        return [
            Action("pick", "cover"),
            Action("install", "cover"),
            Action("tool_change", "driver"),
            Action("fasten", "cover", "driver"),
            Action("inspect", "assembly"),
            Action("transfer", "assembly"),
        ]
    if complexity == "standard":
        return [
            Action("observe", "cover"),
            Action("verify_fixture", "assembly"),
            Action("pick", "cover"),
            Action("install", "cover"),
            Action("tool_change", "driver"),
            Action("fasten", "cover", "driver"),
            Action("inspect", "assembly"),
            Action("transfer", "assembly"),
        ]
    if complexity == "extended":
        return [
            Action("observe", "cover"),
            Action("verify_fixture", "assembly"),
            Action("pick", "cover"),
            Action("install", "cover"),
            Action("tool_change", "driver"),
            Action("fasten", "cover", "driver"),
            Action("inspect", "assembly"),
            Action("tool_change", "gripper"),
            Action("label", "assembly", "gripper"),
            Action("transfer", "assembly"),
        ]
    raise ValueError(f"Unknown complexity: {complexity}")


def candidate_error_for(scenario: Scenario) -> str:
    """Draw the same synthetic candidate error for all semantic methods.

    This represents a controlled semantic-plan perturbation model, not an LLM.
    The seed is attached to the scenario to make all comparisons paired.
    """

    rng = random.Random(scenario.seed * 1009 + 17)
    if rng.random() >= scenario.semantic_error_rate:
        return "none"
    return rng.choice(
        (
            "wrong_tool",
            "wrong_order",
            "missing_inspection",
            "unknown_target",
            "missing_tool_change",
        )
    )


def perturb_plan(plan: Sequence[Action], error: str) -> List[Action]:
    """Inject one well-defined candidate-plan error into a nominal recipe."""

    candidate = list(plan)
    if error == "none":
        return candidate
    if error == "wrong_tool":
        return [
            replace(action, declared_tool="gripper")
            if action.kind == "fasten"
            else action
            for action in candidate
        ]
    if error == "wrong_order":
        fasten_index = next(i for i, action in enumerate(candidate) if action.kind == "fasten")
        inspect_index = next(i for i, action in enumerate(candidate) if action.kind == "inspect")
        candidate[fasten_index], candidate[inspect_index] = (
            candidate[inspect_index],
            candidate[fasten_index],
        )
        return candidate
    if error == "missing_inspection":
        return [action for action in candidate if action.kind != "inspect"]
    if error == "unknown_target":
        return [
            replace(action, target="ghost_cover")
            if action.kind == "pick" and action.target == "cover"
            else action
            for action in candidate
        ]
    if error == "missing_tool_change":
        return [
            action
            for action in candidate
            if not (action.kind == "tool_change" and action.target == "driver")
        ]
    raise ValueError(f"Unknown candidate error: {error}")


def make_initial_world(scenario: Scenario) -> World:
    # Basic recipes omit an explicit observation but start from a known pose.
    return World(
        complexity=scenario.complexity,
        pose_known=True,
        fixture_verified=not requires_fixture_check(scenario.complexity),
        disturbance=scenario.disturbance,
    )


def compiler_reason(action: Action) -> Optional[str]:
    """Schema and type validation, deliberately distinct from state verification."""

    if action.kind not in VALID_ACTIONS:
        return "unknown_operator"
    if action.target not in VALID_TARGETS:
        return "unknown_target"
    if action.kind == "fasten" and action.declared_tool not in {"driver", "gripper"}:
        return "malformed_tool_field"
    if action.kind == "label" and action.declared_tool not in {"gripper", None}:
        return "malformed_tool_field"
    return None


def check_action(world: World, action: Action) -> Optional[str]:
    """Return a modeled constraint failure, or None when the action is enabled."""

    schema_problem = compiler_reason(action)
    if schema_problem:
        return schema_problem

    if action.kind == "observe":
        return None
    if action.kind == "verify_fixture":
        return None
    if action.kind == "wait":
        return None
    if action.kind == "tool_change":
        if action.target == "driver" and world.driver_unavailable_ticks > 0:
            return "driver_unavailable"
        return None
    if action.kind == "pick":
        if action.target != "cover":
            return "unknown_target"
        if world.current_tool != "gripper":
            return "pick_requires_gripper"
        if not world.pose_known:
            return "pose_unknown"
        if world.holding is not None:
            return "robot_not_empty"
        if world.cover_installed:
            return "cover_already_installed"
        return None
    if action.kind == "install":
        if world.holding != "cover":
            return "cover_not_held"
        if requires_fixture_check(world.complexity) and not world.fixture_verified:
            return "fixture_not_verified"
        if world.station_blocked_ticks > 0:
            return "station_blocked"
        return None
    if action.kind == "fasten":
        if action.declared_tool != "driver":
            return "tool_incompatible"
        if world.current_tool != "driver":
            return "fasten_requires_driver"
        if not world.cover_installed:
            return "cover_not_installed"
        return None
    if action.kind == "inspect":
        if not world.cover_installed or not world.fastened:
            return "inspection_precondition_failed"
        if world.rework_required:
            return "rework_required"
        return None
    if action.kind == "label":
        if not requires_label(world.complexity):
            return "label_not_required"
        if action.declared_tool not in {"gripper", None} or world.current_tool != "gripper":
            return "label_requires_gripper"
        if not world.quality_pass:
            return "quality_not_passed"
        return None
    if action.kind == "transfer":
        if not world.quality_pass:
            return "quality_not_passed"
        if requires_label(world.complexity) and not world.label_applied:
            return "label_not_applied"
        return None
    if action.kind == "rework":
        if not world.rework_required:
            return "rework_not_authorized"
        return None
    return "unknown_operator"


def apply_action(world: World, action: Action) -> None:
    """Apply an enabled action to the abstract environment state."""

    if action.kind == "observe":
        world.pose_known = True
    elif action.kind == "verify_fixture":
        world.fixture_verified = True
    elif action.kind == "tool_change":
        world.current_tool = action.target
    elif action.kind == "pick":
        world.holding = "cover"
    elif action.kind == "install":
        world.cover_installed = True
        world.holding = None
    elif action.kind == "fasten":
        world.fastened = True
    elif action.kind == "inspect":
        world.quality_pass = True
    elif action.kind == "label":
        world.label_applied = True
    elif action.kind == "transfer":
        world.transferred = True
    elif action.kind == "wait":
        world.station_blocked_ticks = max(0, world.station_blocked_ticks - 1)
        world.driver_unavailable_ticks = max(0, world.driver_unavailable_ticks - 1)
    elif action.kind == "rework":
        world.rework_required = False
        world.fastened = False
        world.quality_pass = False


def disturbance_fires(world: World, action: Action) -> Optional[str]:
    """Inject exactly one exogenous event after action preconditions hold."""

    if world.disturbance_fired or world.disturbance == "none":
        return None
    event = world.disturbance
    if event == "grasp_failure" and action.kind == "pick":
        world.disturbance_fired = True
        return "grasp_failure"
    if event == "pose_shift" and action.kind == "install":
        world.disturbance_fired = True
        world.pose_known = False
        return "pose_shift"
    if event == "station_blockage" and action.kind == "install":
        world.disturbance_fired = True
        world.station_blocked_ticks = 1
        return "station_blockage"
    if event == "tool_unavailable" and action.kind == "tool_change" and action.target == "driver":
        world.disturbance_fired = True
        world.driver_unavailable_ticks = 1
        return "tool_unavailable"
    if event == "inspection_reject" and action.kind == "inspect":
        world.disturbance_fired = True
        world.rework_required = True
        world.quality_pass = False
        return "inspection_reject"
    if event == "low_confidence" and action.kind == "pick":
        world.disturbance_fired = True
        world.pose_known = False
        return "low_confidence"
    return None


def execute_action(world: World, action: Action) -> Tuple[bool, Optional[str], bool]:
    """Attempt a plant dispatch and return (success, reason, is_disturbance)."""

    reason = check_action(world, action)
    if reason:
        return False, reason, False
    event = disturbance_fires(world, action)
    if event:
        return False, event, True
    apply_action(world, action)
    return True, None, False


def remaining_plan(world: World, complexity: str) -> List[Action]:
    """Build a valid suffix from the current state using known symbolic goals."""

    plan: List[Action] = []
    if world.station_blocked_ticks > 0 or world.driver_unavailable_ticks > 0:
        plan.append(Action("wait", "assembly"))
    if world.rework_required:
        plan.append(Action("rework", "assembly"))
    if not world.cover_installed:
        if not world.pose_known:
            plan.append(Action("observe", "cover"))
        if requires_fixture_check(complexity) and not world.fixture_verified:
            plan.append(Action("verify_fixture", "assembly"))
        if world.current_tool != "gripper":
            plan.append(Action("tool_change", "gripper"))
        if world.holding != "cover":
            plan.append(Action("pick", "cover"))
        plan.append(Action("install", "cover"))
    if not world.fastened:
        if world.driver_unavailable_ticks > 0:
            plan.append(Action("wait", "assembly"))
        if world.current_tool != "driver":
            plan.append(Action("tool_change", "driver"))
        plan.append(Action("fasten", "cover", "driver"))
    if not world.quality_pass:
        plan.append(Action("inspect", "assembly"))
    if requires_label(complexity) and not world.label_applied:
        if world.current_tool != "gripper":
            plan.append(Action("tool_change", "gripper"))
        plan.append(Action("label", "assembly", "gripper"))
    if not world.transferred:
        plan.append(Action("transfer", "assembly"))
    return plan


def serialize_plan(plan: Sequence[Action]) -> List[Dict[str, Optional[str]]]:
    return [
        {"kind": action.kind, "target": action.target, "declared_tool": action.declared_tool}
        for action in plan
    ]


def verify_and_repair(
    plan: Sequence[Action],
    world: World,
    complexity: str,
    metrics: Metrics,
    trace: Optional[List[Dict[str, object]]] = None,
) -> Optional[List[Action]]:
    """Compile, simulate, and locally replace only the invalid suffix.

    The verifier operates on the abstract, explicitly modeled constraints. A
    successful verification is therefore not a general safety guarantee.
    """

    candidate = list(plan)
    for verification_pass in range(MAX_PREDISPATCH_REPAIRS + 1):
        sim = copy.deepcopy(world)
        repaired = False
        for index, action in enumerate(candidate):
            reason = compiler_reason(action) or check_action(sim, action)
            if reason:
                metrics.predispatch_repair_triggers += 1
                if verification_pass >= MAX_PREDISPATCH_REPAIRS:
                    if trace is not None:
                        trace.append(
                            {
                                "stage": "predispatch_repair_exhausted",
                                "reason": reason,
                                "invalid_action": serialize_plan([action])[0],
                                "repair_scope": "verified_suffix",
                            }
                        )
                    return None
                metrics.verified_suffix_repairs += 1
                if trace is not None:
                    trace.append(
                        {
                            "stage": "predispatch_repair",
                            "reason": reason,
                            "invalid_action": serialize_plan([action])[0],
                            "repair_scope": "verified_suffix",
                        }
                    )
                candidate = candidate[:index] + remaining_plan(sim, complexity)
                repaired = True
                break
            apply_action(sim, action)
        if repaired:
            continue
        if goal_satisfied(sim):
            return candidate
        metrics.predispatch_repair_triggers += 1
        if verification_pass >= MAX_PREDISPATCH_REPAIRS:
            if trace is not None:
                trace.append(
                    {
                        "stage": "predispatch_repair_exhausted",
                        "reason": "goal_not_reached_after_candidate",
                        "repair_scope": "append_missing_goal_suffix",
                    }
                )
            return None
        metrics.verified_suffix_repairs += 1
        if trace is not None:
            trace.append(
                {
                    "stage": "predispatch_repair",
                    "reason": "goal_not_reached_after_candidate",
                    "repair_scope": "append_missing_goal_suffix",
                }
            )
        candidate = candidate + remaining_plan(sim, complexity)
    return None


def compile_plan(plan: Sequence[Action]) -> Optional[str]:
    for action in plan:
        reason = compiler_reason(action)
        if reason:
            return reason
    return None


def initial_plan_for(method: str, scenario: Scenario, metrics: Metrics) -> List[Action]:
    nominal = base_plan(scenario.complexity)
    if method in {"semantic_direct", "structured_no_verify", "vcrisp"}:
        metrics.candidate_error = candidate_error_for(scenario)
        return perturb_plan(nominal, metrics.candidate_error)
    metrics.candidate_error = "none"
    if method == "classical_global":
        return remaining_plan(make_initial_world(scenario), scenario.complexity)
    return nominal


def is_constraint_error(reason: str) -> bool:
    return reason not in {
        "grasp_failure",
        "pose_shift",
        "station_blockage",
        "tool_unavailable",
        "inspection_reject",
        "low_confidence",
    }


def run_episode(
    method: str, scenario: Scenario, include_trace: bool = False
) -> Dict[str, object]:
    """Run one matched episode and return a flat raw-log record."""

    if method not in METHODS:
        raise ValueError(f"Unknown method: {method}")
    world = make_initial_world(scenario)
    metrics = Metrics()
    trace: Optional[List[Dict[str, object]]] = [] if include_trace else None
    start = time.perf_counter()
    plan = initial_plan_for(method, scenario, metrics)
    if trace is not None:
        trace.append(
            {
                "stage": "candidate_plan",
                "candidate_error": metrics.candidate_error,
                "plan": serialize_plan(plan),
            }
        )
    metrics.planner_actions_emitted += len(plan)
    metrics.planning_cpu_ms += (time.perf_counter() - start) * 1000.0

    if method == "vcrisp":
        verify_start = time.perf_counter()
        verified = verify_and_repair(plan, world, scenario.complexity, metrics, trace)
        metrics.verification_cpu_ms += (time.perf_counter() - verify_start) * 1000.0
        if verified is None:
            metrics.human_intervention = 1
            metrics.terminal_reason = "verification_exhausted"
            return episode_record(method, scenario, metrics, trace)
        plan = verified
        if trace is not None:
            trace.append(
                {"stage": "verification_authorized", "plan": serialize_plan(plan)}
            )
    elif method == "structured_no_verify":
        compile_problem = compile_plan(plan)
        if compile_problem:
            metrics.predispatch_repair_triggers += 1
            metrics.current_state_recipe_rebuilds += 1
            replan_start = time.perf_counter()
            plan = remaining_plan(world, scenario.complexity)
            metrics.planning_cpu_ms += (time.perf_counter() - replan_start) * 1000.0

    cursor = 0
    while cursor < len(plan):
        action = plan[cursor]
        metrics.actions_dispatched += 1
        ok, reason, disturbance = execute_action(world, action)
        if trace is not None:
            trace.append(
                {
                    "stage": "dispatch",
                    "action": serialize_plan([action])[0],
                    "outcome": "success" if ok else "failure",
                    "reason": reason,
                    "is_disturbance": disturbance,
                }
            )
        if ok:
            metrics.virtual_makespan += ACTION_COST[action.kind]
            cursor += 1
            continue

        assert reason is not None
        if disturbance:
            metrics.disturbance_detected = 1
            if metrics.fault_time is None:
                metrics.fault_time = metrics.virtual_makespan
        elif is_constraint_error(reason):
            # The dispatch guard rejects the action before apply_action runs.
            # This counter is therefore a rejected modeled-constraint attempt,
            # not an executed physical or safety violation.
            metrics.modeled_constraint_rejections += 1

        recoverable = method in {"classical_global", "structured_no_verify", "vcrisp"}
        if not recoverable or metrics.recovery_attempts >= MAX_RUNTIME_RECOVERY_ATTEMPTS:
            metrics.human_intervention = 1
            metrics.terminal_reason = reason
            if trace is not None:
                trace.append(
                    {"stage": "terminal", "outcome": "escalated", "reason": reason}
                )
            break

        metrics.recovery_attempts += 1
        if method == "vcrisp":
            # The replacement is a suffix from the current state, preserving
            # the completed prefix and avoiding a full episode restart.
            metrics.verified_suffix_repairs += 1
            replan_start = time.perf_counter()
            plan = remaining_plan(world, scenario.complexity)
            metrics.planning_cpu_ms += (time.perf_counter() - replan_start) * 1000.0
            verify_start = time.perf_counter()
            verified = verify_and_repair(plan, world, scenario.complexity, metrics, trace)
            metrics.verification_cpu_ms += (time.perf_counter() - verify_start) * 1000.0
            if verified is None:
                metrics.human_intervention = 1
                metrics.terminal_reason = "verified_suffix_repair_exhausted"
                break
            plan = verified
        else:
            # The baseline discards the remaining candidate suffix and rebuilds
            # an unverified recipe from the current symbolic state.
            metrics.current_state_recipe_rebuilds += 1
            replan_start = time.perf_counter()
            plan = remaining_plan(world, scenario.complexity)
            metrics.planning_cpu_ms += (time.perf_counter() - replan_start) * 1000.0
        metrics.planner_actions_emitted += len(plan)
        if trace is not None:
            trace.append(
                {
                    "stage": "runtime_repair",
                    "repair_scope": "verified_suffix" if method == "vcrisp" else "current_state_recipe",
                    "trigger": reason,
                    "plan": serialize_plan(plan),
                }
            )
        cursor = 0

    metrics.success = goal_satisfied(world)
    if metrics.success:
        metrics.terminal_reason = "goal_reached"
    elif not metrics.terminal_reason:
        metrics.terminal_reason = "goal_not_reached"
    if scenario.disturbance != "none":
        metrics.detected_and_completed = int(metrics.success and metrics.disturbance_detected)
        if metrics.disturbance_detected:
            metrics.completion_after_detection = int(metrics.success)
        if metrics.detected_and_completed and metrics.fault_time is not None:
            metrics.virtual_time_to_completion_after_detection = (
                metrics.virtual_makespan - metrics.fault_time
            )
    if trace is not None:
        trace.append(
            {
                "stage": "terminal",
                "outcome": "success" if metrics.success else "failure",
                "reason": metrics.terminal_reason,
            }
        )
    return episode_record(method, scenario, metrics, trace)


def episode_record(
    method: str,
    scenario: Scenario,
    metrics: Metrics,
    trace: Optional[List[Dict[str, object]]] = None,
) -> Dict[str, object]:
    """Convert internal state to a stable, tabular provenance record."""

    record: Dict[str, object] = {
        "method": method,
        "scenario_id": scenario.scenario_id,
        "seed": scenario.seed,
        "scenario_kind": scenario.scenario_kind,
        "complexity": scenario.complexity,
        "disturbance": scenario.disturbance,
        "semantic_error_rate": scenario.semantic_error_rate,
    }
    record.update(asdict(metrics))
    if trace is not None:
        record["trace_json"] = json.dumps(trace, sort_keys=True)
    return record


def build_scenarios(
    seeds: Iterable[int],
    episodes_per_stratum: int,
    semantic_error_rate: float,
    include_disturbances: bool = True,
    candidate_profile_increment: float = 0.10,
) -> List[Scenario]:
    """Generate balanced synthetic task and candidate-error conditions.

    The two no-disturbance profiles differ only in injected candidate-plan error
    probability. They are not compositional instructions or language inputs.
    Disturbance strata retain the supplied base error rate so that the event
    effect is not confounded with a different candidate-error probability.
    """

    scenarios: List[Scenario] = []
    serial = 0
    for evaluation_seed in seeds:
        for complexity_index, complexity in enumerate(COMPLEXITIES):
            profiles = (
                ("base_candidate_profile", semantic_error_rate),
                (
                    "elevated_candidate_profile",
                    min(0.95, semantic_error_rate + candidate_profile_increment),
                ),
            )
            for profile_index, (scenario_kind, profile_error_rate) in enumerate(profiles):
                for replicate in range(episodes_per_stratum):
                    serial += 1
                    scenario_seed = (
                        evaluation_seed * 1_000_003
                        + complexity_index * 10_007
                        + replicate * 97
                        + profile_index * 29
                    )
                    scenarios.append(
                        Scenario(
                            scenario_id=f"{evaluation_seed}-{serial}",
                            seed=scenario_seed,
                            scenario_kind=scenario_kind,
                            complexity=complexity,
                            disturbance="none",
                            semantic_error_rate=profile_error_rate,
                        )
                    )
            if include_disturbances:
                for disturbance_index, disturbance in enumerate(DISTURBANCES[1:]):
                    for replicate in range(episodes_per_stratum):
                        serial += 1
                        scenario_seed = (
                            evaluation_seed * 1_000_003
                            + complexity_index * 10_007
                            + disturbance_index * 809
                            + replicate * 97
                            + 53
                        )
                        scenarios.append(
                            Scenario(
                                scenario_id=f"{evaluation_seed}-{serial}",
                                seed=scenario_seed,
                                scenario_kind="disturbance",
                                complexity=complexity,
                                disturbance=disturbance,
                                semantic_error_rate=semantic_error_rate,
                            )
                        )
    return scenarios


def run_benchmark(scenarios: Sequence[Scenario]) -> List[Dict[str, object]]:
    """Run each method on every scenario; pairing is by scenario_id."""

    records: List[Dict[str, object]] = []
    for scenario in scenarios:
        for method in METHODS:
            records.append(run_episode(method, scenario))
    return records
