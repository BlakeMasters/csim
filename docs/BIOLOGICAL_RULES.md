# Lightweight biological rules

The rules layer lets a model author state a small cell-response hypothesis as
JSON and execute it with the Python standard library. It currently supports a
concentration switch with hysteresis and a switch-gated saturable material
transfer. This is a custom reference implementation using the existing
conservative kernel. Its biological qualification remains `unqualified`.

The immediate use is to inspect explicit hypotheses, units, state transitions,
and amount accounting before selecting larger engines or fitting biological
parameters. Execution evidence belongs in
[IMPLEMENTATION_STATUS.md](../IMPLEMENTATION_STATUS.md); this guide describes
the interfaces and their scope.

## Run or inspect

From the project directory:

```powershell
python tools/run_rule_demo.py --inspect configs/biological_rules.synthetic.json
python tools/run_rule_demo.py --output runs/my-rule-demo
python tools/run_rule_demo.py --inspect configs/biological_rules.oxygen.template.json
```

Choose a new output directory for every attempt. `--inspect` prints readiness
without executing a rule. A valid planning document can have `runnable: false`;
the report lists the unresolved fields. Schema errors raise an error instead.

The default demonstration uses `biological_rules.synthetic.json`, one synthetic
cell, one cubic voxel, and five prescribed reservoir concentrations. Each
interval is 0.1 s. The example selects `synthetic_tracer`; its dimensioned
parameters are engineering choices with no biological cell identity.
`--rules PATH` accepts another synthetic ruleset for this same fixed scenario.
Other supported worlds can use the Python API directly.

The demo saves the requested JSON, `trace.jsonl`, `final_world.json`, and
`results.json`. Results record source/test/tool and configuration identities,
runtime, scenario, costs, balances, and success or failure. Intermediate traces
remain available if an attempt fails. Existing output directories are refused.
Inspection and argument-parsing errors do not create a run directory.

## Supported operations

| Operation | Inputs | Meaning |
|---|---|---|
| `concentration_switch` | Species, selected cell IDs, two thresholds, initial state | Read extracellular concentration at each cell's containing voxel and propose an `on`/`off` annotation. |
| `saturable_transfer` | Species, selected cell IDs, `vmax`, `km`, optional switch gate | Transfer the same species from its voxel into the selected cell inventory. |

For a switch, `on_below` must be strictly less than `off_above`. The inclusive
decision boundaries are:

- Concentration at or below `on_below`: state becomes `on`.
- Concentration at or above `off_above`: state becomes `off`.
- Concentration strictly between the thresholds: retain the previous state.

Before a committed transition exists, the previous state is `initial_state`.
All switches read the same pre-transfer world. Their newly computed states gate
transfers in that interval, so rule ordering does not create a delayed gate.
These are discrete decisions at the evaluated time; crossing times within an
interval are not located by an event-detection solver.

An active transfer proposes
`amount = dt * vmax * concentration / (km + concentration)`.
`vmax` is a per-cell amount rate, not a concentration rate or a surface flux.
Each cell samples one voxel. Demands from all selected cells for one species
are computed together. Collective demand above the available voxel amount
rejects the complete proposal; reduce the interval or revise the declared model.

The transfer debits the field and credits the cell by the same amount. It
describes transport into a tracked inventory. Metabolism, interconversion, or
loss from the tracked system requires a separate reaction or ledger model.
In the demo, reservoir replacement is an external amount change with a signed
boundary ledger entry; it is distinct from the conservative cell transfer.

## Configuration and evidence

Every ruleset declares its schema version, identity, execution mode, context,
source references, rules, and runnable flag. Every rule selects explicit cell
IDs and a named species. Parameters carry these fields:

| Field | Contract |
|---|---|
| `value` | Finite nonnegative number, or `null` during planning; `km` must be positive. |
| `unit` | Exact `mol/m^3` for thresholds and `km`; exact `mol/s` for `vmax`. |
| `provenance` | `synthetic`, `assumed`, `measured`, or `unknown`. |
| `source_ref` | Reference string or `null`; a populated `measured` value requires a reference. |
| `uncertainty` | Currently `null`; uncertainty propagation is a future extension. |

Units are checked by their exact labels; conversion must be explicit before
loading. A nonnull value cannot retain `unknown` provenance. A source reference
records a declaration; the interpreter does not authenticate the paper, assay,
parameter extraction, or suitability for a cell context.

`synthetic` execution requires synthetic parameter provenance. `hypothesis`
execution additionally requires declared cell identity and tissue context.
Both require selected cells and all parameter values before evaluation. These
readiness checks establish that the supported operations can be attempted;
they do not establish calibration or biological validity.

