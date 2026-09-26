# Synthetic finite secretion and field sensing

`cellsim_v2.ligand_communication` is a two-cell reference interaction in one
fixed 3D voxel. The sender starts with 0.1 mol of `synthetic_ligand`, and the
receiver starts with no ligand. Both values are engineering inputs without a
cell-line or measured parameter identity.

The `SecretionRate` action is mol/s. `secretion_step` multiplies it by the
declared interval to obtain an integrated molar amount, rejects demand beyond
the sender's finite inventory, debits the sender and credits the field with
one pure `Update`. There is no external source ledger because this is an
internal paired transfer. Field concentration is the field amount divided by
the voxel's 0.125 m³ volume.

The receiver senses the **accepted pre-step** field concentration through the
existing synthetic scalar relaxation law. Its response memory is dimensionless
and private to the episode wrapper. Sensing does not debit the field, credit
the receiver's ligand inventory, bind a receptor or consume the ligand. A
secretion during one interval can affect the receiver's next interval response.
This staging is explicit and synthetic; no spatial gradient is resolved.

```python
from cellsim_v2.ligand_communication import (
    LigandCommunicationEpisode, LigandRejected,
)

episode = LigandCommunicationEpisode()
observation = episode.reset()
transition = episode.step(episode.make_action(rate_mol_s=0.04))
checkpoint = episode.checkpoint()
resumed = LigandCommunicationEpisode.from_checkpoint(checkpoint)
```

`step` computes sensing and secretion on copies, validates amount balance and
aligned clocks, then publishes the `World` and receiver response state together.
Overdraw, stale intervals and identity mismatches raise `LigandRejected` without
changing the accepted state. The checkpoint covers world, private response,
model, configuration and stage clock and supports deterministic JSON roundtrip
continuation. It has a corruption checksum, not malicious-writer authentication.
There is no RNG, external solver-private state or event queue in this slice.

Run from the repository root:

```powershell
python -c "import sys,unittest;sys.path[:0]=['src','tools'];suite=unittest.defaultTestLoader.discover('tests',pattern='test_ligand_communication.py');result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())"
python tools/run_ligand_demo.py --output runs/ligand_demo_20260926_01
```

The focused suite passed **4/4** tests on Windows 11, Python 3.13.5, CPU.
The preserved [results](../runs/ligand_demo_20260926_01/results.json) have
top-level `status: pass`, configuration, step trace, source/test/tool SHA-256,
maximum closed amount balance residual, replay equality, overdraw rejection,
valid retry and limitations. The first 0.5 s secretion at 0.04 mol/s raises
field concentration to 0.16 mol/m³ while receiver memory stays zero; on the
following zero-secretion interval the receiver's memory increases. This is a
synthetic communication mechanism, not receptor biology, tissue validation or
an intercellular signaling claim for a named system.
