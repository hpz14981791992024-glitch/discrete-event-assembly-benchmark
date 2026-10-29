"""Inspect endpoint contacts and replay checked paths with execution contact."""

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import mujoco
import numpy as np

import experiment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    with (args.results / "episodes.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    model = mujoco.MjModel.from_xml_string(experiment.XML)
    counts = Counter()
    contact_replays = []
    for row in rows:
        target = np.array([float(row["target_x"]), float(row["target_y"])])
        obstacle = [float(row["obstacle_x"]), float(row["obstacle_y"])]
        goal = experiment.inverse_kinematics(*target)
        data = mujoco.MjData(model)
        data.mocap_pos[0] = [*obstacle, 0.15]
        mujoco.mj_forward(model, data)
        start_contact = experiment.collision(model, data)
        data.qpos[:] = goal
        mujoco.mj_forward(model, data)
        goal_contact = experiment.collision(model, data)
        counts[(str(start_contact), str(goal_contact), row["policy"], row["status"])] += 1
        if row["policy"] != "checked_waypoints" or row["status"] != "contact":
            continue
        path = experiment.choose_path(model, obstacle, goal)
        if path is None:
            raise ValueError(f"path replay failed for scenario {row['scenario']}")
        data = mujoco.MjData(model)
        data.mocap_pos[0] = [*obstacle, 0.15]
        mujoco.mj_forward(model, data)
        first_contact = None
        contact_steps = 0
        for start, end in zip(path, path[1:]):
            for alpha in np.linspace(0.0, 1.0, experiment.SEGMENT_STEPS):
                command = start + alpha * (end - start)
                data.ctrl[:] = command
                mujoco.mj_step(model, data)
                if experiment.collision(model, data):
                    contact_steps += 1
                    if first_contact is None:
                        first_contact = {"time_seconds": float(data.time),
                                         "max_joint_tracking_error_rad": float(np.max(np.abs(data.qpos - command)))}
        for _ in range(experiment.SETTLE_STEPS):
            data.ctrl[:] = path[-1]
            mujoco.mj_step(model, data)
            if experiment.collision(model, data):
                contact_steps += 1
                if first_contact is None:
                    first_contact = {"time_seconds": float(data.time),
                                     "max_joint_tracking_error_rad": float(np.max(np.abs(data.qpos - path[-1])))}
        if contact_steps != int(row["contact_steps"]):
            raise ValueError(f"contact replay mismatch for scenario {row['scenario']}")
        contact_replays.append({"scenario": int(row["scenario"]), "segments": len(path) - 1,
                                "start_contact": start_contact, "goal_contact": goal_contact,
                                "contact_steps": contact_steps, "first_contact": first_contact})
    summary = {"mujoco_version": mujoco.__version__,
        "diagnostic_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "experiment_script_sha256": hashlib.sha256(Path(experiment.__file__).read_bytes()).hexdigest(),
        "episodes_sha256": hashlib.sha256((args.results / "episodes.csv").read_bytes()).hexdigest(),
        "endpoint_status_counts": [
        {"start_contact": k[0] == "True", "goal_contact": k[1] == "True",
         "policy": k[2], "status": k[3], "count": n}
        for k, n in sorted(counts.items())], "checked_execution_contact_replays": contact_replays}
    output = json.dumps(summary, indent=2) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(output)
    print(output, end="")


if __name__ == "__main__":
    main()
