# Shared local Csim demo with required Ocura OSS record

The shared demo runs thirteen bounded components on this laptop and records the
command through **Ocura OSS**. The `direct` mode is its internal workload and
for tests. An installed Ocura Engine prototype can optionally execute that
same workload through OSS; no Engine files are included in this repository.
OSS verifies the command logs and does not qualify numerical or biological
behavior. Component JSON files and focused tests carry those narrower checks.

From the repository root in PowerShell, use the pinned local environment and
a **new** run directory:

```powershell
$RunDir = 'runs/integrated_demo_oss_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
& .venv/Scripts/python.exe tools/run_integrated_demo.py oss --output $RunDir
Get-Content "$RunDir/receipt.json"
```

If the local environment is absent, create it and install the tested pins in
`requirements-hackathon.txt` before this command. Ocura OSS 0.4.0 is required
for this shared route. A missing OSS executable produces a failed
`receipt.json` in the new directory. Run artifacts and the `.ocura-oss/`
ledger should be retained when reviewing a demonstration.

The observed-data stage also requires the local file
`data/scmat_sequentialstim.mat` with SHA-256
`69495462c1ee0f7f10eb04963803b55a7f2852833aebcd95ca166a4e3cc415fa`.
The `data/` file and `runs/` evidence are local inputs/artifacts, not tracked
package contents. The OSS entrypoint writes a failed receipt with a clear
missing-input or hash-mismatch error if this exact source is unavailable.

The workload runs symbolic rules, offline response memory, the joint episode,
the bounded proposer/learner curriculum, finite ligand secretion/sensing,
the fixed-3D uptake/splitting study, and the one-to-five-cell shared-field
arena. It then exports the supplied NF-κB observed traces, fits the causal
reporter basis on the predeclared sequence split, computes observed cell
dispersion, attaches author-reported nominal extracellular dose metadata,
and runs deterministic and seeded illustrative NF-κB/payload episodes using
that **fresh** observed artifact. The fitted candidate, comparison overlay,
[source-dose metadata](../runs/nfkb_metadata_20260926_01/metadata.json),
and synthetic episodes remain separate artifacts. The fitted model's parameters
are not inserted into the illustrative
pathway parameters. The run stops dependent work if the observed export or
fit or downstream data chain fails. The receipt lists component paths, statuses and hashes, OSS
atom/chokepoint IDs, OSS verification and a source/test/tool fingerprint
checked across the command.

The optional Engine route requires an independently installed local Engine
CLI and still records through OSS:

```powershell
$EngineCli = '<path-to-your-installed-ocura-engine-cli>'
$RunDir = 'runs/integrated_demo_engine_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
& .venv/Scripts/python.exe tools/run_integrated_demo.py engine --output $RunDir --engine-cli $EngineCli
```

No Engine API, binary or vendor code is copied into the shared repository.
The native Windows process adapter reports execution and resource samples;
requested limits are not stress-tested by the demo. The previous
[six-component Engine/OSS receipt](../runs/integrated_demo_engine_20260926T2036Z/receipt.json)
remains preserved.

The [passing OSS-only receipt](../runs/integrated_demo_oss_20260926T2119Z/receipt.json)
records 13/13 accepted components, OSS atom
`atom-72077317b969450a810c66e82e51d90d`, successful verification of 64
logs with zero reported problems, and identical source/test/tool fingerprints
before and after the workload
(`5cf05e39058a7ac417553ade849ed0a3a3200cf2243eb7b20e33c44a203d2cae`).
It ran on Windows 11 with Python 3.12.6 and CPU. The thirteen-component
[direct integration checkpoint](../runs/integrated_demo_direct_20260926T2117Z/results.json)
also passed with a stable fingerprint and a fresh observed→fit→episode
dependency chain. The first [OSS-only attempt](../runs/integrated_demo_oss_20260926T2107Z/receipt.json)
retained all ten components that existed at that point and verified OSS logs,
but was marked failed because concurrent source edits changed its fingerprint
during execution. That failed attempt remains preserved.

All arena and delivery amounts, parameters and scores are synthetic. The
observed NF-κB trace and separate empirical fit have declared source and
split provenance; neither establishes the illustrative pathway as a fitted
mechanistic model or a drug-response predictor. No external spatial solver,
live biological calibration or GPU qualification is claimed.
