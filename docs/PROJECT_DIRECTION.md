# Project direction

The goal is a reusable platform for learning cell responses and composing them
with a physical tissue environment. A shared model would represent relationships
between starting cell state, context, intervention, time, and measured response.
Cell-type adapters and eventual subject-specific adapters would specialize that
model using identified observations. Their value must be measured against shared
models without adaptation and models fitted separately for each task.

The proposed RL learner is the virtual cell response model itself. It would learn
state transitions and supported physical effects from a fixed environment and
assay evaluator; an agentic experiment controller is optional. Trained cell models
could later form interacting populations in a tissue environment. Alternative
models expressing uncertainty belong in separate simulated worlds. The
[RL environment design](CELL_MODEL_RL_ENVIRONMENTS.md) evaluates this direction,
the XiaomiMiMo release and direct virtual-cell RL prior art. It is a proposal;
no cell policy or RL trainer is implemented yet.

The immediate product is a small research environment that can run on the local
CPU: express a biological hypothesis, inspect its units and effects, and execute
it with the conservative reference kernel. This supports the parallel learning
workflow: prepare data, fit a baseline, freeze its identity, inspect prediction
errors, and preserve the evidence needed to decide the next experiment.

## What exists and what comes next

| Stage | Current position | Completion evidence |
|---|---|---|
| Physical and data foundation | Reference transport, paired amount transfers, synthetic export, grouped manifests, and campaign verification are implemented. | Recorded numerical checks and artifact identities; see [GROUNDWORK_REPORT.md](GROUNDWORK_REPORT.md). |
| Lightweight biological rules | Reference implemented: JSON concentration switches, event-backed memory, and gated conservative transfer. | Five-interval synthetic demo; regressions for rule-ID separation and frozen continuation identity; biological values remain unresolved. |
| Synthetic learning prototype | Reference implemented: standard-library nearest-neighbor increment prediction, no-change/mean baselines, and an exact synthetic-law control. | Training-only scaling, validation-selected five-neighbor candidate frozen before 32 held-out one-step predictions, and per-cohort results. |
| Independent physical verification | Planned comparator and uptake/splitting work. | Matched equations, units, boundaries, and refinement in two implementations. |
| Measured cell-response learning | Dataset selection and ingestion remain open. | Authenticated provenance, explicit assay/observable, experimental-unit splits, simple controls, and untouched evaluation. |
| Shared model and cell-type adaptation | Research direction. | Improvement over independent and shared-only baselines on predeclared unseen contexts or interventions. |
| Subject adaptation and tissue coupling | Later research. | Frozen support/query episodes, functional evidence, typed physical effects, continuation/replay, and scoped applicability. |

See [BASELINE_PROTOTYPE.md](BASELINE_PROTOTYPE.md) for the learning prototype's
commands and execution record. A result on the current synthetic law establishes
an engineering behavior within that fixture. The first nearest-neighbor result
improved over the no-change and training-mean controls on 32 held-out records.
All 32 had at least one feature outside its training range; this small synthetic
test does not characterize general extrapolation or recursive rollout accuracy.

[BIOLOGICAL_RULES.md](BIOLOGICAL_RULES.md) describes the lightweight rules path.
It uses the existing reference kernel and Python standard library. Specialist
engines can be added later when a particular equation or measurement warrants
them. Rule parameters remain explicit hypotheses until supported by a defined
cell context, observations, and independent evaluation.

[RESEARCH_IMPLEMENTATION_EVALUATION.md](RESEARCH_IMPLEMENTATION_EVALUATION.md)
adds a concrete data audit and module plan. The small Murphy spheroid tables are
the first ingestion candidate, with destructive endpoint semantics. The inspected
Godet RNA-seq series alone cannot support an independent memory benchmark; IRIS
is a separate signaling-inference candidate with unresolved ingestion/reproduction
details. No candidate is yet accepted as biological training data.

## Model boundary

Keep four parts explicit:

1. **Observation:** named assay features, units, acquisition conditions,
   missingness, and an operator linking measurements to modeled quantities.
2. **Response:** a prediction for a declared intervention and horizon. Endpoint
   observations and repeatable state transitions have different requirements.
3. **Adaptation:** a limited fitted change tied to a cell context or subject,
   with base model, adaptation data, preprocessing, and feature identity recorded.
4. **Physical effect:** a supported mapping to typed transfer, rate, force, or
   event proposals accepted by the conservative simulator.

Gene-expression and physical-response tasks can share training infrastructure.
Expression features retain assay semantics; converting them into a physical law
requires its own definition, measurements, and evaluation. A coupled rollout also
needs private model state, random state, integrator history, and event state
sufficient for continuation and rejected-step replay.

Cell plasticity is a biological motivation for this direction. The reviewed
literature supports specific forms of differentiation, reprogramming, and immune
adaptation, each with distinct mechanisms and evidence. It does not establish a
single complete state representation or universal transfer across cell types.
The sources and proposed architecture are in
[DOWNSTREAM_LEARNING_PLAN.md](DOWNSTREAM_LEARNING_PLAN.md) and
[VIRTUAL_CELL_RESEARCH.md](VIRTUAL_CELL_RESEARCH.md).

## Personalization protocol

First separate subjects across development and evaluation. For a new subject,
declare which **support observations** may fit the adapter and which **query
outcomes** will evaluate it. Freeze the adapted candidate before query scoring.
Keep related cultures, biopsies, time points, and preparation histories grouped;
record temporal cutoffs and data that would actually be available at prediction.

This episodic protocol extends the existing train/validation/test contract and
still needs implementation. Donor identity alone does not demonstrate a faithful
representation of all donor properties. Calibration must state the observable,
measurement uncertainty, parameter uncertainty, and unsupported conditions.

Personalized vaccine or engineered immune-cell research would add distinct
antigen, recognition, effector, and tissue-context models. Early endpoints should
be matched assay responses with independent measurements. Patient-level utility
is a further evidence stage beyond successful cellular prediction.

## Research after the baseline

- **Adaptive curricula/self-play:** compare fixed, random, and coverage-based
  condition selection before a learned selector. Keep physics and final cohorts
  fixed and charge generation plus learning costs. See
  [SELF_PLAY_PRETRAINING_REVIEW.md](SELF_PLAY_PRETRAINING_REVIEW.md).
- **Contrastive distillation:** use a clear output preference task and compare
  inexpensive controls. Independent scientific checks must support any claim
  of better biological or numerical correctness. See [RLCD_REVIEW.md](RLCD_REVIEW.md).
- **Calibrated decisions:** fit a named failure/event probability from labels,
  then measure calibration, discrimination, coverage, and false acceptance on
  untouched cohorts. This has a separate evaluation from response accuracy.

Learning, case selection, and reliability estimation keep separate identities
and fitting data. Final evaluation freezes every component that can influence
the result. Success requires the selected observable to improve under a fair
comparison with measured total costs and retained failures.

The next implementable work and scientific gates are tracked in
[BUILD_BACKLOG.md](BUILD_BACKLOG.md). Exact results and supported descriptions
belong in [IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md), with the
commands and immutable artifacts supporting each result.
