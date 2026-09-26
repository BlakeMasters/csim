# Verification audit: proposed multi-fidelity cellular simulation architecture

**Audit date:** 17 September 2026  
**Status:** evidence review, source inspection, executable acceptance probes and conditional mathematical analysis; not biological or regulatory validation.  
**Artifact audited:** `multifidelity_cell_sim_architecture.zip`  
**Original SHA-256:** `e0e7df515b25389598123943400377729accbbb7874c865feb5f677e98a7b5c1`

## Executive assessment

The literature supports modular process/state composition, hybrid discrete-cell/continuum-field models, multirate numerical execution, partitioned multiphysics, model interchange and context-dependent credibility assessment. It does not establish that the proposed combination of Warp, SOFA, ESPResSo, Tissue Forge and preCICE has been integrated, has a common sufficient biological state, switches representations accurately, or meets an experimentally grounded error tolerance. These are separate propositions.

Several earlier statements therefore need narrowing. Specialist solvers are numerical comparators, not biological oracles. A finer mesh is not necessarily a more accurate biological model. The FDA guidance is not approval and explicitly excludes standalone machine learning. A morphologically vascularized spheroid is not automatically a perfused preparation. A calibrated tumor model need not predict a withheld perturbation. Existing compositional and regional hybrid models also prevent a broad novelty claim.

The supplied package explicitly labels its numerical routines as toys. All **four original tests pass**, and its example runs. However, **16 targeted additional checks produce 4 passes, 12 failures and no test errors**: eight failures concern numerical/state requirements; four concern proposed input/evidence safeguards. These were deliberately chosen probes, not a random sample from which a defect percentage should be estimated. No specialist physics engine, GPU kernel, wet-lab dataset, or biological prediction was executed in this audit.

The defensible present claim is: **a literature-informed architectural proposal with a small executable scaffold and identified implementation defects**. A credible integrated simulator remains a development and validation objective, not a demonstrated result.

## 1. Audit method and evidence hierarchy

This audit uses 30 primary-source, author-institution, official-documentation or explicitly classified methodological records. The registry records titles, DOI identifiers where applicable, access depth, support and limitations. Twenty-six claims are recorded in the accompanying CSV/JSON matrix. The systems-biology credibility review is included to establish what it proposes, not as primary experimental proof. Abstract-only checks are explicitly labeled. See `SOURCES.md` and `../evidence/source_registry.json`.

Four different propositions must not be conflated:

| Proposition | What would support it |
|---|---|
| A method is established | Relevant primary methods literature or official specification |
| Code solves the intended mathematical problem | Analytical/manufactured solutions, numerical convergence, invariants and independent implementations |
| A model predicts an experimental observable | Comparison against independent measurements with matched conditions and uncertainty |
| A tool is accepted for a regulated purpose | A specific qualification or submission decision, not mere citation of guidance |

A paper describing one solver is not evidence that a new adapter works. Likewise, importing a file format, passing a smoke test, or reproducing a teacher solver does not establish biological validity. The FDA's context-specific framework is useful for structuring these distinctions, subject to its stated scope. [S09]

This is a targeted audit of the consequential claims, not a systematic review claiming exhaustive coverage of all cancer modeling literature. Full ASME V&V 40 text was not inspected, and no compliance determination was made.

## 2. What the implementation actually does

The unchanged archive was checksum-verified and extracted into an isolated audit directory. Source inspection establishes the following implementation boundary.

| Component | Actual artifact status |
|---|---|
| Canonical state | Python dataclasses and dictionaries for cells, fields, external entities and metadata |
| Process abstraction | Read/write/unit declarations and `evaluate`/`StateDelta` methods; declarations are not enforced |
| Scheduling | Priority-ordered multirate loop with full-state deep copies |
| Native mechanics | Toy center-based pairwise overlap relaxation |
| Transport | Homogeneous explicit-Euler decay, clipped at zero; no spatial transport PDE |
| Intracellular state | Toy hypoxia response, not an SBML reaction-network solver |
| Fidelity | Threshold classifier; no error estimator, applicability database or runtime backend switching |
| SOFA/ESPResSo/Tissue Forge/preCICE | Adapter placeholders raising `NotImplementedError` |
| Warp | No implemented Warp backend |
| Integrated example | Two spherical cell centers and two normalized oxygen values |
| Vascular microtumor YAML | Design configuration, not loaded by the runnable example |
| Experimental validation | No calibration or independent biological validation performed |

The example calls the fidelity classifier once after advancing the simulation, with hardcoded strain and gradient inputs. Its printed `F1_DETAILED_NATIVE` label is not execution of a detailed solver. The 1,000-cell/vessel/chemical configuration is not the system exercised by that example.

There is no implemented FEM, lattice-Boltzmann fluid solver, diffusion mesh, chemical boundary exchange, preCICE coupling iteration, surrogate training, or switching history. The present mechanics loop is quadratic in the number of supplied entities; the scheduler deep-copies the world on each process execution. Million-cell performance and specialist-like accuracy at native throughput are therefore design aspirations, not measurements. [Local source: `examples/run_microtumor.py`; `src/cellsim/backends/`; `src/cellsim/core/`; `src/cellsim/processes/`]

### 2.1 Original tests

