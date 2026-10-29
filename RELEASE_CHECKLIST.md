# Release Status and Next-Release Checklist

This repository has an immutable public release: `v1.0.1`, archived by Zenodo
at [10.5281/zenodo.23766150](https://doi.org/10.5281/zenodo.23766150). The
[concept DOI](https://doi.org/10.5281/zenodo.23766149) resolves to the latest
Zenodo version. Do not move, delete, or recreate the `v1.0.1` tag: its archive
and version DOI refer to the files fixed at that tag.

The archive contains code, synthetic results, publication figures, metadata,
licenses, and checksums. It does not contain the unpublished `manuscript/`
directory, `.venv/`, `results_smoke/`, `results_pre_rerun_20261028/`, or LaTeX
build intermediates. Archival does not turn this finite-state benchmark into
evidence about a physical robot, LLM/VLM, geometric planner, or
safety-certified system.

## v1.0.2 release

1. Confirm the intended public files and leave the unpublished `manuscript/`
   directory out of the release.
2. Rerun the tests and regenerate the authoritative results and publication
   figures.
3. Update `CITATION.cff`, `.zenodo.json`, README files, version numbers, and
   license metadata for the new release. Do not guess its version DOI.
4. Run `python3 make_release_manifest.py`, review `SHA256SUMS`, commit all
   intended changes, then create and push a new immutable Git tag.
5. After Zenodo has archived the new tag, verify its landing page, files,
   version, creators, repository URL, licenses, and DOI. Only then add that
   version DOI to the repository documentation, citation metadata, and the
   local manuscript.

The release candidate contains the regenerated main, sensitivity, and matched
component-ablation records. `v1.0.1` remains frozen and must not be moved,
deleted, or recreated. The `v1.0.2` DOI is deliberately absent until Zenodo
confirms the archive; never infer it from a tag name or a previous DOI.

## Local verification

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest -v test_simulator.py
python3 run_experiments.py --output-dir results
python3 analyze_results.py --results-dir results
python3 audit_results.py --results-dir results
python3 generate_qualitative_trace.py --output-dir results/analysis
python3 figures/make_figure1_composite.py
python3 figures/make_publication_figures.py
```

The `results/analysis/integrity_audit.json` file must report a passing pairing
audit and no source-hash mismatches. Regenerate `SHA256SUMS` after every change
to a file intended for the next release.
