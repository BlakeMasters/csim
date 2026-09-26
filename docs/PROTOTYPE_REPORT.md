# Local response and rules prototype: execution record

Date: **25 September 2026, America/Los_Angeles**. This milestone implements the
requested baseline learning workflow and a small biological-hypothesis rules
layer that can run on the current device. All execution was on **Windows 11
10.0.26200, Python 3.12.6, 64-bit AMD64, CPU**, using the standard library.
No external engine, biological dataset, patient data, pretrained model or new
package installation was used.

## Delivered code and prose

| File | Implemented scope |
|---|---|
| `src/cellsim_v2/physical_dataset.py` | Strict synthetic JSONL ingestion, declaration/row agreement, complete sample coverage, numeric/unit checks and repeated file-integrity checks |
| `src/cellsim_v2/response.py` | Training-only range scaling, deterministic KNN increment baselines, no-change/mean controls, explicit same-law positive control and JSON artifact validation |
| `tools/train_response_baseline.py` | Fresh generation, fitting, validation selection, complete candidate freeze, final one-step evaluation, grouped metrics and costs |
| `src/cellsim_v2/biological_rules.py` | Typed JSON hypotheses, readiness checks, hysteresis switches, gates, paired transfers and accepted-event continuation identity |
| `tools/run_rule_demo.py` | Synthetic local scenario, signed reservoir ledger, decision traces, artifact/source identity and retained failure records |
| `tests/test_biological_rules.py` | Two targeted regressions added before repairing reviewed history defects |
| New configs and guides | Synthetic rules, unresolved oxygen template, baseline neighbor config, `PROJECT_DIRECTION.md`, `BIOLOGICAL_RULES.md`, and `BASELINE_PROTOTYPE.md` |

README, architecture, setup, status, limitations, operations and backlog now
describe the current executable prototype and the remaining biological work.
The earlier [GROUNDWORK_REPORT.md](GROUNDWORK_REPORT.md) remains a historical
record of the transport/data foundation.

## Commands and retained outcomes

Commands ran from the project root. The targeted unittest commands used an
absolute `src` path in the child process's `PYTHONPATH`; output was captured in
the named directories before the corresponding code fix.

| Exact command | Evidence directory / result |
|---|---|
| `python tools/run_checks.py` | `runs/checks_qvf5cpk1`: starting 135 tests, 134 passed, one skip |
| `python -m unittest discover -s tests -p test_biological_rules.py -v` | `runs/rule_namespace_red`: one error; delimiter-bearing IDs shared a prefix |
| `python -m unittest discover -s tests -p test_biological_rules.py -v` | `runs/rule_identity_red`: one pass/one failure; edited rules silently changed continuation identity |
| `python tools/train_response_baseline.py --output runs/response_baseline_first` | Completed; `knn_k5` selected on validation, frozen before final scoring |
| `python tools/run_rule_demo.py --output runs/rule_demo_first` | Completed five intervals with accepted switch memory and paired transfers |
| `python tools/run_rule_demo.py --inspect configs/biological_rules.oxygen.template.json` | Reported nonrunnable with nine unresolved/declaration issues |
| `python tools/run_checks.py --output runs/prototype_rules_checks` | **137 tests, 136 passed, zero failures/errors, one skipped**; numerical checks passed |
| `python tools/run_rule_demo.py --rules configs/biological_rules.oxygen.template.json --output runs/rules_unresolved_attempt` | Expected exit 1; unresolved rules refused, requested configuration and failure report retained |

The skip is actual Windows symlink creation privilege; existing mocked
root-confinement coverage remains. The source/test/tool identity for the completed
learning run, rule run, refusal record and final suite is:

```text
9f74a4307bc5e14d85bb0041d3753c40d044c39bd3e0b7c4c78796d8d04f8eff
```

The aggregate suite includes existing reference, transport, dataset, campaign
and exporter checks plus two new rule-history regressions. It does not supply
dedicated unit coverage of the new physical loader, learner or baseline runner.
Those paths have completed the recorded example and received code review.
The fresh-interpreter equality result belongs to the existing numerical demo,
not to a claimed new-model or new-rule restart experiment.

## Learning configuration and result

The exporter used the unchanged example: 4×3×2 voxels of width 0.25 m,
diffusivity 0.01 m²/s, dt 0.05 s, eight steps per condition, and two cells with
synthetic uptake parameters. There were three training conditions, one validation
condition and two final conditions, yielding 48/16/32 rows.

