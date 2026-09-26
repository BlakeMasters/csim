# Evidence inventory

`research_implementation_sources.json` records the 25 September 2026 primary-source,
data-availability and MiMo release inspections. It separates inspected source
revisions from tested dependency pins. Small Murphy workbooks were parsed in
memory; no biological dataset was ingested for training and no external code was
executed. The associated repository baseline is preserved at
`../runs/checks_weh0phac/`. See `../docs/RESEARCH_IMPLEMENTATION_EVALUATION.md` and
`../docs/CELL_MODEL_RL_ENVIRONMENTS.md` for decisions and limitations.

`final_run/` is the preserved initial reference-core execution record: 76 passing tests on Linux/Python 3.13.5. `run_01/` is the earlier 68-test development run. Their fingerprints describe their historical source versions. `legacy_reproduction/` replays the original unmodified archive's known results, not tests against the replacement API.

Current prototype evidence is under `../runs/prototype_rules_checks/`: 137 tests, 136 passed, no failures/errors and one symlink privilege skip on Windows 11/Python 3.12.6/CPU, plus the analytical studies. The newest two regressions concern discovered local-rule state defects; they do not establish broad ML unit coverage. `../runs/response_baseline_first/` contains the fitted synthetic baseline, frozen campaign and grouped test results. `../runs/rule_demo_first/` records the local switch/transfer demonstration and amount balance. See `../docs/PROTOTYPE_REPORT.md` for current commands, hashes and evidence limits.

The earlier `../runs/groundwork_final/` retains its 135-test preparation record, and `../runs/groundwork_training_fixture/` retains its 96 synthetic records and balance reports. Their original account is in `../docs/GROUNDWORK_REPORT.md`. Generated runs are excluded from the release manifest. No historical evidence files were replaced.

`inherited_*` files are preserved metadata from the supplied verification archive. `revision_source_checks.json` records which sources were actually revisited while writing this revision; other literature access claims are inherited, not new full-text checks. `revision_claim_matrix.*` maps the 26 audited claims to new decisions, and `regression_traceability.json` maps the 12 audited failures to new API tests.

`schema_validation.json` concerns only two provisional JSON shape contracts. No entry in this directory is biological validation, clinical qualification or execution of an external specialist engine. Full raw historical artifacts are under `../provenance/`.
