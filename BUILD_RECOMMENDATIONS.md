# Build recommendations and scientific considerations

## 1. Recommended scope

Build a **custom, evidence-scoped cellular environment with replaceable numerical models**, not a merger of four complete simulators. The first release should solve one specified biological question with known inputs and observable outputs. Generality should come from explicit interfaces, not from adding every possible process to the first experiment.

The immediate implementation choice is an independent CPU reference path, a typed physical-state contract, and offline comparator jobs. Choose one accelerated or specialist backend only after its corresponding numerical benchmark exists. Warp is a possible kernel backend; SOFA, ESPResSo, and Tissue Forge are candidate comparators for different model classes. Their capabilities do not create an accuracy ordering. [S22–S25]

### Decisions that change the original architecture

| Original direction | Revised recommendation | Reason |
|---|---|---|
| Warp is the central architecture | Biological and numerical contracts are backend independent | JIT/accelerator choice is not biological evidence |
| One complete canonical state owns everything | Shared state plus versioned backend-private state | Projection may discard necessary dynamical memory |
| SOFA/ESPResSo are accuracy oracles | Independently verified comparators for a specified model/QoI | Different equations cannot be compared as implementation replicas |
| Fixed F0–F3 ladder | Observable- and regime-specific portfolio | Cell centers, vertex models, and FEM need not form nested approximations |
| Threshold strain or OOD score establishes qualification | Missing evidence means unqualified; future policy must be tested on held-out outcomes | Confidence scores are not error certificates |
| Live coupling from the beginning | Offline component comparison first, one live interface later | Save/restore, mappings, convergence, and topology are substantial work |
| Vascularized microtumor as first test | Amount transport, then oxygen-perturbed spheroid, then perfusion | The first measurable experiment should isolate fewer unknowns |
| Four passing smoke tests establish the core | Audited regressions plus numerical convergence, failure injection, and restart | Executability is not numerical correctness |

## 2. Build boundaries

**Implement yourself:** experiment semantics, species/entity identity, observation definitions, interventions, event/lineage records, interface quantities, model ownership, amount ledgers, provenance, benchmark specifications, and acceptance decisions.

**Reuse where justified:** numerical linear algebra, mesh/neighbor operations, a selected acceleration runtime, specialist constitutive solvers, SBML readers, and later a coupling library. Do not write a new sparse linear algebra library merely to make the biological model “from scratch.” Conversely, do not let an imported engine silently determine what a cell or intervention means.

**Do not implement yet:** a complete cell metabolism/signaling/epigenetic model, patient-specific prognosis, automatic compound-to-phenotype inference, GPU scale claims, million-cell live federations, general differentiable division, or continuously self-updating learned fidelity policies.

The dependency-free reference core in this package is an executable specification of small invariants. Its all-pairs mechanics, deep copies, and scalar loops are deliberately unsuitable as a large-scale production design. There is no performance claim to defend by retaining them.

## 3. Work packages and completion gates

### W0 — Reproduce and freeze the reference contract

Run `tools/run_checks.py` and archive its source hash, environment, test names, and outputs. Inspect `docs/TRACEABILITY.md`, including changed division semantics. Confirm that state fields use SI amounts and geometry, not unlabeled normalized values. Do not relabel engineering tolerances as experimental ones.

The delivered reference covers selected timing, pair symmetry, division bookkeeping, balance, transaction, and evidence-failure requirements. It does not close W0 for a future production implementation. Port the same independent checks when data structures or kernels change. Add property tests across magnitudes, floating-point precision, zero populations, and adversarial topology before claiming broader readiness.

**Exit evidence:** test outcomes; exact equations; schema version; execution fingerprint; documented unsupported cases. **Not permitted:** “cell simulator validated.”

### W1 — Conservative transport and a fixed cell–field interface

A fixed rectilinear 3D reference slice now complements the 1D/radial fixtures: amount-based passive diffusion, explicit inward boundary flux and one point-sampled saturable cell transfer law. Analytical studies and targeted regressions exercise this slice; W1 remains partial. Retain amounts as authoritative state and derive concentration from compartment volume. Every internal material transfer needs paired source/destination entries. For irreversible consumption or interconversion, specify what leaves the tracked system or which reaction accounts for it.

Test constant fields, analytic modes, unequal voxel volumes, impermeable boundaries, imposed flux, uptake saturation, nonnegative amounts, and decreasing timestep/mesh size. Keep a closed-box mass test separate from an open-system amount ledger. A parameterized nutrient law is not calibrated merely because its dimensions are correct.

Only then add growth or phenotype updates, with parameters and observation maps in a separate versioned model definition.

**Exit evidence:** spatial/temporal refinement; source/boundary accounting; documented positivity/stability behavior; dimensional conversions; stationary and dynamic cases. **Not permitted:** “oxygen physiology reproduced” without data.

### W2 — One independent numerical comparator

