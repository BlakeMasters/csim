# Cellular simulation and shared cell-response models

This project is building a platform for learning how cells respond to their
environment and to interventions, then using those responses within a larger
biological simulation. The direction is a shared response model that can adapt
to different cell types and, eventually, individual subjects using measured data.
Whether sharing improves prediction over separate models is a research question.

The current foundation includes a small Python reference simulator, conservative
3D transport, synthetic cell-field datasets, and contracts for reproducible
training and evaluation. A lightweight rules layer executes explicit cell-response
hypotheses. A synthetic learning baseline also runs
on the local CPU. Biological calibration and validation remain future milestones.
This package is a build specification and executable reference
foundation; its evidence does not establish a validated tumor simulator.

## Start here

- **[Project direction](docs/PROJECT_DIRECTION.md):** the intended platform,
  current capabilities, and the next milestones.
- **[Cell-model RL environments](docs/CELL_MODEL_RL_ENVIRONMENTS.md):** proposed
  training of virtual cell dynamics, MiMo reuse assessment, and interacting cell ensembles.
- **[Research implementation evaluation](docs/RESEARCH_IMPLEMENTATION_EVALUATION.md):**
  actual data feasibility, proposed contracts, controls, and implementation gates.
- **Future work:** [development targets](docs/FUTURE_DEVELOPMENT_TARGETS.md),
  [research ideas](docs/RESEARCH_IDEAS.md), and
  [experiment blueprints](docs/EXPERIMENT_BLUEPRINTS.md).
- **[Biological rules](docs/BIOLOGICAL_RULES.md):** inspect JSON hypotheses and
  run the standard-library switch and conservative transfer example.
- **[Training setup](docs/TRAINING_SETUP.md):** generate synthetic trajectories,
  validate grouped datasets, and freeze evaluation artifacts.
- **[Baseline prototype](docs/BASELINE_PROTOTYPE.md):** guide for the synthetic
  response model, controls, frozen evaluation, and recorded results.
- **[Implementation status](IMPLEMENTATION_STATUS.md):** executed results,
  environments, and the limits of each implemented component.
- **[Build backlog](docs/BUILD_BACKLOG.md):** concrete tasks and completion criteria.
- **[Hackathon environment](docs/HACKATHON_ENVIRONMENT.md):** local XLSX/MAT
  reader qualification, pinned optional dependencies, and the Ocura OSS ledger.
- **[Work board](.agents/BOARD.md):** assignments, status, and evidence IDs for
  work coordinated in this checkout.

## Run the current groundwork

From this directory, use Python and its standard library:

```powershell
python tools/run_checks.py
python tools/run_rule_demo.py --inspect configs/biological_rules.oxygen.template.json
python tools/run_rule_demo.py --output runs/my-rule-demo
python tools/prepare_training_fixture.py --output runs/my-training-fixture
python tools/training_manifest.py validate --manifest runs/my-training-fixture/manifest.json
python tools/train_response_baseline.py --output runs/my-response-baseline
```

Choose a new output directory for each attempt. The rules demo uses a synthetic
concentration switch and gated material transfer; its oxygen planning template
retains unresolved biological values as `null`. See the
[rules guide](docs/BIOLOGICAL_RULES.md) for units, state, and evidence requirements.

The exporter records simulation settings, pre-step inputs, next-step amounts,
cohort assignments, artifact hashes,
balances, and success or failure. All cells and time points sharing one synthetic
environment stay in the same train, validation, or test split.

The supplied fixture contains 96 paired records from six synthetic conditions.
It provides a small reproducible starting point for the data and learning workflow.
Its SI-valued parameters are engineering examples, with no biological cell-line
identity. See the [training guide](docs/TRAINING_SETUP.md) for configuration,
output formats, and campaign freeze/verification commands.

The recorded groundwork ran on Python 3.12.6, Windows 11, CPU. The original core
also has a separate historical Linux/Python 3.13.5 record. Python 3.10+ is the
intended runtime floor; broader runtime/device coverage requires new execution
evidence. These commands run without package installation or third-party engines.

