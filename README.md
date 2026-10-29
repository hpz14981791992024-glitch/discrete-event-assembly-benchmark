# V-CRISP Synthetic Discrete-Event Assembly Benchmark

[简体中文](README.zh-CN.md)

V-CRISP is a small, reproducible benchmark for studying plan checking and
recovery in a synthetic assembly workflow. It compares several ways of
handling an imperfect candidate plan after the modeled environment changes.
The goal is to make the experimental logic easy to inspect, rerun, and adapt.

The benchmark is intentionally narrow. It is a finite-state simulation, not a
physical robot or factory study. It does not use LLMs, VLMs, ROS, perception,
geometric motion planning, collision checking, or an independently validated
safety model. Its results should therefore be read as evidence about the
declared simulation only.

## What is included

Each scenario starts from a freshly reset modeled state. A nominal assembly
recipe is perturbed to create a candidate plan, then evaluated by one of five
methods:

- `rule_script`: follows a fixed recipe and does not recover from errors.
- `classical_global`: rebuilds a recipe from the complete modeled state; this
  is an oracle-style reference rather than a deployable planner.
- `semantic_direct`: dispatches the perturbed candidate directly, without
  schema checks or recovery.
- `structured_no_verify`: checks the candidate schema and rebuilds from the
  current modeled state, but does not run process or resource checks before
  dispatch.
- `vcrisp`: uses a structured candidate, a compiler, pre-dispatch checks,
  executor event records, and verified suffix repair.

The component ablation reuses the same 4,800 scenario identifiers and compares
four configurations: `structured_no_verify`, initial checking only
(`checker_only`), runtime suffix verification only (`repair_only`), and the
full `vcrisp` configuration. The ablation is a timing comparison within the
same finite-state semantics; it is not a comparison of independently
validated safety models.

Candidate-plan errors include a wrong tool, wrong order, omitted inspection,
unknown target, and omitted tool change. A scenario can also contain one
scheduled disturbance: grasp failure, pose shift, station blockage, tool
unavailability, inspection rejection, or low confidence. These are named
finite-state conditions, not physical faults or sensor observations.

## Requirements

The reference run was made with Python 3.9.6 on arm64 macOS, NumPy 2.0.2, and
Matplotlib 3.9.4. Python 3.9 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Reproduce the benchmark

Run the following from the repository root. `run_experiments.py` replaces the
authoritative contents of `results/`, so do not combine outputs from separate
runs.

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

The main experiment contains 4,800 matched scenarios and 24,000 method-level
records. It covers 20 random seeds, 10 reset episodes per stratum, three recipe
sizes, two candidate-error profiles without disturbances, six disturbance
types, and five methods. The sensitivity experiment contains 2,400 matched
scenarios and 12,000 records, and sweeps candidate-error rates of 0.05, 0.10,
0.20, and 0.30.

The component ablation contains 4,800 matched scenarios and 19,200 records
(four configurations per scenario). Its summary and paired bootstrap tables
are `results/analysis/table_component_ablation.csv` and
`results/analysis/component_ablation_bootstrap.csv`.

## Read the outputs

`results/` is the machine-readable record of a completed run. It includes raw
episode records, source hashes, analysis tables, paired bootstrap contrasts, an
integrity audit, and a qualitative trace. The main summary tables are:

- `results/analysis/table_overall.csv`
- `results/analysis/table_robustness.csv`
- `results/analysis/table_runtime_scalability.csv`

Before using a run, check
`results/analysis/integrity_audit.json`. It should report complete matched
records, no duplicates, and no source-hash mismatches.

Virtual makespan fields use abstract action-cost units, not manufacturing time.
The historical fields named `planning_cpu_ms` and `verification_cpu_ms` record
local elapsed time from `time.perf_counter()`, not CPU time. Similarly, `disturbance_detected` means the
executor reached the scheduled state and recorded a reason code; it is not a
sensor-detection result. `human_intervention` is a simulated escalation flag
when recovery does not occur, not a measurement of human work.

`figures/publication/` contains the publication figure exports. Figure 1 is an
abstract three-dimensional workstation-state illustration used to explain the
event flow; it is not robot-simulation or physical-robot evidence. The PDF and
SVG figure files, with their JSON quality records, are the archival versions.

## Citation and releases

Use `CITATION.cff` when citing this repository. The immutable `v1.0.1` release
is archived by Zenodo at
[10.5281/zenodo.23766150](https://doi.org/10.5281/zenodo.23766150), but it does
not contain the component-ablation results. Version `v1.0.2` is archived at
[10.5281/zenodo.23768078](https://doi.org/10.5281/zenodo.23768078); use this
version DOI to identify the results in the current release. The
[concept DOI](https://doi.org/10.5281/zenodo.23766149) resolves to the latest
Zenodo version. The version DOI was added to this branch after the immutable
release was archived.

To create a checksum manifest after a full rerun and figure regeneration:

```bash
python3 make_release_manifest.py
```

`SHA256SUMS` covers the release files, including executable source,
authoritative results, publication figures, licenses, and release metadata.

## License

The source code is available under the [Apache-2.0 license](LICENSE). Synthetic
benchmark records in `results/` and publication figure exports are available
under [CC BY 4.0](LICENSE-DATA).

These licenses govern reuse; they do not expand the scope of the experimental
evidence. The repository does not support claims about factory data, physical
robots, real LLM or VLM performance, geometric feasibility, collision
avoidance, independent safety verification, safety certification, or deployment
readiness.
