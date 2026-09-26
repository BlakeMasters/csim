# Local hackathon data readers and run ledger

Qualified locally on 2026-09-26: Windows 11, CPython 3.12.6, CPU. The raw `data/` files were read, not changed. This qualification covers file opening, ZIP/compressed-data integrity, structure, and a reference test run. It does not approve biological interpretation, a training split, a model fit, or an AWS endpoint.

## Recreate the isolated environment

Run in PowerShell from the project root:

```powershell
C:\Python312\python.exe -m venv .venv
.venv\Scripts\python.exe -m pip install --no-cache-dir -r requirements-hackathon.txt
.venv\Scripts\python.exe -m pip check
.venv\Scripts\python.exe -I -B tools\check_data_readers.py --root data
.venv\Scripts\python.exe tools\run_checks.py
```

`requirements-hackathon.txt` pins the versions actually exercised here: NumPy 2.2.6, SciPy 1.14.1, openpyxl 3.1.5, et-xmlfile 2.0.0, and ocura-oss 0.4.0. This is an optional inspection environment; the reference core still runs without these packages. The Ocura OSS wheel downloaded for this run has SHA256 `140539d072746dd2b4a0f523f919a006e350469aa4ad4097fa6384d7cefdb281`. The install report is retained at `runs/hackathon_environment_20260926/install-report.json`.

The machine's global Python 3.12.6 had SciPy 1.14.1 with NumPy 2.5.0 and produced a compatibility warning; it also lacked openpyxl. Use `.venv` for the data readers and Ocura OSS. The installed MATLAB R2022b license was expired; the eight supplied MATLAB v5 files opened with SciPy and did not need MATLAB for this check. This does not qualify other MATLAB formats or MATLAB code execution.

## Reader findings

The read-only `tools/check_data_readers.py` opened all 11 files: 3 XLSX workbooks with openpyxl and 8 MATLAB v5 files with SciPy. Every XLSX archive passed a full ZIP CRC check; every MAT array loaded with compressed-data integrity verification. The report returned `passed` with zero parser problems. A deliberately damaged `.mat` in `runs/hackathon_environment_20260926/invalid-input/` returned `failed` and exit code 1; it is separate from `data/`.

Issues to resolve before a typed ingestion adapter or fitting:

- `ExpOA_WM164.xlsx` repeats `Day`, `OuterRadius`, `InhibitedRadius`, `NecroticRadius`, `Keep`, and `PIMOuterRadius` as column headers. Choose the intended table and map each field by position and meaning.
- `ExpOA_WM983b.xlsx` has an empty `PIMOuterRadius` cell at `J120`. Specify whether it is missing, inapplicable, or an input error; do not impute silently.
- `scmat_sequentialstim.mat` contains 5 NaN, 16 positive infinity, and 82 negative infinity entries in `scmatcomb_norm`. Define handling before numeric training.
- `scmatcomb_norm` is 11267 x 172 while `featmat` in `featmat_sequentialstim.mat` is 11265 x 28. Row correspondence is unestablished. Do not join by row index without source keys and provenance.

The source metadata still needs dataset identity, terms of use, experimental units, assay units, condition and time mappings, and an observable plus frozen split. The format check does not assign any of those. See `B01`, `B02`, `H01`, and `T03` in `docs/BUILD_BACKLOG.md`.

## Ocura OSS run ledger and board

The published `ocura-oss` package provides a local branchable command-run ledger with verified logs. It does not provide live agent messaging. The editable [work board](../.agents/BOARD.md) holds assignments and status; `.ocura-oss/` holds local command records. Both `.ocura-oss/` and `runs/` are ignored by Git, so back them up separately if they must survive a new checkout. Do not put secrets or source data into labels or board text.

This project already has one initialized ledger. To inspect it:

```powershell
.venv\Scripts\ocura-oss.exe verify --root (Get-Location).Path --json
.venv\Scripts\ocura-oss.exe pathways --root (Get-Location).Path --json
.venv\Scripts\ocura-oss.exe chokepoints --root (Get-Location).Path --json
```

On a fresh checkout only, initialize once with `ocura-oss init --root (Get-Location).Path --name cellular-sim-v2 --json`. To record a new check, use `ocura-oss run --root (Get-Location).Path --json --param check=<label> -- <executable> <arguments>`; preserve the returned atom and chokepoint IDs in the board. Run one mutating ledger command at a time. `--param` labels the run and does not pass arguments to the executable.

Current recorded runs are `atom-c74d6004cc5c4d7e9855afacbda3cf98` (file reader check) and `atom-1d7cd91212c545c38a5aedf044c3623f` (reference checks). `ocura-oss verify` reported `ok`: one pathway, two atoms, two chokepoints, four checked logs, zero problems.

## Exact local checks and evidence

| Command | Outcome | Preserved evidence |
|---|---|---|
| `python tools/run_checks.py` (global Python, before environment change) | 137 tests, 136 passed, 1 skipped; source/test/tool SHA256 `9f74a4307bc5e14d85bb0041d3753c40d044c39bd3e0b7c4c78796d8d04f8eff` | `runs/checks_oj4fy_oj/` |
| `.venv\Scripts\python.exe -m pip check` | No broken requirements | Local install |
| `.venv\Scripts\python.exe -I -B tools\check_data_readers.py --root data` | 11 files opened; 0 parser problems | `.ocura-oss/logs/atom-c74d6004cc5c4d7e9855afacbda3cf98.stdout.log` |
| `.venv\Scripts\python.exe -I -B tools\check_data_readers.py --root runs\hackathon_environment_20260926\invalid-input` | Expected exit 1 and `failed` for damaged MAT header | `runs/hackathon_environment_20260926/invalid-input/result.json` |
| `.venv\Scripts\python.exe tools\run_checks.py` | 137 tests, 136 passed, 1 skipped; numerical and 3D transport checks passed; source/test/tool SHA256 `d78136a95f0caeb9dc221c6ecff4d8d1a32e44f66f2ff83156b5043657b6095a` | `runs/checks_tvrhqjf8/`; `.ocura-oss/logs/atom-1d7cd91212c545c38a5aedf044c3623f.stdout.log` |
| `.venv\Scripts\ocura-oss.exe verify --root (Get-Location).Path --json` | `ok`, 0 problems | `.ocura-oss/` |

The unchanged reference suite used its built-in synthetic numerical configurations. Its retained 3D transport case used explicit Euler for `dc/dt = D Laplacian(c)` on a 1 x 1 x 1 m domain, no-flux faces, and `D = 0.1 m^2/s`; the balance limit was `1e-12 mol`. The separate decay check used `dc/dt = -0.7 c` from `c(0) = 1` to `T = 1`, with steps from `0.2` down to `0.025`. Exact settings, refinements, and results are in `runs/checks_tvrhqjf8/numerical_checks.json` and `runs/checks_tvrhqjf8/transport_checks.json`.

No measured-data adapter, independent solver comparison, AWS model-endpoint call, or biological validation was exercised by these checks.

The reader tool SHA256 is `dbcce2913cc191a048e67bfebf6ce2daff64ff8c138c707250633b2b2dac84a5`; the pinned requirements file SHA256 is `7f84f9fe3da94dd2f18b2e52f2dd79c9629a0a30d7cc1b45a4ecd9f13e24ca89`. Only Windows 11, CPython 3.12.6, and CPU execution were exercised for this setup.
