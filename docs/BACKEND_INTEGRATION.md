# Backend adoption and integration

## Selection criteria

Candidate software is not bundled, installed or benchmarked in v2. Published/official capabilities were checked as described in `SOURCES.md`; pinned versions and build combinations have not been selected.

| Candidate | Scoped role | Qualification experiment | Principal build consideration |
|---|---|---|---|
| CPU reference | Small exact-law comparisons and debugging | Delivered analytic fixtures | Scalar loops and deep copies; not a scale target |
| Warp | Optional implementation of selected verified kernels | Same equations, input cases and precision comparison as CPU | Record JIT, device, warm/cold and deterministic behavior; no benefit assumed [S25] |
| SOFA | Mechanics comparator for an explicitly matched constitutive problem | Force–displacement, relaxation and constrained deformation | Material/contact assumptions, plugin availability, mesh convergence [S22] |
| ESPResSo | Fluid/elastic-object comparator | Specified flow channel, traction/velocity/deformation QoIs | Map units and hydrodynamic parameters; fluid and membrane discretization [S23] |
| Tissue Forge | Particle/vertex model comparison | Matched interaction/area-volume laws and boundary conditions | Confirm required 3D topology and quality operations; do not infer maturity from visualization [S24] |
| preCICE | Later inter-solver exchange | Fixed-topology two-participant manufactured or analytic problem | Custom adapters and participant-owned restart/mapping contracts [S05–S07] |

Do not add all candidates as mandatory dependencies. Introduce one at a time and remove a candidate when it adds unidentifiable model complexity or unnecessary integration work.

## Offline adapter first

The first adapter should consume a case manifest and create an isolated job directory containing model parameters, geometry, input units and execution controls. It returns an output manifest with quantities, coordinates, units, model/solver fingerprints, residuals and elapsed resource usage. It should be independently runnable without the main simulator.

The pipeline is **export -> run -> inspect -> compare**, not serialize a `World` object into whatever fields the solver accepts. Write down transformations and missing variables. Never synthesize unmeasured material parameters solely to satisfy an engine's constructor and then treat them as biological facts.

Comparison types must be labeled:

- same equations/discretization family, independently implemented: implementation/calculation verification;
- different model form but same experimental target: model-discrepancy comparison;
- model versus independently acquired measurement: biological validation in the stated context.

## Live coupling prerequisites

Define one owner for each material region and process term. Overlapping responsibility for diffusion, drag or contact causes double counting. Interface sign conventions, geometry orientation, sampling location and timestamps belong in the contract.

Implement actual save/restore before enabling implicit coupling. preCICE specifies checkpoint requests but the participant must restore sufficient state to repeat the same mapping from interface inputs to outputs. [S06] This requires RNG state, stochastic decisions, solver-private history and event proposals in addition to shared geometry where those affect behavior. Topology-changing events should initially be forbidden inside an unaccepted coupling window.

Use bounded iterations, explicit residual definitions and a failure outcome. Repeat with tighter coupling tolerances and smaller coupling windows. Investigate stability rather than masking divergence with arbitrary relaxation. The chosen mapping must be tested for its relevant invariant, including unit/mesh weights. [S07]

The official adapter catalog inspected for this revision does not list these three target engines. Mark any proposed adapter `planned` until an actual source revision and passing case are recorded. Absence from that catalog does not establish that no third-party implementation exists. [S05]

## Pinning template

`configs/backend_candidates.json` intentionally leaves versions and execution evidence unset. Before activation, populate repository revision, release tag where available, compiler/toolchain, OS/architecture, Python ABI if used, enabled engine features, numerical precision, accelerator driver/runtime if applicable, license/notice inventory, and test artifact hashes.

Do not claim a set of versions is compatible because each package installs separately. Test the actual adapter call sequence and restart. Online installation commands are deliberately omitted until an integration is selected and executed.

## Runtime isolation and resource budgets

Prefer separate processes for early specialist jobs so that crashes and dependency conflicts do not corrupt the main world. Specify time/memory budgets and recoverable failure codes. A worker timeout is a failed reference case, not a successful low-fidelity result. Temporary files must be per-run and output ingestion must validate schemas, finite numbers and hashes.

Process isolation is useful engineering but does not decide third-party license compatibility or protect against arbitrary trusted plugin behavior. Distribution terms require review at the pinned source revisions.
