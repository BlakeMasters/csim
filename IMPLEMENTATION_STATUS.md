# Implementation and verification status

## Local NF-κB live-demo checkpoint — 26 September 2026

The current laptop demo is described in the [live runbook](docs/LIVE_DEMO_RUNBOOK.md).
The local playground at `http://127.0.0.1:8766/` offers one to five identified
synthetic cell instances, typed stimulus and finite generic-payload actions,
pixel inspection, replay, a paired 82-step comparison, and separate panels for
observed p65, a frozen empirical predictor, symbolic examples, proposer/learner
iterations, and Ocura OSS evidence. The board is at `:8765`; the preserved
30-pair campaign review is served at `:8766/campaign`. The launcher checks the
local source and evidence before serving. Ocura OSS is required; an installed
Ocura Engine CLI is optional and remains outside this repository.

The final repository check, `python tools/run_checks.py`, ran on Windows 11,
Python 3.13.5 and CPU. It recorded **242 tests, 241 passed, zero failures,
zero errors and one symlink-privilege skip**, plus passing numerical, fixed
3D transport and fresh-interpreter continuation checks in
[`runs/checks_03ej3tf1/`](runs/checks_03ej3tf1/). Its ordered
source/test/tool SHA-256 is
`da785e21b2ad00f50699d50f902c45d6ab2dd895d290f1dec68331f0be174928`.
An earlier concurrent-edit run is retained at
[`runs/checks__3lyvtsp/`](runs/checks__3lyvtsp/) with one import-time error
while the symbolic UI handler was being added; the final run completed after
that source was committed. These checks are reference-kernel evidence and do
not qualify the synthetic response against biological intervention data.

The observed lane resolves 11,267 source matrix rows, 75 conditions, and 83
six-minute reporter samples per condition. Its frozen sequence holdout compares
a causal state-space baseline with current-only and no-change controls
([evidence](runs/nfkb_model_20260926_02/comparison.json)); the held-out
author-normalized reporter MAEs are 0.2990, 0.3426, and 0.3643 respectively.
This is a sequence split, without known per-row run/chamber IDs or a fresh
independent biological cohort. The illustrative stimulus/payload and generic
mediator models are separate from the measured reporter and are not calibrated
drug-response predictors.

The synthetic campaign preserved 30 matched pairs across cell counts one to
five and fixed/seeded variants, 4,920 accepted steps, per-step traces and
amount ledgers, failure accounting, and an Ocura OSS sidecar
([result](runs/nfkb_campaign_20260926_02/results.json),
[OSS record](runs/nfkb_campaign_20260926_02/oss_record.json)). A separate
finite generic-mediator arena adds next-interval cell-to-cell sensing through
one shared voxel, pure amount-transfer `Update` proposals, full-state
rejection and seeded checkpoint replay
([contract](docs/COUPLED_NFKB_ARENA.md),
[result](runs/coupled_nfkb_arena_20260926_04/results.json)). The current
symbolic work comprises a narrow v0 concentration-switch/transfer language,
a bounded typed response graph, and a typed episode workflow; these are not
a unified general pathway interpreter. The proposer/learner exercise is a
synthetic frozen-evaluation curriculum, not an RL or biological result.

The `data/` and `runs/` inputs cited here are preserved on this laptop and
ignored by Git. They must be supplied again in a fresh checkout. Earlier
status below is historical and does not describe this live-demo checkpoint.

## Historical status — 25 September 2026

Research/design update, 25 September 2026: the new
[implementation evaluation](docs/RESEARCH_IMPLEMENTATION_EVALUATION.md) and
[cell-model RL design](docs/CELL_MODEL_RL_ENVIRONMENTS.md) audit data feasibility,
MiMo infrastructure and the path to learned cell populations. They add proposed
contracts and nonrunnable study/episode templates, without runtime or test changes.
The repository-required baseline was rerun in `runs/checks_weh0phac/` with the same
source/test/tool identity and outcomes below. No continuous cell policy, RL
environment, biological ingestion adapter or MiMo integration was implemented.

