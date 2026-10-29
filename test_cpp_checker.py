"""Cross-language checks for the optional C++ action checker."""

from __future__ import annotations

import itertools
import os
import random
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import simulator
from simulator import Action, World


ROOT = Path(__file__).resolve().parent


class CppCheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        compiler = os.environ.get("CXX", "c++")
        if shutil.which(compiler) is None:
            raise unittest.SkipTest(f"C++ compiler not found: {compiler}")
        cls.tmpdir = tempfile.TemporaryDirectory(prefix="vcrisp-cpp-test-")
        suffix = ".dylib" if sys.platform == "darwin" else ".so"
        cls.library = Path(cls.tmpdir.name) / ("action_checker" + suffix)
        try:
            subprocess.run(
                [
                    compiler, "-std=c++17", "-O2", "-shared", "-fPIC",
                    str(ROOT / "cpp" / "action_checker.cpp"), "-o", str(cls.library),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            simulator.configure_action_checker("cpp", library_path=cls.library)
        except Exception:
            cls.tmpdir.cleanup()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        simulator.configure_action_checker("python")
        cls.tmpdir.cleanup()

    def test_expected_reasons_and_precedence(self) -> None:
        cases = [
            (World("basic"), Action("bad", "ghost"), "unknown_operator"),
            (World("basic"), Action("pick", "ghost"), "unknown_target"),
            (World("basic"), Action("fasten", "cover", None), "malformed_tool_field"),
            (World("basic", current_tool="driver", pose_known=False), Action("pick", "cover"), "pick_requires_gripper"),
            (World("basic", pose_known=False, holding="cover"), Action("pick", "cover"), "pose_unknown"),
            (World("standard", holding=None, fixture_verified=False, station_blocked_ticks=1), Action("install", "cover"), "cover_not_held"),
            (World("standard", holding="cover", fixture_verified=False, station_blocked_ticks=1), Action("install", "cover"), "fixture_not_verified"),
            (World("basic", current_tool="gripper"), Action("fasten", "cover", "gripper"), "tool_incompatible"),
            (World("basic", current_tool="gripper"), Action("fasten", "cover", "driver"), "fasten_requires_driver"),
            (World("extended", quality_pass=False, current_tool="driver"), Action("label", "assembly", "gripper"), "label_requires_gripper"),
            (World("extended", quality_pass=True, label_applied=False), Action("transfer", "assembly"), "label_not_applied"),
            (World("basic", driver_unavailable_ticks=1), Action("tool_change", "driver"), "driver_unavailable"),
            (World("basic", cover_installed=True, fastened=True, rework_required=True), Action("inspect", "assembly"), "rework_required"),
            (World("basic"), Action("rework", "assembly"), "rework_not_authorized"),
            (World("basic"), Action("observe", "cover"), None),
        ]
        for world, action, expected in cases:
            with self.subTest(world=world, action=action):
                self.assertEqual(simulator.check_action_python(world, action), expected)
                self.assertEqual(simulator.check_action(world, action), expected)

    def test_backend_configuration_fails_loudly(self) -> None:
        with self.assertRaises(ValueError):
            simulator.configure_action_checker("unknown")
        with self.assertRaises(ValueError):
            simulator.configure_action_checker("cpp")
        with self.assertRaises(FileNotFoundError):
            simulator.configure_action_checker(
                "cpp", library_path=Path(self.tmpdir.name) / "missing-library"
            )
        self.assertEqual(simulator.get_action_checker_metadata()["backend"], "cpp")

    def test_cross_language_state_and_action_matrix(self) -> None:
        rng = random.Random(918273)
        kinds = list(simulator.ACTION_COST) + ["unknown", ""]
        targets = ["cover", "driver", "gripper", "assembly", "ghost_cover", ""]
        tools = [None, "driver", "gripper", "unknown", ""]
        actions = [Action(*args) for args in itertools.product(kinds, targets, tools)]

        for _ in range(150):
            world = World(
                complexity=rng.choice(("basic", "standard", "extended")),
                pose_known=rng.choice((True, False)),
                fixture_verified=rng.choice((True, False)),
                current_tool=rng.choice(("gripper", "driver", "unknown", "")),
                holding=rng.choice((None, "cover", "other", "")),
                cover_installed=rng.choice((True, False)),
                fastened=rng.choice((True, False)),
                quality_pass=rng.choice((True, False)),
                label_applied=rng.choice((True, False)),
                transferred=rng.choice((True, False)),
                station_blocked_ticks=rng.choice((-1, 0, 1, 3)),
                driver_unavailable_ticks=rng.choice((-1, 0, 1, 3)),
                rework_required=rng.choice((True, False)),
                disturbance=rng.choice(simulator.DISTURBANCES),
                disturbance_fired=rng.choice((True, False)),
            )
            for action in actions:
                expected = simulator.check_action_python(world, action)
                actual = simulator.check_action(world, action)
                if actual != expected:
                    self.fail(f"{world!r}, {action!r}: Python={expected!r}, C++={actual!r}")

    def test_matched_episode_results_excluding_timings(self) -> None:
        scenarios = simulator.build_scenarios(
            range(1, 4), 2, 0.30, include_disturbances=True
        )
        methods = tuple(dict.fromkeys(simulator.METHODS + simulator.ABLATION_METHODS))
        simulator.configure_action_checker("python")
        try:
            expected = simulator.run_benchmark(scenarios, methods=methods)
            simulator.configure_action_checker("cpp", library_path=self.library)
            actual = simulator.run_benchmark(scenarios, methods=methods)
        finally:
            simulator.configure_action_checker("cpp", library_path=self.library)

        self.assertEqual(len(expected), len(actual))
        timing_fields = {"planning_cpu_ms", "verification_cpu_ms"}
        for python_row, cpp_row in zip(expected, actual):
            for key, value in python_row.items():
                if key not in timing_fields:
                    self.assertEqual(
                        cpp_row[key], value,
                        f"{python_row['scenario_id']}, {python_row['method']}, {key}",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
