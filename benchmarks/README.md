# Benchmark status

`campaign.json` distinguishes the three executable numerical fixtures from proposed independent-solver, biological, coupling and fidelity campaigns. Commands are null for unimplemented campaigns.

Run `python tools/numerical_checks.py`. Results are also captured by `tools/run_checks.py` under its output directory. The study equations and assumptions are in `../docs/NUMERICAL_CONTRACTS.md`.

The decay test uses forward Euler at decreasing timesteps. The periodic diffusion study reduces spatial spacing and timestep jointly. The steady radial finite-volume solve uses increasing shell counts. Reported orders are empirical behavior on these examples, not a theorem about general domains. Fixture tolerances are engineering limits for synthetic tests, not biological uncertainty.

No benchmark here uses realistic cancer-cell parameter estimates. The analytic sphere has constant uptake, fixed geometry, and a surface Dirichlet concentration; it has no growth, vasculature, intracellular biology or necrosis law. Rejecting negative concentration is not a hypoxia model.

For a new benchmark, record equations, exact or independently verified reference, parameter units and provenance, boundary/initial conditions, refinement sequence, quantities/norms, numerical tolerance justification, source revision, measured costs and observed failures. Do not add a `passed` biological status without independent data and an immutable split.