Current prototype execution: **137 tests, 136 passed, 0 failures, 0 errors, 1 skipped** in `runs/prototype_rules_checks/`. Runtime: Python 3.12.6, Windows 11, CPU. The symlink privilege test was skipped on this host. The two newest tests address discovered rule-state namespace and continuation-identity defects; the count does not imply broad machine-learning unit coverage or proof of complete correctness.

The original three synthetic analytic studies and fixed 3D spatial, temporal and joint-refinement studies passed their engineering regression limits. A small synthetic response baseline was fitted on 48 training rows, selected on 16 validation rows and evaluated on 32 test rows from two held-out conditions. A separate local-rule demo exercised a concentration switch with hysteresis and gated conservative transfer. No specialist engine, biological dataset, biologically trained model or GPU path was run.

The historical `evidence/final_run/` record remains unchanged: 76/76 tests passed on Linux x86-64 with Python 3.13.5. Its two optional JSON shape checks used `jsonschema` 4.26.0; the current standard-library execution does not require that package. That Linux record does not exercise the new groundwork code. Python 3.10+ remains the intended runtime floor, without a tested version matrix.

Current source/test/tool SHA-256: `9f74a4307bc5e14d85bb0041d3753c40d044c39bd3e0b7c4c78796d8d04f8eff`. See `docs/PROTOTYPE_REPORT.md` for current commands, hashes and results. The earlier 135-test groundwork record and `docs/GROUNDWORK_REPORT.md` retain their historical source identity.

Validation selected `knn_k5`. On the synthetic test cohort its macro condition MAE was `3.48189e-06 mol`, compared with `1.42370e-05 mol` for the training-mean increment and `4.28890e-05 mol` for no change. The generator-law positive control had zero error and was excluded from selection. All 32 test rows were outside at least one training feature range. These are teacher-forced one-step endpoints, with no learned rollout or cost-benefit result.

The synthetic rule demo accepted five intervals and four rule events, ending with intracellular amount `0.001208074534161491 mol` and total balance residual `0 mol`. Its explicit thresholds and transfer parameters are synthetic. The biological oxygen template retains null parameters, unset cell identity and a nonrunnable status.

## Executed evidence

| Evidence | Location | Interpretation |
|---|---|---|
| Current prototype checks | `runs/prototype_rules_checks/results.json` and `tests.log` | Windows execution, per-test outcomes and source identity |
| Fixed 3D analytical studies | `runs/prototype_rules_checks/transport_checks.json` | Smooth synthetic cosine modes; no independent solver |
| Fitted synthetic response baseline | `runs/response_baseline_first/` | 96 grouped records, frozen candidate and controls, validation selection and test metrics |
| Local-rule demonstration | `runs/rule_demo_first/` | Accepted switch/transfer events, trace, rule identity and amount balance |
| Earlier groundwork | `runs/groundwork_final/` and `runs/groundwork_training_fixture/` | Historical preparation evidence, before the fitted baseline and rules |
| Per-test results and environment | `evidence/final_run/results.json` | New API's named contract/regression checks |
| Raw test log | `evidence/final_run/tests.log` | Includes fresh-interpreter checkpoint continuation |
| Numerical configurations/results | `evidence/final_run/numerical_checks.json` | Analytic comparisons for transparent synthetic cases |
| Demo | `evidence/final_run/demo.json` | Small bookkeeping/transport/contact example, not tumor biology |
| Optional schema checks | `evidence/schema_validation.json` | Template/example structure only |
| Legacy audit replay | `evidence/legacy_reproduction/` | Original 4 smoke tests pass; original 16 acceptance probes give 4 pass / 12 fail |

`evidence/run_01/` is an earlier development check with 68 passing tests, retained for provenance. Historical evidence is retained with its own source identity; `runs/prototype_rules_checks/` records the current source/test/tool fingerprint.

## Observed numerical behavior

