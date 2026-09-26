# Architecture specification

**Implemented subset:** `src/cellsim_v2`. **Proposed system:** the interfaces below, except where explicitly mapped to code. Sources are indexed in `SOURCES.md`.

## System boundary

```text
Question + observable + experimental context
                    |
          Experiment specification
   initial state / parameters / interventions
                    |
      Shared physical state and identity
   amounts / geometry / lineage / observations
                    |
        Versioned process contracts
   ownership / units / clocks / failure modes
        /             |               \
  mechanics       transport      intracellular
        \             |               /
       synchronization and transactions
                    |
     backend-private state and adapters
   CPU reference / selected backend / comparator
                    |
      trajectory + cost + provenance records
                    |
       verification and validation evidence
```

No central object claims to encode every possible biological state. Shared fields are an interoperability contract. Solver-private state can be essential and remains part of restart, model identity and transfer requirements. Vivarium provides architectural precedent, not a proof of sufficiency for this schema. [S01]

## Ownership

Each state quantity has one authoritative owner during an accepted step. Multiple solvers may propose an update, but they may not independently commit the same force, flux or phenotype effect. Every adapter declares whether its output is a full state, an increment, an integrated amount, an instantaneous rate, a nodal force or a traction. These are not interchangeable.

Use shared entity IDs independently of mesh/particle IDs. A mapping registry relates representations and is versioned with the topology. Field species use authoritative molar amounts and compartment volume. Concentrations are derived quantities. An external source identifies both its chemical/physical identity and a response law; an unknown response remains unknown.

## Implemented state

`Cell` contains ID, position in meters, volume in cubic meters, molar amounts, a drag coefficient, parent slot ID and division counter. Radius is derived from the spherical volume. `AmountField` contains amounts and volumes, not a general grid geometry. `World` contains rational time, synchronization-window count, cell/field dictionaries, a ledger and event history.

`RectilinearGrid3D` now supplies separate fixed orthogonal geometry, with explicit field-volume matching. Typed `BoundaryFlux` and `CellUptake` inputs produce conservative `Update` proposals. The synthetic exporter records geometry, process order, parameters and source identity in its configuration/fingerprint. General port ownership and solver-private restart remain future work.

The new `training` module validates offline dataset and split declarations and binds data/candidate/preprocessing/evaluation artifacts in a create-only campaign snapshot. Physical trajectories and unpaired assay observations share provenance machinery, not state semantics. No assay values become physical inventories through this API. See `TRAINING_SETUP.md` for executable contracts and `VIRTUAL_CELL_RESEARCH.md` for the broader design.

`physical_dataset` adds strict ingestion for the synthetic amount JSONL format.
`response` fits small increment predictors; the baseline runner freezes a
validation-selected candidate before final evaluation. These endpoint predictions
have no physical write authority. `biological_rules` separately interprets typed
concentration switches and gated conservative transfers. Accepted events preserve
switch memory and bind selected cells to an unchanged ruleset. See
`BASELINE_PROTOTYPE.md` and `BIOLOGICAL_RULES.md` for the distinct interfaces.

There is no finite-element mesh, intracellular reaction solver, ECM state, vessel graph, event queue, general observation model or particle fluid in this implementation. Adding those fields to a document is not an implementation.

## Shared versus private state

A future adapter checkpoint must include the shared state and any necessary material history, integrator history, contact state, stochastic state, pending events and coupling-window data. A hash references external blobs; it does not substitute for their contents. A JSON `private_json` round-trip exists in this package only to make the boundary explicit. No third-party solver snapshot is implemented.

A full-state transfer uses `x_next = L(Phi_h(R(x)))`, where the representation change has been specified. A partial replacement must select only its owned components. The old expression `x + L(S(R(x)))` is invalid if `S` and `L` already return a state. See `NUMERICAL_CONTRACTS.md` for the identity counterexample and virtual-work conditions.

## Execution modes

| Mode | Role | Status |
|---|---|---|
| Small CPU reference | Verify toy laws and orchestration contracts | Implemented |
| Synthetic training-data preparation | Generate fixed-grid uptake trajectories and check grouped manifests/payloads | Implemented for the physical fixture |
| Offline response baseline | Fit simple synthetic increment models and select on validation | Implemented; frozen one-step evaluation, no learned rollout |
| Local declarative rules | Inspect hypotheses and propose conservative effects | Reference switches and transfers implemented; biological parameters unresolved |
| Offline comparator jobs | Match numerical models across independent engines | Planned |
| Biological calibration/evaluation | Compare predictions against specified experiments | Planned |
| One fixed-topology live coupling | Establish transfer and implicit restart semantics | Planned |
| Surrogate cost/accuracy comparison | Reduce measured cost at scoped error | Research proposal; no savings demonstrated by the small baseline |
| Regional switching across engines | Handle representation changes during a rollout | Deferred research |

The architecture does not require all modes in every run. There is no preCICE dependency in the reference runtime.

## External entity lifecycle

The proposed lifecycle is register -> validate manifest -> acquire authorized ports -> initialize -> schedule -> propose -> validate -> atomically accept or reject -> checkpoint. A plugin must declare species/material prerequisites and cannot promote the run's credibility status. See `EXTERNALS.md`. The current runtime enforces broad write categories; it does not implement registration, process isolation or fine-grained port security.

## Version identity

Keep model definition, parameter fit, mesh, observation operator, intervention schedule, solver implementation and numerical controls as separate identifiers. Compose them into the execution fingerprint. A software update or material-law change can invalidate old comparisons even if cell IDs and geometry are unchanged.

## Standards boundary

Map biological semantics to CBO/MultiCellDS where useful; use supported SBML for intracellular models and SED-ML for expressible experiments. [S02,S03,S19,S20] Use an OMEX archive only with a correct manifest and declared custom formats; a generic ZIP of YAML files is not standardized executable semantics. [S21]

This package is an ordinary ZIP with a SHA-256 manifest, **not an OMEX-conformant experiment**. Future standard support requires package-specific round-trip and independent execution tests.
