# Executable NF-κB action protocol, version 1

`cellsim_v2.symbolic_workflow` is a closed, data-only protocol for actions
accepted by the existing synthetic `NfkbEpisode`. It binds an initial
checkpoint, one to five cell/model digests, a time grid, four categorical
author stimulus labels, and typed material effects. It lowers each interval
to `NfkbEpisode.make_scheduled_action`; the episode remains the owner of
physical conservation, private response state, rejection and checkpointing.

| Construct | Version 1 execution | Boundary |
|---|---|---|
| `T/I/L/P` author order | Switches at 0, 120, 240, 360 min on an aligned step grid | Categorical only; no dose conversion |
| Stimulus reservoir → field | Integrated mol at each switch | Finite source checked by episode |
| Previous stimulus field → waste | Current field amount at each switch | Paired debit/credit checked by episode |
| Generic payload reservoir → field | One integrated mol amount at a declared grid time | No identified drug or efficacy mapping |
| Payload field → cells | One mol/min rate per bound cell identity and model digest | Actual transfer depends on existing uptake kernel and finite field |
| NF-κB proxy feedback equations | Separate `cellsim_v2.symbolic_response` pure graph | This workflow does not encode or change response dynamics |
| Observed p65 data and frozen reporter fit | Separate read-only artifacts | Not a simulator parameter source or policy oracle |

Unknown fields, duplicate JSON keys, nonfinite numbers, unsupported effects,
unit/species mismatches, off-grid times, missing or forged cell identities,
and mismatched initial checkpoints are rejected. Reservoir or field overdraw
is rejected transactionally by the episode. No arbitrary expressions,
generated Python, reactions, secretion/sensing, topology changes, seeded RNG
semantics or general graph composition are executable in this protocol.

Example from the repository root:

```python
from cellsim_v2.nfkb_episode import NfkbEpisode
from cellsim_v2.symbolic_workflow import protocol_from_episode, run_protocol

episode = NfkbEpisode(cell_count=3, horizon_steps=82, step_min=6.0)
program = protocol_from_episode(
    episode, sequence_key="TIPL", stimulus_amount_mol=0.1,
    payload_start_min=120.0, payload_amount_mol=0.02,
    rates_mol_min_by_cell={"cell_1": 0.00002,
                           "cell_2": 0.00002, "cell_3": 0.00002},
)
result = run_protocol(program, episode)
```

Run the focused verification and complete demonstration:

```powershell
$env:PYTHONPATH='src'; .venv\Scripts\python.exe -m unittest tests.test_symbolic_workflow -v
.venv\Scripts\python.exe tools/run_symbolic_workflow_demo.py --output runs\symbolic_workflow_demo_20260926_01
```

The [preserved demo](../runs/symbolic_workflow_demo_20260926_01/results.json)
completed 82 accepted intervals for three cells. Its lowered actions,
transitions and final checkpoint matched direct scheduled execution exactly;
JSON checkpoint replay matched; maximum paired amount residual and rejection
controls are recorded. The [program](../runs/symbolic_workflow_demo_20260926_01/program.json)
is the inspectable typed input. Focused tests passed **4/4** on Windows 11,
Python 3.12.6, local CPU. These are synthetic reference checks, not
biological validation or a paper reproduction.
