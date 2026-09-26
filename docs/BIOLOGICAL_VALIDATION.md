# Biological evaluation design

**Status:** proposed experiments and data requirements. No experimental data were acquired, fitted or validated in v2. Sources are indexed in `SOURCES.md`.

## First context of use

Select one spheroid model and an oxygen intervention for which independent measurements can be obtained. The initial prediction target should be explicit: a time course, spatial profile or segmented region under a stated culture/boundary schedule. Avoid “overall realism” and whole-patient treatment claims.

Murphy et al. [S27] provide time-dependent oxygen experiments relevant to this choice. Bull et al. [S26] provide cell/oxygen modeling precedent, but the audited implementation in that paper is restricted to two dimensions; it is not evidence that our 3D model is valid. The supplied steady-sphere numerical fixture does not reproduce either paper.

## Dataset acceptance

Before using a measurement, record cell-line name and identifier, identity/authentication evidence, culture/batch history, assay protocol, actual measured quantity and calibration, units, acquisition times, intervention delivery schedule, geometry, and the independent experimental unit. Record missing metadata instead of inferring it from another paper.

Store immutable raw references and checksums, processing code/version, exclusion criteria and reasons, uncertainty estimates, access/consent restrictions, and reuse terms. Separate raw data from digitized plot estimates. Do not use image-based digitization where raw data can be obtained; uncertainty and access limitations must accompany any fallback.

The MDA-MB-435 issue in the inherited audit is a concrete warning: a paper's tumor-type label does not replace cell identity verification. [S17,S18] Do not relabel an unassayed historical sample as definitely authenticated; document the conflict and narrow the inference.

## Calibration, policy development and validation

Partition data by experimental unit. Repeated frames from one spheroid are correlated; splitting frames between train and test leaks information. Where batch effects are important, reserve entire batches or culture conditions. Reserve an intervention schedule or regime that was not used for fitting, selecting a model, selecting a surrogate, or setting the final policy threshold.

Use development data to estimate parameters and decide model structure. Freeze both before evaluating the final holdout. A seed holdout tests stochastic reproducibility, not necessarily biological transfer. Keep failed conditions and predeclared exclusions visible.

Approximate Bayesian computation is one possible inference strategy, not a requirement. The cited tumor example [S17] is conditional on a 2D model, selected data and no-death simplification; its posterior does not cover arbitrary omitted biology. Fit identifiability and posterior-predictive checks matter more than choosing a named inference algorithm.

## Observation model

Write an explicit observation operator `y = H(state, assay_parameters) + noise`. For imaging, define whether the observable is concentration, reporter intensity, viable-region segmentation, measured diameter or inferred volume. Measurement processing and simulation postprocessing must use compatible definitions.

A rendering that resembles microscopy is not a validation metric. Compare matched quantities with uncertainty. Aggregate radius alone can be consistent with several growth, death and transport mechanisms; include an independent internal or perturbational observable when it is measurable.

## Proposed endpoints and controls

| Stage | Example target | Required control | Evidence claim |
|---|---|---|---|
| Analytic transport | Concentration mode or radial steady profile | Exact solution and refinement | Numerical accuracy for declared equations |
| Passive tracer experiment | Penetration/washout under fixed geometry | Known boundary delivery and tracer properties | Transport prediction in that setup |
| Oxygen spheroid | Growth plus internal spatial response after oxygen change | Simpler growth/transport models; held-out schedule | Scoped biological prediction |
| Confinement mechanics | Nuclear/cell deformation or force response | Matched material/loading protocol | Mechanics-specific model suitability [S29,S30] |
| Perfused tumor chip | Tracer delivery, vessel morphology, sprouting as separately measured | Matched transport and geometry controls | Only those chip observables [S16] |

Metric selection and acceptance tolerances must be based on the intended scientific decision and measurement precision, then frozen before held-out evaluation. Numeric thresholds in synthetic fixtures are software regression tolerances only.

## Perfusion evidence must remain separated

Ascheid et al. [S14] support multicellular spheroid organization and imaging-based perturbation observations. Their in-vivo perfusion results are not functional perfusion measurements of the in-vitro spheroids. Quintard et al. [S15] support vascularization/perfusion engineering in the studied non-cancer organoid systems, not cancer-treatment prediction. Skubal et al. [S16] provide a renal-cancer chip with measured bead/tracer behavior; tracer distribution is not a therapeutic drug's pharmacokinetics.

Treat these as distinct datasets with distinct observation maps. A biologically comprehensive model cannot be validated by merging their labels while ignoring assay and cell-system differences.

## Reporting uncertainty and failure

Report parameter sensitivity and which combinations are not identifiable from the chosen measurements. Distinguish measurement noise, biological variability, parameter uncertainty, stochastic simulation variance, numerical error and model discrepancy. A narrow posterior can still be biased by the wrong model form or biased data selection.

Failures to predict holdouts should remain in the release. Refit only on a new development cycle with a new untouched evaluation cohort. Do not turn the failed validation set into calibration and continue to call it a holdout.

The reusable `context_of_use` and `dataset_manifest` templates include null fields where evidence is not yet available. They must remain unqualified until those fields refer to actual records.