| Fixture | Observed refinement orders | Finest reported error |
|---|---|---|
| Euler decay | 1.0535, 1.0257, 1.0126 | 0.0030680258 absolute |
| Periodic diffusion | 2.0321, 2.0135 | 1.5140902e-05 L2 |
| Steady radial uptake | 2.0000, 2.0000, 2.0000 | 3.0517578e-06 maximum |
| 3D spatial diffusion operator | 1.8938, 1.9735 | 8.35685e-04 L2 mol/(m³ s) |
| 3D Euler time refinement | 1.0577, 1.0277, 1.0136 | 2.32481e-04 L2 mol/m³ |
| 3D joint trajectory refinement | 2.0284, 2.0168 | 2.33115e-05 L2 mol/m³ |

Periodic diffusion refines `dx` and `dt` jointly; these orders are not an isolated spatial-order theorem. Its finest-run total-amount discrepancy is 2.2204e-16. Error units and configurations are in the recorded JSON. Parameters are illustrative, not measured cell parameters.

The 3D studies use a closed unit cube, constant diffusivity 0.1 m²/s and a smooth voxel-average cosine mode. Spatial operator refinement, time refinement against a fixed-grid semidiscrete solution, and joint refinement against the continuous solution are separate checks. They do not establish coupled uptake/splitting convergence or performance at scale.

## Implemented versus proposed

| Component | Status | Important restriction |
|---|---|---|
| Amount/volume state | Implemented and selected tests passed | Fixed rectilinear grid added; no general dimensional type system or moving mesh |
| Atomic shared-state updates | Implemented and selected tests passed | Single-threaded, not distributed/private-state atomicity |
| Time stepping | Implemented and selected tests passed | Sequential Lie-split windows with per-process subcycling |
| Contact | Implemented and selected tests passed | Linear pair spring, spheres, O(N²), no cell material calibration |
| Division | Implemented and selected tests passed | Retained-slot bookkeeping, not physical cytokinesis |
| Chemical exchange | Implemented and selected tests passed | Finite transfer/decay plus point-sampled saturable transfer; no metabolism or calibrated membrane law |
| Diffusion | Implemented reference kernels | Periodic 1D, steady radial sphere and fixed 3D scalar isotropic diffusion; guarded explicit steps |
| Checkpoints | Implemented and selected tests passed | Shared world and RNG; opaque JSON private payload only |
| Exact-case evidence lookup | Implemented and selected tests passed | No unseen-state applicability or live solver selection |
| External port schema | Design example with shape check | Not an implemented plugin/port system |
| 3D cell–field environment | Reference slice implemented | Unequal voxel volumes, inward flux ledger and same-species cell transfer; N01/N02 production gates remain partial |
| Training preparation | Reference implemented | Grouped declarations, hashes, candidate freeze/verify and strict synthetic physical JSONL ingestion; no general assay adapter or enforced holdout access |
| Synthetic response baseline | Fitted and evaluated | Training-only range scaling and nearest-neighbor increments; validation selection; frozen one-step test evaluation; no biological training |
| Local declarative rules | Reference slice implemented | Event-backed concentration switches and gated conservative transfer; synthetic demo, two targeted regressions, unresolved biological parameters |
| SOFA/ESPResSo/Tissue Forge adapters | Planned | No adapter or compatible build selected |
| preCICE coupling | Planned | No live interface or solver-private restart implemented |
| Intracellular SBML | Planned | No SBML reader/integrator/conformance tests |
| Surrogate/adaptive portfolio | Research proposal beyond synthetic baseline | Small endpoint baseline exists; no live learned state update, solver selector or cost-benefit outcome |
| Biological validation | Not performed | No calibration or experimental holdout |

See `docs/KNOWN_LIMITATIONS.md` before treating any field or test as a production guarantee.

## Permitted current description

An evidence-adjusted build specification and an executable, small numerical reference core with targeted regression and analytic tests. It does not establish a universal virtual cell, an integrated tumor simulator, regulatory approval, broad novelty, or a scaling result.
