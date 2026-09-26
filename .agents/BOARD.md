# Hackathon work board

Updated: 2026-09-26 18:04 UTC. This is a shared Markdown coordination file. Edit a row when work changes hands, and append a dated evidence note when it finishes. The local Ocura OSS ledger records command executions and verifies their logs; it does not deliver agent messages. Run mutating ledger commands one at a time.

| ID | Work | Status | Owner | Evidence / next action |
|---|---|---|---|---|
| DATA-01 | Check the supplied XLSX and MATLAB files on this machine | Done | Codex | 11 files parsed; [format report](../.ocura-oss/logs/atom-c74d6004cc5c4d7e9855afacbda3cf98.stdout.log), Ocura atom `atom-c74d6004cc5c4d7e9855afacbda3cf98` |
| ENV-01 | Isolate and pin the local reader/ledger environment | Done | Codex | [setup and qualification](../docs/HACKATHON_ENVIRONMENT.md); Windows 11, CPython 3.12.6, CPU |
| TEST-01 | Run the reference checks in that environment | Done | Codex | 137 run, 1 skipped, 0 failures; [log](../.ocura-oss/logs/atom-1d7cd91212c545c38a5aedf044c3623f.stdout.log), Ocura atom `atom-1d7cd91212c545c38a5aedf044c3623f`, [preserved evidence](../runs/checks_tvrhqjf8) |
| DATA-02 | Resolve source identity, units, conditions, missingness, and row keys | Needs source metadata | Unassigned | Keep raw files unchanged. Resolve duplicate headers, one blank cell, nonfinite values and the sequential matrix row-count difference before any fit or join. See [setup and qualification](../docs/HACKATHON_ENVIRONMENT.md). |
| DATA-03 | Define one approved typed ingestion adapter and frozen data split | Waiting on DATA-02 | Unassigned | Follow `B01`, `B02`, `H01`, and `T03` in [the build backlog](../docs/BUILD_BACKLOG.md). Record source-row provenance and observation units. |
| AWS-01 | Qualify an AWS model-endpoint connector for a declared workload | Later | Unassigned | Specify endpoint contract, credentials handling, cost bounds, and a separate integration test before use. No endpoint was exercised here. |

## Completed activity

| UTC date | Event | Ledger / evidence |
|---|---|---|
| 2026-09-26 | Parsed the 3 XLSX and 8 MATLAB v5 files using an isolated local Python environment. | `atom-c74d6004cc5c4d7e9855afacbda3cf98`; `chokepoint-1db75fc676e644a996e645fa02ae1858` |
| 2026-09-26 | Ran the reference suite in the same environment. | `atom-1d7cd91212c545c38a5aedf044c3623f`; `chokepoint-21c0685ba1574cd4b83a83614f199f4c` |
| 2026-09-26 | Verified the local Ocura OSS state: 1 pathway, 2 atoms, 2 chokepoints, 4 logs, 0 problems. | `.ocura-oss/` local state; verification command in [setup and qualification](../docs/HACKATHON_ENVIRONMENT.md) |

Do not place dataset contents, secrets, credentials, or personal data in this board or command labels. Keep failures and their original run IDs; append the resolution as a new entry.