The original command `PYTHONPATH=src python -m unittest discover -s tests -v` passes all four tests. The example also completes. The original tests check basic delta application, a manually balanced scalar exchange, threshold branches and the fact that decay decreases a value while the final clock equals the requested time. Those assertions do not test integration length, force symmetry, conservation under division, rollback, or actual specialist coupling.

### 2.2 Additional acceptance checks

The additional test file is shipped unchanged with machine-readable outcomes and complete assertion traces. The table states the tested requirement, not a claim that every requirement was explicitly promised by the original toy API.

| Check | Observed result | Interpretation |
|---|---|---|
| Zero elapsed time | `advance(..., until=0)` applies a full decay step | Continuous state advances without elapsed time |
| Endpoint integration | Three half-second Euler steps occur for a one-second interval | Endpoint is integrated once too often |
| Isolated equal pair | Midpoint changes from 0.75 to 0.7375 | Pair response is asymmetric under equal-mobility assumptions |
| Entity permutation | Reversing entity order changes positions | Physics depends on enumeration order |
| Instantaneous division | Total radius-cubed doubles from 1 to 2 | No conservative split under the tested no-growth event semantics |
| Repeated division | Second division of retained parent collides with `a.g1` | Lineage/identifier update is incomplete |
| Rejected state delta | Position changes survive a later duplicate-ID exception | Commit is not atomic |
| Absolute-error report | A loss of 0.5 is reported as absolute error -0.5 | Field name and computation disagree |
| Zero process timestep | Construction succeeds | Proposed preflight validation is absent; no infinite loop was executed |
| Nonfinite fidelity metric | NaN is accepted | Invalid measurement does not fail closed |
| Missing fidelity evidence | Empty metrics produce an affirmative qualification reason | No evidence is mistaken for a qualified regime |
| Declared writes | A process declaring no writes can change a position | Interface declaration is not an enforced contract |

Four positive controls pass: nonoverlapping cells remain stationary; an explicitly equal-unit amount exchange balances; a deep copy isolates nested state; backwards time is rejected.

For decay rate 0.1, initial value 1 and timestep 0.5, two explicit-Euler steps should return

\[
(1-0.1\times0.5)^2 = 0.9025.
\]

The implementation returns

\[
(1-0.1\times0.5)^3 = 0.857375.
\]

The reference here is the expected **discrete Euler method**, not the exact exponential solution. This isolates the extra-step defect from ordinary discretization error. The scheduler executes at 0, 0.5 and 1.0 while applying a full timestep at each event.

For pair mechanics, the loop adds the interaction to the earlier entity but never adds its counterpart to the later entity. This is a symmetry defect in the toy pair law, not a claim that momentum must be conserved in every overdamped, actively driven biological model.

The division check assumes an instantaneous split without growth or a material source. A phenomenological birth model can use different semantics, but those semantics must be explicit rather than silently interpreted as conservative physical division. Similarly, atomic commit and enforced write contracts are necessary proposed architecture requirements, not features the original implementation already guaranteed.

## 3. Source-by-source verification of the main methodological claims

### 3.1 State/process separation: supported, not universal state sufficiency

Vivarium demonstrates processes connected through stores, heterogeneous model composition and different process timescales. Its paper already discusses restriction/lifting and solver-private state. That supports a shared interface, but not the proposition that every solver's history can be reconstructed from positions, concentrations and phenotype labels. [S01]

The Cell Behavior Ontology supports shared biological semantics. The cited MultiCellDS work proposes digital cell-line and snapshot descriptions and is a 2016 preprint in the reviewed source record. Neither establishes complete, lossless interoperation of arbitrary solver states. [S02, S03]

**Revision:** own the shared biological semantics and exchange state, but also preserve versioned backend-private state, event history and random-number generator state when they influence continuation. A canonical interchange schema and an exact restart format are different objects.

### 3.2 Hybrid cells and fields: supported under declared approximations

PhysiCell is primary evidence for discrete cells coupled to substrate transport and for separating diffusion, mechanics and phenotype timescales. Bull et al. provide an experimentally connected spheroid example combining off-lattice cells and a continuous oxygen calculation, but their reported simulations are restricted to two dimensions. [S04, S26]

These papers justify the decomposition, not the particular timesteps in the ZIP. Convergence must be checked for the actual coupled equations, boundary conditions and quantities of interest. An implementation using several timestep values is not automatically a verified multirate integrator.

### 3.3 Specialist solvers and preCICE: feasible infrastructure, missing integrations

SOFA documents nonlinear mechanics and multiple geometric representations. ESPResSo documents triangulated elastic objects coupled to fluid. Tissue Forge documents vertex/body mechanics and qualifies the maturity of automatic mesh-quality operations, particularly in three dimensions. Those capabilities are relevant, but they do not rank biological accuracy or calibrate tumor-cell materials. [S22–S24]

The current official preCICE adapter overview does **not list SOFA, ESPResSo or Tissue Forge**. This does not prove that no external or private adapter exists; it means ready-made support for the named stack was not verified. [S05]

preCICE requires participants to implement their own save/restore operations for implicit coupling. Its documentation also requires repeatable outputs from restored state and identical inputs for quasi-Newton coupling. For stochastic biology, preserving RNG and event state follows as an additional adapter requirement. [S06]

