# V-CRISP Synthetic Discrete-Event Assembly Benchmark

[简体中文](README.zh-CN.md)

This repository contains a finite-state assembly benchmark for comparing plan
checking and recovery policies. It includes the simulator, episode records,
analysis scripts, and figures from the reference run.

The scenarios are synthetic. The benchmark has no physical robot, perception,
language model, geometric planner, or independently validated safety model.
Results describe behavior under the rules implemented here.

## What is included

Each scenario starts from a reset state. A candidate plan is generated from a
nominal recipe, with an error injected in some scenarios. The main experiment
compares five methods:

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

Candidate errors cover wrong tools or ordering, omitted inspection or tool
changes, and unknown targets. Scenarios may also schedule one of six modeled
disturbances: grasp failure, pose shift, station blockage, tool unavailability,
inspection rejection, or low confidence.

The component ablation compares `structured_no_verify`, initial checking only
(`checker_only`), runtime suffix verification only (`repair_only`), and full
`vcrisp` on the same 4,800 scenarios. The checker and dispatch guard share the
same action rules, so the ablation does not test an independent verifier.

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

Run these commands from the repository root. The experiment command replaces
files in `results/`; keep a copy elsewhere if you need to retain a previous run.

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

The main run has 4,800 matched scenarios and 24,000 method records. It uses
20 seeds, 10 reset episodes per stratum, three recipe sizes, two candidate-error
profiles without disturbances, and six disturbance types. The component
ablation adds 19,200 records for those 4,800 scenarios. The sensitivity run has
2,400 scenarios and 12,000 records across candidate-error rates of 0.05, 0.10,
0.20, and 0.30.

## Read the outputs

The raw episode files are `results/episodes_main.csv`,
`results/episodes_component_ablation.csv`, and `results/episodes_sensitivity.csv`.
The `results/analysis/` directory contains summary tables, paired bootstrap
contrasts, and a qualitative trace. Useful starting points are:

- `table_overall.csv`: main comparison.
- `table_component_ablation.csv` and `component_ablation_bootstrap.csv`: component comparison.
- `table_robustness.csv`: outcomes by disturbance.
- `table_sensitivity.csv`: outcomes by candidate-error rate.
- `table_runtime_scalability.csv`: local timing and virtual makespan by recipe size.
- `integrity_audit.json`: pairing, duplicate, and source-hash checks.

Check that `integrity_audit.json` reports a passing audit before using a run.

Virtual makespan fields use abstract action-cost units, not manufacturing time.
The historical fields named `planning_cpu_ms` and `verification_cpu_ms` record
local elapsed time from `time.perf_counter()`, not CPU time.
`disturbance_detected` records a scheduled state-machine event, not sensor
detection. `human_intervention` is a simulated escalation flag, not a measure
of human work.

`figures/publication/` contains the PDF and SVG figure exports and their JSON
quality records. Figure 1 is an illustrative 3D view of an abstract cell, not a
robot simulation or physical experiment.

## Citation and releases

Use `CITATION.cff` to cite the repository. The archive containing the component
ablation is [v1.0.2, DOI 10.5281/zenodo.23768078](https://doi.org/10.5281/zenodo.23768078).
The earlier [v1.0.1 archive](https://doi.org/10.5281/zenodo.23766150) does not
include that ablation. The [concept DOI](https://doi.org/10.5281/zenodo.23766149)
points to the latest Zenodo version.

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
