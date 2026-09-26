# Build backlog and explicit completion criteria

Owners and dates are intentionally unset; dependencies and evidence, not schedule estimates, define the sequence.

| ID | Task | Depends on | Required result | State |
|---|---|---|---|---|
| C01 | Expand reference property tests across scales and edge inputs | Delivered core | Failure artifacts and stable invariants, not merely count growth | Partial: new transport/data/failure regressions; broader property coverage remains |
| C02 | Define production state and per-port ownership schema | C01 | Schema/examples, unit conversions, ambiguity rejection | Partial: typed grid/flux/uptake; general ownership remains open |
| C03 | Versioned execution fingerprint and robust restart | C02 | Code/model/order/parameter fingerprint; corrupted/mismatched restore rejected | Partial reference only |
| N01 | Fixed 3D conservative diffusion grid | C01,C02 | Manufactured/exact cases, amount balance, spatial/temporal convergence | Reference slice implemented: fixed orthogonal grid and analytical 3D studies; production gates remain |
| N02 | Single membrane uptake law and typed source | N01 | Positivity, finite reservoir and boundary accounting | Reference slice implemented: saturable transfer and inward flux; no calibrated law |
| N03 | Stiff reaction/uptake and splitting study | N02 | Timesteps/window tolerances derived from QoI error | Open |
| R01 | Choose one matched independent comparator | N01 or selected mechanics contract | Standalone reproducible case and pinned engine build | Open |
| R02 | Refine both numerical implementations | R01 | Discretization error and model difference separated | Open |
| B01 | Acquire/authenticate one oxygen dataset | None | Dataset/rights/identity/units/observation manifest | Open |
| B02 | Freeze biological question and holdout | B01 | Context of use, metrics, experimental-unit split | Open |
| B03 | Fit identifiable parameters and evaluate holdout | B02,N02,R02 | Uncertainty, controls, unchanged holdout and failures | Open |
| P01 | Real shared/private/RNG checkpoint for selected engine | R01,C03 | Restart and implicit rollback demonstrated | Open |
| P02 | Fixed-topology two-participant coupling | P01,R02 | Mapping invariants, iteration and window refinement | Open |
| F01 | Offline surrogate/selector comparison | R02 | Fixed training/selection/test cohorts and full cost ledger | Open |
| F02 | Evaluate switching and state-transfer artifacts | F01,P02 | Rollout errors, false acceptance, abstention | Deferred |
| S01 | Profile and port only bottleneck kernels | N01 plus selected QoI | Matched numerical outputs and measured cold/warm performance | Open |
| S02 | Dynamic topology and large runs | P02,F02,S01 | New topology/restart/transfer evidence; actual memory scaling | Deferred |
| T01 | Dataset/split/candidate preparation contracts | C01 | Artifact hashes, group leakage rejection, immutable evaluation identity | Reference implemented; declarations and file integrity only |
| T02 | Synthetic cell-field trajectory export | N01,N02,T01 | Reproducible rows, predefined condition splits, balances and failed-attempt records | Implemented synthetic fixture; now consumed by T04 |
| T03 | One real data ingestion adapter and baseline training | B01,B02,T01 | Feature/unit mapping, provenance review, training-only preprocessing, baseline outcomes | Open; AnnData/STATE are candidates, not dependencies |
| T04 | Small synthetic response baseline | T02 | Strict payload ingestion, training-only preprocessing, validation selection, frozen grouped test and controls | Reference prototype executed: fitted nearest-neighbor increments and one-step synthetic evaluation; broad ML coverage remains open |
| L01 | Local declarative response-rule infrastructure | N02,C03 | Explicit units/provenance, conservative proposals, accepted-state history and trace | Partial reference: hysteretic concentration switch, gated transfer, synthetic demo and two targeted state regressions |
| L02 | One sourced biological response-rule context | L01,B01,B02 | Authenticated cell identity, parameter/source records, observation mapping and unchanged holdout | Open; oxygen template retains null parameters and is nonrunnable |
| H01 | Observation and exposure-history contracts | T01,B01 for measured data | Source-row and experimental-unit mapping, timing/availability, missingness, destructive versus longitudinal semantics | Proposed; first candidate is Murphy endpoint radii, with unresolved identity/terms mappings |
| H02 | Pure offline continuous response memory | L01,C03 | Explicit initialization/state, exact synthetic relaxation controls, matched-current-input/different-history challenge and replay | Proposed; current switch is discrete hysteresis only |
| H03 | Measured history-response comparison | H01,H02,B02,T03 | Strong summary/model controls, identifiability, verified full candidate bundle, reserved schedules/units or a narrower declared scope | Gated on data sufficiency; does not close integrated B03 |
| H04 | Transaction-owned response state and physical effects | H02,C02,C03; R02,N03 for physical claims | Stage clocks, joint memory/amount rollback, complete checkpoint identity, event handling and coupled refinement | Proposed; synthetic transaction work may precede biological fitting |
| H05 | Shared/context adaptation episodes | H03,T01 | Related-group closure, outer context holdout, fixed support/query budget and adapter-byte verification | Proposed; separate/shared/hierarchical controls required |
| H06 | Optional adaptive experimental acquisition | H03; synthetic-only comparison may start after V01 | Development-only label revelation, fixed batch snapshots, random/coverage/information controls and full costs | Proposed; controller separate from the cell learner |
| V01 | Numeric cell-learning episode environment | H02,H04 reference transaction slice | Causal local observations, typed transfer proposals, fixed evaluator, hidden training targets, complete replay and failure records | Proposed; no environment adapter or trainer implemented |
| V02 | RL versus direct cell-response fitting | V01 | Same allowed inputs and comparable capacity, reserved histories, rollout/distribution error and total costs | Proposed; backend selection follows a demonstrated learning task |
| V03 | Measured evaluation of a learned cell model | V02,H01,B02,T03 | Frozen model and assay map; independent observations with appropriate pairing and uncertainty | Gated; none of the inspected datasets is accepted yet |
| V04 | Interacting cell populations and uncertainty ensembles | V03,H04,R02,N03 | Distinct population/uncertainty semantics, supported interactions, conservative joint demand and tissue-level holdout | Later research; no tumor-response or therapy capability implemented |
| V05 | Optional controller or external trainer adapter | V01 plus measured workload need | Correct numeric/token learner interface, tested build, replay and measured resource costs | Deferred implementation; MiMo inspected as a design reference only |