Its mapping documentation distinguishes global-sum conservation for extensive data from interpolation of intensive variables. That does not automatically guarantee every force/torque/virtual-work identity, nor does it supply chemical stoichiometry or biological state-transfer rules. [S07]

**Revision:** first use specialist solvers offline as independently configured comparators. Introduce live partitioned coupling only after mapping, restart, interface iteration and coupling-step convergence are measured.

### 3.4 BioModels cross-engine result: verified, with a narrow transfer scope

Smith et al.'s *Verification and reproducible curation of the BioModels repository* was published on 4 December 2025. The reported 932/1,055 result is genuine: at least two of five engines agreed for those ODE models. The work includes standardized template experiments and does not mean that every original paper result was reproduced. [S08]

This is strong precedent for cross-implementation verification. It is not verification of spatial cell/fluid coupling, validation against cancer tissue, or evidence that different constitutive models ought to agree. A meaningful cross-engine comparison must first align equations, units, parameters, initial/boundary conditions, observables and numerical tolerances.

### 3.5 Regulatory credibility: useful methodology, limited scope

The earlier statement that FDA guidance does not approve this architecture was correct. An important omitted condition is that the November 2023 guidance explicitly excludes standalone statistical/ML models and addresses only first-principles aspects of hybrid models. It is nonbinding medical-device guidance, not approval of a tumor simulator or of the proposed learned fidelity controller. [S09]

Tatka et al. propose adapting credibility practice to computational systems biology. That paper is a review and methodological proposal, not an issued standard or a validation study of this architecture. [S10]

**Revision:** use a context-of-use evidence record, but separately justify the ML component. Do not label a software object `CredibilityCase` as evidence that such a case has been established.

### 3.6 Multifidelity surrogates: precedent, not inherited accuracy

Sajjadinia et al. describe low-/high-fidelity soft-tissue finite-element surrogate modeling. The author-institution abstract and bibliographic record were verified; a full methods audit of that paper was not completed here. It supports feasibility, not a numeric speedup claim for this project, online coverage guarantees, or transfer to tumor phenotypes. [S11]

The F0–F3 hierarchy is a proposed organization. SOFA, ESPResSo and Tissue Forge often represent different physical models, not simply successive mesh refinements of one model. A portfolio indexed by observable and regime is more defensible than assuming a universal accuracy ordering.

### 3.7 Novelty: not established

Kim, Stolarska and Othmer's 2007 primary modeling paper already combines discrete growing tumor regions with continuum quiescent/necrotic regions and extracellular matrix. Vivarium supplies compositional state/process and multiscale prior art. [S12, S01]

The current *Process Bigraphs and the Architecture of Compositional Systems Biology* preprint, version 2 dated 14 August 2026, is additional closely related prior art for typed composition, hierarchy and model translation. It is a preprint, not peer-reviewed validation. [S13]

The exact proposed controller may still support a specific research contribution, but novelty requires a narrower comparison. The absence of an identical system in this targeted search does not establish priority.

## 4. Biological evidence: useful experiments, narrower claims

### 4.1 Distinguish vascular morphology from functional perfusion

Ascheid et al. (2024) construct a four-population spheroid system and evaluate pseudovascular organization and drug-response phenotypes using imaging. The in-vitro spheroid results support a morphology/TME benchmark, not demonstrated spheroid perfusion. The paper also reports separate in-vivo perfused-vessel comparisons; it would be incorrect to say that the entire paper contains no perfusion-related evidence. [S14]

Quintard et al. (2024) demonstrate functional vascularization/perfusion with mesenchymal and pancreatic-islet spheroids and vascular organoids. This is relevant vascular-engineering methodology; the tested systems are not a cancer-treatment validation dataset. [S15]

Skubal et al. (2025) provide a more directly relevant renal-cancer chip with sprouting, bead transport and fluorescein experiments. Figure 3 specifies one chip for bead perfusion and four for tracer measurements. These are scoped observables: beads are not deformable cells, and fluorescein is not a general therapeutic's pharmacokinetics. [S16]

**Revision:** assign each experiment only to the quantities it measures. Do not aggregate “vascularized” papers into one broad claim that fluid dynamics, tumor biology and drug response have all been independently validated.

### 4.2 ABC calibration is real but conditional on model and data

Wang et al. (2024) calibrate a two-dimensional Voronoi tumor-growth model to mouse xenograft data using SMC-ABC. The simplified model omits cell death. The paper removes declining late measurements for one mouse because that behavior conflicts with its assumptions. These are explicit limitations on the supported use. [S17]

The breast-labeled dataset uses MDA-MB435. Cellosaurus flags MDA-MB-435 as a misidentified M14 melanoma derivative. This resource-level warning does not retrospectively assay the historical vial, but it requires a clear identity qualification before drawing breast-specific conclusions. [S18]

A posterior distribution is conditional on model form, observation model, priors and selected data. It is not a complete distribution over all sources of predictive error. Calibration data should not also serve as independent validation; splitting by independent experiment/batch or biological context is often more informative than random rows from one trajectory.

### 4.3 Oxygen perturbation is a useful first biological target