Choose the comparator by the first quantity of interest. For force–displacement or stress relaxation, inspect SOFA. For flow and deformable suspended objects, inspect ESPResSo. For a matched particle/vertex interaction law, inspect Tissue Forge. Their official descriptions support these capabilities, not calibrated cancer material laws. [S22–S24]

Run the selected engine as a standalone job first. Export model/mesh/initial conditions and import results. Align equations, material units, geometry, loading, boundary conditions, and solver tolerances. Refine both implementations. If one is a different constitutive model, call the comparison **model discrepancy**, not a failed cross-implementation verification.

**Exit evidence:** pinned dependency manifest, reference case, independent refinement, QoI comparison, license review record, deterministic replay where expected. **Not permitted:** universal high-fidelity ranking.

### W3 — First biological context: oxygen perturbation of a spheroid

Select one authenticated experimental system with obtainable measurements, not a cross-paper combination of unrelated cells. Murphy et al. provide a candidate source of time-dependent oxygen experiments; Bull et al. provide relevant modeling precedent, with the latter's dimensionality restriction retained. [S26,S27]

Write the question before fitting: for example, prediction of a specified spatial viability observable after a held-out change in boundary oxygen, conditional on the chosen spheroid and culture protocol. First verify data accessibility and reuse terms, acquisition times, calibration units, cell identity, and segmentation/measurement definitions. The package contains a study plan, not downloaded biological observations.

Calibrate only on declared development experiments. Freeze parameters and model form before opening a holdout intervention. Split by biological experimental unit—independent spheroid, culture batch, or donor as applicable—not individual frames from the same trajectory. Compare against simpler growth and transport controls. Preserve observations the model fails to explain.

**Exit evidence:** authenticated dataset manifest, independent holdout, observation model, uncertainty/sensitivity analysis, negative results and exclusions. **Not permitted:** patient-specific predictions or generalization to other cancer types.

### W4 — One live coupled interface

Introduce preCICE only when separate solvers work and the interface justifies it. The checked official adapter catalog does not list ready-made SOFA, ESPResSo, or Tissue Forge adapters; this is not a proof that no external adapter exists. Budget explicit adapter implementation and testing. [S05]

Start with fixed topology, fixed model ownership, and one pair of exchanged physical quantities. Define sign/orientation, location, units, interpolation, conservation and virtual-work tests, convergence criterion, maximum iterations, and a failure outcome. No rejected implicit iteration may commit a biological division or consume a random stream irreversibly. preCICE delegates checkpoint content and restoration to participants. [S06,S07]

**Exit evidence:** full rollback/replay; restart; mapping consistency; coupling-step refinement; stable solution under tighter interface tolerance; refusal on unsupported events. **Not permitted:** topology-changing live federation without separate evidence.

### W5 — Offline model selection and reduced-order research

The synthetic plumbing and small offline baseline now run end to end: strict physical JSONL ingestion, training-only range scaling, nearest-neighbor increment fitting, validation selection, candidate/control freeze and test evaluation. The 96 records belong to six conditions assigned before generation. This completes a bounded synthetic prototype; W5's independent-comparator, rollout, uncertainty and cost-benefit gates remain open. No biological model has been trained. See `docs/BASELINE_PROTOTYPE.md` and `docs/PROTOTYPE_REPORT.md` for the workflow and measured results.

Collect reference cases with measured costs and numerical errors. Define training, policy-selection, and untouched test cohorts before building surrogates. Hold out parameters, geometry families, intervention schedules, or regimes—not just seeds. Freeze one selection policy before comparing it with always-cheap, always-reference, and a simple error-trigger control.

Use actual trajectory/QoI error, unsupported-case frequency, false acceptance, conservation drift, and total cost. Record the cost of generating reference data, fitting, failed runs, mappings, restarts, inference, storage and refresh. A useful surrogate can approximate a reference solver without predicting biology; keep the two claims separate. [S11]

**Exit evidence:** held-out cost–error results, full accounting, uncertainty calibration, failure rates, switching artifacts if switching is tested. **Not permitted:** guaranteed unseen-state error from an ensemble spread or low OOD score.

### W6 — Scale, topology, and wider biology

Only after W1–W5 evidence exists, add variable-resolution regions, evolving meshes, many-cell interactions, parallel workers, and higher-level biological mechanisms. Each change can invalidate earlier transfer and error estimates. Report the regime where evidence still applies.

Do not infer million-cell capacity from solver advertisements or illustrative population counts. Measure throughput, memory, setup cost, warm/cold behavior, and validated QoIs on the actual implementation. Acceleration can change numerical errors and reproducibility; repeat relevant verification after porting.

## 4. Minimum module contracts

