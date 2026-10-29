# MuJoCo planar reaching experiment

This experiment models a two-joint arm and a fixed cylindrical obstacle. The
goal represents a location the arm must reach during an assembly task. It does
not model a gripper, object grasping, insertion, robot hardware, or a factory.

Each scenario has a target and an obstacle. Two policies start from the same
joint state. `direct` interpolates directly to the inverse-kinematics solution.
`checked_waypoints` tests the direct path and then a fixed list of two-segment
paths. Candidate configurations are checked using MuJoCo's collision model.
The first path without sampled contact is executed. If none is found, the run
is counted as a failure with `no_candidate_path` and no motion is executed.

MuJoCo simulates joint actuation and rigid-body contact. Success requires the
tool tip to finish within 0.02 m of the target with no arm-obstacle contact
at any simulation step. The obstacle is stationary. Candidate collision checks
use the same MuJoCo model as execution, so they do not validate an independent
safety model. The waypoint list is a simple finite search, not a general
motion planner. Planning time is a local elapsed-time diagnostic.

On macOS or Linux, from the repository root:

```bash
python3 -m venv robot_sim/.venv
robot_sim/.venv/bin/python -m pip install -r robot_sim/requirements.txt
robot_sim/.venv/bin/python -m unittest discover -s robot_sim -p 'test_*.py' -v
robot_sim/.venv/bin/python robot_sim/experiment.py --output NEW_EMPTY_DIRECTORY --count 300 --seed 20261029
robot_sim/.venv/bin/python robot_sim/analyze.py --results NEW_EMPTY_DIRECTORY --output NEW_EMPTY_DIRECTORY/summary.json
robot_sim/.venv/bin/python robot_sim/diagnose.py --results NEW_EMPTY_DIRECTORY --output NEW_EMPTY_DIRECTORY/endpoint_diagnostics.json
```

The output directory must be new or empty. `episodes.csv` contains one row per
policy and scenario. `manifest.json` records versions, seed, parameters, and
the script hash. MuJoCo is distributed under Apache-2.0. This experiment uses
MuJoCo 3.3.7 and NumPy 2.0.2.