Bull et al. supply a hybrid spheroid model and show why similar bulk growth does not imply identical internal cell composition. Murphy et al. (2023) provide time-dependent oxygen experiments in authenticated melanoma cell lines and mechanistic growth/adaptation analysis. These are useful sources of predeclared observables, not validation of the supplied code. [S26, S27]

A first experiment should therefore measure more than spheroid radius: radial oxygen/viability structure, proliferative fraction, necrotic region and response to changed boundary oxygen provide additional constraints. This is a proposed experimental design, not a result obtained here.

### 4.4 Mechanics has direct experimental support, not universal thresholds

Stöberl et al. (2024) report nuclear deformation and migration dynamics in compliant three-dimensional hydrogel channels, with a physical model of changing force generation. Bastianello et al. (2024) connect confined mitosis with chromosome-segregation defects and molecular changes in their studied systems. [S29, S30]

These primary studies support selecting confinement mechanics and cell-state consequences as observables. They do not supply a universal strain threshold for rupture, mutation or solver escalation. A local mechanical error target also does not automatically bound the error in downstream division, damage or survival probability.

## 5. Conditional mathematical results and counterexamples

The following statements are derived here. They are not claims that the current software satisfies their assumptions.

### 5.1 A shared schema need not be a sufficient dynamical state

Let detailed state be \(y\), coarse projection \(R\), and detailed evolution over a step \(\Phi_h\). If there exist \(y_1,y_2\) for which

\[
R(y_1)=R(y_2),\qquad R(\Phi_h(y_1))\ne R(\Phi_h(y_2)),
\]

then no deterministic coarse Markov map \(G\) can satisfy \(G(Ry)=R(\Phi_h y)\) for both states. Proof: the input to \(G\) is identical while the required outputs differ.

This gives a precise requirement for state design. When hidden stress, chemical history or internal solver variables alter future behavior, either expose sufficient history, carry a closure model, or acknowledge unresolved uncertainty. A common field name cannot recover discarded information.

### 5.2 Restriction and lifting must distinguish a state from an increment

The earlier schematic update \(x_{n+1}=x_n+L(S(Rx_n))\) is incorrect if \(S\) returns a full state and \(L\) reconstructs a full state. With all maps equal to the identity, it doubles \(x_n\) although no evolution occurred.

For full-state reconstruction, use replacement \(x_{n+1}=L(\Phi_h(Rx_n))\). For a subset of fields, a compatible update can be written

\[
x_{n+1}=x_n+P\left[L(\Phi_h(Rx_n))-x_n\right],
\]

where \(P\) selects replaced components and all operations are dimensionally consistent. This does not eliminate reconstruction error; it fixes state-versus-increment semantics.

### 5.3 Displacement and force maps can preserve discrete virtual work

If fine displacements satisfy \(u_f=H u_c\), choose nodal force transfer \(f_c=H^T f_f\). Then

\[
f_c^T\delta u_c=f_f^TH\delta u_c=f_f^T\delta u_f.
\]

This proves a discrete work identity for the stated maps. Traction-field representations require the appropriate quadrature weights. The identity alone does not establish nonlinear stability, correct contact, torque preservation or biological validity. These are additional conditions, not consequences of naming an interpolation “conservative.”

### 5.4 Chemical conservation must be an amount balance

With concentration \(c_{vk}\), voxel volume \(V_v\), and intracellular amount \(n_{ik}\), total amount is

\[
M_k=\sum_v V_v c_{vk}+\sum_i n_{ik}.
\]

The current helper sums raw field values and cell values without volume or unit conversion. For a counterexample, volumes \((1,9)\) and concentrations \((1,1)\) give amount 10. Changing concentrations to \((0.5,1.5)\) leaves their raw sum at 2 but increases amount to 14. Thus an unchanged concentration sum can conceal a 40% amount change.

Reactions can change individual species. For \(\dot n=Nv(n)\), a linear conserved moiety must satisfy \(\ell^TN=0\); then \(d(\ell^T n)/dt=0\) absent boundary/source terms. The engine must distinguish transfer, reaction and external source/sink ledgers rather than demand every species be individually conserved.

### 5.5 Teacher agreement cannot establish biological prediction error

Let \(q_H\) be a teacher solver, \(\hat q\) a surrogate and \(y\) the physical observable. The triangle inequality gives

\[
|\hat q-y|\le |\hat q-q_H|+|q_H-y|.
\]

Surrogate training may reduce the first term. It gives no bound on the second term without independent evidence. A perfectly reproduced incorrect constitutive law remains incorrect.

Likewise, \(\widehat E+\lambda U\le\epsilon\) is merely a score until the meanings of \(U\), coverage, calibration distribution and tolerance have been specified and tested. An ensemble spread or out-of-distribution score is not automatically a confidence bound. Sequential decisions and distribution shifts must be evaluated explicitly.

### 5.6 Local discrepancy requires a global stability argument

Suppose a reference map is Lipschitz with constant \(L\) in a common norm. Let \(e_n\) be state error, \(\eta_n\) the local approximate-update error, and \(\sigma_n\) the switching/projection error. Under aligned timesteps and states,

\[
e_{n+1}\le L e_n+\eta_n+\sigma_n.
\]

Induction yields

\[
e_N\le L^N e_0+\sum_{n=0}^{N-1} L^{N-1-n}(\eta_n+\sigma_n).
\]

