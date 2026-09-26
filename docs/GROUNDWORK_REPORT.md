# Infrastructure groundwork: execution and scope

Date: **2026-09-25, America/Los_Angeles**. Work implements the requested foundation
for physical cell-response and gene-expression model development. Only the
physical synthetic fixture is generated. Both modalities can declare datasets
through the common contract; no model is trained and no biological data are used.

## Delivered changes

- `src/cellsim_v2/transport.py`: fixed orthogonal 3D geometry, unequal volumes,
  conservative explicit diffusion, typed inward boundary influx, simultaneous
  saturable cell uptake, collective-demand rejection, and pure `Update` proposals.
- `src/cellsim_v2/training.py`: strict JSON dataset declarations, artifact hashes,
  disjoint experimental-unit/trajectory splits, optional extra holdout dimensions,
  feature ordering and pairing semantics, and create-only evaluation snapshots
  verified against an independently retained digest.
- `tools/prepare_training_fixture.py`: reproducible synthetic trajectories,
  configuration/source identity, predefined splits, amount accounting, timings,
  and preserved partial/failed attempts.
- `tools/training_manifest.py`: validation, freeze and verification CLI. Model
  artifact bytes are hashed, never loaded as executable model code.
- `tools/transport_checks.py`: separate spatial-operator and temporal studies
  plus complete 3D continuum-trajectory refinement, integrated into `run_checks`.
- New targeted tests and revised status/backlog/setup/research documentation.

`README.md` links the runnable guide in `TRAINING_SETUP.md`. Web-inspected primary
sources and documentation, their access depths, and design inferences are in
`VIRTUAL_CELL_RESEARCH.md`. Later self-play/RLCD analysis is documentation only.
`DOWNSTREAM_LEARNING_PLAN.md` incorporates the user's cell-reprogramming and
personalization direction, including proposed response/adapter interfaces and
separate vaccine/CAR-T evidence requirements. It adds no trained capability.

## Executed commands and environment

All commands below ran from the project root, on **Windows 11
10.0.26200, Python 3.12.6 (64-bit AMD64), CPU**, without installing dependencies.
The baseline started at 2026-09-26 03:14:35 UTC; the final check record is timestamped
2026-09-26 03:26:33 UTC (September 25 Pacific local date).

```powershell
python tools/run_checks.py
python tools/run_checks.py --output runs/groundwork_first_integrated
python tools/run_checks.py --output runs/groundwork_final
python tools/prepare_training_fixture.py --output runs/groundwork_training_fixture --config configs/training_fixture.example.json
python tools/training_manifest.py validate --manifest runs/groundwork_training_fixture/manifest.json
```

Baseline `runs/checks_jame_u7r`: 76/76 pass, with initial source/test/tool SHA-256
`1f8d8f4af477cafe0d427264c0212902e04da4437d386a7845a4c9784b51e5a5`.

Final `runs/groundwork_final`: **135 tests, 134 pass, zero failures/errors,
one skipped**. The skipped real-symlink test lacks Windows creation privilege;
resolved-path escape is separately covered using a mock. Original numerical
checks, 3D numerical checks, and fresh-interpreter demo equality all passed.

Final source/test/tool SHA-256:

```text
d70ef5c3bcf7a2f148b78f83d6f9a4207a2cf589cc0437dd8a2172a4bb742243
```

The fingerprint covers sorted relative names and bytes of all `src/**/*.py`,
`tests/*.py`, and `tools/*.py`, as implemented by the runner. Configuration identity
is separately included in the fixture execution fingerprint. Documentation-only
closeout does not alter the source/test/tool fingerprint. The root file manifest
covers the current package contents; generated runs are retained separately.

## Numerical configuration and observed results

The 3D study solves `dc/dt = 0.1 * Laplacian(c)` on a 1 m cube with six impermeable
faces. Initial concentration is the exact voxel average of
`1 + 0.25 cos(pi*x) cos(pi*y) cos(pi*z)` mol/m³. These are synthetic engineering
parameters, without a biological interpretation.

| Study | Configuration | Observed orders | Finest error |
|---|---|---|---|
| Spatial operator | 4³, 8³, 16³ voxels; derivative probe dt 0.001 s | 1.8938, 1.9735 | 8.3568549e-04 mol/(m³ s), L2 |
| Time | Fixed 4³ grid; T 0.2 s; 4, 8, 16, 32 steps; exact semidiscrete reference | 1.0577, 1.0277, 1.0136 | 2.3248142e-04 mol/m³, L2 |
| Full trajectory | T 0.05 s; 4³/8³/16³; 5/17/65 explicit steps | 2.0284, 2.0168 | 2.3311468e-05 mol/m³, L2 |

All recorded total-amount errors in these 3D mode studies were 0.0 in the executed
floating-point outputs. The engineering amount limit was 1e-12 mol. Full-trajectory
dx and dt are refined jointly. This does not prove order on arbitrary meshes,
coupled uptake accuracy, or independent-solver agreement. Historical 1D/radial/decay
studies remain in the adjacent `numerical_checks.json`.

