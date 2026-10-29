"""Regression tests for the declared synthetic benchmark semantics."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from simulator import (
    MAX_PREDISPATCH_REPAIRS,
    MAX_RUNTIME_RECOVERY_ATTEMPTS,
    METHODS,
    Action,
    Metrics,
    Scenario,
    World,
    base_plan,
    build_scenarios,
    compiler_reason,
    run_benchmark,
    run_episode,
    verify_and_repair,
)


class SimulatorTests(unittest.TestCase):
    def test_base_plan_lengths_match_declared_complexity(self) -> None:
        self.assertEqual(len(base_plan("basic")), 6)
        self.assertEqual(len(base_plan("standard")), 8)
        self.assertEqual(len(base_plan("extended")), 10)

    def test_compiler_rejects_unknown_target(self) -> None:
        self.assertEqual(compiler_reason(Action("pick", "ghost_cover")), "unknown_target")

    def test_all_methods_share_scenario_identifiers(self) -> None:
        scenarios = build_scenarios(range(1, 2), 1, 0.20, include_disturbances=True)
        records = run_benchmark(scenarios)
        self.assertEqual(len(records), len(scenarios) * len(METHODS))
        for scenario in scenarios:
            observed = {row["method"] for row in records if row["scenario_id"] == scenario.scenario_id}
            self.assertEqual(observed, set(METHODS))

    def test_vcrisp_has_no_modeled_constraint_rejection_attempts(self) -> None:
        scenarios = build_scenarios(range(1, 5), 2, 0.30, include_disturbances=True)
        records = run_benchmark(scenarios)
        vcrisp = [row for row in records if row["method"] == "vcrisp"]
        self.assertTrue(vcrisp)
        self.assertTrue(all(row["modeled_constraint_rejections"] == 0 for row in vcrisp))

    def test_disturbance_strata_keep_the_base_candidate_error_rate(self) -> None:
        scenarios = build_scenarios(range(1, 2), 1, 0.20, include_disturbances=True)
        disturbance_scenarios = [scenario for scenario in scenarios if scenario.disturbance != "none"]
        self.assertTrue(disturbance_scenarios)
        self.assertTrue(all(scenario.semantic_error_rate == 0.20 for scenario in disturbance_scenarios))
        self.assertNotIn("compositional", {scenario.scenario_kind for scenario in scenarios})

    def test_outcomes_are_reproducible_except_cpu_timings(self) -> None:
        scenario = Scenario(
            scenario_id="repro",
            seed=77,
            scenario_kind="disturbance",
            complexity="extended",
            disturbance="inspection_reject",
            semantic_error_rate=0.30,
        )
        first = run_episode("vcrisp", scenario)
        second = run_episode("vcrisp", scenario)
        for key in first:
            if key in {"planning_cpu_ms", "verification_cpu_ms"}:
                continue
            self.assertEqual(first[key], second[key], key)

    def test_predispatch_repairs_are_bounded_and_final_suffix_is_rechecked(self) -> None:
        metrics = Metrics()
        invalid_suffix = [Action("pick", "ghost_cover")]
        with patch("simulator.remaining_plan", return_value=invalid_suffix):
            verified = verify_and_repair(
                invalid_suffix,
                World(complexity="basic"),
                "basic",
                metrics,
            )
        self.assertIsNone(verified)
        self.assertEqual(metrics.verified_suffix_repairs, MAX_PREDISPATCH_REPAIRS)
        self.assertEqual(metrics.predispatch_repair_triggers, MAX_PREDISPATCH_REPAIRS + 1)

    def test_runtime_recovery_budget_allows_three_attempts_then_escalates(self) -> None:
        scenario = Scenario(
            scenario_id="runtime-budget",
            seed=1,
            scenario_kind="base_candidate_profile",
            complexity="basic",
            disturbance="none",
            semantic_error_rate=0.0,
        )
        with patch(
            "simulator.execute_action",
            return_value=(False, "forced_runtime_event", True),
        ) as mocked_execute:
            record = run_episode("structured_no_verify", scenario)

        self.assertEqual(record["recovery_attempts"], MAX_RUNTIME_RECOVERY_ATTEMPTS)
        self.assertEqual(record["current_state_recipe_rebuilds"], MAX_RUNTIME_RECOVERY_ATTEMPTS)
        self.assertEqual(record["actions_dispatched"], MAX_RUNTIME_RECOVERY_ATTEMPTS + 1)
        self.assertEqual(mocked_execute.call_count, MAX_RUNTIME_RECOVERY_ATTEMPTS + 1)
        self.assertEqual(record["human_intervention"], 1)
        self.assertFalse(record["success"])
        self.assertEqual(record["terminal_reason"], "forced_runtime_event")


if __name__ == "__main__":
    unittest.main(verbosity=2)
