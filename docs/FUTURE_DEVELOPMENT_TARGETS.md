# Future development targets

Drafted 25 September 2026. This document organizes proposed work; completion
status remains authoritative in [BUILD_BACKLOG.md](BUILD_BACKLOG.md) and
[IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md). Owners, dates, training
budgets and biological acceptance thresholds are intentionally unset.

## Direction

Build reusable **virtual cell models that learn responses to their environment**,
retain relevant history, and interact through explicit physical interfaces.
Train and evaluate those models in reproducible numerical environments. Assemble
qualified components into cell populations and eventually tissue-response studies.
An agentic experiment controller is an optional outer layer.

The initial scientific objective is predictive fidelity: reproduce declared
measurements under new conditions. Designing cells or interventions to achieve a
desired outcome is a separate later objective with its own evaluation.

### Read this set together

- **This document:** implementation sequence, deliverables and promotion gates.
- **[Research ideas](RESEARCH_IDEAS.md):** hypotheses worth exploring and reasons
  to retain, narrow or abandon them.
- **[Experiment blueprints](EXPERIMENT_BLUEPRINTS.md):** comparisons that can turn
  an idea into evidence.
- **[RL environment design](CELL_MODEL_RL_ENVIRONMENTS.md):** learner, environment,
  reward, ensemble and MiMo integration boundaries.
- **[Implementation evaluation](RESEARCH_IMPLEMENTATION_EVALUATION.md):** data
  availability, numerical contracts and inspected sources.

## Starting point

The repository supplies conservative reference transport, typed same-species
transfers, discrete hysteresis rules, grouped training declarations and a small
synthetic endpoint predictor. Continuous response memory, a numeric RL episode
environment, biological ingestion, cell-model RL training and tissue ensembles
remain proposed work.

The existing execution record applies to that reference scope. A new document,
configuration or model weight file does not complete a development milestone.

## Development sequence

| Stage | Development target | Existing backlog IDs | Deliverable that advances the project |
|---|---|---|---|
| 1 | Explicit response memory | H02 | Pure numeric transition with inspectable state, initialization and model identity |
| 2 | Transactional cell-learning environment | H04 reference slice, V01 | Reproducible episodes with local observations, typed actions, fixed feedback and replay |
| 3 | Learning-method comparison | V02 | Frozen comparison of fitted, supervised and RL cell models on a useful sequential task |
| Parallel data track | One measured assay pipeline | B01, B02, H01, T03 | Traceable observations, exposure histories, independent units and a declared holdout |
| 4 | Measured response and context adaptation | H03, H05, V03 | A scoped biological prediction result and a separately evaluated adaptation protocol |
| 5 | Interacting populations and alternative model worlds | H04, V04, R01/R02, N03 | Supported interactions, joint conservation and population-level evaluation |
| 6 | Optional automated experimentation and external training | H06, V05 | Demonstrated acquisition or training benefit with complete cost accounting |

The reference learning path can begin on the local CPU. The first production
physical extension retains its existing transport, independent-comparison and
splitting gates. An offline assay comparison can proceed without waiting for a
large engine when its equations do not require one.

## Target 1 — Explicit response memory

**Purpose:** let a virtual cell's future response depend on its accepted history.

Proposed additions are `response_state.py` and `response_memory.py` under
`src/cellsim_v2`. Final filenames may change when implementing the contract.

- Define state identity, cell/context identity, units, time, initialization
  provenance and the model definition that can advance it.
- Start with a small deterministic relaxation law and synthetic parameters.
- Return a replacement state and declared observations without mutating inputs.
- Keep dimensionless latent state separate from molecular amounts.
- Include histories that reach the same current environment but require different
  future predictions under the known synthetic law.

**Promotion gate:** transparent numerical reference, preserved state across
continuation, explicit failure on missing/incompatible history, and meaningful
memory-versus-summary controls. This establishes an engineering capability.

**Next decision:** retain the smallest state that the comparison needs. Adding a
recurrent neural network is a hypothesis to evaluate after this contract works.

## Target 2 — A cell-model training environment

**Purpose:** turn the reference simulator into a controlled source of sequential
training episodes for numeric cell policies.

- Extend `World`/`Update`, scheduler ownership and checkpoint identity together
  so response memory and material effects commit or reject atomically.
- Specify process-stage clocks and intervention discontinuities explicitly.
- Add reset, step, observation, scoring, termination and replay operations.
- Restrict the first action space to one supported transfer and fixed topology.
- Separate policy-visible inputs from reference parameters and future outcomes.
- Record complete episode provenance, accepted/rejected proposals and costs.
- Freeze weights while collecting each episode; keep evolving response state
  distinct from a training update.

**Promotion gate:** replay and rejected-step behavior are demonstrated, hidden
targets do not enter policy observations, and all material changes have valid
paired transfers or a justified ledger entry. Unsupported behavior fails explicitly.

**Next decision:** assess whether the environment presents a learnable sequential
problem. Its first policies can be fixed or fitted controls; a distributed trainer
is not required to establish the environment contract.

## Target 3 — Establish when RL is useful

**Purpose:** evaluate RL as a training method for the virtual cell itself.

