# Release Checklist

This checklist prepares the repository for a fixed, citable release. It does
not convert the synthetic benchmark into evidence about a physical robot,
LLM/VLM, geometric planner, or safety-certified system.

## Release contents

Include the source files, final `results/` directory, final figure exports,
dependency file, release metadata, and final checksum manifest. Do not include
the unpublished `manuscript/` directory, `.venv/`, `results_smoke/`,
`results_pre_rerun_20261028/`, or LaTeX build intermediates.

## Author decisions required before release

1. Confirm code ownership and choose an SPDX license. Do not publish a license
   file until the rights holder has approved it.
2. Verify the checked-in `CITATION.cff` and `.zenodo.json` against the final
   author names, affiliations, ORCIDs, repository URL, release version, and
   license scope. Do not create a DOI field until Zenodo has minted it.
3. Create a public repository, tag an immutable release, and archive that tag in
   a DOI-minting service such as Zenodo or an institutional repository.
4. Verify that the DOI landing page, authors, version, repository URL, file list,
   license, and checksum manifest match the released files.
5. Replace the DOI, repository URL, release tag, and license placeholders in the
   manuscript, then rebuild the final PDF.

## Local verification before upload

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
audit and no source-hash mismatches. Recreate `SHA256SUMS` after the final PDF,
author information, DOI, and license have been inserted.
