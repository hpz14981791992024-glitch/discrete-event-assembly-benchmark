# V-CRISP Synthetic Discrete-Event Assembly Benchmark

[简体中文](README.zh-CN.md)

This benchmark compares plan checking and recovery in a simulated assembly
cell. The repository includes the simulator, experiment records, analysis
scripts, and figures.

The scenarios use a finite-state model. They do not include a physical robot,
perception, a language model, or geometric planning. The checker is not an
independent safety model. Results apply to the rules in this repository.

## What is included

Each scenario starts from a reset state. The simulator creates a candidate plan
from a nominal recipe. Some candidates contain an injected error. The main
experiment compares five methods:

- `rule_script`: follows a fixed recipe and does not recover from errors.
- `classical_global`: rebuilds a recipe from the complete modeled state. This
  is an oracle-style reference, not a deployable planner.
- `semantic_direct`: dispatches the perturbed candidate directly, without
  schema checks or recovery.
- `structured_no_verify`: checks the candidate schema and can rebuild the
  recipe from the current state. It skips process and resource checks before
  dispatch.
- `vcrisp`: uses a structured candidate, a compiler, pre-dispatch checks,
  executor event records, and verified suffix repair.

Candidate errors include wrong tools, wrong ordering, omitted steps, and
unknown targets. A scenario may also include one modeled disturbance. These
cover grasp failure, pose shift, station blockage, tool unavailability,
inspection rejection, and low confidence.

The component ablation uses the same 4,800 scenarios. It compares four
configurations: `structured_no_verify`, `checker_only`, `repair_only`, and
`vcrisp`. The checker and dispatch guard use the same action rules. This
ablation does not test an independent verifier.

## Requirements

The reference run was made with Python 3.9.6 on arm64 macOS, NumPy 2.0.2, and
Matplotlib 3.9.4. Python 3.9 or newer is required. The optional C++ checker
also requires a C++17 compiler.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
```

## Reproduce the benchmark

Run these commands from the repository root. The experiment command replaces
files in `results/`. Keep a copy elsewhere if you need the previous run.

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

The default checker uses Python, as in the archived v1.0.2 run. To use the C++
checker, build the library and choose a new output directory:

```bash
mkdir -p build
c++ -std=c++17 -O2 -fPIC -shared cpp/action_checker.cpp -o build/action_checker.so
python3 -m unittest -v test_cpp_checker.py
python3 run_experiments.py --checker-backend cpp --checker-library build/action_checker.so --output-dir results_cpp
python3 analyze_results.py --results-dir results_cpp
python3 audit_results.py --results-dir results_cpp
```

Python handles scenario generation, execution, repair, and analysis. Both
verification and dispatch use the selected checker. The C++ backend is not an
independent safety verifier. The run manifest records the backend, compiler,
and library hash. C++ runs need a new or empty output directory.

`results_cpp/` contains a C++ checker run on the same scenarios as v1.0.2.
`compare_backends.py` compares its non-timing fields with the archived Python
records. `results_model_mismatch/` contains 16 hand-built cases with paired
checker and guard rules. Run the latter with:

```bash
python3 -m unittest -v test_compare_backends.py test_model_mismatch_experiment.py
python3 model_mismatch_experiment.py --output-dir NEW_EMPTY_DIRECTORY
python3 compare_backends.py PATH_TO_V1_0_2_RESULTS results_cpp --output comparison.json
```

`robot_sim/` contains a separate MuJoCo planar reaching comparison. It does not
run V-CRISP. See [robot_sim/README.md](robot_sim/README.md) for setup and scope.

The main run has 4,800 matched scenarios and 24,000 method records. It uses
20 seeds and 10 reset episodes per stratum. It covers three recipe sizes, two
candidate-error profiles without disturbances, and six disturbance types.
The component ablation adds 19,200 records for the same 4,800 scenarios.
The sensitivity run has 2,400 scenarios and 12,000 records. It tests candidate
error rates of 0.05, 0.10, 0.20, and 0.30.

## Read the outputs

The raw episodes are in `results/episodes_main.csv`,
`results/episodes_component_ablation.csv`, and `results/episodes_sensitivity.csv`.
The `results/analysis/` directory contains summary tables, paired bootstrap
contrasts, and a qualitative trace. Start with:

- `table_overall.csv`: main comparison.
- `table_component_ablation.csv` and `component_ablation_bootstrap.csv`: component comparison.
- `table_robustness.csv`: outcomes by disturbance.
- `table_sensitivity.csv`: outcomes by candidate-error rate.
- `table_runtime_scalability.csv`: local timing and virtual makespan by recipe size.
- `integrity_audit.json`: pairing, duplicate, and source-hash checks.

Check that `integrity_audit.json` reports a passing audit before using a run.
The bundled `results/` records were generated from the archived v1.0.2 tag.
Use that tag to audit their source hashes. New runs have their own manifests.

Virtual makespan fields use abstract action-cost units, not manufacturing time.
The historical fields named `planning_cpu_ms` and `verification_cpu_ms` record
local elapsed time from `time.perf_counter()`, not CPU time.
`disturbance_detected` records a scheduled state-machine event. It is not a
sensor result. `human_intervention` marks simulated escalation. It does not
measure human work.

`figures/publication/` contains the PDF and SVG figure exports and their JSON
quality records. Figure 1 is an illustrative 3D view of an abstract cell, not a
robot simulation or physical experiment.

## Citation and releases

Use `CITATION.cff` to cite the repository. The archive containing the component
ablation is [v1.0.2, DOI 10.5281/zenodo.23768078](https://doi.org/10.5281/zenodo.23768078).
That archive predates the C++ checker and contains the Python implementation.
[v1.0.3, DOI 10.5281/zenodo.23770139](https://doi.org/10.5281/zenodo.23770139)
adds the C++ run, checker/guard mismatch cases, and a separate MuJoCo reaching
experiment.
The earlier [v1.0.1 archive](https://doi.org/10.5281/zenodo.23766150) does not
include that ablation. The [concept DOI](https://doi.org/10.5281/zenodo.23766149)
points to the latest Zenodo version.

To create a checksum manifest after a full rerun and figure regeneration:

```bash
python3 make_extended_manifest.py
```

`SHA256SUMS` covers the release files, including executable source,
authoritative results, publication figures, licenses, and release metadata.

## License

The source code is available under the [Apache-2.0 license](LICENSE). Synthetic
benchmark records in `results/` and publication figure exports are available
under [CC BY 4.0](LICENSE-DATA).