## Generated training fixture

`runs/groundwork_training_fixture` contains a 4×3×2 grid with 0.25 m widths,
D = 0.01 m²/s, dt = 0.05 s, eight windows, and two point-sampled cells. One
synthetic uptake law is applied before diffusion. The config supplies all
parameters and inward-flux schedules. Cell volume does not displace field volume.

There are six condition/trajectory groups: three train, one validation and two
test, yielding **48/16/32 rows**, respectively, and **96 rows total**. The same
trajectory's cells and frames stay together. Conditions are frozen in config
before generation. Records contain pre-step inputs and next-step intracellular
amount; no future target is supplied as an input.

The manifest validation command succeeded. The largest final-trajectory ledger
residual was **4.4885969940899884e-17 mol**, below its recorded tolerance. No model
was trained or evaluated. Timing categories and their exact coverage are in
`results.json`; these tiny fixtures establish no performance or savings claim.

| Identity | SHA-256 |
|---|---|
| Fixture execution (source/config/environment) | `da367c61d422732c83d5b2e149c3cd6d693ab68b89f4bdc97ad844389133d7f3` |
| Dataset canonical manifest digest | `384e904660087686e25d250927a3dc6c80f793998803ec3bfd58fffcc99e947e` |
| Manifest file bytes | `807c0dce88df9de8708792fd14290e32f43902101c05ece71de7a93089248cb3` |
| Sample JSONL file bytes | `49d48e9a6c29dcfd8afa962f5809e6836f3886237e559903b9e88990480b1cf` |
| Final check results file | `fb87118a3dfb1b6e00d31bfadf96d48b422c7da36012f3dade1798bd04df6209` |
| 3D study report file | `dfc58df897e5eef396cbe1fbd0c1020fdb55b5aa90057be3035ec951e43ee182` |

The canonical dataset digest and manifest-file digest differ because canonical
content hashing and formatted JSON file bytes are different encodings.

## Preserved failures and reviews

Tests were added before new modules and before fixing review defects. Initial
missing-module probes, development runs and actual failing regressions remain:

| Directory under `runs/` | Evidence |
|---|---|
| `groundwork_fixture_red` | Initial exporter regression before implementation |
| `training_contract_red_35ukksko` | Initial dataset/campaign tests before implementation |
| `transport_red_kl50b89w` | Initial transport tests before implementation |
| `training_cli_red_8_pwhd6y` | CLI workflow before implementation |
| `transport_review_red_mndeu92f` | Decimal-grid CFL roundoff and large-origin geometry regressions |
| `transport_underflow_red_3sscrw93` | Uptake underflow regression |
| `transport_flux_red_bxtxqh1v` | Internal/boundary flux underflow regression |
| `review_training_failure_38734be09a34` | Malformed CLI config losing its failure record |
| `groundwork_config_red` | Regression for that missing failure artifact |
| `groundwork_first_integrated` | Earlier 126-test combined development run |
| `groundwork_final` | Current 135-test run with final source fingerprint |

Final code reserves a floating-point margin for explicit diffusion, rejects
unresolved coordinates and detected positive-to-zero underflows, and retains raw
malformed configuration bytes. It does not clip amounts or alter geometry.
Intermediate metadata for `training_contract_final_vnu9pf9r` records a reporting
serialization error after the test run and its recovery; current combined results
were produced independently by `run_checks.py`.

## Remaining gates

N01/N02 and C01-C03 are partial reference milestones. Independent comparison,
stiffness/splitting studies, general ownership, solver-private replay, biological
data ingestion/authentication, calibrated response laws and actual model training
remain open. No external dependency/version was selected or pinned. The new code
has only Windows/Python 3.12.6 CPU execution evidence; historical Linux results
apply to the initial package.

The folder has no Git repository metadata; no branch or commit was created. The
original archives and inherited audit are retained. The original package manifest
was copied to `provenance/initial_build_MANIFEST.sha256` before regenerating the
working package manifest. Self-play and RLCD remain proposed downstream research,
with no policy, reward model, foundation model, or RL training run added.

## Documentation closeout

After documentation/configuration updates, source/test/tool hashing still matched
the final run above. All four inherited input hashes matched `provenance/inputs.json`;
the saved initial manifest matched the root manifest before replacement. No further
source edits were made. The full suite was not rerun for documentation closeout.

The current manifest is rebuilt from sorted package files, excluding `runs/`,
cache directories, bytecode and the root manifest itself. Final file-integrity
verification command:

```powershell
python tools/check_manifest.py
```

Its captured output is retained in `runs/groundwork_closeout/manifest.log`.
File integrity and the earlier numerical checks carry their respective scopes;
neither establishes experimental calibration or biological validity.