The implemented slices above do not close their parent work-package gates. See `PROTOTYPE_REPORT.md` for current execution evidence and `BASELINE_PROTOTYPE.md` for the fitted synthetic workflow. `GROUNDWORK_REPORT.md` preserves the earlier preparation stage. T04 does not close T03 or F01; no biological training, independent comparator or cost-benefit result has been produced.

`DOWNSTREAM_LEARNING_PLAN.md` scopes proposed self-play, contrastive-distillation,
calibration and cell-state specialization experiments under F01/T03. Patient
support/query adaptation and typed learned-state continuation require additional
contracts. They are research proposals. Current implementation priority is the
local-rule path L01/L02; R01/R02 and N03 remain open physical verification gates.

The clarified learner is the virtual cell model itself. H02 plus the H04
transaction slice prepare V01, a small synthetic numeric-cell RL environment;
B01/H01/T03 form the parallel measured-data path. This reference work does not
replace the first production transport/independent-verification gates. See
[CELL_MODEL_RL_ENVIRONMENTS.md](CELL_MODEL_RL_ENVIRONMENTS.md) for the MiMo assessment
and ensemble design, and
[RESEARCH_IMPLEMENTATION_EVALUATION.md](RESEARCH_IMPLEMENTATION_EVALUATION.md)
for the actual source/data audit and detailed contracts. No H/V item is completed
by adding these documents or their nonrunnable templates.

The companion [future development targets](FUTURE_DEVELOPMENT_TARGETS.md)
organize these IDs into a staged roadmap and recommend H02 as the next bounded
reference increment. [Research ideas](RESEARCH_IDEAS.md) hold exploratory
hypotheses; [experiment blueprints](EXPERIMENT_BLUEPRINTS.md) define how to assess
them. This table remains the authoritative status ledger. Those drafts do not
complete any implementation or scientific gate.

## Conditions that invalidate a completion claim

A changed assertion without rationale does not resolve a numerical defect. A populated JSON template is not execution evidence. A successful import is not adapter correctness. A matched growth curve on fitted data is not validation. A CPU pass is not GPU verification. Replacing the primary experimental system invalidates its old applicability record unless justified with new evidence.

## Review checklist for each change

Record scope and exact equations, parameter/units provenance, expected invariant, independent test, command and environment, outcome, failures, performance accounting if relevant, and applicability limits. Link all of them to immutable artifacts. Do not claim that the entire architecture is qualified when only one work package has passed.