The fit used concentration, Vmax, Km and interval as features; scaling used only
training rows. Candidate k values were 1/3/5. Validation selection minimized the
unweighted mean of per-condition endpoint MAEs, with a fixed simple-control-first
tie order. `knn_k5` won with validation MAE `2.02854790405648e-6 mol`.

| Frozen final model/control | MAE on 32 test rows, mol |
|---|---:|
| Selected five-neighbor increment model | 3.481890319790012e-6 |
| Training-mean increment | 1.4236986941550072e-5 |
| No change | 4.288904167319916e-5 |
| Exact synthetic generator law | 0 |

All 32 test rows were outside at least one training feature range. These flags
are diagnostics. They supply neither calibrated uncertainty nor a general
extrapolation result. The exact-law control uses the label-generating equation;
it is excluded from selection and supplies no independent verification.

The model bundle and preprocessing were reloaded from their frozen JSON files.
Campaign verification succeeded before and after final scoring. The campaign
digest retained during the run was:

```text
8250d2f2c2c66233afe15c9474dba657f859536f789c686c8d0cc58899de5d90
```

Physical manifest digest:
`cf76d5075742cceeaf29c006359592068ec95a8a91ef2939933b7b2b73a44ce9`.
Rebased campaign manifest digest:
`7ceba8b3b8ce7634bce64b24593d687792b1b977bd6083206fda42b4f6f42686`.
They differ because artifact and sample paths have different relative roots.

## Rule configuration and result

The scenario used one 1 m³ voxel, one synthetic cell of volume 0.001 m³, and
five 0.1 s intervals. Reservoir concentrations were prescribed as
`0.4, 0.65, 0.9, 0.65, 0.4 mol/m³`, with every replacement paired to a signed
boundary-ledger amount. The low-signal switch entered at or below 0.5 mol/m³
and left at or above 0.8 mol/m³. Transfer used Vmax 0.01 mol/s and Km 0.5 mol/m³
only while that switch was off. Every number is an engineering fixture value.

Accepted switch states were `on, on, off, off, on`. The final cell amount was
`0.001208074534161491 mol`. Recorded interval and total balance residuals were
`0.0 mol` in this execution. Four events comprise one ruleset binding and three
switch transitions. No growth, oxygen metabolism, viability or differentiation
was modeled. The oxygen template's biological quantities stayed null.

Canonical ruleset digest:
`9d73dea5e05740b3272e5b154a8d3fc5470dcf8e25f01779f793f2decceb795c`.
The interpreter rejects continuation if the complete ruleset changes for a cell
with an accepted binding. It has no migration layer between model versions.

## File identities and cost scope

| Artifact | SHA-256 |
|---|---|
| Final suite results | `4705b3d79b65ba4f76ca84b838570ebcc3492c109351e7eb37ae2c4b937711c7` |
| Model bundle | `81fb83f00eef9b8a35d9d5688dd5fe1a790eb7fa4cc54fc9a72b482abec3fbba` |
| Preprocessing | `8de83478a5f4a023118dad7851855885bb847cdb9fbaeacd0bbb1fc260f24406` |
| Final response evaluation | `d46019066b4debebb392556ea5113088964166ebb9faff2459c2f74475c7df67` |
| Rule demonstration results | `167b38226d2cd7d92fe0ae583494472bc4f38407ef75d3a8f6e60d7b9a84f08e` |
| Unresolved-rule failure results | `0647fbccea37fe09e9b18f49d69fbedd20858128524d8e377d96fe0e7130091a` |

The response runner recorded 0.40752969999448396 s before its final report write,
including generation, fitting, selection, artifact verification and final scoring.
Nested fixture timings overlap preparation and must not be added again. The rule
demo recorded 0.15283999999519438 s, including its repeated trace/step evaluation.
Timers exclude imports/startup, output-directory creation and final report writes.
These are single tiny runs on this host, without a throughput or savings claim.
Development, research and prior check runs are separate work; the phase timers
are not a complete project-cost ledger. Failed attempt records remain preserved.

## Remaining work

The deliverable is a local prototype for explicit rules and synthetic response
learning. Broader rule/ML regressions, independent transport comparison,
coupling/interval refinement, authenticated observations, parameter uncertainty,
functional biological validation and real-data model baselines remain open.
Shared foundation models, subject adapters, immune mechanisms, self-play and RLCD
remain downstream research. All biological qualification fields remain unqualified.

The workspace has no Git repository metadata. Source, test and tool hashes plus
the root package manifest identify the work. Original ZIPs/audit artifacts remain
preserved. Generated runs are retained outside the package manifest. Final
manifest verification uses `python tools/check_manifest.py`; its output is saved
in `runs/prototype_closeout/manifest.log` after documentation closeout.