Use the same task and permitted information for small fitted models, supervised
sequence models and a numeric RL candidate. Compare comparable model capacity
where possible, and record remaining differences. Keep the observation operator,
intervention families and scoring fixed.

Evaluate trajectory/endpoint error, distributional behavior when relevant,
constraint failures, generalization across histories and total cost. A return
computed from hidden training targets is still training feedback; the final
benchmark never participates in optimization or curriculum decisions.

**Promotion gate:** a useful measured advantage on the declared objective, or a
clear negative result identifying when a simpler method is sufficient. Numeric
backend selection requires an actually exercised build and correct action
distribution/log-probability handling.

**Next decision:** retain a simple trainer if it suffices. MiMo-style task and
grader organization can inform the design independently of its LLM token trainer.

## Parallel target — Make one assay usable

**Purpose:** create a trustworthy bridge from measurements to learning targets.

The prior audit identifies small Murphy spheroid endpoint tables as an ingestion
candidate. Select a source only after resolving its use terms, biological context,
specimen identities, schedule mapping and observation definition. Preserve raw
rows, author quality flags and our exclusions separately.

Destructive endpoints remain population observations. Use original measurement
units with explicit conversions. A categorical exposure is acceptable when the
data do not support a physical concentration estimate.

**Promotion gate:** an accepted observation manifest and frozen study question,
with independent units and a feasible evaluation split. If the data cannot test
history generalization, narrow the claim rather than invent trajectories.

## Target 4 — Shared models and limited adaptation

**Purpose:** determine whether common response structure reduces the observations
needed for a new cell context.

Begin with shared parameters plus small context-specific parameter subsets.
Compare shared-only, separately fitted and hierarchical models. Add a learned
adapter only if it improves the declared comparison. Treat donor-specific work
as a later, explicit support/query protocol with an outer donor holdout.

**Promotion gate:** benefit on unseen contexts under a fixed support budget, with
preprocessing, initialization and adaptation frozen before query scoring. Report
contexts where transfer harms prediction.

**Next decision:** broaden the context library one justified assay at a time.
Cell identity, preparation history and functional competence remain separate
parts of the evidence record.

## Target 5 — Interacting populations and tissue response

**Purpose:** compose trained cell models into a shared physical environment.

Start with two declared response contexts and one measured or explicitly
synthetic interaction. Reuse weights where appropriate while preserving private
cell state. Compute competing material demands from a common snapshot. Introduce
contact, signaling, reactions or topology only with their own laws and checks.

Maintain two distinct ensemble axes:

- **Within a world:** biological heterogeneity among coexisting cell instances.
- **Across worlds:** alternative model forms or parameter fits representing
  specified uncertainty.

**Promotion gate:** independent numerical comparison and coupled refinement,
supported interaction measurements, and a population-level holdout that was not
used to tune components. Component accuracy alone does not establish composition.

**Later applications:** tumor microenvironment response, engineered immune-cell
interactions, cell manufacturing and other tissue/culture research. Each adds its
own observable, interaction model and evidence requirements. Any intervention
controller evaluates frozen response models; it cannot improve its score by
changing the simulated biology to match the desired result.

## Target 6 — Optional self-play and experimental automation

**Purpose:** spend development compute or experimental measurements more usefully.

A curriculum proposer can select supported exposure histories and cell contexts.
A later experiment controller can identify measurements that distinguish competing
models. Compare these against random, fixed-coverage and information-based controls.
Record all generation, labels, training, failed work and evaluation costs.

**Promotion gate:** benefit on independently reserved tasks at a matched resource
budget. Mutual agreement among learned cells or evaluators does not create new
experimental evidence. An LLM controller is useful only if it improves a defined
task enough to justify its added complexity and cost.

## First development session

Recommended bounded scope: **H02, the pure synthetic memory reference**.

1. Read the canonical project instructions and state/scheduler/checkpoint contracts.
2. Define the response-state schema, initialization and time semantics.
3. Specify the synthetic relaxation equation and expected discrete behavior.
4. Implement the pure transition and its declared observation output.
5. When implementing, add the appropriate targeted checks, including a regression
   before any fix; preserve failures and complete execution evidence.
6. Record exact commands, source/test/tool hash, environment, numerical settings,
   outcomes and remaining limitations. Update H02 only to the scope actually shown.

Keep neural training, live solver integration, biological parameters and dynamic
topology for their dependent targets. This makes the first change independently
reviewable and supplies the state contract needed by V01.

## Maintaining the roadmap

Use [BUILD_BACKLOG.md](BUILD_BACKLOG.md) as the single task-status ledger. Link
new evidence there when a target advances. Keep speculative questions in
[RESEARCH_IDEAS.md](RESEARCH_IDEAS.md) and promote them through a predeclared
[experiment blueprint](EXPERIMENT_BLUEPRINTS.md). Record negative results and
reasons to defer a target alongside successes.

This drafting pass changes Markdown and release-integrity records only. Runtime
and test code remain unchanged; no new training, biological fitting or numerical
campaign is implied. The existing baseline is preserved in `runs/checks_weh0phac/`.
