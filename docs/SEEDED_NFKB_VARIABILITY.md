# Seeded synthetic cell-response variability

`SeededNfkbEpisode` in `cellsim_v2.seeded_nfkb_episode` is an optional
illustrative extension around the deterministic
[`NfkbEpisode`](NFKB_SYNTHETIC_EPISODE.md). One to five cells keep separate
fixed initial response time constants. Their feedback and reporter indices
receive a bounded log-multiplicative perturbation after each accepted step.
The seed, cell ID, accepted-step counter and channel address each draw; no
global mutable RNG advances on a rejected action. The seed and per-cell
parameters are present in the JSON checkpoint. The response variation is
synthetic and is **not** estimated from the measured dispersion.

The wrapper clones the complete accepted episode, applies the typed action
through the conservative amount kernel, perturbs only candidate private
response state, revalidates the full checkpoint, then publishes it. A rejected
aggregate payload overdraw leaves all field/cell/reservoir amounts, private
states, seed and accepted-step counter unchanged. Same-seed JSON checkpoint
continuation is exact on the tested host. Different seeds can yield different
reporter traces while amounts and paired ledgers remain the same under the
same actions.

```python
from cellsim_v2.seeded_nfkb_episode import SeededNfkbEpisode

episode = SeededNfkbEpisode(seed=17, cell_count=3)
observation = episode.reset()
transition = episode.step(episode.make_scheduled_action(sequence_key="TIPL"))
restored = SeededNfkbEpisode.from_checkpoint(episode.checkpoint())
```

Run from the repository root:

```powershell
python -c "import sys,unittest;sys.path[:0]=['src','tools'];suite=unittest.defaultTestLoader.discover('tests',pattern='test_seeded_nfkb_episode.py');result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())"
& .venv/Scripts/python.exe tools/run_seeded_nfkb_demo.py --output runs/seeded_nfkb_demo_20260926_01
```

Focused tests passed **4/4** on Windows 11, Python 3.13.5, CPU. The
preserved [result](../runs/seeded_nfkb_demo_20260926_01/results.json) passed
with source/test/tool SHA-256
`64f579284ef0be12fa5a013577298bd0264137f1e01f6b6df36a48963c80354c`.
Four seeds (7, 17, 29, 43) across cell counts 1/3/5 produced 12 seeded
replicates; three deterministic baseline cases used the same verified `TIPL`
schedule. All 1,230 attempted steps were accepted, all seeded continuations
replayed exactly, and deliberate overdraw left the accepted checkpoint
unchanged. Maximum tracked amount residual was 1.39e-17 mol. Terminal
reporter-index spans among seeds were 0.0857, 0.0543 and 0.0440 for the
1-, 3- and 5-cell cases. These are reproducible examples of declared noise,
not estimates of biological variability or uncertainty coverage.
