# Virtual cell training groundwork

This workspace now has a runnable fixed 3D environment, a synthetic trajectory
exporter, and dataset/evaluation contracts. The contracts support physical
observables and unpaired gene-expression observations. The supplied executable
fixture covers synthetic material uptake only. Biological datasets, an AnnData
reader, external solvers and a GPU runtime remain future additions.

A small synthetic response learner now exercises these contracts end to end.
Run `python tools/train_response_baseline.py --output runs/my-response-baseline`;
see [BASELINE_PROTOTYPE.md](BASELINE_PROTOTYPE.md) for its fitted controls,
selection procedure and one-step results. The [rules layer](BIOLOGICAL_RULES.md)
provides a separate conservative path for declared effects.

## Run the groundwork

From the project root, using Python and the standard library:

```powershell
python tools/run_checks.py
python tools/prepare_training_fixture.py --output runs/my-training-fixture
python tools/training_manifest.py validate --manifest runs/my-training-fixture/manifest.json
```

Choose a new output directory for each preparation attempt. Existing directories
are refused. The optional `--config configs/training_fixture.example.json` selects
an explicit synthetic configuration. Its parameters have SI dimensions but are
engineering examples, with no cell-line identity or biological calibration.
Failed generation retains configuration, completed rows, and a failure report.
Malformed supplied configuration bytes are retained as `requested_config.json`.

The default fixture has 24 voxels, two point-sampled cells, six independent
synthetic conditions, and eight steps per condition: **96 paired records**.
All cells and times from one trajectory belong to one split. Conditions are
assigned before generation: three train, one validation, two test. Different
initial concentrations and boundary influx schedules are held out; this is a
synthetic condition split, not evidence of biological generalization.

| Output | Contents |
|---|---|
| `simulation_config.json` | Geometry, species, synthetic parameters, process order, conditions, split assignments |
| `samples.jsonl` | Sample/group IDs, current time and interval, pre-step local inputs, next intracellular amount |
| `final_states.json` | Accepted final worlds for inspection; not a complete external-solver restart |
| `manifest.json` | Observable, units, ordered target features, pairing, artifact hashes and grouped splits |
| `results.json` | Environment/source identity, counts, per-trajectory balances, timings, success or failure |

The target is intracellular amount after one explicitly ordered uptake/diffusion
window. Inputs are captured before uptake. No future field or target is included
among inputs. Known synthetic uptake parameters are included; this is a fixture
for building data plumbing and later numerical surrogates, not a claim that those
parameters could be measured for an arbitrary cell. Cell volume is an intracellular
compartment and does not displace the grid's extracellular volume.

Timing categories record measured generation, validation and artifact writes.
Total timing begins inside the preparation function. Imports, interpreter startup,
output-directory creation and the final report write are outside that measurement.
Failed-attempt duration is the total failed attempt, not an additive cost category.
No cost superiority, memory scaling, or performance result is inferred.

## Dataset contract

`cellsim_v2.training.validate_dataset(manifest, root)` validates a declared dataset
and returns a detached JSON value. `dataset_digest` only canonicalizes and hashes
declarations, including ordered features and split assignments; it does not open
artifact files. `validate_dataset` checks:

- Relative artifact paths, resolved root confinement, and actual SHA-256 contents.
- Unique sample IDs, nonempty train/validation/test splits, and disjoint
  experimental units and trajectories across those splits.
- Optional extra holdouts through `split_policy.held_out_dimensions`: use
  `condition_id` or keys supplied in each sample's `metadata`.
- Explicit modality, observable, observation operator, unit, ordered `feature_ids`,
  and `pairing` (`longitudinal` or `unpaired`). Longitudinal samples require a
  trajectory belonging to one experimental unit. Unpaired samples require null
  trajectory IDs.
- Experimental source and reuse-term declarations. These are required strings;
  validating them does not authenticate the experiment or determine legal rights.

The validator verifies declarations and whole-file hashes. It does not parse
AnnData/JSONL observation payloads, compare metadata against every data row, infer
missing units, fit preprocessing, or identify biological experimental units.
The supplied exporter has an end-to-end test linking its records to the manifest.
Other formats need equivalent ingestion checks before training.

