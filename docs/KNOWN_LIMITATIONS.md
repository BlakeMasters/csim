# Known limitations and nonclaims

## Reference runtime

The implementation is small, serial Python. Pair mechanics is all-pairs and state transactions deep-copy the object graph. It is an executable contract, not a production scaling solution. There is no spatial neighbor engine, concurrent update, MPI implementation or acceleration backend.

The time stepper uses sequential Lie splitting and per-process subcycling over synchronization windows. It has no stiff implicit solve, event root localization, independent asynchronous clocks, interpolation between asynchronous states or adaptive error controller. Off-grid caller segmentation may change the step partition. Private process side effects are not rolled back; current processes must be pure.

Write categories are coarse (`cells`, `fields`, `ledger`, `events`), and reads are not capability-controlled. This does not protect against malicious or side-effecting Python. The amount ledger verifies declared accounting, not the truth of a declared sink/reaction or biological plausibility.

## Physical and biological assumptions

Cell geometry is spherical volume and a center. Contact is a linear overlap spring with overdamped Euler motion. There is no nucleus, membrane, adhesion, tissue constitutive calibration, fluid, ECM, vasculature, metabolic network or immune-cell behavior. Coincident centers are explicitly unsupported.

Division is finite-volume/amount bookkeeping with a retained storage slot. There is no nutrient cost, cell-cycle rule, membrane formation, force-balanced post-division placement, death, phagocytosis or physical lineage reconstruction. A configurable symmetric separation is not a biological division law.

Fields are arrays of amounts and volumes. The historical periodic solver supports a uniform 1D grid; the radial solver is a fixed steady sphere with constant uptake. The new 3D solver supports fixed orthogonal rectilinear grids, scalar constant isotropic diffusivity and nonnegative inward flux on entire exterior faces. It has no outward flux boundary, advection, heterogeneous diffusivity or moving mesh. Cell uptake uses one voxel sample and transfers the same species; it does not implement metabolism. Cells do not displace extracellular volume. There is no general reaction stoichiometry, pH, pharmacokinetics, hypoxic adaptation or necrosis model.

The local-rule interpreter supports declarative concentration switches with hysteresis and optional gating of conservative same-species transfer. Switch state and rule identity persist through accepted world events. This is discrete rule infrastructure with synthetic execution evidence; it does not implement a biological HIF pathway, viable/dead state law or uncertainty model. Biological oxygen thresholds, transfer parameters and cell context remain unset in the nonrunnable template. Provenance declarations are not experimental authentication.

## Evidence and uncertainty

The evidence function verifies file existence, content hash, finite supplied metrics and exact identifiers. It does not read the artifact as a mathematical certificate, authenticate a reviewer, validate the reported error, generalize to unseen states or execute a fallback solver. Every result explicitly denies biological qualification.

Empirical convergence on the historical fixtures and new smooth 3D cosine modes does not establish global accuracy, order on nonsmooth problems or robustness through topology changes. No independent external solver comparison has run. The regression suite targets known risks; it is not a random sample of all possible defects and not formal verification. Intermediate and final test records have different fingerprints and must not be conflated.

General training contracts validate grouping declarations and artifact hashes. A separate strict loader now checks the synthetic physical JSONL payload against every declared sample, and a small nearest-neighbor response baseline fits training-only scaling and increments. It was selected on validation conditions and evaluated after freeze on two synthetic test conditions. No general observation-array ingestion, biological authentication, experimental-unit inference, AnnData/STATE adapter or gene-expression-to-physical-rate mapping exists.

The response evaluation is teacher-forced and one step: observed current inputs are supplied for every prediction. Endpoints are not conservative `Update` proposals, and no learned rollout or effect estimate was evaluated. All 32 test rows were outside at least one fitted feature range; that diagnostic is not an error bound. The zero-error positive control repeats the exact synthetic generator law and was excluded from candidate selection. The result does not establish biological generalization, confidence coverage or cost superiority.

Campaign change detection requires a separately retained trusted digest and stable files during evaluation; it is not filesystem immutability or access control. A shared JSONL artifact is parsed in full for integrity checks even when only development rows are returned. Two new targeted regressions cover discovered rule namespace and continuation-identity defects. The baseline run and those regressions do not establish broad unit coverage for the new loader, learner or rule interpreter. See `PROTOTYPE_REPORT.md` for the current evidence scope.

## Persistence and portability

JSON checkpoints are limited to small worlds, a standard-library RNG, and caller-provided JSON private data. No solver-private adapter state is reconstructed. Fingerprint construction is the caller's responsibility; fixture labels alone are not cryptographic execution identity. File replacement provides no cross-host/distributed transaction or guarantee against power loss on every filesystem.

The original core has historical Linux/Python 3.13.5 evidence. Current groundwork and prototype execution used Windows 11/Python 3.12.6/CPU; the new files have not been exercised on Linux. Intended Python 3.10+ compatibility is not a tested matrix. A separate historical optional schema check used `jsonschema` 4.26.0. No GPU, macOS, numerical-library or specialist-engine configuration was tested. Actual symlink creation in one Windows test is skipped because the current token lacks that privilege; path resolution confinement has a separate mocked regression.

## Research and deployment

No biological data acquisition, calibration, experimental holdout, clinical evaluation, cost superiority, million-cell scaling, or novelty result is claimed. Backend candidates and dataset/protocol templates are plans, not capabilities. The package is not FDA/ASME approval, not an SBML/SED-ML execution engine and not OMEX conformance.

The next improvements should be chosen from the build gates, not by removing these limitations from the document before the corresponding evidence exists.
