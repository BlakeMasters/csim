# Data-scheduled illustrative NF-κB episode

`cellsim_v2.nfkb_episode.NfkbEpisode` accepts one to five independently
identified cells in a fixed 3D voxel. It uses a verified **categorical**
stimulus order and 6-minute sampling clock from the supplied sequential
NF-κB experiment. The implemented response states are a bounded nuclear
proxy, delayed feedback and a delayed dimensionless reporter index. Their
relaxation constants and effect scales are declared synthetic demonstration
values, not estimated molecular rates. The [Hoffmann et al. 2002](https://pubmed.ncbi.nlm.nih.gov/12424381/)
and [Nelson et al. 2004](https://pubmed.ncbi.nlm.nih.gov/15499023/) primary
studies motivate feedback and time-dependent nuclear response as concepts;
this reduced equation does not reproduce either paper.

The [observed trace artifact](../runs/nfkb_observed_20260926_01/observed_traces.json)
comes from the supplied `scmat_sequentialstim.mat` and the
[Wang et al. source study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10794069/).
For the demo, condition 2 is a frozen evaluation sequence `T,I,P,L` with
switches at 0, 120, 240 and 360 minutes. The source reports author-normalized
nuclear/cytoplasmic p65 trajectories at 0:6:492 minutes. The code and raw
source row keys are preserved in the output. [Versioned source metadata](../runs/nfkb_metadata_20260926_01/metadata.json)
records author-reported nominal high/mid/low extracellular concentrations in
ng/mL from the paper's STAR Methods. Its normalization algorithm and per-row
run/chamber identities remain unresolved. The model's synthetic reporter
index is shown on the same time axis as the observed mean as a **distinct,
uncalibrated curve**; no residual, fitted parameter or biological prediction
score is calculated from their numerical difference.

The environment also tracks finite synthetic stimulus and generic inhibitor-
like payload reservoirs. Administration actions specify integrated molar
amounts; cell payload uptake proposals specify rates in mol/min. At a
stimulus switch, a typed withdrawal sends the previous field amount to a
tracked waste inventory before the next reservoir-to-field transfer. Stimulus
sensing is non-consuming. Payload uptake debits the field and credits each
cell's amount through the existing pure conservative transport update. Every
step computes on a candidate world and private-state copy and publishes them
together after paired ledgers, nonnegative amounts, identities and clocks pass.
Aggregate overdraw rejects the entire proposal; no demand is scaled or
clipped. These synthetic molar amounts are not mapped to the experiment's
ligand concentrations. The payload scenario is not measured drug efficacy.

```python
from cellsim_v2.nfkb_episode import NfkbEpisode, NfkbRejected

episode = NfkbEpisode(cell_count=3, horizon_steps=82, step_min=6.0)
observation = episode.reset()
action = episode.make_action(stimulus_code="T", stimulus_admin_mol=0.125)
transition = episode.step(action)
checkpoint = episode.checkpoint()
resumed = NfkbEpisode.from_checkpoint(checkpoint)

# A caller holding a verified four-letter order can emit scheduled actions.
next_action = episode.make_scheduled_action(sequence_key="TIPL")
```

`observe()` returns `time_min`, `next_time_min`, accepted stimulus code,
field amount/concentration for each species, finite reservoir and waste
amounts, and `cells` keyed by stable IDs with declared positions, per-cell
model identity, payload amount, nuclear proxy, feedback and reporter index.
`make_action()` also accepts `stimulus_withdraw_mol`, `payload_admin_mol`
and `payload_uptake_rates_mol_min_by_cell`. `step()` returns the new
observation and a ledger for both species. A full JSON checkpoint retains
physical and private response state, finite stores, parameters, accepted code
and stage clock. Its hash detects accidental corruption, not a malicious
writer. There is no RNG or external solver state in this slice.
`make_scheduled_action()` accepts a verified T/I/L/P permutation and emits
the same typed action at 0/120/240/360-minute switches, with a separate
optional payload start. It requires switch and payload times to align with
the episode's step. The sequence is supplied by the caller; `observe()` does
not reveal future codes or target values.

Run from the repository root:

```powershell
python -c "import sys,unittest;sys.path[:0]=['src','tools'];suite=unittest.defaultTestLoader.discover('tests',pattern='test_nfkb_episode.py');result=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not result.wasSuccessful())"
python tools/run_nfkb_demo.py --output runs/nfkb_demo_20260926_03
```

Focused tests passed **5/5** on Windows 11, Python 3.13.5, CPU, including
one-through-five-cell paired transfers, a delayed reporter, the 120-minute
switch, deliberate reservoir and collective-uptake overdraw, identity/clock
rejection, exact JSON replay, and schedule-helper timing. The preserved
[result](../runs/nfkb_demo_20260926_03/results.json) has top-level
`status: pass`, source/test/tool SHA-256
`d60dfe14621a99a056ecc10db69df56be014396f96287f32e92a51af730a6195`,
82 accepted steps per full scenario, 1/3/5-cell bounded cases and an observed
condition-2 overlay. Maximum amount residual in the two full scenarios is
1.735e-18 mol. At 492 minutes the illustrative one-cell reporter index is
0.525 for stimulus alone and 0.278 with generic payload. These numbers only
describe the declared synthetic equations and inputs.

The same result contains a fixed-protocol delivery sweep of **20** cases:
all cell counts 1–5 crossed with 0, 0.01, 0.02 and 0.03 mol initial payload
administration at 120 minutes, followed by 0.00002 mol/min proposed uptake
per cell. All 1,640 attempted steps were accepted; each case replayed its
checkpoint exactly. Maximum amount residual was 1.39e-17 mol. At five cells,
mean terminal reporter indices across those four payload amounts were 0.5247,
0.4911, 0.4672 and 0.4505. This is a deterministic synthetic sensitivity
check. The [previous `_02` artifact](../runs/nfkb_demo_20260926_02/results.json)
is preserved as the pre-sweep run.