The oxygen template intentionally leaves cell identity, tissue, selection,
thresholds, and transfer parameters unresolved. Keep its `runnable: false`
until a specific experiment supplies the model context and parameter decisions.
A low-oxygen annotation alone does not define HIF signaling, viability, death,
or differentiation. Use [BIOLOGICAL_VALIDATION.md](BIOLOGICAL_VALIDATION.md)
for observation matching, calibration, uncertainty, and held-out evaluation.

## State, ownership, and integration

`evaluate_rules(world, grid, ruleset, dt_s)` returns a `RuleProposal` containing
an `Update`, a decision trace, and the canonical ruleset digest.
`propose_rules(...)` returns the `Update` for a reference `Process`.
The interval must be positive. Evaluation leaves its input world unchanged;
state transitions become persistent only when the update is accepted.

Configure the process to write `cells`, `fields`, and `events`. The existing
`WindowStepper` applies pure proposals within its shared-state acceptance
boundary. Switch transitions are saved as world events, so reference world
checkpoints retain this discrete memory. First acceptance also records a binding
between every selected cell and the complete ruleset digest. Continuation with
a different digest is rejected, including metadata-only changes and cells whose
switches have never changed state. Combine a cell's rules in one definition;
revised definitions require a fresh context. Automatic state migration is outside
this interface.
Preserve event ordering and let the scheduler advance time between steps.

Selections must refer to cells in the world. Required species must be present,
field volumes must match the fixed grid, and sampled positions must be supported
by that grid. A gate must reference a switch covering all its selected cells.
Multiple transfers owning the same cell/species are rejected even when their
gates differ. Multiple switches can annotate the same cell; there is no implicit
priority or combination operator between their states.

Malformed JSON, duplicate keys, extra schema fields, nonfinite numbers, unresolved
parameters, invalid gates, and unavailable material produce failures. Kernel
amount and positivity checks still apply. Record failures with their attempted
configuration; changing a timestep or parameter creates a distinct attempt.

## Operating limits and next steps

The interpreter executes these two operations only. It has no expression
evaluation, probabilistic rule engine, reaction-network integrator, gene network,
topology-changing behavior, general phenotype-to-mechanics mapping, or automatic
gene-expression-to-molar-rate conversion. It loads no external engine and has no
PhysiCell or SBML adapter. Pure-process checks enforce the reference contract;
they are not an arbitrary-code sandbox.

Standard-library scalar loops, event-history reads, and world copies suit small
fixtures. The demo records time for loading, evaluation, stepping, and intermediate
persistence, with exact exclusions in its cost report. Trace evaluation is
repeated by the stepper and both evaluations are charged. No scale or comparative
performance result follows from this design.

Next, define one measured observable and cell context, authenticate parameter
sources, and specify observation/parameter uncertainty. Compare the chosen rule
against simpler controls on independent experimental units. Study interval and
coupling error before adding new operations. Fit learned response models through
the same explicit observation and physical-effect contracts described in
[PROJECT_DIRECTION.md](PROJECT_DIRECTION.md).

## Recorded execution

`python tools/run_rule_demo.py --output runs/rule_demo_first` completed five
synthetic intervals on Windows 11, Python 3.12.6, CPU. The switch sequence was
`on, on, off, off, on`; the four accepted events comprise one identity binding
and three transitions. Final cell tracer amount was `0.001208074534161491 mol`,
with reported total balance residual `0.0 mol`. Exact configuration, traces,
artifact hashes, and costs are in `runs/rule_demo_first/`.

The associated `runs/prototype_rules_checks/` record contains 137 tests:
136 passed and one host-dependent symlink test skipped. The two added rule
regressions cover delimiter-bearing rule IDs and rejection of changed ruleset
identity after acceptance. Their initial failures are preserved under
`runs/rule_namespace_red/` and `runs/rule_identity_red/`. Source/test/tool SHA-256:
`9f74a4307bc5e14d85bb0041d3753c40d044c39bd3e0b7c4c78796d8d04f8eff`.
These selected checks and the demo establish limited implementation evidence;
biological calibration, coupled convergence, and broader rule coverage remain open.

## Inspected sources

Accessed 2026-09-25, America/Los_Angeles. These support modeling concepts;
the current equations, schema, and code are independent project decisions.

- [Johnson et al., cell behavior hypothesis grammar](https://pmc.ncbi.nlm.nih.gov/articles/PMC13012569/):
  primary article; indexed Results text inspected because direct PMC access
  presented a browser challenge. Supports explicit signal-to-behavior hypotheses
  with contextual parameters and a PhysiCell implementation. It supplies no
  validation of this project's two operations or synthetic parameter values.
- [libSBML 5.18.0 qualitative models documentation](https://sbml.org/software/libsbml/5.18.0/docs/formatted/c-api/group__qual.html):
  official documentation, introduction inspected. Supports distinguishing discrete
  activity transitions from quantitative reaction kinetics. This concept reference
  establishes neither SBML conformance nor a tested libSBML dependency here.
