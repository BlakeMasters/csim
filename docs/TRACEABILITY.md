# Audit-to-revision traceability

The inherited audit is preserved under `provenance/`. Its failure outcomes were reproduced again on the unchanged original archive. The tests below are **re-expressed requirements in the new API**, not a claim that unmodified legacy tests now pass. Source/test/tool identities are recorded in the final run.

## Twelve audited acceptance requirements

| ID | Audited issue | New test in `test_reference_core.py` | Resolution and scope |
|---|---|---|---|
| A01 | Zero elapsed time evolved continuous state | `TimingTests.test_zero_duration_is_noop` | Fixed by interval semantics; no process call for zero duration. |
| A02 | Endpoint received an extra full Euler step | `TimingTests.test_exact_endpoint_two_updates` | Exactly two half-interval steps over one unit; partial final intervals also tested. |
| A03 | Equal pair midpoint drifted under pair-only mechanics | `MechanicsDivisionTests.test_equal_pair_preserves_midpoint` | Equal/opposite forces from frozen positions; equal-drag condition explicit. |
| A04 | Pair results depended on entity iteration order | `MechanicsDivisionTests.test_entity_order_independent` | Sorted IDs and symmetric accumulation; not a cross-device determinism guarantee. |
| A05 | Instantaneous division doubled volume | `MechanicsDivisionTests.test_division_volume_amount_balance` | Explicit partition of volume and amounts; not a cytokinesis model. |
| A06 | Repeated retained-parent division collided on daughter ID | `MechanicsDivisionTests.test_repeated_division_unique_ids` | Sequence-based IDs and event history; no silent collision renaming. |
| A07 | Rejected delta partially mutated state | `StateTests.test_duplicate_birth_is_atomic` | Preflight a candidate copy before publishing; entire failed window also tested. |
| A08 | Absolute error could be negative | `ChemistryTests.test_absolute_error_nonnegative` | Separate signed residual and nonnegative absolute error. |
| A09 | Zero process timestep was accepted | `TimingTests.test_zero_process_step_rejected` | Nonpositive step/window rejected before iteration. |
| A10 | NaN fidelity metric silently selected a level | `EvidenceTests.test_nonfinite_metric_rejected` | Finite-value checks; threshold controller removed rather than patched. |
| A11 | No metrics could imply scientific qualification | `EvidenceTests.test_missing_evidence_unqualified` | Missing evidence returns unqualified; exact-case match still has no biological qualification. |
| A12 | Declared write contract was not enforced | `TimingTests.test_undeclared_write_rejected_without_mutation` | Broad categories enforced; fine-grained ports and read authorization still planned. |

Additional checks cover unequal-volume amount accounting, source ledgers, positivity limits, radial/periodic diffusion, invalid geometry, stale updates, snapshot mutation, world/RNG persistence, fresh-process continuation and package claims. These selected tests do not establish an exhaustive absence of defects.

The groundwork adds `test_transport.py` for fixed 3D diffusion, unequal-volume face accounting, inward boundary ledgers, simultaneous saturable transfer, collective overdraw, represented geometry, floating-point step limits, underflow rejection and rollback. Training-contract tests cover grouped splits, artifact integrity, candidate snapshots and the synthetic exporter. The later prototype adds two regressions in `test_biological_rules.py`: `test_delimited_rule_ids_keep_independent_history` and `test_rule_edit_requires_a_new_context_after_acceptance`. They address discovered event-namespace and continuation-identity defects and do not imply broad machine-learning unit coverage.

Current suite outcomes and analytical studies are in `runs/prototype_rules_checks/`; the fitted synthetic response run is in `runs/response_baseline_first/` and local-rule trace/balance evidence is in `runs/rule_demo_first/`. See `PROTOTYPE_REPORT.md` for exact commands and source identity. `GROUNDWORK_REPORT.md` and the historical 76-test Linux record remain unchanged. Independent-solver, biological and production gates remain open.

## Architectural and literature corrections

The machine-readable map `../evidence/revision_claim_matrix.json` carries all 26 inherited claim IDs, original verdicts and the specific v2 action. The table below is a disposition map, not 26 new experimental confirmations.

