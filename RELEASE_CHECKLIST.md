# Release Status and Checklist

The current archived release is
[`v1.0.2`](https://doi.org/10.5281/zenodo.23768078), which includes the main,
sensitivity, and component-ablation records. The earlier
[`v1.0.1`](https://doi.org/10.5281/zenodo.23766150) does not include the
component ablation. The [concept DOI](https://doi.org/10.5281/zenodo.23766149)
points to the latest Zenodo version.

The archive contains code, synthetic results, publication figures, metadata,
licenses, and checksums. The unpublished `manuscript/`, local environment,
scratch results, and LaTeX build files are excluded. Do not move, delete, or
recreate an archived tag.

## Before the next release

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

The `v1.0.2` DOI was added to the main branch after archival; its frozen tag
therefore does not contain the DOI in `CITATION.cff`.

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
