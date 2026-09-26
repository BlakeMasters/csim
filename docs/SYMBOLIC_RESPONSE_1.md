# Typed illustrative NF-κB response graph v1

`cellsim_v2.symbolic_response` represents the existing illustrative
`NfkbEpisode` response recurrence as a **data-only, executable expression
graph**. It is separate from symbolic IR v0's concentration switch and gated
same-species transfer, and from the proposed workflow v1 that schedules typed
episode actions. The graph does not create, consume, or transfer an amount. It
does not set a biological mechanism or claim calibrated NF-κB kinetics.

The canonical [program JSON](../runs/symbolic_response_demo_20260926_01/program.json)
has 23 ordered nodes. Inputs are the accepted interval's post-transfer
stimulus concentration (`mol/m^3`) and per-cell payload amount (`mol`), the
previous private nuclear/feedback/reporter indices (`1`), the step duration
(`min`), and six declared illustrative parameters. The graph computes:

```text
drive = c / (Kstim + c)
inhibition = 1 + feedback_strength * old_feedback + payload / Kpayload
nuclear_target = drive / inhibition
next_nuclear = relax(old_nuclear, nuclear_target, dt, nuclear_tau)
next_feedback = relax(old_feedback, old_nuclear, dt, feedback_tau)
next_reporter = relax(old_reporter, old_nuclear, dt, reporter_tau)
relax(old, target, dt, tau) = old + (target - old) * -expm1(-dt / tau)
```

This matches the staging and arithmetic of
[`NfkbEpisode.step`](../src/cellsim_v2/nfkb_episode.py): the episode first
checks finite reservoir and paired field/cell transfers, then evaluates the
response against the new field/payload and previous private state, then
commits all accepted state together. `evaluate_response` is pure and returns
only the three candidate indices. It cannot commit a transaction or replay a
checkpoint on its own.

The closed parser admits only fixed source names, finite constants, `add`,
`mul`, `div`, and first-order `relax`. Every node has a declared unit; references
must point backward to defined nodes. It rejects duplicate JSON keys or node
IDs, unknown sources/operations/fields, unsupported units, inconsistent
dimension arithmetic, missing runtime inputs, nonfinite values, forward
references, and graphs over 64 nodes, depth 16, or 32 KiB. Division by zero
and out-of-domain outputs fail without clipping. Validation of an alternate
well-typed graph does not establish that it represents the canonical response
formula; the parity result below is for the exported canonical program.

From the repository root on Windows 11, CPython 3.12.6, CPU:

```powershell
$env:PYTHONPATH='src;tools'
.venv\Scripts\python.exe -m unittest discover -s tests -p test_symbolic_response.py -v
.venv\Scripts\python.exe tools\run_symbolic_response_demo.py --output runs\symbolic_response_demo_20260926_01
git diff --check
```

Focused tests passed **4/4**. The preserved
[demo result](../runs/symbolic_response_demo_20260926_01/results.json)
compared the graph with eight accepted episode intervals, four each for one
and three cells: 16 cell-interval rows, 48 scalar output comparisons, maximum
absolute difference **0.0** on the exercised host. It retained a rejected
unknown-reference program, the [per-cell trace](../runs/symbolic_response_demo_20260926_01/trace.json),
program SHA-256 `34d7d600599128c66905a1f3b920fbd0c39e009ae01a03728d8338914653a380`,
and ordered source/test/tool SHA-256
`2a0b8573805c7042138fd10ddbe3a9a87ccb979e8f392c328c23014665abdaa7`.
Local execution before result persistence took 0.034 s. No independent solver
or biological data comparison was performed for this symbolic graph.

The 1–5-cell NF-κB episode, generic inhibitor-like delivery, external
reservoirs, amount ledgers, accepted-state rejection and checkpoint replay
remain owned by `NfkbEpisode`; seeded variability and secretion/sensing remain
separate Python references. Workflow v1 may invoke this evaluator per cell
after its typed actions pass the episode's transfer checks, but workflow
composition alone will not validate the response law or drug efficacy.
