# Future cell-model experiments

**Status: proposed experiments; none is executed by this document.** The primary
learner is the numeric virtual-cell response model. An experiment or curriculum
controller is optional and has a separate identity, fitting data and evaluation.

These cards turn the [RL environment design](CELL_MODEL_RL_ENVIRONMENTS.md) and
[history-response proposal](RESEARCH_IMPLEMENTATION_EVALUATION.md) into bounded
development targets. Prerequisite IDs refer to [BUILD_BACKLOG.md](BUILD_BACKLOG.md);
an implemented reference slice does not close its remaining scientific gates.
The [episode template](../configs/cell_model_rl.template.json) is nonrunnable.
The [development roadmap](FUTURE_DEVELOPMENT_TARGETS.md) supplies sequencing;
[research ideas](RESEARCH_IDEAS.md) records additional hypotheses and extensions.

## Common rules before execution

- Declare the observable, prediction-time inputs, grouping, controls, metrics,
  budget and acceptance rationale before fitting. Numerical tolerances need a
  numerical justification; biological margins need assay and decision evidence.
- Freeze every component influencing final scores. Preserve original data,
  attempted configurations, failed cohorts, source/model identities and costs.
  The current verifier binds one model file and one preprocessing file; use a
  self-contained bundle or implement verification of all additional artifacts.
- Targets supplying training rewards are training information even when hidden
  from policy observations. Final benchmark outcomes cannot tune any component.
- Report acquisition/generation, fitting, tuning, sampling, inference, evaluation,
  persistence and failed-work costs. Record actual interpreter, device and OS.
- Synthetic agreement, independent numerical comparison, measured prediction and
  patient-level utility remain separate evidence stages. No inspected biological
  dataset is already accepted for these experiments.

## 1. Can retained history improve a numeric cell response?

**Purpose.** Establish a small sequential problem where the current local inputs
alone are insufficient. Compare cells exposed to different histories that reach
the same current environment but have different future reference responses.

**Prerequisites.** H02 and the H04 transaction slice prepare V01; C02/C03 supply
ownership and restart requirements. T01/T02/T04 provide existing infrastructure
and a memoryless control. Their present uptake fixture cannot establish a memory
benefit. R01/R02/N03 remain separate gates for physical-accuracy claims.

**Protocol.** Define one explicitly synthetic memory law, fixed topology and one
supported same-species transfer. The environment owns time, interventions,
conservation and scoring. The learner proposes a rate or integrated transfer
with explicit units plus replacement response state. Accept memory and physical
effects together. Keep the fixed reference trajectory and its hidden parameters
separate from the learner's predicted world; retain their shared task identity.
Use known schedule boundaries, explicit prehistory and fixed rollout horizons.

**Controls.** Current-input-only prediction; the same inputs plus prespecified
exposure summaries; a fitted small memory model; and the exact generator law as
a labeled positive control. Give learned candidates the same permitted history.
Use history removal/shuffling only where it preserves the experimental design.

**Grouping.** Keep whole trajectories and their related initializations together.
Declare which schedule families are reserved. A new random seed alone does not
establish history or parameter-regime transfer. Fit preprocessing on development
data and freeze it before final scoring.

**Metrics.** Observable error by horizon and schedule, matched-history contrast
error, balance residuals, invalid-proposal counts, replay agreement and total
cost. Report one-step and recursive results separately. Initial-state and memory
parameter recovery are synthetic diagnostics, not biological identifiability.

**Success / failure / next decision.** Advance to V02 if retained state improves
the declared rollout target beyond the strongest summary control while preserving
the transaction contract. If summaries suffice, retain them. If histories produce
indistinguishable reference outcomes, redesign the benchmark before increasing
model size. Numerical or replay failures stop the coupled comparison.

**Scope.** CPU reference engineering; learning the declared synthetic law. This
does not demonstrate a cellular memory mechanism or biological prediction.

## 2. Does RL add value beyond direct response fitting?

**Purpose.** Compare training methods when cell proposals alter later environment
and state, but feedback arrives only at declared assay times or episode end.
Delayed feedback is a task property, not evidence of an RL advantage.

**Prerequisites.** V01 enables V02. A measured branch additionally requires
B01/B02, H01, T03 and the V03 data gate. H03 applies to a measured history claim;
N03/R01/R02 remain required for the corresponding physical claims. Select any
external numeric trainer through V05 only after the interface and need are clear.

**Protocol.** Begin with fixed synthetic reference targets. Run a separately
identified measured study only after assay mapping, provenance, reuse terms and
independent units are accepted. Score predicted observations using a frozen
discrepancy or justified likelihood. Hard material constraints cannot be traded
for reward. Fix weights within each collected episode; update between training
episodes or batches. Do not give the cell policy unavailable future assays.

**Controls.** Small-model parameter fitting; supervised endpoint fitting;
multi-step sequence/distribution fitting; and RL with comparable model capacity,
inputs and tuning budgets. Distinguish optimization differences from architecture
changes. Use the exact synthetic law only as a disclosed generator control.
For stochastic actions, define the actual numeric distribution and its likelihood.

**Grouping.** Reserve complete units and histories before training. Reward-bearing
training episodes cannot double as final evaluation. Paired measurements can
support trajectory losses; unpaired destructive assays require population-level
comparisons. Record whether measurements are assimilated during prediction or
whether the rollout proceeds without further observations.

**Metrics.** Error versus horizon, per-unit/cohort error, distributional fidelity
when applicable, invalid episodes, optimization variability and full costs.
Compare both fixed-budget performance and cost to a predeclared error target.
Assess coverage only for a defined predictive distribution with independent data.

