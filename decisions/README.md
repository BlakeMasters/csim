# Architecture decisions

These are accepted design choices for this revision, not experimentally established universal rules.

| Decision | Choice | Rejected alternative | Evidence needed to revisit |
|---|---|---|---|
| D01 | Backend-independent shared state plus private state | Treat a single dataclass as complete biological state | Demonstrated lossless projection/closure for a restricted problem |
| D02 | Authoritative amounts and volumes in SI | Ambiguous normalized “concentration” dictionaries | Explicit alternative unit model with conversion and balance tests |
| D03 | Small pure reference processes with atomic window commits | General mutable asynchronous process graph from the beginning | Complete state/clock/event/rollback protocol and convergence |
| D04 | Offline comparator before live integration | Federate three solvers before checking individual equations | Standalone matched cases plus interface justification |
| D05 | Observable-specific model portfolio | Fixed coarse-to-fine biological realism ranking | Empirical monotonic suitability for a declared observable/domain |
| D06 | Exact-case evidence lookup only in this release | Default confidence/strain threshold that declares qualification | Held-out error and coverage results, explicit domain/failure handling |
| D07 | Oxygen perturbation as first biological target | Full vascularized microtumor as first proof | A narrower context with stronger obtainable data and simpler confounding |
| D08 | Explicitly nonrunnable future manifests | Adapter stubs appearing as supported integrations | Actual source/build and passing independent tests |

Any change to these choices should cite the affected contract, new evidence, migration impact and test results. The old sources are available in `../provenance/`, and current literature scope is indexed in `../docs/SOURCES.md`.