For gene-expression work, use an assay-specific modality, an explicit measurement
representation such as declared counts or normalized expression, and ordered gene
identifiers. Keep unrelated control/perturbed cells unpaired. Store context,
perturbation, batch/donor, acquisition timing and control availability in metadata;
their biological meanings require dataset review. The future AnnData mapping is
discussed in [VIRTUAL_CELL_RESEARCH.md](VIRTUAL_CELL_RESEARCH.md).

## Freeze an evaluation candidate

Once real candidate and preprocessing artifacts exist beneath the dataset root,
use the CLI to create a new snapshot. Example paths below must refer to actual
files; the command never loads or executes the model.

```powershell
python tools/training_manifest.py freeze --manifest runs/my-training-fixture/manifest.json --candidate-id candidate-001 --model models/candidate.bin --preprocessing models/preprocess.json --evaluation configs/training_evaluation.example.json --output runs/my-training-fixture/campaign.json
python tools/training_manifest.py verify --manifest runs/my-training-fixture/manifest.json --campaign runs/my-training-fixture/campaign.json --expected-digest ORIGINAL_CAMPAIGN_SHA256
```

Save the digest printed at freeze time in an independently trusted record. Verify
against that original digest immediately before evaluation. Verification detects
changed dataset declarations, splits, features, data, candidate, preprocessing,
or evaluation settings. It does not prevent concurrent edits or enforce an
immutable filesystem. The caller must arrange stable files while evaluating.

Current campaign verification opens the dataset artifacts, one model file, and
one preprocessing file. A future selector or calibrator must be included in a
verified bundle, or supported by an explicit extension to the artifact registry.
File paths and hashes placed in arbitrary metadata are not recursively verified.

Metric and baseline IDs are declarations. Neither CLI executes a metric, trains a
baseline, nor prevents a caller from reading holdout data early. Fit preprocessing
on permitted development data; freeze one candidate before final holdout use.
The example's acceptance tolerance remains null and carries no qualification.

## Physical model interface

`RectilinearGrid3D` stores immutable orthogonal grid geometry. `diffusion_step`
and `saturable_uptake_step` return pure `Update` proposals, compatible with the
existing `WindowStepper`. `BoundaryFlux` is an inward flux density in mol/(m² s).
`CellUptake` specifies per-cell maximum transfer in mol/s and Km in mol/m³.
An accepted uptake debits the field and credits the same species inside the cell.
It does not consume oxygen or implement a reaction network.

Call `diffusion_timestep_limit_s` for the conservative explicit step limit.
Collective cell demand exceeding a voxel's available amount rejects the whole
proposal. Change the step explicitly; no demand clipping or scarcity allocation
is performed. Field volumes must exactly match `grid.volumes_m3`.

Learned expression endpoints retain their assay semantics. A future mapping from
expression predictions to uptake, growth, secretion or mechanics needs its own
definition and evidence. A model that predicts one endpoint is not automatically
a repeatable transition model. Both training paths can use this manifest layer
without treating their outputs as interchangeable.

## Next build gates

1. Choose one independent transport comparator, match equations/boundaries, and
   refine both implementations. The current checks are analytical, not R01/R02.
2. Study uptake stiffness and splitting-window error on declared observables.
3. Acquire a real oxygen-perturbation or expression dataset with verified
   provenance, rights, metadata and grouping, then implement one ingestion adapter.
4. Extend the executed synthetic baseline to a reviewed measured dataset and
   freeze a candidate before final evaluation.
5. Extend ownership, restart and model-private/RNG replay before live learned
   coupling or topology changes. C01-C03 and N01-N02 remain partial milestones.

The proposed roles for self-play, contrastive distillation, calibration and
cell-state specialization are in [DOWNSTREAM_LEARNING_PLAN.md](DOWNSTREAM_LEARNING_PLAN.md).
Adaptive curricula, RLCD, calibration and subject adapters remain research plans.
The small supervised nearest-neighbor baseline supplies an initial comparison.
