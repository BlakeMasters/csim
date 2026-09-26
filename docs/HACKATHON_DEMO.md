# Earlier local synthetic Csim/Engine demonstration

The current shared entrypoint is the [integrated Ocura OSS demo](INTEGRATED_DEMO.md),
which requires OSS for its command record. The Engine route documented below
is an earlier, optional local prototype run; Engine is not included in the
shared repository.

This is a runnable local reference demonstration, not a biological experiment.
It shows one five-interval synthetic concentration switch and conservative
field-to-cell tracer transfer through installed Ocura Engine 0.2.0. A second
command deliberately supplies the nonrunnable oxygen hypothesis template and
must fail. Ocura OSS 0.4.0 records both commands and verifies its logs.

## Rerun on this laptop

From the repository root in PowerShell, choose a **new** output directory:

```powershell
$EngineCli = 'C:\Users\blake\.codex\artifacts\ocura-learning-companion-20260926\r2\env-no-ml\Scripts\ocura.exe'
$RunDir = 'runs/hackathon_demo_local01_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
& .venv/Scripts/python.exe tools/run_hackathon_demo.py --output $RunDir --engine-cli $EngineCli
Get-Content "$RunDir/receipt.json"
```

The wrapper uses `.venv/Scripts/python.exe` for the Csim command and
`.venv/Scripts/ocura-oss.exe` for the ledger. It creates the run directory
once, writes both Engine specs, executes each Engine command through OSS, reads
the actual Engine status and process exit code from its report, independently
calculates the Csim transfer and balance metrics from `trace.jsonl`, and calls
`ocura-oss verify`. A failed attempt retains a receipt and the available call
records. The directory and `.ocura-oss/` are ignored by Git; keep them when
moving this evidence to another checkout.

For a direct Csim run without Engine or OSS, use a new directory:

```powershell
& .venv/Scripts/python.exe tools/run_rule_demo.py --rules configs/biological_rules.synthetic.json --output runs/direct_rule_demo_NEW_ID
```

## Declared case and acceptance

The observable is integrated field-to-cell transfer of `synthetic_tracer` in
mol, measured as the sum of cell amount increments across the five accepted
0.1 s intervals. The same-species amount ledger residual is checked after
each interval and over the full run. The example uses one fixed 1 m³ voxel,
one cell, synthetic reservoir concentrations `[0.4, 0.65, 0.9, 0.65, 0.4]`
mol/m³, and the synthetic JSON switch/transfer parameters. No measured data,
fit, holdout, external solver comparison, or GPU is involved.

The wrapper accepts a run only when Csim completes five intervals, the
integrated transfer is positive and matches final cell amount within
`1e-12 mol`, each amount residual and the final ledger residual are within
`1e-12 mol`, Engine success/failure statuses and return codes match the two
cases, OSS outcomes match, all OSS logs verify, the broad source/test/tool
fingerprint is stable during the wrapper, and Engine reports no degraded
capability for the requested limits. This tolerance is an engineering demo
criterion, not measurement uncertainty.

Both Engine attempts request a 15 s phase timeout, 512,000,000 B job memory
limit, and one active process. The wrapper also has a 60 s outer wait per
command. The tested Engine adapter is `native-process` on Windows, whose
published capability posture is **best-effort**. Empty degraded diagnostics
mean these requested limits were accepted during this run; no memory,
process-count, or timeout threshold was stressed. The Engine applies command
execution controls and reports process observations. It does not evaluate the
Csim numerical result or establish a general sandbox.

## Preserved local evidence, 26 September 2026

The earlier [20:16 UTC attempt](../runs/hackathon_demo_local01_20260926T2016Z/receipt.json)
completed both Csim cases, but both Engine reports contained
`job-object-limits-unavailable` when the spec also requested a 10 s CPU-time
limit. Its broad fingerprint changed during concurrent development, so it is
retained as diagnostic evidence and is not the reduced-cap qualification.
The CPU cap was removed for one targeted follow-up; no claim is made that
the CPU-time limit works on this host.

The [20:17 UTC reduced-cap receipt](../runs/hackathon_demo_local01_20260926T2017Z/receipt.json)
reports `passed`. On Windows 11 build 26200, Python 3.12.6, CPU, installed
Engine 0.2.0 and OSS 0.4.0:

