# Numerical contracts and conditional mathematics

These are specified requirements and small derivations, not a theorem establishing general tumor-simulation accuracy. The delivered implementation is intentionally restricted to smooth, small reference problems and explicit bookkeeping operations.

## 1. Time intervals and accepted state

A call advancing from `t` to `T` integrates exactly over `[t,T]`. `T=t` is a no-op; `T<t` is invalid. Each continuous update receives its actual interval duration, including a shortened terminal interval. A final observation must not trigger an extra full integration step.

`WindowStepper` uses rational scheduling times and floating-point numerical updates. It partitions a call into windows bounded by `max_window_s`. In each window, processes run in the supplied order, each with internal substeps no larger than its own `max_step_s`. This is a sequential Lie-split construction. It is not an autonomous multirate event engine, a simultaneous solve, or a second-order Strang integrator.

For two noncommuting operators, splitting error must be studied by refining the synchronization window as well as each solver's timestep. Repeating an operator with smaller internal steps does not remove the error from freezing/ordering other processes. Restart equality is tested at **aligned synchronization boundaries**. Splitting a caller request at an off-grid point can change the numerical step partition and is not promised to yield an identical trajectory.

A whole synchronization window is tentative. A failure discards changes to shared state made in that window; already accepted previous windows remain. Python function side effects and privately mutated solver objects are outside this transaction. Current process functions must be pure and cannot perform irreversible I/O or consume hidden RNG state.

## 2. Atomic updates

`Update` contains full object replacements, births, removals, ledger entries and events. It preflights a clone, validates fields/identifiers/amounts, checks broad write categories and species balances, and only then publishes the candidate state. Invalid replacement IDs, negative amounts, duplicate births or missing balance entries leave the original world unchanged.

Atomicity is single-threaded and process-local, not a concurrent or distributed transaction. Retained Python references to old subobjects become stale after commit. Read authorization is not enforced; write categories are coarse. This is not a security sandbox.

## 3. Pair mechanics

The reference law is an overdamped pair spring:

\[
F_{ij}=k\max(0,R_i+R_j-d_{ij})\frac{x_i-x_j}{d_{ij}},
\qquad F_{ji}=-F_{ij},
\]

\[
x_i^{n+1}=x_i^n+hF_i/\gamma_i.
\]

The kernel accumulates all pair contributions from the same frozen positions and uses a sorted pair order. For an isolated pair with equal drag, the midpoint is invariant. With unequal fixed drags, the drag-weighted center is invariant under this pair-only update. Neither statement extends automatically to active force, external drag or moving boundaries.

Coincident centers have an undefined normal and are rejected. Large explicit steps can overshoot or destabilize relaxation; no global mechanics stability controller is implemented. The spring law has not been calibrated against cell mechanics. It does not resolve membranes, nuclei or incompressibility.

## 4. Division bookkeeping

The demonstration retains one storage slot and creates another; it records an explicit division event, unique event sequence and new slot ID. In the absence of growth, both daughters together preserve pre-event volume and tracked amounts. Equal daughters are placed symmetrically along an explicitly chosen axis. Amounts are split as `left = total/2`, `right = total-left` to make the accounting explicit.

This is not a physical cytokinesis model or full lineage ontology. The retained slot is not an immortal biological parent: the event identifies the pre-split state. Zero separation is allowed for bookkeeping but cannot be passed to the contact kernel. A production implementation must either perform geometry remodeling or specify a physically justified post-division placement and relaxation procedure.

## 5. Amount, concentration and reactions

For fields with molar concentration `c_vk` and volume `V_v`, and cell amounts `n_ik`,

\[
M_k=\sum_v V_vc_{vk}+\sum_i n_{ik}.
\]

The raw sum of concentrations is not material amount. For volumes `(1,9)` and concentrations `(1,1)`, the amount is `10`; for `(0.5,1.5)` it is `14` although the concentration sums are both `2`.

The committed residual is

\[
r_k=M_k^{after}-M_k^{before}-\Delta M_k^{declared}.
\]

`absolute_error_mol = |r_k|`; `signed_residual_mol = r_k`. A sink/source/boundary/reaction entry explicitly records net change. Internal exchange has zero net change and needs no external sink. A ledger can faithfully record a wrong biological law; passing the ledger is not evidence for that law.

For a reaction network `dn/dt = N v(n)`, an actually conserved linear combination obeys `ell^T N = 0`. The reference code does not implement stoichiometric/nullspace checks. Per-species ledger balance and elemental or moiety conservation are separate requirements for the next chemistry module.

## 6. Reference finite-volume checks

The periodic diffusion kernel transfers one paired amount per face:

\[
\Delta n_{i\to j}=h\,DA(c_i-c_j)/\Delta x.
\]

It uses equal `V=A*dx`, a periodic 1D domain and forward Euler. For this stencil, the nonnegative-weight condition is `D h/dx^2 <= 1/2`. Inputs violating it are rejected; negative results are not silently clipped. General meshes, anisotropic diffusion and advection need separate conditions.

The exact periodic mode is

\[
c(x,t)=1+0.25e^{-4\pi^2Dt}\sin(2\pi x).
\]

The included refinement study reduces `dx` and chooses `dt` proportional to `dx^2`. It therefore checks combined spatial/temporal behavior, not an isolated proof of spatial order. The decay fixture independently checks first-order time integration against an exact exponential.

