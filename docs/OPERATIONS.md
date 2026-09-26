# Reproducible builds, checkpoints and evidence

## Commands

From the extracted project root:

```bash
python tools/run_checks.py
python tools/run_demo.py
python tools/numerical_checks.py
python tools/transport_checks.py
python tools/prepare_training_fixture.py --output runs/my-training-fixture
python tools/training_manifest.py validate --manifest runs/my-training-fixture/manifest.json
python tools/train_response_baseline.py --output runs/my-response-baseline
python tools/run_rule_demo.py --inspect configs/biological_rules.oxygen.template.json
python tools/run_rule_demo.py --output runs/my-rule-demo
python tools/check_manifest.py
```

The first command records test names/outcomes, raw logs, numerical outputs, interpreter/platform and a source/test/tool fingerprint in a new `runs/` directory. A nonzero status means some check failed; it must not be reinterpreted as a passing biological model. New runs are not included in the immutable release manifest.

Current prototype evidence in `runs/prototype_rules_checks/` records Windows 11,
Python 3.12.6 and CPU execution: 137 tests, 136 passed, zero failures/errors and
one symlink privilege skip. `runs/groundwork_final/` preserves the earlier
135-test groundwork record. The unchanged historical `evidence/final_run/`
records 76 passing tests on Linux x86-64 with Python 3.13.5; it does not exercise
the new code. Python 3.10+ compatibility is intended but not exercised across a
version matrix. No external package, GPU or special device was required.
Optional `pip install -e .` uses a build frontend and setuptools; it was not used
for these runs. See `PROTOTYPE_REPORT.md` for the learning and rules commands,
results, and coverage limits.

## What the checks cover

Unit and regression cases test interval timing, subcycling, pair symmetry/order, division conservation/IDs, invalid values, amount conversions, explicit sources/sinks, transaction failure, evidence rejection, and JSON world/RNG continuation. New cases cover fixed 3D transport, saturable transfer, geometry/roundoff failures, grouped dataset declarations, artifact integrity and candidate snapshots. Numerical studies compare decay, periodic diffusion, steady radial uptake and closed 3D cosine modes with analytical solutions. None compares to a biological dataset.

The training fixture exporter refuses existing output directories and retains failed attempts. It records configuration, source identity, rows, grouped split declarations, amount balances and measured preparation costs. Manifest validation checks declarations and whole-file hashes; arbitrary observation payload ingestion and experiment authentication remain external responsibilities. Candidate freeze/verify commands record and check identity without training or executing a model. Keep the original campaign digest independently and provide stable files during evaluation. See `TRAINING_SETUP.md` for exact CLI usage and measurement limits.

A fresh interpreter repeats the demo; a dedicated test checks checkpoint loading and continued evolution in a child interpreter. Cross-platform or cross-precision bitwise identity is not promised. GPU execution, specialist restart and failed distributed coupling are not tested.

## Checkpoint content and limits

The current JSON checkpoint stores world state, the standard-library random generator state, a required caller-supplied execution fingerprint, and a caller-supplied JSON dictionary for private data. It contains no pickle or executable model code. It checks content hash, format and fingerprint before returning a restored object.

A caller-supplied string is not automatically a robust fingerprint: production callers must hash model, parameters, code, process order, numerical settings, schema and relevant environment. Existing tests use named fixture fingerprints. `run_checks.py` separately computes a hash of the source, tests and tools used for its execution.

Saved data is serialized and validated before replacing an existing target; a same-directory temporary file and file fsync precede replacement. This provides useful process-level failure protection, not a universal guarantee against power loss, filesystem faults or concurrent writers. There is no distributed transaction, directory-fsync portability layer or multi-writer lock.

The reader has a 10 MiB limit suitable for reference fixtures, not production arrays. Opaque private JSON is only round-tripped; no solver-specific restore occurs. A production checkpoint must include private material/integrator/RNG/event state and associated mesh data needed for replay. [S06]

## Provenance and integrity

`provenance/` preserves supplied inputs and their checksums. The old archive remains unchanged, including any historical files inside it. Do not run old and new suites with ambiguous `PYTHONPATH` settings. The new namespace is `cellsim_v2`.

`MANIFEST.sha256` covers the current release files except itself, generated `runs/` outputs and caches. The initial build manifest is preserved as `provenance/initial_build_MANIFEST.sha256`; historical evidence is unchanged. `tools/check_manifest.py` rejects changed/missing tracked files and out-of-root paths; it does not authenticate the publisher. The ZIP has a separate checksum next to it. Source evidence and assertions remain inspectable regardless of checksum success.

## Evidence promotion

Separate these statuses:

- **implemented**: executable path exists;
- **numerically tested**: specific recorded checks passed;
- **cross-implementation verified**: independent matched calculation and convergence exist;
- **biologically validated in context**: independent measurements support a declared QoI/use;
- **unqualified**: evidence is missing, inapplicable or insufficient.

No generic boolean on the world should silently promote later runs. Changes to models, parameters, solvers, observations, geometry, or intended use can invalidate prior evidence. FDA guidance provides scoped credibility methodology for relevant first-principles models in device submissions; it does not approve this architecture or its proposed ML component. [S09,S10]

## Release policy

Keep tests independent from the implementation under test. A failing reference case cannot be “fixed” by loosening a numerical tolerance without a documented rationale and new recorded result. Keep both old and new traces. Do not replace a difficult biology cohort, remove inconvenient measurements, or select a final policy on the holdout while retaining the same validation claim.

Before a production release, add platform CI, serialization-fuzz testing, file limits, explicit failure injection, numerical precision comparisons, external-worker isolation and dependency/license inventory. These are recommendations, not delivered capabilities.
