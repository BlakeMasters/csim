# Preserved inputs

The two supplied archives, original checksum file and supplied verification report are byte-identical to their mounted inputs. `inputs.json` records their SHA-256 digests and sizes. Historical files inside an old ZIP are intentionally unchanged; the new runtime does not import or execute them.

To reproduce the old audit separately, extract `cellular_architecture_verification.zip` into a new directory and run its `reproduce.py --expect-known-findings`. Its normal mode exits nonzero because the original acceptance requirements fail. Reproducing a known failure does not constitute fixing it.

The new package uses `cellsim_v2`, with explicit amount and scheduling semantics. See `../docs/MIGRATION.md` and `../docs/TRACEABILITY.md`. Never overwrite these inputs with a revised build.

`initial_build_MANIFEST.sha256` preserves the manifest from before the infrastructure groundwork. The root `MANIFEST.sha256` describes the current release files; generated runs and caches are excluded. Historical audit artifacts and execution records retain their original content and scope.