The steady sphere fixture solves

\[
D\nabla^2c-q=0,\quad c(R)=c_b,\quad c'(0)=0,
\]

with shell finite volumes. Its exact solution is

\[
c(r)=c_b-\frac{q}{6D}(R^2-r^2).
\]

The constant-uptake regime requires `c_b - q R^2/(6D) >= 0`. The code rejects a negative-center analytic regime instead of interpreting negative oxygen as hypoxia. It has fixed geometry, constant uptake, and no cellular response. The tested values are synthetic numerical inputs, not biological measurements.

### Fixed 3D transport and cell transfer

`RectilinearGrid3D` stores positive finite axis widths and immutable voxel geometry, with x varying fastest. `AmountField.volumes_m3` must match its voxel volumes exactly. Represented edge widths, half-widths and adjacent center distances must agree with nominal lengths within relative `1e-12`, with zero absolute tolerance. Distorted geometry is rejected. Exact internal edges map to the voxel on their positive side; the maximum exterior edge maps to the final voxel.

For each internal face, scalar constant diffusivity gives conductance `g_ij = D*A_ij/d_ij` in m³/s and paired amount `h*g_ij*(n_i/V_i - n_j/V_j)`. The real-arithmetic explicit positivity condition is `h <= min_i V_i/sum_j g_ij`. `diffusion_timestep_limit_s` sums the same per-face conductances used in transfers, reserves a `32*sys.float_info.epsilon` relative margin, and rounds the bound toward zero. This margin addresses ordinary floating-point roundoff; unsupported arithmetic and negative results still reject without clipping.

Exterior faces default to no flux. `BoundaryFlux` supplies a nonnegative inward density in mol/(m² s) uniformly over one exterior axis face. Its integrated additions have matching boundary ledger entries. Outward flux, Dirichlet boundaries, spatially varying diffusivity, advection and moving geometry are unsupported by this 3D kernel.

`CellUptake` specifies `vmax` in mol/s per cell and positive `Km` in mol/m³. Every requested transfer uses the same pre-step voxel concentration and amount `h*vmax*c/(Km+c)`. The field debit credits the same species inside the cell. Collective demand above available voxel amount rejects the entire proposal; the implementation does not clip or allocate scarcity. Cells sample their containing voxel; they do not displace extracellular grid volume. This transfer does not model consumption, reaction stoichiometry or biological oxygen physiology.

Both processes are pure `Update` proposals. The existing ordered stepper supplies shared-state rollback for a rejected window. Nonzero concentrations, diffusion transfers, inward boundary additions, uptake saturation, rates or integrated amounts that underflow to zero are rejected where detected. A computed overflow or negative amount also rejects. These checks do not promise arbitrary-magnitude floating-point accuracy.

`tools/transport_checks.py` separately studies the spatial diffusion operator, Euler time error against a semidiscrete cosine mode, and joint refinement against continuous closed-cube voxel averages. Unequal-volume invariants, uptake, roundoff and failure injection have targeted regressions. Coupled uptake/splitting refinement and an independent numerical solver remain open.

## 7. Representation sufficiency and transfer

Let `R` project a detailed state `y` to shared state `x`. If `R(y1)=R(y2)` but `R(Phi_h(y1)) != R(Phi_h(y2))`, no deterministic coarse update on `x` alone can reproduce both futures. This is a direct contradiction: the same input would need two outputs. Retain history/private state or introduce a measured closure, rather than hiding it in a universal schema claim.

Full state transfer has the form `x_next=L(Phi_h(R(x)))`. Partial replacement can be written `x_next=x+P[L(Phi_h(R(x)))-x]` only for compatible representations and an explicit component selection `P`. A state and an increment are different API types. The invalid expression `x+L(S(R(x)))` doubles the state when all maps are identity.

For displacement interpolation `u_f=H u_c`, choosing nodal force transfer `f_c=H^T f_f` preserves discrete virtual work:

\[
f_c^T\delta u_c=f_f^TH\delta u_c=f_f^T\delta u_f.
\]

Tractions and continuum fields require appropriate quadrature/mass weights. This identity does not guarantee positivity, torque conservation, contact consistency or stable nonlinear coupling. preCICE's conservative mapping means a declared global-sum property, not all of these properties simultaneously. [S07]

## 8. Predictive error and fidelity limits

The surrogate/reference/observation triangle inequality is

\[
|\hat q-y|\le|\hat q-q_H|+|q_H-y|.
\]

A teacher imitation error controls only the first term. Specialist software and mesh detail do not remove the second.

Under aligned state representations and a Lipschitz reference update,

\[
e_{n+1}\le L e_n+\eta_n+\sigma_n
\]

implies

\[
e_N\le L^N e_0+\sum_{n=0}^{N-1}L^{N-1-n}(\eta_n+\sigma_n).
\]

Here `eta` is local approximation error and `sigma` is representation/switching error. These assumptions can fail across division, rupture, changing contacts or other discontinuities. No empirical threshold in this package establishes the bound's assumptions.

Numerical, parameter, model, coupling, surrogate, stochastic and observation errors need not be independent or separately identifiable. Summing estimated standard deviations or calling an OOD score an error bound is not justified without an explicit statistical model.