**Success / failure / next decision.** Retain RL if its measured accuracy/cost
tradeoff improves on strong direct-fitting controls under the declared objective.
If simpler fitting matches it, use that method. If reward improves without better
independent assay metrics, inspect reward misspecification and stop expansion.
If sparse endpoints cannot distinguish dynamics, narrow the claim or acquire a
discriminating measurement; additional RL iterations do not fix identification.

**Scope.** Method comparison for the specified task. Synthetic and measured
results are reported separately; neither establishes a universal cell learner.

## 3. Can a shared model adapt with limited new-context data?

**Purpose.** Determine whether a fixed shared response model plus a restricted
adapter uses new-context observations more effectively than shared-only or
separate fitting. Subject adaptation is one possible context, not a patient twin.

**Prerequisites.** H05 depends on H03/T01 and their measured-data prerequisites.
Implement explicit episode roles and related-group validation first: the current
train/validation/test manifest does not enforce support/query adaptation.

**Protocol.** Fit the shared model using development contexts. Before each new
context episode, declare the support budget, available observation times, allowed
adapter parameters and adaptation algorithm. Fit only from permitted support;
then freeze actual adapter bytes, base-model identity, preprocessing and initial
state before query scoring. Query outcomes cannot select an adapter checkpoint,
initialize hidden memory or tune its hyperparameters. State evolution follows
the frozen transition; additional fitting ends that query campaign.

**Controls.** Shared-only prediction; separate fitting using the same support;
and a hierarchical or restricted-adapter model. Include exposure-summary controls
where history matters. Fit preprocessing on allowed data, declare any use of
unlabeled query features, and compare methods with the same support information.

**Grouping.** Hold out donors/contexts in the outer partition. Keep related
specimens, cultures, preparations and technical replicates together, resolving
overlapping group identities. Within each held-out context, designate support
and query explicitly with temporal cutoffs. Their permitted relationship differs
from the outer context split; do not disguise support rows as ordinary training.

**Metrics.** Query error by context and support budget, gain relative to shared
and separate controls, worst-context error, adaptation failures and total cost.
Use independent-unit uncertainty estimates where replication supports them;
report poor coverage or unsupported contexts rather than silently excluding them.

**Success / failure / next decision.** Retain adaptation if it improves declared
query performance under the support budget across held-out contexts. If it adds
no value, retain shared-only prediction. If gains disappear after grouping or
temporal restrictions, correct leakage and begin a new untouched comparison.
Unidentifiable adapters require fewer fitted parameters or additional evidence.

**Scope.** The specified assay, preparation route and adaptation protocol only.
Donor identity does not establish preservation of all donor properties or clinical
utility. An optional controller selecting support data needs a separate study.

## 4. Do interactions and ensembles improve population prediction?

**Purpose.** Evaluate two distinct objects: heterogeneous cells coexisting within
one physical world, and alternative fitted models defining separate possible
worlds. Uncertainty models must not become extra physical cells.

**Prerequisites.** V04 requires V03/H04/R02/N03; R01 precedes R02. Use P01/P02
if introducing an external solver or live participant. Synthetic interaction
fixtures may prepare these contracts but cannot close the measured V04 gate.
Identify an interaction observable and supporting mixed-population data first.

**Protocol.** Start with a justified second context and one explicit interaction.
Share model weights where appropriate while retaining per-cell context, history
and RNG state. Compute competing material demands from the same snapshot; reject
unsupported collective demand. For model uncertainty, choose a coherent bundle
for each complete rollout. Declare within-population variation separately and
preserve model identity through time. Freeze observation maps and components.

**Controls.** Homogeneous/shared-only population; context-specific cells without
the selected interaction; the justified interacting model; and separate fitted
worlds. Interaction ablations must preserve conservation and comparable inputs.
Label simulator-derived counterfactual credit as model-based, not measured truth.

**Grouping.** Reserve whole co-cultures/tissues and related donors, batches and
preparations. Cells from one shared field are not independent replicates. Reserve
composition or intervention regimes when supported by the design. Component
training must not consume final mixed-population outcomes.

**Metrics.** Population and cell-type observables, spatial/temporal errors where
measured, cohort failures, material residuals, window/refinement sensitivity,
replay and total cost. Evaluate ensemble error and calibrated coverage separately
from its spread; spread alone is not predictive uncertainty.

**Success / failure / next decision.** Retain an interaction if it improves held-out
population prediction beyond component-only controls after numerical gates pass.
If all worlds agree but fail observations, revise the hypothesis set. If coupling
error dominates, refine the numerical model before fitting more flexible cells.
Only a separately evaluated controller may later optimize interventions on the
frozen ensemble, followed by independent experimental assessment.

**Scope.** Supported interactions and observables in the chosen population.
Component accuracy does not establish tumor response, treatment efficacy or
patient-specific utility. Recognition, contact and delivery require their own data.

## Development handoff

Begin with card 1 and the parallel H01/B01 data audit. Card 2 determines whether
an RL trainer is useful; cards 3 and 4 remain gated by measured evidence and the
stated contracts. Consult [TRAINING_SETUP.md](TRAINING_SETUP.md) for current
artifact capabilities and [BIOLOGICAL_VALIDATION.md](BIOLOGICAL_VALIDATION.md)
for the biological evidence boundary. The inspected sources are indexed in
[the research registry](../evidence/research_implementation_sources.json).
No runtime, tests, installations or new experiment results accompany this draft.