| Case | Engine run ID | Engine status / child exit | OSS atom / chokepoint | Observed result |
|---|---|---|---|---|
| Synthetic transfer | `20260926-201728-487` | `passed` / `0` | `atom-b3f493b89cce4baa84b8e7ace3ce4811` / `chokepoint-6730b1ec840348f28f1fafc72562866f` | `0.001208074534161491 mol` integrated transfer; `0 mol` total and maximum interval amount residual |
| Nonrunnable hypothesis | `20260926-201729-249` | `failed` / `1` | `atom-7c6a060a405c476098198e714f7d6de5` / `chokepoint-842858e6e4474d4e9d796737dd0e6fda` | Csim `ValueError`; null biological parameters and unset identity rejected |

Both Engine reports had empty `degraded_capabilities`. The success phase had
three resource samples, 27,066,368 B peak RSS, 0.217 s phase duration, and
0.755 s OSS command duration. The reduced-cap run directory held about 86.5 KB
when inspected. OSS verification returned `ok`: 24 atoms, 24 chokepoints,
48 checked logs, zero problems. The success and deliberate failure each have
their own Csim `results.json`, Engine report, run spec, and OSS call/result.

The reduced-cap run's source/test/tool SHA-256 was
`45c3d3b59d3c7329ff6788edd598373acc7de1ed1828a828de745846c45d3a2e`
at wrapper start, in both Csim results, and at wrapper end. The synthetic
rules file SHA-256 was
`fbbe28a8af23cdb9bc55bb03549a6923bddb44c5896056579d31c3d76b2e30cd`;
the installed Engine package-content SHA-256 was
`9b09e263abec9b30162ba1ce346d6c1f780de14b87b256e3673a0e59dc7d40b3`.
The [receipt](../runs/hackathon_demo_local01_20260926T2017Z/receipt.json)
lists per-artifact hashes and the exact commands. The repository's separate
reference suite baseline for this session is
`runs/checks_on93yn7e/`: 137 run, 136 passed, 1 skipped.

This qualifies the short synthetic command route on the tested local build.
It does not qualify an Engine-backed biological model, independent numerical
comparator, live coupling, production resource isolation, or GPU execution.

## Expanded local workflow and interactive trace replay

The later [integrated demo guide](INTEGRATED_DEMO.md) gives the one-command
Ocura OSS route for thirteen components, including a separately fitted
observed NF-κB reporter trace and illustrative synthetic episodes. Its
[passing receipt](../runs/integrated_demo_oss_20260926T2119Z/receipt.json)
retains each component status, dependency, artifact path, and source fingerprint.
The proposer/learner component runs a bounded synthetic curriculum with equal
development budgets and frozen evaluation weights. It implements neither a
reinforcement-learning update nor cell-versus-cell competition.

An accepted uptake session exported from the local browser as
`cellsim.interactive-uptake-trace.v1` can be replayed independently. The
export contains its initial numeric configuration and one accepted typed rate
per interval; rejected browser attempts remain in the browser session. For a
new local output directory, run:

```powershell
$EngineCli = 'C:\Users\blake\.codex\artifacts\ocura-learning-companion-20260926\r2\env-no-ml\Scripts\ocura.exe'
$RunDir = 'runs/interactive_trace_engine_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
& .venv/Scripts/python.exe tools/replay_interactive_trace.py engine --input path/to/exported-session.json --output $RunDir --engine-cli $EngineCli
Get-Content "$RunDir/receipt.json"
```

The [replay receipt](../runs/interactive_trace_engine_20260926T2045Z/receipt.json)
records four accepted steps, Engine run `20260926-204309-044`, OSS atom
`atom-d0c57a6c276e4fe69f8a151b86003417`, 52 verified logs, and a zero
same-species amount residual. The direct
[overdraw example](../runs/interactive_trace_overdraw_20260926T2042Z/results.json)
retains its one-step accepted prefix and confirms the rejected next proposal
left the complete accepted checkpoint unchanged. The wrapper accepts finite
nonnegative numeric inputs within the browser bounds and at most 32 steps;
physical overdraw remains a reported failure. This one-cell replay is
synthetic, not a measured exposure or biological response.
