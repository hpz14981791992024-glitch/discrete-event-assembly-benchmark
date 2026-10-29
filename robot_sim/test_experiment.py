import unittest

import mujoco
import numpy as np

import experiment


class ReachingExperimentTests(unittest.TestCase):
    def setUp(self):
        self.model = mujoco.MjModel.from_xml_string(experiment.XML)

    def test_inverse_kinematics_matches_tip(self):
        data = mujoco.MjData(self.model)
        target = np.array([0.40, 0.25])
        data.qpos[:] = experiment.inverse_kinematics(*target)
        mujoco.mj_forward(self.model, data)
        tip = mujoco.mj_name2id(self.model, mujoco.mjtObj.mjOBJ_SITE, "tool_tip")
        np.testing.assert_allclose(data.site_xpos[tip, :2], target, atol=1e-12)

    def test_contact_detection_and_candidate(self):
        data = mujoco.MjData(self.model)
        data.mocap_pos[0] = [0.35, 0.0, 0.15]
        mujoco.mj_forward(self.model, data)
        self.assertTrue(experiment.collision(self.model, data))
        goal = experiment.inverse_kinematics(0.40, 0.25)
        path = experiment.choose_path(self.model, [0.35, 0.0], goal)
        self.assertIsNone(path)

    def test_seed_and_outcomes_are_reproducible(self):
        first = experiment.run(4, 27)
        second = experiment.run(4, 27)
        self.assertEqual(len(first), 8)
        for a, b in zip(first, second):
            for key in a:
                if key != "planning_elapsed_ms":
                    self.assertEqual(a[key], b[key], key)


if __name__ == "__main__":
    unittest.main()
