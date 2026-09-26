# Coupled synthetic NF-κB arena

`CoupledNfkbArena` composes the existing illustrative `NfkbEpisode` or
`SeededNfkbEpisode` with a **separate finite generic paracrine-mediator
World**. One to five identified cells have distinct declared 3D positions and
intracellular mediator inventories in mol. A single fixed voxel holds mediator
amount in mol; concentration in mol/m³ is derived from its 0.125 m³ volume.
Mediator waste is a separately tracked molar amount. The mediator has no
asserted cytokine, receptor, cell-line or biological dose identity.

For each six-minute interval, a typed action contains the existing NF-κB
environment action, a per-cell secretion **rate** in mol/min and a field
clearance first-order **rate** in min⁻¹. The pure
`mediator_secretion_update` returns an `Update` that debits finite cell
inventories and credits the field by the same integrated amounts. The pure
`mediator_clearance_update` returns an `Update` that debits only the pre-step
field and records the paired waste credit in the wrapper ledger. Rejected
overdraw is never scaled or clipped. The pre-step field concentration is
sensed without consuming mediator; material secreted now first affects the
**next** interval's nuclear proxy. The synthetic saturating private response
boost is dimensionless and feeds the existing feedback/reporter delay. It is
not a fitted NF-κB/IκB mechanism.

The wrapper computes candidate mediator and NF-κB transitions on clones,
checks SI amount balance and full JSON checkpoints, then jointly publishes
mediator World, waste, core physical/private state, seed and accepted clock.
Its checkpoint contains the complete mediator World, including its ledger,
and the core checkpoint with seed/response continuation state. Both mediator
and core rejection injections leave the checkpoint byte-for-byte unchanged in
focused tests; replay from an accepted checkpoint matches future actions and
states on this Windows CPU host.

Run a new local artifact:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_coupled_nfkb_arena.py -v
.venv\Scripts\ocura-oss.exe run --root (Get-Location).Path --json --param demo=coupled-nfkb-arena -- .venv\Scripts\python.exe tools\run_coupled_nfkb_arena.py --output runs\coupled_nfkb_arena_NEW
.venv\Scripts\ocura-oss.exe verify --root (Get-Location).Path --json
```

The [current result](../runs/coupled_nfkb_arena_20260926_04/results.json)
compares a three-cell, 82-step TIPL schedule at seed 7 with and without
finite mediator secretion. Cell 1 secretes during steps 0–19 and cell 2
during steps 40–59; clearance is 0.01 min⁻¹. The same seed and stimulus
schedule are used in both arms. `cases.baseline.trace` and
`cases.coupled.trace` contain 83 timed field/cell observations, with
82 interval ledgers each. `comparison` gives per-cell reporter-index AUC
differences; `cell_count_controls` separately exercises counts 1–5.
The focused tests passed 5/5. Both full traces accepted 164/164 steps,
JSON checkpoint replay matched, the deliberate overdraw left state unchanged,
and the maximum amount residual was 3.47e-18 mol. The receiving cell's
first-interval nuclear proxy matched the control, then differed by
0.006716 in the second interval, showing the declared causal lag.
The [adjacent OSS record](../runs/coupled_nfkb_arena_20260926_04/oss_record.json)
retains atom `atom-a6b74311a92748caabd14fd426b450f6`, chokepoint
`chokepoint-6c8e1a92f5994d5988caee95eb117f57`, 72 verified logs and zero
problems. Its source/test/tool SHA-256 is
`981f4b90b963fe3f1a256c0ff6d31bc818d4b838cb4429c3b7f855b0bd3f5584`.
The earlier direct `_01`/`_02` and OSS `_03` runs remain preserved. `_02`
added a pure Update regression without changing the model. A subsequent
checkpoint identity regression proved that a wrapper seed could disagree with
the valid embedded seeded-core checkpoint after both wrapper hashes were
recomputed. The [pre-fix failure](../runs/coupled_seed_fix_20260926/red_tests.log)
and [post-fix 5/5 run](../runs/coupled_seed_fix_20260926/green_tests.log)
are preserved. The wrapper now checks seed and core cell-count/horizon/step
identity before replay; `_04` is the refreshed demo receipt.
The exact retained commands were:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_coupled_nfkb_arena.py -v
.venv\Scripts\ocura-oss.exe run --root (Get-Location).Path --json --param demo=coupled-nfkb-arena-seed-fix -- .venv\Scripts\python.exe tools\run_coupled_nfkb_arena.py --output runs\coupled_nfkb_arena_20260926_04
.venv\Scripts\ocura-oss.exe verify --root (Get-Location).Path --json
```

This is a bounded local reference on Windows 11, Python 3.12.6 and CPU. The
shared mediator field has no spatial gradient; its secretion, clearance and
response parameters are declared synthetic. The reporter index is not the
observed Nuc/Cyto p65 ratio, and the comparison is not measured efficacy,
biological calibration, external solver verification or a tumor prediction.
