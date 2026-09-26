# Research ideas for trainable virtual cells

Idea backlog, 25 September 2026. These are proposed experiments, not delivered
capabilities or claims of novelty. The intended learner is a numeric cell-response
model with shared parameters and private state for each simulated cell. An
experiment controller is optional.

Use [development targets](FUTURE_DEVELOPMENT_TARGETS.md) for sequencing and
[experiment blueprints](EXPERIMENT_BLUEPRINTS.md) to turn a selected card into
a bounded comparison.

The long-term target is a reusable model of how cells respond, adapt and interact,
assembled into tissue simulations with measured applicability. The immediate
opportunity is smaller: determine when retained history improves predictions and
whether learning that response through an environment adds value over direct fitting.

## Starting point and priorities

The current foundation has conservative transport, declarative switch/transfer
rules, grouped synthetic fixtures, and a frozen one-step nearest-neighbor baseline.
Continuous learned cell dynamics, biological fitting and RL remain proposed.
See [implementation status](../IMPLEMENTATION_STATUS.md) for executed evidence.

- **Core/local:** cards 1–4 can begin with small, explicitly synthetic experiments.
- **Data-dependent:** cards 5–7 need accepted observations before biological claims.
- **Later:** cards 8–10 need a useful fixed learner and independent scoring first.

Every card needs a declared observable, split and acceptance criterion before
fitting. Hold out experimental units and the claimed generalization dimension;
freeze all fitted components before final evaluation. Preserve failures and charge
generation, fitting, tuning, labels, inference, evaluation and persistence.
Unknown biological parameters and acceptance margins stay unresolved until sourced.

## Core/local experiments

### 1. A cell model that learns through its environment

- **Question:** Does RL improve a numeric cell model when its responses alter later
  local conditions and receive delayed feedback?
- **First experiment:** Learn one synthetic transfer response over a fixed horizon;
  compare small parameter fitting, sequence fitting and one numeric RL method with
  matched inputs and model capacity where feasible. Include the known-law control.
- **Dependencies:** Episode/replay contract, explicit stochastic action distribution,
  typed proposals, fixed scorer and complete failure/cost records.
- **Progress evidence:** Better held-out rollout accuracy or lower total cost at
  matched accuracy, with admissible transfers throughout the trajectory.
- **Reject or narrow:** If direct fitting matches RL, retain the simpler learner.
  Improved reward without independent prediction improvement is insufficient.

### 2. Compact memory and reversible plasticity

- **Question:** What is the smallest retained state needed to predict different
  responses after different exposure histories at the same current conditions?
- **First experiment:** Introduce a declared synthetic response/recovery law and
  paired exposure schedules. Compare current-state inputs, elapsed-time/cumulative
  exposure summaries, explicit hysteresis and a compact recurrent state.
- **Dependencies:** Accepted-state memory, consistent clocks, intervention boundaries,
  history-shuffling controls and held-out schedule families.
- **Progress evidence:** Reproducible gains beyond exposure-summary controls on new
  schedules; later, gains on independent measured experimental units.
- **Reject or narrow:** Prefer sufficient exposure summaries when they match learned
  memory. Endpoint associations cannot separate intrinsic memory from population
  selection; weight updates and biological state adaptation remain distinct.

### 3. Interpretable response modules that can be recombined

- **Question:** Can a small library of response/recovery modules generalize to new
  intervention combinations while keeping physical effects inspectable?
- **First experiment:** Fit a synthetic model with two declared response components;
  compare explicit modules with an unconstrained predictor and reserve one combined
  exposure pattern. Inspect predictions after removing each module.
- **Dependencies:** Module-owned state, units, input domains, conflict handling and
  atomic commits through the existing conservative kernel.
- **Progress evidence:** Accurate reserved combinations, stable identified parameters
  where identifiable, and predictable consequences of module removal.
- **Reject or narrow:** If many decompositions fit equally well, report predictive
  alternatives. A named hidden variable or attractive diagram does not establish
  a biological mechanism. See [biological rules](BIOLOGICAL_RULES.md).

### 4. Uncertainty that changes a research decision

- **Question:** Can alternative fitted models identify where a prediction needs
  more evidence, while remaining useful on supported conditions?
- **First experiment:** Fit a small ensemble to synthetic development cases and
  compare its error-event probabilities with a constant-rate and simple calibrated
  predictor on reserved histories. Evaluate coverage, errors and abstentions.
- **Dependencies:** Separate calibration data roles, fixed error-event definition,
  proper scoring, and independent worlds for alternative model hypotheses.
- **Progress evidence:** Improved probabilistic skill and decision utility across
  held-out cohorts; later evidence must use the relevant biological observable.
- **Reject or narrow:** Ensemble disagreement alone cannot certify error. If all
  models share a bias or abstain on almost everything, narrow the applicability
  region. Uncertainty models are separate worlds, not extra physical cells.

## Experiments that depend on measured data

### 5. Shared responses with cell-context and subject adaptation

- **Question:** Can sharing response structure reduce the observations needed for
  a new cell context without hiding context-specific failures?
- **First experiment:** Compare pooled, separate and hierarchical models for one
  compatible assay. Reserve an entire context; permit adaptation from a declared
  support set and score its separate query units under a fixed adaptation protocol.
- **Dependencies:** Context identity, batch metadata, sufficient independent units,
  compatible observation meaning and explicit support/query separation. Donor
  adaptation waits for donor-resolved data.
- **Progress evidence:** Better query prediction at matched support size and total
  cost, including performance for each reserved context.
