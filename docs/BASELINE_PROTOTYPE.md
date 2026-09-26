# First offline cell-response baseline

The prototype learns a small synthetic uptake response and evaluates it through
the same dataset and campaign contracts intended for later biological work.
It runs with Python's standard library on the local CPU. It is a working learning
and evaluation pipeline; the response labels come entirely from the reference
uptake equation.

## Run

```powershell
python tools/train_response_baseline.py --output runs/my-response-baseline
```

Use a new output directory. Optional `--config` selects a response configuration
such as `configs/response_baseline.example.json`; `--fixture-config` selects a
synthetic configuration accepted by the existing exporter. No download, external
engine, pretrained weights or installation is required.

## Prediction task

Predict the cell's intracellular amount at the end of one uptake/diffusion window,
in mol, using observed pre-step inputs. The learner fits the increment between
the observed current amount and the next amount. It adds that prediction to the
observed current amount to produce the endpoint.

Learned features, in fixed order, are:

1. Extracellular concentration, mol/m³.
2. Per-cell maximum transfer rate, mol/s.
3. Saturation parameter Km, mol/m³.
4. Requested interval, s.

These parameters are known inputs in this fixture. Their availability is an
explicit assumption, with no implication that they are measured for real cells.
Time, condition identity, cell identity and the current accumulated amount do not
enter the learned distance function. Sample identity only resolves exact distance
ties deterministically.

## Fit, select, freeze, evaluate

1. Generate 96 synthetic records from the existing six-condition fixture.
   The 48 training, 16 validation and 32 test rows retain whole-trajectory groups.
2. Ingest payloads with `load_physical_dataset`: check hashes, units, schema,
   declared IDs, group/split correspondence, finite values and nonnegative uptake.
   Every declared row must occur exactly once in its declared artifact.
3. Fit min/range scaling on training rows only. Constant training dimensions are
   ignored in the distance and separately flagged when a new value differs.
4. Fit uniform nearest-neighbor increment predictors with k = 1, 3 and 5, plus
   no-change and training-mean-increment controls. Effective k is explicitly
   bounded by the number of training rows and stored in the artifact.
5. Select the candidate with the lowest validation mean of per-condition MAEs.
   Ties prefer no-change, then mean increment, then increasing k. The exact
   synthetic-law positive control is scored but cannot win model selection.
6. Freeze the complete model bundle, selection policy, controls, preprocessing,
   dataset declarations and evaluation settings. Reload the saved JSON artifacts,
   verify their original campaign digest, then predict final test rows.
7. Record per-condition and aggregate MAE, RMSE, maximum error and range flags.
   Verify the campaign again after evaluation. No fitted component is updated
   using final-test scores.

The input JSONL stores all splits together. Ingestion parses all rows for integrity
checks while returning only the requested split rows. This enforces separation in
this workflow's fit/selection calls; it is not a holdout-access security boundary.
Model selection uses only one validation condition in the supplied small fixture.

## Saved artifacts

| Artifact | Purpose |
|---|---|
| `dataset/` | Original synthetic configuration, rows, manifest, final worlds and generation report |
| `requested_*_config.json`, `response_config.json` | Attempted inputs and normalized learning configuration |
| `validation_scores.json` | All validation scores, candidate order, selected ID and selection rule |
| `model_bundle.json` | Every candidate/control, selected identity, fit cohort, source identity and selection configuration |
| `preprocessing.json` | Feature order, units, training ranges, constant-dimension policy and fitting sample IDs |
| `campaign_manifest.json`, `campaign.json`, `freeze_receipt.json` | Dataset paths relative to the run root and the complete frozen evaluation identity |
| `predictions.jsonl`, `evaluation.json` | Selected candidate/control predictions and final grouped metrics |
| `results.json`, optional `failure.log` | Commands, environment, timing scopes, counts, digests and retained failures |

Use `dataset/manifest.json` with the physical loader. `campaign_manifest.json`
rebases paths to `dataset/...` for campaign verification from the run root; it
is not an alternative payload-ingestion manifest. Its canonical digest therefore
differs from the physical manifest's digest.

For later verification, retain the original campaign digest independently:

```powershell
python tools/training_manifest.py verify --manifest runs/my-response-baseline/campaign_manifest.json --campaign runs/my-response-baseline/campaign.json --expected-digest ORIGINAL_CAMPAIGN_SHA256
```

The local receipt is convenient provenance. If it and all artifacts are replaced
together, it does not supply an independent trust anchor. Files must stay stable
during execution; the interpreter provides change detection, not filesystem locks.

## Recorded result

The command above, with output `runs/response_baseline_first`, completed on
Windows 11, Python 3.12.6, CPU. Validation selected `knn_k5`. Its validation MAE
was `2.02854790405648e-6 mol`. Final results use 32 rows from two held-out synthetic
conditions, after the model bundle was frozen:

| Model | Test MAE, mol | Test RMSE, mol | Maximum absolute error, mol |
|---|---:|---:|---:|
| Selected five-neighbor increment | 3.481890319790012e-6 | 3.72023422550495e-6 | 5.903162903278189e-6 |
| Training-mean increment | 1.4236986941550072e-5 | 1.7661967301235376e-5 | 2.7089304336253455e-5 |
| No change | 4.288904167319916e-5 | 4.637933828393602e-5 | 7.058823529411764e-5 |
| Exact synthetic uptake law | 0 | 0 | 0 |

The two conditions have equal row counts, so row-averaged and condition-averaged
MAE coincide here apart from floating-point roundoff. All 32 final rows had a
feature outside the training range. The selected model's MAEs were
`2.8979935631642783e-6 mol` for the high-concentration condition and
`4.065787076415746e-6 mol` for the low-concentration condition.

The exact law is the same equation used to produce these labels. Its zero error
is a useful positive control for this pipeline, not independent-solver or
experimental evidence. The learned result demonstrates this small fixture only;
it does not estimate broad extrapolation reliability.

## Current limits and next development

This is one-step evaluation with observed inputs supplied again at each step.
Recursive rollout can accumulate errors and has not been implemented or measured.
The prediction returns an endpoint and increment, without a field debit or shared
reservoir check. It must not replace a physical `Update` or bypass the conservative
rules interpreter.

No expression dataset, cell-type adapter, subject adaptation, preference model,
self-play selector or reliability calibration is fitted. The current uncertainty
output is only an outside-training-range flag. It is neither a probability nor
an error bound. The simple known uptake law is already cheap; this run establishes
no computational advantage for the learned approximation.

Timings include generation, fitting, selection, evaluation, verification and
intermediate persistence. Nested fixture timings overlap the runner's preparation
time and must not be added twice. Import/startup, output-directory creation and
final report writes are excluded as stated in the recorded report. Failed attempts
retain their work and total duration.

The current suite includes the existing dataset/campaign/exporter regressions
and two new rule-history regressions. The new physical loader and learning APIs
have run through this complete example and received code review; dedicated
regression coverage for those APIs remains a next task.

Use this baseline as a stable comparison point for a richer predeclared dataset,
then compare fixed/coverage sampling before a learned curriculum. Measured
biological-response work still needs an authenticated dataset, assay-specific
ingestion and experimental-unit holdouts. See [PROJECT_DIRECTION.md](PROJECT_DIRECTION.md),
[BIOLOGICAL_RULES.md](BIOLOGICAL_RULES.md), and [BUILD_BACKLOG.md](BUILD_BACKLOG.md).
