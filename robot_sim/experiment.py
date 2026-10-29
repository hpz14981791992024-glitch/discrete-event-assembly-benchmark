"""Matched MuJoCo reaching experiment with a planar two-link arm."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import platform
import sys
import time
from pathlib import Path

import mujoco
import numpy as np


XML = """
<mujoco model="planar_assembly_arm">
  <compiler angle="radian"/>
  <option timestep="0.002" gravity="0 0 -9.81" integrator="implicitfast"/>
  <default>
    <joint damping="1" armature="0.01"/>
    <geom friction="0.7 0.01 0.001"/>
  </default>
  <worldbody>
    <body name="base" pos="0 0 0.15">
      <body name="upper">
        <joint name="shoulder" type="hinge" axis="0 0 1"/>
        <geom name="link1" type="capsule" fromto="0 0 0 0.4 0 0" size="0.018" mass="1"/>
        <body name="forearm" pos="0.4 0 0">
          <joint name="elbow" type="hinge" axis="0 0 1"/>
          <geom name="link2" type="capsule" fromto="0 0 0 0.3 0 0" size="0.018" mass="0.7"/>
          <site name="tool_tip" pos="0.3 0 0" size="0.01"/>
        </body>
      </body>
    </body>
    <body name="obstacle" mocap="true" pos="0.4 0.2 0.15">
      <geom name="obstacle_geom" type="cylinder" size="0.045 0.1"/>
    </body>
  </worldbody>
  <actuator>
    <position name="shoulder_motor" joint="shoulder" kp="80"/>
    <position name="elbow_motor" joint="elbow" kp="50"/>
  </actuator>
</mujoco>
"""

DT = 0.002
SEGMENT_STEPS = 500
SETTLE_STEPS = 500
TARGET_TOLERANCE = 0.02
SAMPLES_PER_RADIAN = 50
WAYPOINTS = [(a, b) for a in (-1.4, -0.7, 0.0, 0.7, 1.4, 2.1)
             for b in (-2.0, -1.0, 0.0, 1.0, 2.0)]


def inverse_kinematics(x: float, y: float) -> np.ndarray:
    cos_elbow = (x*x + y*y - 0.4**2 - 0.3**2) / (2 * 0.4 * 0.3)
    if abs(cos_elbow) > 1:
        raise ValueError("target is outside the arm workspace")
    elbow = math.acos(cos_elbow)
    shoulder = math.atan2(y, x) - math.atan2(0.3 * math.sin(elbow), 0.4 + 0.3 * math.cos(elbow))
    return np.array([shoulder, elbow])


def collision(model, data) -> bool:
    obstacle = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, "obstacle_geom")
    links = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_GEOM, name)
             for name in ("link1", "link2")}
    return any((c.geom1 == obstacle and c.geom2 in links) or
               (c.geom2 == obstacle and c.geom1 in links) for c in data.contact)


def path_collision_free(model, data, path) -> bool:
    for start, end in zip(path, path[1:]):
        count = max(2, int(math.ceil(np.max(np.abs(end - start)) * SAMPLES_PER_RADIAN)) + 1)
        for alpha in np.linspace(0.0, 1.0, count):
            data.qpos[:] = start + alpha * (end - start)
            data.qvel[:] = 0
            mujoco.mj_forward(model, data)
            if collision(model, data):
                return False
    return True


def choose_path(model, obstacle, goal):
    data = mujoco.MjData(model)
    data.mocap_pos[0] = [obstacle[0], obstacle[1], 0.15]
    start = np.zeros(2)
    candidates = [[start, goal]] + [[start, np.array(w), goal] for w in WAYPOINTS]
    for path in candidates:
        if path_collision_free(model, data, path):
            return path
    return None


def execute(model, obstacle, target, path):
    data = mujoco.MjData(model)
    data.mocap_pos[0] = [obstacle[0], obstacle[1], 0.15]
    mujoco.mj_forward(model, data)
    contact_steps = 0
    for start, end in zip(path, path[1:]):
        for alpha in np.linspace(0.0, 1.0, SEGMENT_STEPS):
            data.ctrl[:] = start + alpha * (end - start)
            mujoco.mj_step(model, data)
            contact_steps += int(collision(model, data))
    for _ in range(SETTLE_STEPS):
        data.ctrl[:] = path[-1]
        mujoco.mj_step(model, data)
        contact_steps += int(collision(model, data))
    mujoco.mj_forward(model, data)
    site = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_SITE, "tool_tip")
    error = float(np.linalg.norm(data.site_xpos[site, :2] - target))
    return error, contact_steps, float(data.time)


def scenarios(count: int, seed: int):
    rng = np.random.default_rng(seed)
    for index in range(count):
        angle = rng.uniform(0.25, 1.25)
        radius = rng.uniform(0.38, 0.62)
        target = np.array([radius * math.cos(angle), radius * math.sin(angle)])
        obstacle = np.array([rng.uniform(0.25, 0.58), rng.uniform(0.08, 0.35)])
        yield index, target, obstacle


def run(count: int, seed: int):
    model = mujoco.MjModel.from_xml_string(XML)
    rows = []
    for index, target, obstacle in scenarios(count, seed):
        goal = inverse_kinematics(*target)
        for policy in ("direct", "checked_waypoints"):
            start = time.perf_counter()
            path = [np.zeros(2), goal] if policy == "direct" else choose_path(model, obstacle, goal)
            planning_ms = (time.perf_counter() - start) * 1000
            if path is None:
                error, contact_steps, sim_seconds, success, status = None, 0, 0.0, False, "no_candidate_path"
            else:
                error, contact_steps, sim_seconds = execute(model, obstacle, target, path)
                success = error <= TARGET_TOLERANCE and contact_steps == 0
                status = "success" if success else ("contact" if contact_steps else "target_error")
            rows.append({"scenario": index, "policy": policy, "target_x": target[0], "target_y": target[1],
                         "obstacle_x": obstacle[0], "obstacle_y": obstacle[1], "success": success,
                         "status": status, "target_error_m": error, "contact_steps": contact_steps,
                         "simulation_seconds": sim_seconds, "planning_elapsed_ms": planning_ms})
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("count must be positive")
    if args.output.exists() and any(args.output.iterdir()):
        parser.error("output directory must be empty")
    args.output.mkdir(parents=True, exist_ok=True)
    rows = run(args.count, args.seed)
    with (args.output / "episodes.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    source = Path(__file__).read_bytes()
    manifest = {"mujoco_version": mujoco.__version__, "numpy_version": np.__version__,
                "python": sys.version, "platform": platform.platform(), "seed": args.seed,
                "scenarios": args.count, "records": len(rows), "timestep_seconds": DT,
                "segment_steps": SEGMENT_STEPS, "settle_steps": SETTLE_STEPS,
                "target_tolerance_m": TARGET_TOLERANCE, "collision_samples_per_radian": SAMPLES_PER_RADIAN,
                "script_sha256": hashlib.sha256(source).hexdigest(),
                "scope": "planar arm reaching; no grasp, physical cell, or industrial safety validation"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for policy in ("direct", "checked_waypoints"):
        group = [r for r in rows if r["policy"] == policy]
        print(policy, "success", sum(r["success"] for r in group), "/", len(group),
              "contact", sum(r["contact_steps"] > 0 for r in group),
              "no_path", sum(r["status"] == "no_candidate_path" for r in group))


if __name__ == "__main__":
    main()