- **Reject or narrow:** If batch correction explains the gain or a context suffers
  negative transfer, keep separate models or restrict sharing. Cell-line transfer
  does not establish patient-specific response prediction.

### 6. One response representation, several measured functions

- **Question:** Can a shared representation support useful predictions across
  expression, morphology and a measured cellular function in general cell R&D?
- **First experiment:** Choose one context with compatible assays; predict one
  functional endpoint using a representation learned from another modality and
  compare with function-only and assay-specific controls.
- **Dependencies:** Assay provenance, timing, missingness and observation operators;
  justified pairing or explicitly unpaired population comparisons. Any physical
  output needs a measured, unit-bearing functional mapping.
- **Progress evidence:** Improved reserved functional prediction beyond nuisance
  variables and individual-modality baselines, with subgroup errors preserved.
- **Reject or narrow:** If only expression similarity improves, retain that scope.
  Never fabricate same-cell trajectories or convert expression into molar rates
  without a supported law. Reuse study contracts across R&D domains before assuming
  that one learned representation transfers between them.

### 7. Interacting cell populations and tissue response

- **Question:** Do learned local responses predict a mixed population more
  accurately than independent cells, and when do interaction rules matter?
- **First experiment:** Start with two synthetic contexts sharing one field and
  frozen response models. Compare coupled and uncoupled controls under reserved
  compositions; then select one measured co-culture interaction and observable.
- **Dependencies:** Joint reservoir accounting, replay, coupled numerical refinement,
  explicit interaction ownership, composition/spatial metadata and co-culture data.
- **Progress evidence:** Accurate interaction-sensitive outcomes across reserved
  compositions and interventions, beyond predictions based on isolated populations.
- **Reject or narrow:** A good pooled average can hide wrong cell-type responses.
  Broader tissue or tumor-response work waits for each needed growth, fate, contact
  and delivery mechanism plus independent assembled-system measurements. Antigen
  recognition and immune effector function require separate evidence.

## Later learning and research loops

### 8. Self-play as a curriculum for difficult response histories

- **Question:** Can a task proposer find informative, valid exposure histories
  that improve the cell learner faster than random or coverage-based sampling?
- **First experiment:** Select from a reviewed finite synthetic pool. Compare fixed
  coverage, random selection and measured learning-progress selection at equal
  total cost, using a fixed development probe and a sealed final benchmark.
- **Dependencies:** A useful fixed baseline, acquisition history, bounded proposer,
  independent targets and versioned learner/proposer checkpoints.
- **Progress evidence:** Lower total cost to a prespecified final error, without
  concentrating only on a narrow regime or exploiting invalid episodes.
- **Reject or narrow:** Prefer coverage when selector overhead erases the benefit.
  Generated trajectories teach supplied assumptions; they add no independent
  biological observations. This is an adapted simulator curriculum, not a
  reproduction of [the reviewed self-play method](SELF_PLAY_PRETRAINING_REVIEW.md).

### 9. Assay feedback and contrastive preference learning

- **Question:** Can independently scored comparisons of candidate responses help
  learn from a difficult assay evaluator beyond direct numerical fitting?
- **First experiment:** Rank paired candidate trajectories using a frozen synthetic
  scorer, later a declared assay score with independent labels. Compare direct
  score optimization, supervised preference fitting and reward-based adaptation;
  retain ties and uncertain rankings.
- **Dependencies:** Comparable candidates, label uncertainty, scorer independence,
  grouped splits and metrics outside the learned preference/reward model.
- **Progress evidence:** Better held-out assay fidelity at matched total cost,
  including distributional variation and failure cohorts.
- **Reject or narrow:** Gains only against the learned scorer indicate possible
  overoptimization. Original RLCD assigns preferences using contrasting prompts;
  externally scored numeric trajectory preferences are a separate adaptation,
  not the original method or generic contrastive representation learning.
  See [the RLCD review](RLCD_REVIEW.md) for the distinction and controls.

### 10. An optional controller for the next informative experiment

- **Question:** Can a controller choose experiments that distinguish response
  hypotheses or reduce prediction error with fewer measured resources?
- **First experiment:** Replay acquisition from a finite, independently labeled
  development pool; compare fixed coverage, random and simple information-based
  selection before considering an RL or language-model controller.
- **Dependencies:** A declared acquisition budget, hidden unacquired labels,
  experiment feasibility constraints and a final cohort excluded from every loop.
- **Progress evidence:** Better final prediction or hypothesis discrimination per
  total cost; a later prospective study must confirm real experimental utility.
- **Reject or narrow:** If gains require access to future outcomes or changing the
  evaluator, reject them. If simple selection suffices, retain it. An optional
  controller manages the study; the numeric cell model remains the response learner.

## Turning an idea into a project milestone

Promote one card at a time into [the build backlog](BUILD_BACKLOG.md), with an
observable, accepted data source, controls, numerical prerequisites, frozen
evaluation protocol and full cost record. Start with cards 1–3 and parallel
measured-data feasibility work; advance card 4 when there is enough independent
error evidence to evaluate it.

[Cell-model RL environments](CELL_MODEL_RL_ENVIRONMENTS.md) specifies the proposed
numeric interface. [Research implementation evaluation](RESEARCH_IMPLEMENTATION_EVALUATION.md)
records dataset feasibility and evidence gates; its
[source registry](../evidence/research_implementation_sources.json) identifies
inspected primary sources and access depth. [Downstream learning](DOWNSTREAM_LEARNING_PLAN.md)
develops the longer-term adaptation and cell-engineering direction. These sources
guide the questions above; no reviewed result validates this project's models.
