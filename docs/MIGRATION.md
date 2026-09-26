# Migration from the original scaffold

This is a breaking rewrite of the illustrative core, not a drop-in patch. Preserve old files and recorded outcomes. New imports begin with `cellsim_v2`.

| Old construct | New construct | Important semantic change |
|---|---|---|
| `ScalarFieldState.values` with free-form units | `AmountField.amounts_mol` and `volumes_m3` | Explicit conversion required; no guessing whether old values were normalized or molar |
| `CellState.geometry.radius` | `Cell.volume_m3` and derived sphere radius | SI quantities; reference sphere only |
| `StateDelta` assorted dictionaries | `Update` full replacements/ledger/events | Atomic validation, write categories and amount balance |
| `MultiRateScheduler` due-time loop | `WindowStepper` | Correct intervals; deliberately limited sequential Lie-split windows |
| `FidelityLevel` thresholds | `lookup_reference_case` | No online selector, no universal ladder, no default qualification |
| `DivisionEventProcess` | `divide_retained_slot` | Explicit volume/amount partition, unique event/slot IDs, no physical cytokinesis claim |
| Adapter classes with `NotImplementedError` | Candidate manifests and build tasks | Planned adapters are not importable capabilities |
| `run_microtumor` toy example | `run_demo` | Honest numerical/bookkeeping name |

There is no automatic converter for the old normalized/ambiguous quantities. Recover their units and intended meaning first. A conversion that multiplies all old values by an arbitrary constant would create invented physical data.

Regression tests re-express the audited requirements. The old API tests are preserved in the original verification archive; they do not run unmodified on v2. The v2 requirement matrix states which semantics changed and what remains unimplemented.
