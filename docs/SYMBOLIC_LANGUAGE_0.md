# Symbolic IR version 0: executable synthetic subset

`cellsim_v2.symbolic_logic` is a data-only, closed-vocabulary encoding of the
two rules already implemented by `cellsim_v2.biological_rules`. It introduces
no new biological mechanism or runtime effect. Its purpose is to make the
existing rule meaning inspectable before lowering to the reference interpreter.

## Vocabulary and ownership

The top-level JSON object has exactly `schema_version`, `kind`, `id`,
`execution`, `context`, `source_refs`, `symbols`, `statements`, and
`ruleset_sha256`. Version `0` requires `kind: cellsim_symbolic_ir` and
`execution: {"mode":"synthetic","runnable":true}`. A planning or measured
context document is outside this executable subset.

`symbols` declares three separate namespaces:

| Declaration | Supported type and unit | Owner |
|---|---|---|
| `cells` | Stable local cell IDs, `kind: cell` | Selected cell |
| `species` | Material IDs, amount `mol`, concentration `mol/m^3` | Tracked field or cell inventory |
| `compartments` | One `extracellular_field` and one `cell_inventory`, amount `mol`, volume `m^3` | `world` and `selected_cell`, respectively |

Each statement names selected cells and one declared species. Its input is
that species' extracellular **concentration** in `mol/m^3`, derived by the
existing world from tracked amount and volume. The two admitted statement
forms are:

| Statement | Effect | Parameter and timing meaning |
|---|---|---|
| `concentration_switch` | `event_state_replacement`, dimensionless `on`/`off`, committed only on an accepted window | `on_below` and `off_above` in `mol/m^3`; existing hysteresis and initial-state semantics |
| `saturable_transfer` | `paired_integrated_amount_transfer` from field to selected cell inventory for the **same species** | `vmax` in `mol/s`, `km` in `mol/m^3`; existing interpreter integrates over `dt` and pairs source debit with destination credit; optional switch gate |

The IR stores the canonical digest of the lowered original ruleset. Its own
canonical digest separately hashes the complete typed JSON object with sorted
mapping keys and preserved array order. Lowering verifies that the ruleset
digest remains unchanged; this preserves the identity used by accepted-state
history events. Editing a statement or context needs a new ruleset identity
and a fresh accepted context. A digest detects accidental changes, not a
malicious writer.

## Static gate and execution

`parse_symbolic_json` rejects duplicate JSON keys, nonfinite values, unknown
fields, unsupported statement/effect kinds, undefined identities, unit
mismatches, ambiguous compartment ownership, unpaired transfers, unresolved
executable parameters, bad gates, and duplicate transfer ownership. The
existing ruleset validator and readiness check run before lowering.
`from_ruleset` encodes a runnable synthetic ruleset; `to_ruleset` produces the
same executable ruleset data. Neither function runs generated code.

Run the local demonstration with a fresh output directory:

```powershell
python tools/run_symbolic_demo.py --output runs/my-symbolic-demo
```

The demo saves the IR, lowered ruleset, a rejected unsupported statement,
and two executions of the existing five-interval rule demo. It requires the
direct and round-tripped runs to have identical trace bytes, final world
bytes, and accepted-history digest. The interpreter retains authority for
runtime availability, amount balance, accepted events, and rejection.

This static representation does not support ligand/receptor binding, gene
regulation, mutation, ion current, reactions, topology changes, or learned
policy output. Passing its checks does not establish biological calibration,
independent numerical verification, or general language interoperability.