| Module | Owned state | Declared exchange | Required failure behavior |
|---|---|---|---|
| Mechanics | Positions, mechanical history needed by that model | Forces/displacements with units and orientation | Reject invalid geometry or unresolved solve |
| Transport | Compartment amounts and volumes | Amount flux or rates, not unlabeled concentration changes | Reject negative states and failed balances |
| Intracellular model | Its explicitly named species/state variables | Reaction/transport rates and event proposals | Unsupported conditions remain unsupported |
| Event/lineage system | Identity changes and event history | Atomic create/remove/split operations | No partial topology changes |
| External plugin | Its private state and authorized effect ports | Typed sources, materials, loads or population changes | No arbitrary shared-state writes |
| Specialist adapter | Solver-private state, mesh and integrator history | Explicitly mapped interface variables | Complete rollback or refuse implicit coupling |
| Evidence manager | Provenance and scoped measurements | Applicability records and measured errors | Missing, stale or invalid evidence is not qualification |

The current code enforces broad write categories and amount balances, not the entire future port system. Arbitrary Python extensions are trusted code; they are not sandboxed by this package.

## 5. Model and numerical choices needing explicit decisions

**State sufficiency.** Geometry alone may not encode viscoelastic history, molecular adaptation, cell-cycle state, or contact history. A reduced representation needs a closure model or retained private state. A uniform dataclass does not prove a Markov state. [S01]

**Scale separation.** Estimate diffusion, mechanical relaxation, and response times for the selected model. Use quasi-steady transport only after checking its effect on the relevant observable under transient interventions. Independent nominal timesteps do not automatically control splitting error. [S04]

**Cell representation.** A cell center with a sphere radius, deformable shell, vertex body, and continuum cell/nucleus are competing assumptions. Fit the complexity to the observable and identifiable parameters. Do not label detailed geometry “more biological” without a comparative experiment.

**Chemistry.** Species identity includes compartment, chemical form and units. A drug name cannot supply diffusivity, binding, uptake, metabolism, or phenotype response. Separate tracer transport from therapeutic pharmacology.

**Topology.** Division bookkeeping is not membrane remodeling. State projection must preserve the intended material balances and avoid spurious energy/work. Mesh repair and remeshing can alter model state and require their own tests.

**Uncertainty.** Parameter posterior spread, stochastic variation, numerical error, model discrepancy and observation noise are distinct. They need not be independent. An additive list of errors is not a joint statistical model.

**Observations.** The experiment may observe a fluorescent proxy, image-derived region or sparse time series rather than the model's internal concentration or cell state. Specify the observation operator and calibration before comparing them.

## 6. Execution and dependency policy

Use the dependency-free path for core regression tests. Add each external engine in an isolated, version-pinned environment, recording compiler/ABI, enabled features, OS/architecture, driver when relevant, and a smoke/convergence test. The candidate profiles intentionally have null version/commit fields: no integration has been tested here. Do not fill them with “latest.”

A native CPU development route is sufficient for the delivered fixtures. Hardware acceleration is optional research, not a prerequisite. The current groundwork has recorded Windows 11/Python 3.12.6 CPU results; the initial reference core also has historical Linux/Python 3.13.5 evidence. The new groundwork has not been exercised on Linux, and macOS and GPU paths remain untested.

Before distributing any combined binary or service, check the actual pinned repositories and subcomponents for applicable license obligations and data/model terms. Process isolation is not a substitute for a licensing determination. No third-party component is automatically fetched by this package.

## 7. Research acceptance and stopping rules

Reject or narrow a model when it matches aggregate growth but fails the held-out spatial response, when posterior predictions depend on unsupported priors, or when a more complicated model cannot improve the predeclared QoI over a simpler control. Preserve those failures; do not silently replace cohorts or redefine the outcome.

Stop a coupled rollout if the interface does not converge, a balance residual exceeds the declared tolerance, a required state variable is unavailable, a checkpoint cannot restore its private solver state, or a requested intervention has no justified response model. A run may still be useful as an explicitly exploratory output, but it must not be marked qualified.

For a learned selector, report abstention and false acceptance rather than treating forced selection as success. An evidence gap should remain visible even when a slow solver is available: increasing resolution does not remove model-form error.

## 8. Immediate next build recommendation

Prioritize the local biological-rule infrastructure: extend the existing declarative concentration switch and gated conservative transfer only with explicit units, ownership, accepted-state history and sourced parameter context. The runnable example remains synthetic; populate the oxygen planning template only after authenticating a matching experimental context and its observations. Rules that need missing biological parameters should remain unresolved.

The fixed 3D transport and small fitted synthetic baseline provide supporting reference paths. Independent numerical comparison and coupled uptake/splitting refinement remain open prerequisites for stronger physical claims. Real biological ingestion/training, learned rollout and cost-benefit evaluation also remain open. See `docs/BUILD_BACKLOG.md` and `docs/PROTOTYPE_REPORT.md` for current work boundaries.

That sequence preserves the ambitious external-interaction environment while creating testable evidence at each step.
