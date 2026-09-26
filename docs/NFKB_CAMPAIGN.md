# Bounded NF-κB synthetic experiment campaign

`tools/run_nfkb_campaign.py` executes a fixed manifest matrix over the existing
`NfkbEpisode` and `SeededNfkbEpisode` reference models. Each declared cell
count (1–5), payload timing/amount protocol, and deterministic or explicitly
seeded replicate receives a matched stimulus-only baseline and payload
intervention. The same seed is used in both arms. A manifest is copied byte
for byte and its SHA-256 anchors every pair and trace ID.

The time grid is fixed at 0–492 minutes in six-minute samples (82 accepted
steps). The stimulus order is a four-letter categorical permutation of
T/I/L/P, with synthetic 0/120/240/360-minute field switches. Every stimulus
and generic inhibitor-like payload amount remains a declared **molar synthetic
amount**. Letters do not imply the author-reported experimental ng/mL doses.

The tracked response is a dimensionless illustrative reporter index. For each
complete run, the campaign reports each cell's peak, earliest sampled
time-to-peak, and trapezoidal area under the reporter curve over 0–492
minutes. The same metrics are computed from the per-time mean of the cells;
`delta_mean_metrics` is intervention minus baseline. These differences do not
estimate measured efficacy. Each trace records all samples, typed actions,
paired transfer ledgers, maximum amount residual and the accepted physical
checkpoint hash on failure. Failed runs retain their partial traces; pair
deltas are null if either arm fails. The result charges attempted/accepted/
failed steps, deterministic/seeded runs, metric evaluations, trace bytes and
wall time. The matrix is bounded at 40 pairs.

Run the [example manifest](nfkb_campaign_example.json) through the required
local Ocura OSS ledger in a **new** run directory. The source checkout uses
the pinned `.venv` and keeps Engine optional:

```powershell
$RunDir = 'runs/nfkb_campaign_' + (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$OssRun = & .venv/Scripts/ocura-oss.exe run --root (Get-Location).Path --json --param campaign=nfkb-synthetic-matrix -- .venv/Scripts/python.exe tools/run_nfkb_campaign.py --manifest docs/nfkb_campaign_example.json --output $RunDir | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $OssRun.outcome -ne 'passed') { throw 'OSS campaign command failed' }
$OssVerify = & .venv/Scripts/ocura-oss.exe verify --root (Get-Location).Path --json | ConvertFrom-Json
if ($LASTEXITCODE -ne 0 -or $OssVerify.status -ne 'ok' -or $OssVerify.problems.Count -ne 0) { throw 'OSS verification failed' }
$Campaign = Get-Content "$RunDir/results.json" -Raw | ConvertFrom-Json
if ($Campaign.status -ne 'pass') { throw 'Campaign contains failed runs' }
$ResultHash = (Get-FileHash "$RunDir/results.json" -Algorithm SHA256).Hash.ToLowerInvariant()
$Record = [ordered]@{status='passed'; atom_id=$OssRun.atom_id; chokepoint_id=$OssRun.chokepoint_id; pathway_id=$OssRun.pathway_id; oss_outcome=$OssRun.outcome; child_return_code=$OssRun.return_code; verification=$OssVerify; manifest_sha256=$Campaign.manifest_sha256; results_sha256=$ResultHash; source_test_tool_sha256=$Campaign.source_test_tool_sha256}
$Record | ConvertTo-Json -Depth 10 | Set-Content "$RunDir/oss_record.json" -Encoding utf8
```

This command stops if OSS is unavailable, the child fails, the ledger fails
verification, or a campaign run fails. It writes the OSS atom/chokepoint and
verification beside `results.json` as `oss_record.json`. The reader can inspect `pairs[]`, then
open each `traces/<trace_id>.json` by its recorded path and SHA-256. The
manifest, trace, and result files must be preserved together. This campaign
does not fit a pathway law, map the supplied measured reporter to the
synthetic index, vary tissue geometry, use a biological drug, or establish
clinical or cellular predictive validity. It is a reproducible local protocol
and amount-ledger comparison on Windows CPU.

The first [local campaign receipt](../runs/nfkb_campaign_20260926_01/oss_record.json)
records OSS atom `atom-7785ff41fae84949b4d9ae64e7cf8870` and 66 verified
logs. Its [result](../runs/nfkb_campaign_20260926_01/results.json) has 30
matched pairs, 60 complete runs and 4,920 accepted steps, zero failed runs,
manifest SHA-256 `77c921c02b9f6c8059890dac049fe792d7378c1a64ca84b523d2f432394f6bc1`,
and source/test/tool SHA-256
`c2e2245b954e842a1b47f89c7f0eb314db57cf66806b5d9b1d5c8f169fc838e1`.
The first run passed. An additional regression confirmed that matched arms
have identical samples through minute 120; it found no defect but changed the
source/test/tool hash. The
[current run](../runs/nfkb_campaign_20260926_02/results.json) repeated the
same matrix and passed under [OSS verification](../runs/nfkb_campaign_20260926_02/oss_record.json):
atom `atom-e7bf920412eb4819b6a060c56808832d`, 68 logs with zero problems,
maximum amount residual `1.39e-17` mol, source/test/tool SHA-256
`b7a57b3bf1f4decc8399aab3c42a39611d0052b0b45c3100fb49329850ac53e8`.
The exact current commands were:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p test_nfkb_campaign.py -v
.venv\Scripts\ocura-oss.exe run --root (Get-Location).Path --json --param campaign=nfkb-synthetic-matrix-v2 -- .venv\Scripts\python.exe tools\run_nfkb_campaign.py --manifest docs\nfkb_campaign_example.json --output runs\nfkb_campaign_20260926_02
.venv\Scripts\ocura-oss.exe verify --root (Get-Location).Path --json
```
