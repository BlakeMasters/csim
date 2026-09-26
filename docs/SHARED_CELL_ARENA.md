# Synthetic shared-field cell arena

`cellsim_v2.shared_cell_arena.SharedCellArena` is a bounded one-to-five-cell
reference. One fixed 3D voxel holds a finite `synthetic_tracer` field amount.
Each cell has its own identity, amount inventory and private response-memory
instance. Positions are declared and distinct within that voxel; positions do
not imply a resolved spatial gradient. All cells sample the same accepted
pre-step concentration.

## What is a cell here?

The implemented core `Cell` carries a stable identity, a 3D position, volume,
intracellular SI amounts, and lineage fields (`parent_id`, `division_count`).
The arena layers a separately identified response model and private state on
each core cell. A policy sends a typed maximum-uptake **rate** (`vmax_mol_s`)
for each cell; the shared field provides a concentration observation derived
from its amount and voxel volume. These model instances currently use the same
illustrative response equation. Their identities permit later per-cell model
choices. The fixed geometry and saturable uptake law are reference choices,
not required properties of a future cell model.

Each accepted 0.25 s step evaluates all typed actions simultaneously using
the existing pure `saturable_uptake_step`. The update debits the field and
credits each cell by the same integrated amount. The episode verifies the
closed total and publishes physical `World` plus all private response states
only after validation. If aggregate demand exceeds the field, the entire
proposal raises `ArenaRejected` and leaves the accepted state unchanged. It
never rescales demands or silently allocates scarce material. Private response
memory senses the pre-step concentration without consuming field amount.

```python
from cellsim_v2.shared_cell_arena import SharedCellArena, ArenaRejected

arena = SharedCellArena(cell_count=3)
observation = arena.reset()
rates = {cell["cell_id"]: 0.012 for cell in observation["cells"]}
result = arena.step(arena.make_actions(rates))
checkpoint = arena.checkpoint()
resumed = SharedCellArena.from_checkpoint(checkpoint)
```

`observe()` includes the accepted clock, field amount and concentration, each
cell's ID, model/context IDs, declared position, amount and dimensionless
memory. Actions include cell ID, model digest, context, quantity type, species,
clock interval, maximum rate and Km. `step()` returns an observation,
diagnostic score, termination flag, per-cell transfers and a closed amount
ledger (`field_debit_mol`, `cell_credits_mol_by_cell`, external change and signed
residual). The diagnostic score is the negative mean absolute error from a
declared synthetic memory target; the target is private to the evaluator and
is not included in policy observations. Checkpoints cover the world, model
identities, private states, configuration and clock, and support deterministic
JSON roundtrip replay. Their checksum detects accidental corruption; it is
not authentication against a malicious writer.

Run from the repository root:

```powershell
python -c "import sys,unittest;sys.path[:0]=['src','tools'];suite=unittest.defaultTestLoader.discover('tests',pattern='test_shared_cell_arena.py');result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())"
python tools/run_two_cell_arena.py --output runs/two_cell_arena_20260926_02
```

The focused suite passed **5/5** on Windows 11, Python 3.13.5, CPU. The
preserved [result](../runs/two_cell_arena_20260926_02/results.json) has
`status: pass`, source/test/tool SHA-256
`5ae996ca4f2dce2f35ec62897ed0a6287002d5c29ee0b126807daf30c784eae9`,
six-step traces for 1, 2, 3 and 5 cells, deterministic replay, permutation
invariance and deliberate collective-overdraw rejection. The two-cell field
amount decreases from 0.125 to 0.11025934216769111 mol over six steps; the
five-cell case reaches 0.06972706038692437 mol. The maximum per-step closed
amount residual among these count traces is below 1.4e-17 mol.

The CLI also compares development-selected rates with a fixed rate and seeded
random control. It charged 72 development episodes and 24 separate synthetic
evaluation episodes; all were accepted, and policy hashes stayed frozen
during evaluation. The conditions, target and score are synthetic. This is
neither biological holdout validation nor an RL algorithm. There is no
resolved spatial transport, metabolism, cell division, receptor interaction,
heterogeneous internal equation, external solver or scale assessment here.
