# V-CRISP Synthetic Discrete-Event Assembly Benchmark

简体中文说明：[README.zh-CN.md](README.zh-CN.md)

This repository contains the reproducible artifact for a deliberately limited
synthetic discrete-event assembly benchmark. It evaluates whether a typed
candidate-plan interface, pre-dispatch modeled-constraint checking,
executor-emitted event recording, and verified suffix repair change outcomes
under declared state transitions and injected errors.

It is not a physical robot or factory experiment. It does not use an LLM, VLM,
ROS, perception, geometric task and motion planning, collision checking, or an
independently validated safety model. The pre-dispatch checker and dispatch
guard share the same modeled action semantics, so zero guard rejections is not
independent safety-validation evidence.

## Scope and methods

Each matched scenario begins from an independently reset modeled state. The
five method keys in the CSV files have the following interpretation:

- `rule_script`: fixed recipe without recovery.
- `classical_global`: oracle-state symbolic reference that rebuilds a recipe
  from the full modeled state; it is not a deployable classical planner.
- `semantic_direct`: perturbed candidate direct dispatch, without schema
  checking or recovery.
- `structured_no_verify`: perturbed structured candidate with schema checking
  and unverified current-state rebuilding, but no process/resource
  pre-dispatch checker.
- `vcrisp`: structured candidate, compiler, pre-dispatch checker,
  executor-emitted event recording, and verified suffix repair.

The candidate is a controlled stochastic perturbation of a nominal recipe, not
the output of an LLM or VLM. The modeled candidate errors are wrong tool, wrong
order, missing inspection, unknown target, and missing tool change. Scheduled
single-event disturbances are grasp failure, pose shift, station blockage,
tool unavailability, inspection reject, and low confidence. These labels are
finite-state benchmark conditions, not sensor observations or physical faults.

## Environment

The tested environment is Python 3.9.6 on arm64 macOS with NumPy 2.0.2 and
Matplotlib 3.9.4. Python 3.9 or later is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Complete local rerun

Run these commands from the repository root. The first command replaces the
authoritative `results/` outputs; do not mix files from separate runs.

```bash
python3 -m py_compile \
  simulator.py run_experiments.py analyze_results.py audit_results.py \
  generate_qualitative_trace.py make_release_manifest.py \
  figures/audit_panel_alignment.py figures/make_figure1_composite.py \
  figures/make_publication_figures.py
python3 -m unittest -v test_simulator.py
python3 run_experiments.py --output-dir results
python3 analyze_results.py --results-dir results
python3 audit_results.py --results-dir results
python3 generate_qualitative_trace.py --output-dir results/analysis
python3 figures/make_figure1_composite.py
python3 figures/make_publication_figures.py
```

The primary run has 4,800 matched scenario instances and 24,000 per-method
records. The sensitivity run has 2,400 matched instances and 12,000 records.
The default primary design uses 20 seeds, 10 reset episodes per stratum, three
recipe sizes, two no-disturbance candidate-error profiles, six disturbance
types, and five methods. The sensitivity sweep uses candidate-error rates
0.05, 0.10, 0.20, and 0.30.

## Outputs and interpretation

`results/` is the authoritative machine-readable record for one complete run.
It contains raw per-method episodes, a run manifest with source hashes,
analysis tables, bootstrap contrasts, an integrity audit, and the qualitative
trace. The principal manuscript table sources are:

- `results/analysis/table_overall.csv` -> Table IV.
- `results/analysis/table_robustness.csv` -> Table V.
- `results/analysis/table_runtime_scalability.csv` -> Table VI.

`results/analysis/integrity_audit.json` must report complete paired records,
no duplicates, and no source-hash mismatches before results are used. The
virtual makespan and event-to-completion values are abstract `action-cost`
units, not elapsed process time.

The raw field `disturbance_detected` means that the finite-state executor
reached the scheduled event and emitted its reason code. It is not a sensor
detection result. The raw field `human_intervention` is a simulated escalation
flag set when the modeled controller terminates without recovery; it is not a
measurement of a human intervention. Accordingly, results report
event-recorded and simulated-escalation rates rather than perception or human
performance.

`figures/publication/` contains the final figure exports. Fig. 1 is an
abstract three-dimensional workstation-state illustration; it explains the
modeled event flow and is not robot-simulation evidence. The production PDFs
and SVGs, together with their JSON QA records, are the figure files intended
for the release manifest. PNG, TIFF, overlay PDFs, and alignment SVGs are
rendering or QA by-products rather than canonical archival files.

## Release preparation

Create a checksum manifest only after rerunning the experiment, regenerating
the figures, and compiling the final manuscript:

```bash
python3 make_release_manifest.py
```

The manifest includes authoritative results, publication PDFs/SVGs and their
required JSON QA records, executable source, and formal release metadata. It
excludes `.venv/`, `results_smoke/`, `results_pre_rerun_20261028/`, all local
manuscript files, and noncanonical figure by-products.

The canonical repository is
[`hpz14981791992024-glitch/discrete-event-assembly-benchmark`](https://github.com/hpz14981791992024-glitch/discrete-event-assembly-benchmark).
The author-metadata release is prepared as `v1.0.1`. `CITATION.cff` and
`.zenodo.json` identify Pengzhi Hong and Jiaming Zhang of the Shenyang
University of Chemical Technology. A version-specific DOI can only be stated
after the release has been archived by Zenodo or another DOI-minting service;
it is intentionally absent until that occurs. See `RELEASE_CHECKLIST.md` for
the remaining archival steps.

## License

The executable source code is licensed under Apache-2.0; see `LICENSE`.
The synthetic benchmark records in `results/` and publication figure exports
are licensed under CC-BY-4.0; see `LICENSE-DATA`. The unpublished manuscript
is retained locally and is not part of this public artifact.

Neither license changes the evidence boundary of this project: the released
records support only the declared synthetic discrete-event benchmark.

## Evidence boundary

These data are genuine outputs of the local simulation, but support only the
declared finite-state benchmark claim. They must not be described as factory
data, physical-robot data, real LLM/VLM performance, geometric feasibility,
collision avoidance, independent safety verification, safety certification,
or deployment readiness.
