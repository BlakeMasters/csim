# Adaptive fidelity as a later, testable research problem

## Present implementation

`lookup_reference_case` verifies that evidence files exist under a permitted root, match their SHA-256 hash, contain finite nonnegative supplied metrics, and match the exact requested execution/case/QoI/unit identifiers. It picks the least recorded cost among matching cases under a requested empirical error tolerance. It returns `reference_case_match` or `unqualified`, and always `biological_qualification = none`.

It is an evidence lookup, not an automatic solver invocation, continuous applicability estimator, learned controller, certified interpolant or novel algorithm. Hashes prove neither the truth of measurements nor the competence of their author; evidence review remains necessary. The lookup does not interpret the artifact's contents as a proof.

## Portfolio rather than universal ladder

Index candidates by mathematical model, representation, parameter domain, observable, numerical tolerance and execution cost. A center-based tumor model and a nuclear finite-element model can answer different questions. The reference hierarchy must be specified per question, not inherited from software brand or mesh size.

The fact that older adaptive hybrid tumor models and recent multifidelity biomechanics exist supports studying this approach. It does not establish novelty or feasibility of this particular online cellular federation. [S11,S12,S13]

## Recommended first experiment

Use offline, fixed-topology component cases. Generate a balanced grid of geometry/loading/parameter regimes and deliberately include difficult cases. Separate reference-data generation, surrogate fitting, policy selection and final evaluation. Freeze one candidate and one error definition before the final holdout. Charge all reference evaluations and fitting work.

Controls should include always using the cheap model, always using the independently converged comparator, a simple fixed rule and the candidate learned/adaptive rule. Give every method the same input observations, allowable outputs and access to cached artifacts. Do not give only the candidate a privileged reference trajectory.

Record QoI error, worst-tail error, false acceptance, abstention/coverage, amount or energy-balance defects, solver failures, time and memory. Report performance both for a fixed query count and over an amortization curve.

## Cost accounting

An illustrative break-even expression is

\[
C_{build}+N(C_{native}+C_{select}+C_{map}+p C_{reference}) < N C_{fixed-reference}.
\]

This is an accounting identity for the stated model, not a speed claim. Expand `C_build` to include data generation and learning; expand per-query cost to include observations, discarded candidates, failed attempts, persistence, loading, inference and warm/cold execution. `p` must be measured on the held-out workload, not assumed. Reference and native paths need equal output rights and comparable stopping conditions.

## Uncertainty and qualification

An expression such as `estimated_error + lambda * uncertainty <= tolerance` is only a heuristic until the estimator, reference target, distribution, coverage and error norm are validated. Evaluate false acceptance under distribution shift. Do not equate a low OOD score, ensemble agreement or large training set with a guaranteed error bound.

Numerical agreement with a teacher leaves the teacher's biological model discrepancy untouched. A finely resolved wrong constitutive model can be less useful than a calibrated coarse model for the intended observable.

## Live switching gates

Only attempt online switching after exact replay, interface mapping and fixed-topology comparison pass. Test lift/restrict round trips, conservation, private-state loss, transient jumps, hysteresis and accumulated error. Keep switching disabled at unmodeled division/rupture/remeshing events. An abstention is preferable to a falsely qualified state.

Novelty requires a separate prior-art comparison and implemented evidence. This package makes no novel-method or general-superiority claim.
