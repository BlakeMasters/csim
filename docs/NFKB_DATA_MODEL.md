# Sequential NF-κB observed reporter and local model demo

This is a data-backed **reporter-trajectory** demonstration. The observed
signal is the author-supplied normalized nuclear/cytoplasmic p65 fluorescence
readout from the [Wang et al. study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10794069/).
It is dimensionless. It is not an absolute NF-κB amount, a secreted cytokine,
or a measurement of the illustrative drug-delivery input in the simulation.

## Source and typed projection

The supplied `data/scmat_sequentialstim.mat` is read-only. Its SHA-256 is
`69495462c1ee0f7f10eb04963803b55a7f2852833aebcd95ca166a4e3cc415fa`
and Git blob SHA-1 is `dc97c1296ec48bc9ca20fd1f1f25b25b3e945761`, matching
the previously listed source blob. MATLAB variable `scmatcomb_norm` has shape
11,267 × 172 and `float64` values. The [author figure code](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/main/f1and2_supps.m#L14-L22)
plots columns 1–83 at 0:6:492 minutes with switches at 120, 240, and 360
minutes. Its [condition use](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/main/f1and2_supps.m#L42-L52)
places the condition ID in column 167, four stimulus codes in 168–171, and dose
tier in 172 (all MATLAB one-based). The [figure title decoder](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/main/f1and2_supps.m#L428-L469)
maps codes 0–3, 4–7, and 8–11 to T/I/L/P within each tier. The [author dose
loop](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/main/f1and2_supps.m#L74-L80)
labels tiers 1/2/3 high/mid/low. T/I/L/P refer to TNF-α, IL-1β, LPS, and
PAM2CSK4 in the study. Code 12 is plotted as `FM`; its physical meaning and
ligand are left unset here. Conditions 25, 50, and 75 contain only code 12.

Each noncontrol condition holds one of 24 non-repeating four-ligand orders at
one of the three dose tiers. All 75 conditions have internally constant
stimulus/dose metadata. The matrix contains 5 NaN, 16 +Inf, and 82 -Inf
entries. Only two lie in the 83 observed columns: MATLAB row 1757, columns
9–10. The adapter writes null at those two positions, retains the full
nonfinite position/kind inventory in `row_index.jsonl`, and computes each
condition mean from finite values at each time. It neither imputes nor clips.
11,266 rows have complete 83-point observed traces. Five complete source rows
in original row order are included per condition for browser display.

An exact row address has the form
`sha256:<source-file-sha256>:scmatcomb_norm:row:<MATLAB-1-based-row>`.
It is a source row key, not a verified biological cell or experimental run ID.
`featmat_sequentialstim.mat` has 11,265 rows and 28 columns. It is not joined
to this artifact, since stable row correspondence has not been established.
The source paper's experimental system does not supply an independent
run/chamber identifier for each row in this matrix. The author normalization
procedure and explicit reuse terms remain unresolved in this local
qualification. A subsequent source pass resolved the nominal ligand dose
values below; the original frozen training artifact still carries its earlier
null metadata rather than being retroactively changed.

### Versioned nominal stimulus doses

The primary paper's [STAR Methods, "Stimulus conditions," PDF page 19](https://taylab.uchicago.edu/uploads/9/1/8/0/91804060/PIIS2211124722009688.pdf)
lists the high/mid/low values. It is the published Cell Reports 40:111159
(2022-08-16) version, DOI 10.1016/j.celrep.2022.111159. The
[author plotting code at commit c4f448e](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/c4f448e1cc4444f4b9d721d4cf27eaf5e899ca40/f1and2_supps.m#L74-L80)
connects tier 1/2/3 to high/mid/low, and [its figure decoder](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/c4f448e1cc4444f4b9d721d4cf27eaf5e899ca40/f1and2_supps.m#L428-L469)
connects codes 0–3, 4–7, 8–11 within each tier to T/I/L/P. The inspected
author code has SHA-256
`e2569f822c2bd511d08b8a99a71faae141cae5fb5434728ccc9c141b0ae7b588`
and Git blob SHA-1 `71c42bb228f1ae24cc41dd3bb1ba9474b8000dfc`.

| Ligand | High, code tier 1 | Mid, code tier 2 | Low, code tier 3 |
|---|---:|---:|---:|
| TNF-α | 90 ng/mL | 30 ng/mL | 3 ng/mL |
| IL-1β | 3 ng/mL | 0.2 ng/mL | 0.05 ng/mL |
| LPS | 400 ng/mL | 100 ng/mL | 12.5 ng/mL |
| PAM2CSK4 | 1 ng/mL | 0.1 ng/mL | 0.01 ng/mL |

These are **author-reported nominal extracellular stimulus concentrations
in feeding medium**. They are not measured intracellular exposure, an
integrated delivered amount, or the synthetic payload rates in the NF-κB
episode. Code 12 remains labeled `FM` with null ligand/dose. The paper
describes a 64-chamber microfluidic device and replicate experiments, but
neither the single supplied MAT variable nor the inspected plotting code
establishes each row's run, physical chamber, or biological replicate ID.
Column 167 is an author group used for the 75 conditions; its plotting
variable name `chambid` is insufficient to recover those nested identifiers.
The [versioned metadata artifact](../runs/nfkb_metadata_20260926_01/metadata.json)
preserves all 75 schedules with null per-row run/chamber/replicate fields.

## Frozen split and modeling observable

The observable was declared before fitting: each condition's 83-point mean of
the author-normalized p65 nuclear/cytoplasmic reporter. Mean absolute error
is computed for minutes 6–492, equally weighting conditions. The split ranks
the 24 four-ligand order keys by SHA-256 of
`nfkb-sequence-holdout-v1|sha256-sort|16-4-4|<order>` and assigns 16 orders
to development, 4 to validation, and 4 to final evaluation. All three dose
conditions, all cell rows, and all frames of an order stay in one group. The
three `FM` conditions are displayed but excluded from fitting and scoring.
The full frozen assignment is in the observed JSON. This is a **sequence
holdout**, not an independent experimental-run or biological validation split.

The fitted causal reduced model has four ligand-specific fast states, and
four decaying prior-ligand memory states. A fast-state impulse enters when a
ligand starts at an author switch. A prior-memory impulse enters for the
departing ligand when the next ligand starts. Between 6-minute samples, states
decay by `exp(-6 min / tau)`. A regularized linear observation map uses dose,
fast states, and current-ligand-by-prior-memory interactions to emit a
dimensionless reporter proxy. These are mathematical response coordinates;
the fitted time constants and weights are **not** NF-κB/IκB molecular kinetic
parameters. No reporter observations from the held-out orders enter its
prediction. The current-stimulus control uses only the current ligand, dose,
and time since switch. The no-change control uses the held-out condition's
first observed sample and keeps it constant.

Fast constants 12/24/36/48 minutes, slow constants 90/180/360 minutes, and
ridge penalties 0.001/0.1/1/10 were searched: 48 state-space and 16
current-stimulus candidates. Fits used only 48 development condition means;
selection used 12 validation conditions. The selected state-space parameters
were `tau_fast=48 min`, `tau_prior=90 min`, `ridge=0.001`; the current-only
control selected `tau_fast=48 min`, `ridge=0.001`. One candidate JSON was
written and hashed before the 12 final evaluation conditions were scored.
There is no access-control boundary around the source MAT file, so this is a
procedural freeze. No candidate was updated after final evaluation.

| Cohort | Conditions | State-space MAE | Current-only MAE | No-change MAE |
|---|---:|---:|---:|---:|
| Development | 48 | 0.319114 | 0.353124 | 0.373504 |
| Validation | 12 | 0.315813 | 0.330436 | 0.376648 |
| Evaluation | 12 | 0.299038 | 0.342573 | 0.364259 |

This one bounded sequence comparison shows a lower observed error for this
selected reduced model than the two controls. It does not establish a general
biological, drug-response, or patient-level benefit. Per-condition residuals,
including failures, are in `comparison.json`.

Postfreeze inspection keeps all held-out outcomes visible. By dose tier, the
state-space/current-only MAEs are high 0.386246/0.487429, mid
0.389567/0.420212, and low 0.121301/0.120076. The full model is **slightly
worse at low dose** on average. Conditions 64 and 74 have larger state-space
than current-only error; they remain in the evaluation result. A descriptive
same-current-ligand contrast at high dose compares condition orders `LTIP`
and `PLIT` during the third, IL-1β, interval: their observed condition-mean
difference is +0.178381, the frozen state-space predicts +0.287939, and
the current-only control predicts 0 by construction. The model captures the
direction but overstates that contrast. It is a posthoc illustration of how
prior order can enter a causal model, not a fitted mechanism or a new
evaluation criterion. All 12 same-current-ligand pairs and all dose/order
residuals are in the separate [postfreeze residual artifact](../runs/nfkb_residuals_20260926_01/residuals.json).

## Run and inspect

The optional local reader environment in [HACKATHON_ENVIRONMENT.md](HACKATHON_ENVIRONMENT.md)
pins NumPy 2.2.6 and SciPy 1.14.1. The commands used here on Windows 11,
CPython 3.12.6, CPU were:

```powershell
$env:PYTHONPATH='src'
.venv\Scripts\python.exe -m unittest discover -s tests -p test_nfkb_observed.py -v
$env:OPENBLAS_NUM_THREADS='1'
.venv\Scripts\python.exe tools\prepare_nfkb_observed.py --output runs\nfkb_observed_20260926_02
.venv\Scripts\python.exe tools\fit_nfkb_reporter.py --observed runs\nfkb_observed_20260926_02\observed_traces.json --output runs\nfkb_model_20260926_02
python tools\report_nfkb_residuals.py --comparison runs\nfkb_model_20260926_02\comparison.json --overlay runs\nfkb_model_20260926_02\comparison_overlay.json --output runs\nfkb_residuals_20260926_01
.venv\Scripts\python.exe tools\report_nfkb_variability.py --overlay runs\nfkb_model_20260926_02\comparison_overlay.json --output runs\nfkb_variability_20260926_01
python tools\export_nfkb_metadata.py --overlay runs\nfkb_variability_20260926_01\comparison_with_bands.json --output runs\nfkb_metadata_20260926_01
python tools\predict_nfkb_reporter.py --candidate runs\nfkb_model_20260926_02\frozen_candidate.json --stimulus-codes 0 1 3 2 --dose-tier 1 --verify-overlay runs\nfkb_model_20260926_02\comparison_overlay.json --condition-id 2 --output runs\nfkb_prediction_condition2_20260926_02.json
.venv\Scripts\python.exe tools\fit_nfkb_pulse_v2.py --observed runs\nfkb_observed_20260926_02\observed_traces.json --demo-overlay runs\nfkb_metadata_20260926_01\demo_overlay.json --v1-comparison runs\nfkb_model_20260926_02\comparison.json --output runs\nfkb_pulse_v2_20260926_01
$env:PYTHONPATH='src;tools'
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_nfkb_*.py" -v
```

Five focused adapter tests, three frozen-predictor tests, two dispersion
tests, two author-dose mapping tests, and one pulse-basis test passed. The
broader NF-κB focused command above ran 18 tests successfully, including
the five synthetic episode checks. Before these files changed, the full
reference suite passed 170 of 171 tests, with one Windows symlink-privilege
skip, in `runs/checks_8j5tv4g1`. The first observed export and fit are kept
in `_01` directories; `_02` adds exact local cost accounting. The `_02` model
source/test/tool SHA-256 is
`ee2a96eb498ca810fb181ae4dd19886f93e33a62ddff503e9f5b5843a3795b94`.

- [Observed overlay](../runs/nfkb_observed_20260926_02/observed_traces.json)
  and [all source row keys](../runs/nfkb_observed_20260926_02/row_index.jsonl)
  retain the measurement side. [Observed receipt](../runs/nfkb_observed_20260926_02/receipt.json)
  records input/output hashes and parsing time.
- [Frozen candidate](../runs/nfkb_model_20260926_02/frozen_candidate.json)
  carries all 43 feature names and fitted weights. [Comparison](../runs/nfkb_model_20260926_02/comparison.json)
  records all cohort/per-condition metrics and limits. [Browser overlay](../runs/nfkb_model_20260926_02/comparison_overlay.json)
  adds the three predicted curves to each observed condition. [Fit receipt](../runs/nfkb_model_20260926_02/receipt.json)
  records hashes, attempt counts, output size, and persistence time.

### UI and Engine integration contract

The [single-file demo overlay](../runs/nfkb_metadata_20260926_01/demo_overlay.json)
is the recommended browser input (`cellsim-nfkb-demo-overlay/1`). Every one
of its 75 conditions includes `condition_id`, exact author stimulus codes,
four switch-time nominal dose entries, categorical dose tier, split,
`observed.mean/p10/p50/p90/finite_count_by_time`, five sample traces with
source-row keys, and the frozen reduced, current-only and no-change curves.
`time_min` has 83 entries at 0:6:492; switch times are 0/120/240/360.
The author dose labels describe extracellular feeding medium. `observed`
is measured reporter data; the frozen reduced model is a fitted reporter
proxy; the separate NF-κB episode's physical payload and pathway states are
illustrative. Do not convert the paper's ng/mL to the episode's molar amount
ledger without a declared species mass, compartment volume, delivery law,
and source measurements. [Metadata receipt](../runs/nfkb_metadata_20260926_01/receipt.json)
identifies the exact overlay and frozen candidate hashes.

For arbitrary valid four-code schedules, the read-only
`cellsim_v2.nfkb_predictor.predict_frozen(frozen, codes, dose_tier,
frozen_candidate_sha256=...)` returns 83 normalized reporter predictions,
their time/switch axis, nominal author dose schedule and source/model hashes.
The CLI is `tools/predict_nfkb_reporter.py`. It does no fitting and reads no
held-out observations. Its
[condition 2 replay](../runs/nfkb_prediction_condition2_20260926_02.json)
matched the stored comparison overlay to 2.22e-16 maximum absolute
difference; this is an execution invariant, not independent validation.

The [descriptive dispersion artifact](../runs/nfkb_variability_20260926_01/dispersion.json)
computes finite-only p10/p50/p90 across source rows at each time. It
summarizes observed heterogeneity mixed with measurement and environment
variation. No intrinsic nondeterministic cell law or parameter distribution
was estimated from it.

### Exploratory second response family

An exploratory delayed-pulse basis was fitted after the frozen model's
evaluation plots had already been seen. Its two gamma-shaped onset responses,
step response, and prior-ligand memory are phenomenological reporter features,
not molecular kinetics. The 36 candidates were fitted on the original 48
development conditions and selected by the original 12 validation conditions;
zero candidates failed. The selected values are `tau_early=42 min`,
`tau_late=60 min`, `tau_prior=90 min`, and `ridge=1`. The original frozen
candidate and its `_02` evaluation remain unchanged.

| Cohort | Pulse v2 MAE | Frozen v1 MAE | Interpretation |
|---|---:|---:|---|
| Development | 0.306502 | 0.319114 | Fit cohort |
| Validation | 0.315522 | 0.315813 | Original selection cohort; difference is small |
| Previously exposed evaluation | 0.291942 | 0.299038 | Posthoc comparison only |

The second family was motivated by the visible miss in condition 1, yet its
condition-1 error **worsens** to 0.417650 from v1's 0.366052. This failure is
retained in the [per-condition comparison](../runs/nfkb_pulse_v2_20260926_01/comparison.json).
The [exploratory overlay](../runs/nfkb_pulse_v2_20260926_01/pulse_demo_overlay.json)
adds an 83-point `pulse_v2_prediction` to each condition in the stable
`cellsim-nfkb-demo-overlay/1` browser schema; the primary displayed model can
remain the original frozen v1. [Candidate and search files](../runs/nfkb_pulse_v2_20260926_01/frozen_pulse_candidate.json)
and the [receipt](../runs/nfkb_pulse_v2_20260926_01/receipt.json) preserve
weights, attempts, hashes, platform and cost. Loading took 0.068 s, 36 fits
and validation 1.606 s, and posthoc scoring/export 0.079 s on Windows 11,
CPython 3.12.6, NumPy 2.2.6, CPU. Source/test/tool SHA-256 was
`a0bdde7f4f619b3e4e647174d8ac00458afa61ef8d5b0b95f0f56ebcaa52b4e7`.
No fresh untouched sequence holdout exists for this family.

### Local data setup

The source matrix and generated `runs/` artifacts are ignored locally:
`git ls-files data` is empty, so a fresh checkout needs the source supplied
separately. The required filename is `data/scmat_sequentialstim.mat`, with
SHA-256 `69495462c1ee0f7f10eb04963803b55a7f2852833aebcd95ca166a4e3cc415fa`.
The source is available in the [author repository at inspected commit
`c4f448e1cc4444f4b9d721d4cf27eaf5e899ca40`](https://github.com/tay-lab/Sequential_NF-kB_stim/blob/c4f448e1cc4444f4b9d721d4cf27eaf5e899ca40/scmat_sequentialstim.mat).
For another local demo, obtain that version from the author source, place it
at the named path, and verify with
`(Get-FileHash data\scmat_sequentialstim.mat -Algorithm SHA256).Hash` before
running the commands above. No automatic download or redistribution is part
of this package. Explicit reuse/redistribution terms for the file have not
been verified here.

On the recorded run, reading/projection/export of the 14,362,879-byte MAT
took 1.016 s and wrote 5,917,418 bytes before its receipt. Loading the
observed JSON took 0.028 s; 64 fits plus validation took 2.728 s; final
cohort scoring/overlay took 0.078 s, including 0.076 s prediction inference;
persistence before the fit receipt took 0.140 s and wrote 2,254,894 bytes.
All 64 candidates completed; zero failed attempts. These CPU timings are
local measurements, not scale claims. Final held-out condition scoring was
performed once after candidate freeze.