Additional entry points are `tools/run_demo.py`, `tools/numerical_checks.py`,
`tools/transport_checks.py`, and `tools/check_manifest.py`. Groundwork evidence is
indexed in [GROUNDWORK_REPORT.md](docs/GROUNDWORK_REPORT.md); original build
evidence remains under `evidence/final_run/`.

## What the foundation provides

| Component | Current scope |
|---|---|
| Physical state | Cell identity, geometry, molar inventories, field volumes, events, and transfer ledgers |
| Cell-field environment | Fixed rectilinear 3D diffusion, prescribed inward boundary flux, and one synthetic saturable uptake law |
| Declarative rules | JSON concentration switches, event-backed memory, and gated same-species transfers with explicit provenance |
| Execution | Ordered synchronization windows, pure update proposals, atomic shared-state acceptance, and reference checkpoints |
| Training data | Synthetic JSONL trajectory export; explicit observations, units, ordered features, pairing, and grouped splits |
| Evaluation identity | Actual artifact hashing, create-only campaign snapshots, and verification against an independently retained digest |
| Learning baseline | Standard-library nearest-neighbor increments, training-only scaling, validation selection, and frozen one-step evaluation |
| Reference evidence | Targeted regressions, synthetic analytic comparisons, and preserved command/environment records |

Dataset declarations accommodate both physical responses and unpaired
gene-expression observations. Each modality keeps its own observation meaning.
Any future mapping from expression to uptake, secretion, growth, or mechanics
needs a defined law and supporting measurements before it can control the physics.

The first learning run selected a five-neighbor increment model on validation
data and evaluated 32 held-out synthetic records after freezing its JSON
candidate. It improved one-step error over no-change and training-mean controls;
the exact synthetic-law control reproduced the targets. These are predictions
from observed pre-step inputs, with no demonstrated recursive rollout accuracy
or biological benefit. The [prototype guide](docs/BASELINE_PROTOTYPE.md) records
metrics, cohort limitations, and execution details.

## Design and research

[BUILD_RECOMMENDATIONS.md](BUILD_RECOMMENDATIONS.md) defines the implementation
sequence. [ARCHITECTURE.md](docs/ARCHITECTURE.md) and
[NUMERICAL_CONTRACTS.md](docs/NUMERICAL_CONTRACTS.md) explain ownership, units,
continuation state, timing, and conservation. The next physical evidence gates
are an independent transport comparison and uptake/splitting studies.

The first proposed biological study is a sourced oxygen-perturbation experiment.
[BIOLOGICAL_VALIDATION.md](docs/BIOLOGICAL_VALIDATION.md) defines dataset review,
observation matching, calibration, and untouched evaluation cohorts.
[BACKEND_INTEGRATION.md](docs/BACKEND_INTEGRATION.md) scopes future solver adapters.

[VIRTUAL_CELL_RESEARCH.md](docs/VIRTUAL_CELL_RESEARCH.md) records inspected sources
for the training contracts. [DOWNSTREAM_LEARNING_PLAN.md](docs/DOWNSTREAM_LEARNING_PLAN.md)
develops cell-state specialization, subject adaptation, self-play, contrastive
distillation, and calibrated decisions as separately testable research stages.

## Provenance

New imports use `cellsim_v2`. This namespace replaces the earlier toy API while
the original ZIPs and audit remain preserved under `provenance/`.
[TRACEABILITY.md](docs/TRACEABILITY.md) maps the audit findings to corrections
and remaining tasks; [SOURCES.md](docs/SOURCES.md) preserves its source registry.

Numerical evidence applies to the recorded equations, inputs, and execution
environment. Synthetic parameters remain labeled as examples. Biological
datasets, patient data, pretrained models, and specialist engine binaries are
separate future acquisitions. See [NOTICE.md](NOTICE.md) for provenance and
licensing details and [KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) for the
current technical boundaries.
