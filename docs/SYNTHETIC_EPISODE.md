# Synthetic cell episode transaction slice

`cellsim_v2.synthetic_cell_episode` is a deterministic, fixed-topology reference
for one cell and one 3D voxel. It joins the H02 scalar response memory with the
existing same-species saturable uptake `Update`. It is a small H04 transaction
precursor that a local numeric self-play demonstration can call. It does not
train a cell model, close V01, or establish biological response.

## Interface and stage order

```python
from cellsim_v2.synthetic_cell_episode import (
    EpisodeRejected, SyntheticCellEpisode, make_synthetic_episode,
)

episode = make_synthetic_episode(horizon_steps=4, step_s=0.25,
                                 target_response_index=0.5)
observation = episode.reset()
action = episode.make_action(vmax_mol_s=0.1)
transition = episode.step(action)
checkpoint = episode.checkpoint()
resumed = SyntheticCellEpisode.from_checkpoint(checkpoint)
```

`make_action` binds the proposed maximum rate in mol/s to the current cell,
species, model/context identity and interval. The episode fixes `Km` at
0.5 mol/m³. The action specifies a **rate parameter**, not an integrated amount
or an unrestricted amount replacement. The physical update computes the actual
integrated transfer from pre-step concentration and interval duration, debits
the field, and credits the cell with the same species.

At each step, the episode samples the accepted local concentration. It computes
the memory replacement over `[start,end)` from that concentration and separately
computes the uptake `Update` on a clone of the accepted `World`. It validates
the paired transfer, amount total and aligned response/world clocks, then
publishes the new world and memory as one internal accepted tuple. An invalid
action, collective overdraw or incompatible identity raises `EpisodeRejected`;
the caller can retain the exception as a failed-attempt record and the accepted
episode checkpoint is unchanged.

The observation reports only the current local concentration, accepted memory,
cell amount, clock, identity and remaining steps. It excludes the evaluator's
synthetic target and model parameters. `step` returns the new observation,
negative absolute error against the fixed synthetic response-index target,
termination status and numerical diagnostics. This score is **synthetic training
feedback**; receiving it does not convert a final biological benchmark into
training data. The current action cannot affect the memory update for its own
interval because that update uses the accepted pre-step concentration. It can
affect later memory and scores.

The checkpoint contains the complete state needed by this wrapper: the world,
response state, model/configuration, accepted step count and stage clocks. It
has a corruption checksum and validates model/context, world and response
identity, aligned clocks and the closed amount total on restore. This simple
deterministic episode has no RNG, integrator history, event queue, solver-private
state or topology changes. The checksum is not authentication of a malicious
writer. The wrapper does not promise rollback for arbitrary external learners.

## Local execution evidence

Run from the repository root:

```powershell
python -c "import sys,unittest;sys.path[:0]=['src','tools'];suite=unittest.defaultTestLoader.discover('tests',pattern='test_synthetic_cell_episode.py');result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())"
python tools/run_synthetic_episode.py --output runs/synthetic_episode_20260926_02
```

The targeted suite passed **4/4** tests on Windows 11, Python 3.13.5, CPU.
`runs/synthetic_episode_20260926_02/results.json` records a four-step
trajectory with rates 0.1, 0.1, 0.05 and 0 mol/s, a JSON checkpoint roundtrip
with exact continuation equality, an overdraw rejection with unchanged accepted
state, a valid retry, numerical configuration, runtime identity, source/test/tool
SHA-256 and limitations. A targeted checkpoint test also rejects extra
unsupported cell material even if the checkpoint checksum is recalculated.
The maximum reported closed amount balance error is less than 1e-12 mol.
This is evidence for the declared synthetic transaction
only. The consolidated test suite is recorded separately by `tools/run_checks.py`.