Even small local errors can accumulate or amplify. Switching error must be budgeted rather than omitted. Discrete events, discontinuous contacts and changing topology require additional analysis; the stated bound cannot simply be transferred to them. The current threshold controller estimates none of these terms.

### 5.7 Error categories are not automatically independent uncertainties

A telescoping comparison can define signed model, numerical and surrogate discrepancies, but a sum of labels is not an uncertainty model. For random errors,

\[
\operatorname{Var}\!\left(\sum_i E_i\right)=\sum_i\operatorname{Var}(E_i)+2\sum_{i<j}\operatorname{Cov}(E_i,E_j).
\]

Ignoring dependence requires an argument. Biological variation, parameter uncertainty, measurement noise, model discrepancy and numerical error should not be collapsed into a single unexplained fidelity number.

## 6. Evidence-adjusted architecture

The design should preserve the original modular objective while changing execution and qualification semantics.

```text
Question + observable + context of use
                 |
Shared physical state and explicit units
                 |
Process contracts + transactional state updates
                 |
Verified scheduler and event semantics
                 |
Solver/model portfolio, keyed by observable and applicability
       |                     |
Verified native path     Offline specialist comparators
       |                     |
       +---- calibrated discrepancy records ----+
                                                |
                           Frozen, tested fidelity policy
                                                |
                       Optional verified live co-simulation
                                                |
                          Independent biological evaluation
```

Backend-private restart state accompanies the shared state; it is not discarded merely because the biological schema is canonical. A failed update cannot leave partial state behind. Source/sink and reaction ledgers are explicit. Nonfinite inputs and missing evidence produce an unqualified result or a declared fallback, not an affirmative credibility label.

Each experiment should reference a specific model version, solver version, adapter version, parameter domain, dataset split and observable. Changes to a surrogate or its training data create a new version that must be requalified. Online learning should not silently alter a solver during a held-out comparison.

The standards layer is also narrower than the earlier diagram implied. SBML and SED-ML have supported feature sets that must be checked per engine. OMEX is a container with a mandatory manifest; adding custom geometry and YAML is allowed, but it does not make those extensions independently executable. MIASE specifies reporting information, not empirical correctness. [S19–S21, S28]

Warp remains one candidate execution backend. Its documented capabilities do not establish workload-specific speed or biological accuracy. Neither the prior million-cell illustration nor projected surrogate throughput should be quoted as an achieved result. [S25]

## 7. Research gates and acceptable claims

| Gate | Required experiment | Claim allowed only after success |
|---|---|---|
| G0: numerical/state foundation | Correct scheduler endpoints; pair symmetry; conservative division semantics; unique lineage IDs; atomic failure; invalid-input rejection | The tested core invariants hold for the tested configurations |
| G1: transport/mechanics verification | Exact/manufactured solutions, positivity and amount ledgers, spatial/temporal convergence | The implementation solves the declared equations to measured tolerances |
| G2: matched independent implementation | Same model, units, parameters and boundary conditions in native and specialist solvers; refine both | Cross-implementation agreement within the tested regime |
| G3: coupling and restart | Repeated rollback, RNG restoration, force/work transfer, moving geometry and coupling-step refinement | The tested coupling/restart path is numerically controlled |
| G4: component calibration/validation | Fit on development assays; predict independent geometry/load/oxygen conditions | Context-specific predictive capability for selected observables |
| G5: integrated biological holdout | Independent spheroid or chip experiment with declared measurement model and uncertainty | Validated integrated predictions for that context, not all tumors |
| G6: frozen surrogate/fidelity policy | Held-out reference solves, long-horizon rollout error, false-acceptance rate, switching artifacts and fallback behavior | Evidence for controlled approximation in the measured domain |
| G7: compute comparison | End-to-end time/memory including mapping, serialization, reference solves, training, failed attempts and persistence | Actual cost–accuracy tradeoff against strong fixed-fidelity controls |

Acceptance tolerances should be specified from the scientific question and measurement uncertainty before seeing validation results. No generic 20%/40% strain threshold or arbitrary uncertainty cutoff is endorsed here.

For stochastic models, comparisons should evaluate distributions and biologically meaningful statistics over independent runs. Identical random seeds do not generally align trajectories after topology or solver changes. Excluded data, failed fits, uncovered regimes and fallback invocations must remain in the evaluation record.

The first integrated research target should be smaller than the full vascularized microtumor: one verified cell/oxygen coupling problem with one independently measured perturbation. That would establish much more than adding several untested adapters at once. This is a recommended experiment, not an implemented result.

## 8. Limitations and final determination

The audit did not install SOFA, ESPResSo, Tissue Forge, preCICE or Warp; did not reproduce their published benchmarks; did not train a surrogate; did not fit biological data; and did not run an animal, organoid or clinical experiment. Some sources were accessible only as primary-author abstracts. The registry records that distinction. No full ASME standard or regulatory compliance assessment was performed.

There is substantial published justification for the *architecture's constituent methods*. There is no present evidence for its *assembled predictive competence*. The most immediate advance is not another citation or physics backend: it is correcting the verified scaffold defects and producing a converged, matched, independently checked component experiment.

