# Controlled checker/guard model mismatch

This experiment tests a specific failure mode: the pre-dispatch checker omits
one modeled rejection reason while the executor keeps the original guard.
It uses `simulator.verify_and_repair`, `remaining_plan`, and the original
`execute_action`. There are no scheduled disturbances or stochastic draws.

The 16 hand-constructed cases cover fixture verification (2 recipe classes),
mounted-driver availability (3 classes), and the quality gate (3 classes).
Each class has one invalid candidate and one valid control. Each case is run
twice from the same initial state: with a matched checker, and with the target
checker reason suppressed. This creates 32 records, not 32 independent
random samples. No confidence intervals or population claims are made.

| Target reason | Invalid cases | Matched checker misses | Mismatched checker misses | Matched guard rejections | Mismatched guard rejections |
|---|---:|---:|---:|---:|---:|
| `fixture_not_verified` | 2 | 0 | 2 | 0 | 2 |
| `fasten_requires_driver` | 3 | 0 | 3 | 0 | 3 |
| `quality_not_passed` | 3 | 0 | 3 | 0 | 3 |

All 32 runs reached the modeled goal. All eight valid controls had no guard
rejections in either condition. For each invalid candidate, the matched
checker replaced the invalid first action before dispatch. The mismatched
checker retained it, the guard rejected it, and the policy recovered once.
Virtual action cost was equal within every matched pair because rejected
attempts carry no action cost in this model. This does not establish equal
real-world time or cost.

The guard uses the same declared semantics as the original Python checker.
Suppressing one reason is a deliberate mutation of that checker, not a
separately validated safety model. Rejections happen before state mutation;
they are not physical incidents or executed safety violations. The cases
were constructed to expose the selected mutations, so their counts do not
estimate operational failure rates.

Reproduce from the repository root:

```bash
python3 -m unittest -v test_model_mismatch_experiment.py
python3 model_mismatch_experiment.py --output-dir NEW_EMPTY_DIRECTORY
```

`episodes.csv` includes initial states, candidates, authorized plans and
dispatch traces. `summary.csv` aggregates counts. `manifest.json` records
runtime, model mutations and source hashes.
