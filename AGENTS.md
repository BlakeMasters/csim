# Instructions for implementation and research agents

## Objective

Build a custom cellular simulation environment with typed external interactions and evidence-scoped numerical models. The delivered package is a build specification and reference-kernel starting point. Do not describe it as a validated tumor simulator.

## Initial work

Read `README.md`, `BUILD_RECOMMENDATIONS.md`, `IMPLEMENTATION_STATUS.md`, `docs/TRACEABILITY.md`, and the inherited audit before changing code. Run `python tools/run_checks.py`; preserve the emitted directory. Work from the new `cellsim_v2` namespace. Do not overwrite the original ZIP or audit artifacts.

## Scientific rules

Keep implemented capabilities, numerical checks, independent-solver comparisons, experimental calibration, and held-out biological validation separate. No bibliography, passing unit suite, rendered image, deep mesh or pretrained model is sufficient for a biological validity claim. Do not cite reviews as direct experimental evidence or carry an abstract's claim beyond its inspected scope.

Do not invent cell-line identity, parameter values, measurement uncertainty, licenses, source versions, sample counts or engine adapters. Plans may contain null values. Missing evidence is `unqualified`, not a reason to silently choose the finest mesh.

Specify the observable and data split before fitting. Preserve failures and cohorts. Freeze one candidate before the final holdout and charge data generation, failed work, inference, evaluation and persistence. Do not update a surrogate during an immutable evaluation campaign.

## Engineering rules

Track SI amounts separately from concentration and volume. Never change a tracked amount without a paired transfer or a documented ledger change. Do not interpret per-species balance as full reaction stoichiometry.

State replacements, increments, forces, tractions, rates and integrated amounts are different interface types. Keep the solver-private state necessary for continuation; never assume shared geometry alone is sufficient.

Processes in the reference stepper must be pure, returning `Update`. Its checks are not an arbitrary-code sandbox. No backend may claim rollback unless shared/private/RNG/integrator/event state has actually been replayed. Division and topology changes cannot commit inside a rejected coupling iteration.

Add a targeted regression before implementing a fix. Keep positive controls and failure injection. Do not silently clip negative concentrations, jitter coincident cells or weaken assertions to hide undefined mechanics.

Pin an external dependency only after its real version/revision and build have been tested. No placeholder adapter counts as implementation. Start offline, one comparator at a time; preCICE integration is a later task.

## Acceptance and reporting

Every substantial change must record exact commands, source/test/tool hash, test counts and outcomes, numerical configuration, results and remaining limitations. State which operating systems/interpreters/devices were actually exercised. Do not claim scalability, interoperability, regulatory approval or novelty from design intent.

Use `docs/BUILD_BACKLOG.md` for the next tasks. The first production extension is fixed 3D conservative transport plus a single cell–field interface, followed by independent verification and a carefully sourced oxygen-perturbation study.