The research hypothesis remains worth testing: **a solver/model portfolio might reduce total computational cost while meeting a declared prediction-error requirement for specified cellular observables**. The hypothesis must be tested against strong fixed-model controls, with switching and biological model error included. It is not established by the literature alone.

## Reproduction and evidence index

Run `python reproduce.py` from the bundle root using Python 3.10 or newer. It checks the original ZIP checksum, extracts safely, runs the original tests and example, and runs the added acceptance tests. An exit status of 1 is expected for the unchanged scaffold because the added checks fail. Use `python reproduce.py --expect-known-findings` to return success only when the original tests/example succeed and the documented 4-pass/12-failure/no-error pattern is reproduced.

- `../tests/test_architecture_acceptance.py`: all 16 probes.
- `../evidence/acceptance_results.json`: machine-readable recorded outcomes.
- `../logs/acceptance_tests.txt`: full assertion traces.
- `../logs/original_tests.txt`: original four-test result.
- `../logs/original_example.txt`: runnable example output.
- `../evidence/claim_matrix.csv`: 26 scoped claim determinations.
- `../evidence/source_registry.csv`: 30 source records and access limitations.
- `SOURCES.md`: human-readable bibliography and support/limitation notes.
- `../original/multifidelity_cell_sim_architecture.zip`: unchanged input artifact.

No implementation fixes are included or silently applied.


---

# Source appendix

# Primary-source and official-documentation registry

Audit date: 2026-09-17. Access depth is stated per source. A bibliographic record or abstract is not presented as a full methods audit. No paywalled ASME standard was inspected. The single review/proposal (S10) is classified as such and is not used as primary experimental proof.

## S01. Agmon et al. — Vivarium: an interface and engine for integrative multiscale modeling in computational biology (2022)

Type: peer-reviewed primary software paper. Access: full text, sections 2–4.

DOI: 10.1093/bioinformatics/btac049. Source: https://academic.oup.com/bioinformatics/article/38/7/1972/6522109

Supports: Processes, stores, multirate composition, and integrated example models.

Limit: Does not establish a universal sufficient cell state or the correctness of arbitrary coupled modules.

## S02. Sluka et al. — The cell behavior ontology: describing the intrinsic biological behaviors of real and model cells seen as active agents (2014)

Type: peer-reviewed primary ontology paper. Access: full text.

DOI: 10.1093/bioinformatics/btu210. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4133580/

Supports: Biological semantics separable from implementation terminology.

Limit: An ontology does not define complete numerical restart or constitutive state.

## S03. Friedman et al. — MultiCellDS: a community-developed standard for curating microenvironment-dependent multicellular data (2016)

Type: preprint / community data-standard proposal. Access: author-institution abstract and bibliographic record.

DOI: 10.1101/090456. Source: https://www.isi.edu/results/publications/13460/multicellds-a-community-developed-standard-for-curating-microenvironment-dependent-multicellular-data/

Supports: Digital cell lines, snapshots, phenotype and microenvironment data.

Limit: The cited publication is bioRxiv; it is not proof of lossless universal solver interoperability.

## S04. Ghaffarizadeh et al. — PhysiCell: An open source physics-based cell simulator for 3-D multicellular systems (2018)

Type: peer-reviewed primary software paper. Access: full text including timestep discussion.

DOI: 10.1371/journal.pcbi.1005991. Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005991

Supports: Cell agents coupled to substrates; distinct diffusion, mechanics, phenotype time scales.

Limit: Its defaults, convergence and performance do not transfer to the supplied toy scaffold.

## S05. preCICE — Overview of adapters (2026)

Type: official documentation. Access: full page, updated 2026-09-08.

DOI: not applicable. Source: https://precice.org/adapters-overview.html

Supports: Lists official and third-party adapters.

Limit: SOFA, ESPResSo and Tissue Forge are not listed; this is not an exhaustive proof no outside adapter exists.

## S06. preCICE — Step 6: Implicit coupling (2026)

Type: official documentation. Access: full page.

DOI: not applicable. Source: https://precice.org/couple-your-code-implicit-coupling.html

Supports: Iterative coupling requires solver checkpoint/restore and reproducible evaluation.

Limit: preCICE does not implement the participating solver checkpoint internals.

## S07. preCICE — Mapping configuration (2026)

Type: official documentation. Access: full page.

DOI: not applicable. Source: https://precice.org/configuration-mapping.html

Supports: Consistent, conservative and scaled-consistent mappings.

Limit: Global sum preservation is not by itself energy, torque, local flux or biological validity.

## S08. Smith et al. — Verification and reproducible curation of the BioModels repository (2025)

Type: peer-reviewed primary reproducibility study. Access: full text, methods and results.

DOI: 10.1371/journal.pcbi.1013239. Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013239

Supports: 932 of 1055 ODE models agreed across at least two of five engines; published 2025-12-04.

Limit: Many experiments use generic templates; not all original figures were reproduced. Not a spatial biological-validation study.

## S09. FDA — Assessing the Credibility of Computational Modeling and Simulation in Medical Device Submissions (2023)

Type: official nonbinding final guidance. Access: full PDF text and scope-page screenshot, section III printed page 7.

DOI: not applicable. Source: https://www.fda.gov/media/154985/download

Supports: Risk- and context-dependent credibility framework for first-principles/mechanistic models.