| Inherited ID | Claim | V2 disposition | Build documentation |
|---|---|---|---|
| C01 | Solver-independent canonical state has precedent | Shared/private state replaces universal-state sufficiency. | `ARCHITECTURE.md` |
| C02 | Discrete cells plus continuum fields is established | Fixed 3D transport and point-sampled cell transfer now have a runnable reference slice; broader biological structure and validation remain planned. | `ARCHITECTURE.md` |
| C03 | Multirate scheduling is appropriate | Explicit window/subcycling reference; no general multirate accuracy claim. | `NUMERICAL_CONTRACTS.md` |
| C04 | preCICE makes selected packages readily integrable | Offline adapters first; live preCICE integration remains a build task. | `BACKEND_INTEGRATION.md` |
| C05 | SOFA and ESPResSo are high-fidelity biological oracles | Oracle terminology removed; each comparator requires matched model and convergence. | `BACKEND_INTEGRATION.md` |
| C06 | Tissue Forge offers an independent reference | Tissue Forge remains a candidate comparator, not an executed independent reference. | `BACKEND_INTEGRATION.md` |
| C07 | 932/1055 BioModels matched across at least two engines | ODE cross-engine result preserved at its original scope; not extrapolated to spatial physics. | `SOURCES.md` |
| C08 | FDA/ASME credibility methods directly justify the proposed ML/fidelity layer | No regulatory approval or ML qualification inferred. | `OPERATIONS.md` |
| C09 | Surrogate distillation is feasible | A small synthetic nearest-neighbor endpoint baseline is fitted and evaluated after validation selection and freeze; independent-teacher, biological, rollout and cost-benefit claims remain unsupported. | `FIDELITY_RESEARCH.md`, `BASELINE_PROTOTYPE.md` |
| C10 | Mean discrepancy plus lambda uncertainty gives a guarantee | Error-plus-uncertainty guarantee withdrawn; empirical/coverage requirements specified. | `FIDELITY_RESEARCH.md` |
| C11 | Regional multi-fidelity cellular simulation is novel | No novelty claim; dedicated prior-art and implementation evaluation required. | `FIDELITY_RESEARCH.md` |
| C12 | Four-population vascularized spheroids demonstrate functional spheroid perfusion | Spheroid morphology and in-vivo perfusion remain distinct measurements. | `BIOLOGICAL_VALIDATION.md` |
| C13 | Vascularized-organoid paper validates tumor therapy | Non-cancer organoid platform is vascular-engineering precedent only. | `BIOLOGICAL_VALIDATION.md` |
| C14 | Renal tumor chip supplies useful component data | Renal chip target restricted to measured tracer/bead/vascular endpoints. | `BIOLOGICAL_VALIDATION.md` |
| C15 | The ABC paper provides broad evidence for tumor-model calibration | ABC example kept conditional on its model/data and identity caveats. | `BIOLOGICAL_VALIDATION.md` |
| C16 | SBML/SED-ML/OMEX fully specify the proposed world | Custom ZIP is not OMEX; standard support requires actual feature/round-trip tests. | `ARCHITECTURE.md` |
| C17 | Warp is the best or biologically credible production backend | Warp optional; no selection as fastest or biologically preferred. | `BACKEND_INTEGRATION.md` |
| C18 | The packaged example realizes the proposed vascularized microtumor experiment | Example renamed synthetic bookkeeping; microtumor is nonrunnable proposal. | `MIGRATION.md` |
| C19 | The four passing tests establish scaffold correctness beyond smoke testing | Selected regression and numerical evidence reported with explicit limits. | `KNOWN_LIMITATIONS.md` |
| C20 | Total error is a simple sum of independent uncertainties | Error categories distinguished; no unjustified independence assumption. | `NUMERICAL_CONTRACTS.md` |
| C21 | Local solver escalation ensures global trajectory accuracy | Conditional accumulation bound and switching errors stated; no runtime guarantee. | `NUMERICAL_CONTRACTS.md` |
| C22 | Increasing detail monotonically improves biological realism | Observable-specific model portfolio replaces monotonic realism ladder. | `FIDELITY_RESEARCH.md` |
| C23 | Arbitrary external entities can be physically predicted | Externals require typed inputs and justified response laws; the local interpreter implements only declared concentration switches and gated conservative transfer, demonstrated with synthetic parameters. | `EXTERNALS.md`, `PROTOTYPE_REPORT.md` |
| C24 | A validated constitutive law transfers across cell populations | Cell identity, calibration and applicability required before population transfer. | `BIOLOGICAL_VALIDATION.md` |
| C25 | Detailed mechanics and nuclear deformation have experimental relevance | Mechanics evidence motivates scoped later experiments, not blanket detailed modeling. | `BIOLOGICAL_VALIDATION.md` |
| C26 | Mechanical strain can be converted to universal rupture or mutation thresholds | Universal strain/rupture thresholds removed; biological threshold fields remain unset. | `BIOLOGICAL_VALIDATION.md` |