Limit: Standalone ML is excluded; hybrid-model guidance covers first-principles aspects only. No approval of this architecture.

## S10. Tatka et al. — Adapting modeling and simulation credibility standards to computational systems biology (2023)

Type: peer-reviewed review and methodological proposal. Access: full text.

DOI: 10.1186/s12967-023-04290-5. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC10369698/

Supports: Proposes adaptation of credibility practices to systems biology.

Limit: Proposal/review, not a validation experiment or issued regulatory standard.

## S11. Sajjadinia et al. — Multi-fidelity surrogate modeling through hybrid machine learning for biomechanical and finite element analysis of soft tissues (2022)

Type: peer-reviewed primary computational study. Access: author-institution abstract and bibliographic record; publisher full text inaccessible in this audit.

DOI: 10.1016/j.compbiomed.2022.105699. Source: https://bia.unibz.it/esploro/outputs/journalArticle/Multi-fidelity-surrogate-modeling-through-hybrid-machine/991006420497801241

Supports: Empirical reduced-physics plus learned correction for expensive soft-tissue FE models.

Limit: Not a proof of online tumor-solver switching or experimentally calibrated cancer predictions; no quantitative gains adopted here.

## S12. Kim, Stolarska and Othmer — A hybrid model for tumor spheroid growth in vitro I: Theoretical development and early results (2007)

Type: peer-reviewed primary modeling paper. Access: author-institution abstract and bibliographic record.

DOI: 10.1142/S0218202507002479. Source: https://experts.umn.edu/en/publications/a-hybrid-model-for-tumor-spheroid-growth-in-vitro-i-theoretical-d/

Supports: Cell-level growing periphery, continuum quiescent/necrotic regions and ECM, nutrient fields.

Limit: Prior art for regional model heterogeneity; not the exact proposed heterogeneous-engine controller.

## S13. Agmon and Spangler — Process Bigraphs and the Architecture of Compositional Systems Biology (2026)

Type: preprint. Access: abstract and version history; v2 dated 2026-08-14.

DOI: 10.48550/arXiv.2512.23754. Source: https://arxiv.org/abs/2512.23754

Supports: Typed interfaces, hierarchy, model translation and coordination, Vivarium 2.0 demonstrations.

Limit: Preprint; no peer-reviewed journal status confirmed. Closely related prior art, not a proof of this design.

## S14. Ascheid et al. — A vascularized breast cancer spheroid platform for the ranked evaluation of tumor microenvironment-targeted drugs by light sheet fluorescence microscopy (2024)

Type: peer-reviewed primary experimental paper. Access: full text including model construction and results.

DOI: 10.1038/s41467-024-48010-z. Source: https://www.nature.com/articles/s41467-024-48010-z

Supports: Four human-origin populations, pseudovascular organization, imaging/drug-response phenotypes, and additional in-vivo vascular comparisons.

Limit: The in-vitro spheroid arm does not demonstrate intravascular perfusion. The paper also contains in-vivo perfused-vessel measurements; these must not be confused with spheroid perfusion.

## S15. Quintard et al. — A microfluidic platform integrating functional vascularized organoids-on-chip (2024)

Type: peer-reviewed primary experimental paper. Access: full text.

DOI: 10.1038/s41467-024-45710-4. Source: https://www.nature.com/articles/s41467-024-45710-4

Supports: Functional perfusion of mesenchymal/pancreatic-islet spheroids and blood-vessel organoids.

Limit: Not a cancer-treatment validation dataset; useful vascular-engineering precedent.

## S16. Skubal et al. — Vascularized tumor on a microfluidic chip to study mechanisms promoting tumor neovascularization and vascular targeted therapies (2025)

Type: peer-reviewed primary experimental paper. Access: full text and figure captions.

DOI: 10.7150/thno.95334. Source: https://www.thno.org/v15p0766.htm

Supports: Metastatic renal-cell-carcinoma chip with vessel sprouting, bead and fluorescein experiments.

Limit: Figure 3 bead perfusion n=1 chip and fluorescein n=4; tracer transport and beads are not actual drug PK or deformable blood cells.

## S17. Wang et al. — Calibration of agent based models for monophasic and biphasic tumour growth using approximate Bayesian computation (2024)

Type: peer-reviewed primary modeling/calibration paper. Access: full text, sections 2.1 and 2.2.

DOI: 10.1007/s00285-024-02045-4. Source: https://link.springer.com/article/10.1007/s00285-024-02045-4

Supports: SMC-ABC parameter inference for a 2D Voronoi ABM using mouse xenograft data.

Limit: No cell death; declining late measurements excluded for model-assumption compatibility; breast-labeled MDA-MB435 data require authentication qualification.

## S18. Cellosaurus — MDA-MB-435 (CVCL_0417) (2026)

Type: curated primary biological-resource record. Access: full record.

DOI: not applicable. Source: https://www.cellosaurus.org/CVCL_0417

Supports: Lists MDA-MB-435 as an M14 derivative and registered misidentified cell line.

Limit: A resource-level identity warning does not retrospectively assay the exact historical vial used in an experiment.

## S19. SBML specifications (2026)

Type: official standard documentation. Access: official specification index.

DOI: not applicable. Source: https://sbml.org/documents/specifications/

Supports: Software-independent biological model descriptions and level/package distinctions.

Limit: A file format alone does not establish every solver supports each package or arbitrary dynamic cell geometry.

## S20. SED-ML — Simulation Experiment Description Markup Language (2026)

Type: official standard documentation. Access: official standard overview.

DOI: not applicable. Source: https://sed-ml.org/

Supports: Model modifications, simulation procedures, outputs and experiment exchange.

Limit: The proposed ABM/coupling experiment requires explicit supported mappings; schema existence is not runtime conformance.

## S21. Bergmann et al. — COMBINE archive and OMEX format: one file to share all information to reproduce a modeling project (2014)

Type: peer-reviewed primary software/format paper. Access: full text.

DOI: 10.1186/s12859-014-0369-z. Source: https://link.springer.com/article/10.1186/s12859-014-0369-z

Supports: ZIP-based archive with mandatory manifest and optional metadata; can include additional formats.

Limit: Packaging custom files does not make their semantics executable by independent solvers.

## S22. SOFA — Features (2026)

Type: official software documentation. Access: full page.

DOI: not applicable. Source: https://www.sofa-framework.org/about/features/

Supports: FEM, nonlinear material options, contact and representation mappings.

Limit: Capability documentation is not cancer-cell material calibration or a biological accuracy ranking.

## S23. ESPResSo — Object-in-Fluid (2026)

Type: official software documentation. Access: full page.

DOI: not applicable. Source: https://espressomd.github.io/doc/object_in_fluid.html

Supports: Triangulated elastic objects with stretching, bending, area and volume forces in fluid.

Limit: Cell-like mechanics does not itself validate tumor-cell/nuclear constitutive behavior.

## S24. Tissue Forge — Vertex Model Solver (2026)

Type: official software documentation. Access: full page.

DOI: not applicable. Source: https://tissue-forge-documentation.readthedocs.io/en/latest/models/vertex/solver/solver.html

Supports: Surface/body representation and actor-based mechanics.

Limit: Automatic mesh-quality operations are primarily developed for two-dimensional use; not all 3D dynamic-topology behavior can be presumed.

## S25. NVIDIA Warp — Documentation (2026)

Type: official software documentation. Access: full index/capability overview.

DOI: not applicable. Source: https://nvidia.github.io/warp/stable/index.html

Supports: CPU/CUDA kernels, geometry/numerical primitives and differentiability.

Limit: Does not establish biological credibility, comparative speed on this workload, or differentiability of arbitrary discrete events.

## S26. Bull et al. — Mathematical modelling reveals cellular dynamics within tumour spheroids (2020)

Type: peer-reviewed primary modeling paper. Access: full text, model and oxygen sections.

DOI: 10.1371/journal.pcbi.1007961. Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007961

Supports: Off-lattice cell model with continuous quasi-steady oxygen and comparison to spheroid-infiltration experiments.

Limit: Reported simulations restricted to 2D; conditional model assumptions, not general 3D perfused-tumor validation.

## S27. Murphy et al. — Growth and adaptation mechanisms of tumour spheroids with time-dependent oxygen availability (2023)

Type: peer-reviewed primary experimental/modeling paper. Access: full text including cell culture methods.

DOI: 10.1371/journal.pcbi.1010833. Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010833

Supports: Time-dependent oxygen spheroid experiments and growth/adaptation modeling; authenticated melanoma cell lines.

Limit: Provides scoped observables; does not validate the proposed software without matched experiments and held-out predictions.

## S28. Waltemath et al. — Minimum Information About a Simulation Experiment (MIASE) (2011)

Type: peer-reviewed community reporting proposal. Access: full text.

DOI: 10.1371/journal.pcbi.1001122. Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1001122

Supports: Information needed to reproduce model setup, execution and postprocessing.

Limit: Documentation completeness is necessary but not empirical biological accuracy.

## S29. Stöberl et al. — Nuclear deformation and dynamics of migrating cells in 3D confinement reveal adaptation of pulling and pushing forces (2024)

Type: peer-reviewed primary experimental/modeling study. Access: author-institution abstract and bibliographic record; PMC full text blocked.

DOI: 10.1126/sciadv.adm9195. Source: https://research.vu.nl/en/publications/nuclear-deformation-and-dynamics-of-migrating-cells-in-3d-confine/

Supports: Nuclear shapes, displacement-derived forces and migration dynamics in compliant three-dimensional hydrogel channels.

Limit: Supports a confinement-specific mechanics benchmark, not universal strain thresholds or complete cancer-cell constitutive laws.

## S30. Bastianello et al. — Mechanical stress during confined migration causes aberrant mitoses and c-MYC amplification (2024)

Type: peer-reviewed primary experimental study. Access: author-institution full PDF; abstract, results and methods inspected; no numerical figure data digitized.

DOI: 10.1073/pnas.2404551121. Source: https://air.unimi.it/retrieve/dd21f6fc-5335-4270-b5dd-c5c7144e0c5c/pnas.202404551.pdf

Supports: Microfluidic confinement, live imaging and molecular observations connect mitotic confinement with chromosome-segregation defects and oncogenic alterations in studied systems.

Limit: Does not supply a universal deformation-to-mutation equation or validate the proposed simulator.
