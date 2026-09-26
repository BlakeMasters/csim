# Sources and inspection provenance

This bibliography preserves the source IDs and access limits in the supplied verification audit. “Prior audit access” describes that inherited record, not a claim that every source was read again for v2. Targeted current checks are recorded in `../evidence/revision_source_checks.json`. No source establishes accuracy of the assembled proposed simulator. No third-party paper full text is bundled.

## S01

**Agmon et al. — Vivarium: an interface and engine for integrative multiscale modeling in computational biology** (2022). peer-reviewed primary software paper.

Source: https://academic.oup.com/bioinformatics/article/38/7/1972/6522109

DOI: `10.1093/bioinformatics/btac049`.

**Prior audit access:** full text, sections 2–4.

**Supported scope:** Processes, stores, multirate composition, and integrated example models.

**Limit:** Does not establish a universal sufficient cell state or the correctness of arbitrary coupled modules.

**V2 refresh:** Primary paper page reopened; modular state/process precedent. No new universal-state inference.

## S02

**Sluka et al. — The cell behavior ontology: describing the intrinsic biological behaviors of real and model cells seen as active agents** (2014). peer-reviewed primary ontology paper.

Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC4133580/

DOI: `10.1093/bioinformatics/btu210`.

**Prior audit access:** full text.

**Supported scope:** Biological semantics separable from implementation terminology.

**Limit:** An ontology does not define complete numerical restart or constitutive state.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S03

**Friedman et al. — MultiCellDS: a community-developed standard for curating microenvironment-dependent multicellular data** (2016). preprint / community data-standard proposal.

Source: https://www.isi.edu/results/publications/13460/multicellds-a-community-developed-standard-for-curating-microenvironment-dependent-multicellular-data/

DOI: `10.1101/090456`.

**Prior audit access:** author-institution abstract and bibliographic record.

**Supported scope:** Digital cell lines, snapshots, phenotype and microenvironment data.

**Limit:** The cited publication is bioRxiv; it is not proof of lossless universal solver interoperability.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S04

**Ghaffarizadeh et al. — PhysiCell: An open source physics-based cell simulator for 3-D multicellular systems** (2018). peer-reviewed primary software paper.

Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1005991

DOI: `10.1371/journal.pcbi.1005991`.

**Prior audit access:** full text including timestep discussion.

**Supported scope:** Cell agents coupled to substrates; distinct diffusion, mechanics, phenotype time scales.

**Limit:** Its defaults, convergence and performance do not transfer to the supplied toy scaffold.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S05

**preCICE — Overview of adapters** (2026). official documentation.

Source: https://precice.org/adapters-overview.html

**Prior audit access:** full page, updated 2026-09-08.

**Supported scope:** Lists official and third-party adapters.

**Limit:** SOFA, ESPResSo and Tissue Forge are not listed; this is not an exhaustive proof no outside adapter exists.

**V2 refresh:** Official catalog inspected. SOFA, ESPResSo and Tissue Forge not listed. This is not an exhaustive search for external adapters.

## S06

**preCICE — Step 6: Implicit coupling** (2026). official documentation.

Source: https://precice.org/couple-your-code-implicit-coupling.html

**Prior audit access:** full page.

**Supported scope:** Iterative coupling requires solver checkpoint/restore and reproducible evaluation.

**Limit:** preCICE does not implement the participating solver checkpoint internals.

**V2 refresh:** Official implicit-coupling workflow and participant-provided complete checkpoint/repeatability requirements inspected.

## S07

**preCICE — Mapping configuration** (2026). official documentation.

Source: https://precice.org/configuration-mapping.html

**Prior audit access:** full page.

**Supported scope:** Consistent, conservative and scaled-consistent mappings.

**Limit:** Global sum preservation is not by itself energy, torque, local flux or biological validity.

**V2 refresh:** Official mapping definitions inspected; global-sum preservation distinguished from other interface invariants.

## S08

**Smith et al. — Verification and reproducible curation of the BioModels repository** (2025). peer-reviewed primary reproducibility study.

Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1013239

DOI: `10.1371/journal.pcbi.1013239`.

**Prior audit access:** full text, methods and results.

**Supported scope:** 932 of 1055 ODE models agreed across at least two of five engines; published 2025-12-04.

**Limit:** Many experiments use generic templates; not all original figures were reproduced. Not a spatial biological-validation study.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S09

**FDA — Assessing the Credibility of Computational Modeling and Simulation in Medical Device Submissions** (2023). official nonbinding final guidance.

Source: https://www.fda.gov/media/154985/download

**Prior audit access:** full PDF text and scope-page screenshot, section III printed page 7.

**Supported scope:** Risk- and context-dependent credibility framework for first-principles/mechanistic models.

**Limit:** Standalone ML is excluded; hybrid-model guidance covers first-principles aspects only. No approval of this architecture.

**V2 refresh:** FDA landing page reopened, confirming first-principles/mechanistic device-submission scope. Detailed PDF exclusions are inherited from the supplied audit, not re-audited in this build.

## S10

**Tatka et al. — Adapting modeling and simulation credibility standards to computational systems biology** (2023). peer-reviewed review and methodological proposal.

Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC10369698/

DOI: `10.1186/s12967-023-04290-5`.

**Prior audit access:** full text.

**Supported scope:** Proposes adaptation of credibility practices to systems biology.

**Limit:** Proposal/review, not a validation experiment or issued regulatory standard.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S11

**Sajjadinia et al. — Multi-fidelity surrogate modeling through hybrid machine learning for biomechanical and finite element analysis of soft tissues** (2022). peer-reviewed primary computational study.

Source: https://bia.unibz.it/esploro/outputs/journalArticle/Multi-fidelity-surrogate-modeling-through-hybrid-machine/991006420497801241

DOI: `10.1016/j.compbiomed.2022.105699`.

**Prior audit access:** author-institution abstract and bibliographic record; publisher full text inaccessible in this audit.

**Supported scope:** Empirical reduced-physics plus learned correction for expensive soft-tissue FE models.

**Limit:** Not a proof of online tumor-solver switching or experimentally calibrated cancer predictions; no quantitative gains adopted here.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S12

**Kim, Stolarska and Othmer — A hybrid model for tumor spheroid growth in vitro I: Theoretical development and early results** (2007). peer-reviewed primary modeling paper.

Source: https://experts.umn.edu/en/publications/a-hybrid-model-for-tumor-spheroid-growth-in-vitro-i-theoretical-d/

DOI: `10.1142/S0218202507002479`.

**Prior audit access:** author-institution abstract and bibliographic record.

**Supported scope:** Cell-level growing periphery, continuum quiescent/necrotic regions and ECM, nutrient fields.

**Limit:** Prior art for regional model heterogeneity; not the exact proposed heterogeneous-engine controller.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S13

**Agmon and Spangler — Process Bigraphs and the Architecture of Compositional Systems Biology** (2026). preprint.

Source: https://arxiv.org/abs/2512.23754

DOI: `10.48550/arXiv.2512.23754`.

**Prior audit access:** abstract and version history; v2 dated 2026-08-14.

**Supported scope:** Typed interfaces, hierarchy, model translation and coordination, Vivarium 2.0 demonstrations.

**Limit:** Preprint; no peer-reviewed journal status confirmed. Closely related prior art, not a proof of this design.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S14

**Ascheid et al. — A vascularized breast cancer spheroid platform for the ranked evaluation of tumor microenvironment-targeted drugs by light sheet fluorescence microscopy** (2024). peer-reviewed primary experimental paper.

Source: https://www.nature.com/articles/s41467-024-48010-z

DOI: `10.1038/s41467-024-48010-z`.

**Prior audit access:** full text including model construction and results.

**Supported scope:** Four human-origin populations, pseudovascular organization, imaging/drug-response phenotypes, and additional in-vivo vascular comparisons.

**Limit:** The in-vitro spheroid arm does not demonstrate intravascular perfusion. The paper also contains in-vivo perfused-vessel measurements; these must not be confused with spheroid perfusion.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S15

**Quintard et al. — A microfluidic platform integrating functional vascularized organoids-on-chip** (2024). peer-reviewed primary experimental paper.

Source: https://www.nature.com/articles/s41467-024-45710-4

DOI: `10.1038/s41467-024-45710-4`.

**Prior audit access:** full text.

**Supported scope:** Functional perfusion of mesenchymal/pancreatic-islet spheroids and blood-vessel organoids.

**Limit:** Not a cancer-treatment validation dataset; useful vascular-engineering precedent.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S16

**Skubal et al. — Vascularized tumor on a microfluidic chip to study mechanisms promoting tumor neovascularization and vascular targeted therapies** (2025). peer-reviewed primary experimental paper.

Source: https://www.thno.org/v15p0766.htm

DOI: `10.7150/thno.95334`.

**Prior audit access:** full text and figure captions.

**Supported scope:** Metastatic renal-cell-carcinoma chip with vessel sprouting, bead and fluorescein experiments.

**Limit:** Figure 3 bead perfusion n=1 chip and fluorescein n=4; tracer transport and beads are not actual drug PK or deformable blood cells.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S17

**Wang et al. — Calibration of agent based models for monophasic and biphasic tumour growth using approximate Bayesian computation** (2024). peer-reviewed primary modeling/calibration paper.

Source: https://link.springer.com/article/10.1007/s00285-024-02045-4

DOI: `10.1007/s00285-024-02045-4`.

**Prior audit access:** full text, sections 2.1 and 2.2.

**Supported scope:** SMC-ABC parameter inference for a 2D Voronoi ABM using mouse xenograft data.

**Limit:** No cell death; declining late measurements excluded for model-assumption compatibility; breast-labeled MDA-MB435 data require authentication qualification.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S18

**Cellosaurus — MDA-MB-435 (CVCL_0417)** (2026). curated primary biological-resource record.

Source: https://www.cellosaurus.org/CVCL_0417

**Prior audit access:** full record.

**Supported scope:** Lists MDA-MB-435 as an M14 derivative and registered misidentified cell line.

**Limit:** A resource-level identity warning does not retrospectively assay the exact historical vial used in an experiment.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S19

**SBML specifications** (2026). official standard documentation.

Source: https://sbml.org/documents/specifications/

**Prior audit access:** official specification index.

**Supported scope:** Software-independent biological model descriptions and level/package distinctions.

**Limit:** A file format alone does not establish every solver supports each package or arbitrary dynamic cell geometry.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S20

**SED-ML — Simulation Experiment Description Markup Language** (2026). official standard documentation.

Source: https://sed-ml.org/

**Prior audit access:** official standard overview.

**Supported scope:** Model modifications, simulation procedures, outputs and experiment exchange.

**Limit:** The proposed ABM/coupling experiment requires explicit supported mappings; schema existence is not runtime conformance.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S21

**Bergmann et al. — COMBINE archive and OMEX format: one file to share all information to reproduce a modeling project** (2014). peer-reviewed primary software/format paper.

Source: https://link.springer.com/article/10.1186/s12859-014-0369-z

DOI: `10.1186/s12859-014-0369-z`.

**Prior audit access:** full text.

**Supported scope:** ZIP-based archive with mandatory manifest and optional metadata; can include additional formats.

**Limit:** Packaging custom files does not make their semantics executable by independent solvers.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S22

**SOFA — Features** (2026). official software documentation.

Source: https://www.sofa-framework.org/about/features/

**Prior audit access:** full page.

**Supported scope:** FEM, nonlinear material options, contact and representation mappings.

**Limit:** Capability documentation is not cancer-cell material calibration or a biological accuracy ranking.

**V2 refresh:** Official mechanics capabilities and representation mapping reviewed. No engine installed or material law calibrated.

## S23

**ESPResSo — Object-in-Fluid** (2026). official software documentation.

Source: https://espressomd.github.io/doc/object_in_fluid.html

**Prior audit access:** full page.

**Supported scope:** Triangulated elastic objects with stretching, bending, area and volume forces in fluid.

**Limit:** Cell-like mechanics does not itself validate tumor-cell/nuclear constitutive behavior.

**V2 refresh:** Official elastic-object API/mechanical terms reviewed. No fluid benchmark executed.

## S24

**Tissue Forge — Vertex Model Solver** (2026). official software documentation.

Source: https://tissue-forge-documentation.readthedocs.io/en/latest/models/vertex/solver/solver.html

**Prior audit access:** full page.

**Supported scope:** Surface/body representation and actor-based mechanics.

**Limit:** Automatic mesh-quality operations are primarily developed for two-dimensional use; not all 3D dynamic-topology behavior can be presumed.

**V2 refresh:** Official vertex/surface/body description revisited. Model capabilities are not a guarantee of required 3D topology behavior.

## S25

**NVIDIA Warp — Documentation** (2026). official software documentation.

Source: https://nvidia.github.io/warp/stable/index.html

**Prior audit access:** full index/capability overview.

**Supported scope:** CPU/CUDA kernels, geometry/numerical primitives and differentiability.

**Limit:** Does not establish biological credibility, comparative speed on this workload, or differentiability of arbitrary discrete events.

**V2 refresh:** Official stable documentation reviewed for CPU/GPU kernels and numerical primitives. No GPU build or version combination tested.

## S26

**Bull et al. — Mathematical modelling reveals cellular dynamics within tumour spheroids** (2020). peer-reviewed primary modeling paper.

Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1007961

DOI: `10.1371/journal.pcbi.1007961`.

**Prior audit access:** full text, model and oxygen sections.

**Supported scope:** Off-lattice cell model with continuous quasi-steady oxygen and comparison to spheroid-infiltration experiments.

**Limit:** Reported simulations restricted to 2D; conditional model assumptions, not general 3D perfused-tumor validation.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S27

**Murphy et al. — Growth and adaptation mechanisms of tumour spheroids with time-dependent oxygen availability** (2023). peer-reviewed primary experimental/modeling paper.

Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1010833

DOI: `10.1371/journal.pcbi.1010833`.

**Prior audit access:** full text including cell culture methods.

**Supported scope:** Time-dependent oxygen spheroid experiments and growth/adaptation modeling; authenticated melanoma cell lines.

**Limit:** Provides scoped observables; does not validate the proposed software without matched experiments and held-out predictions.

**V2 refresh:** Primary paper page reopened as candidate oxygen-perturbation study. No data acquired or numerical reproduction performed.

## S28

**Waltemath et al. — Minimum Information About a Simulation Experiment (MIASE)** (2011). peer-reviewed community reporting proposal.

Source: https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1001122

DOI: `10.1371/journal.pcbi.1001122`.

**Prior audit access:** full text.

**Supported scope:** Information needed to reproduce model setup, execution and postprocessing.

**Limit:** Documentation completeness is necessary but not empirical biological accuracy.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S29

**Stöberl et al. — Nuclear deformation and dynamics of migrating cells in 3D confinement reveal adaptation of pulling and pushing forces** (2024). peer-reviewed primary experimental/modeling study.

Source: https://research.vu.nl/en/publications/nuclear-deformation-and-dynamics-of-migrating-cells-in-3d-confine/

DOI: `10.1126/sciadv.adm9195`.

**Prior audit access:** author-institution abstract and bibliographic record; PMC full text blocked.

**Supported scope:** Nuclear shapes, displacement-derived forces and migration dynamics in compliant three-dimensional hydrogel channels.

**Limit:** Supports a confinement-specific mechanics benchmark, not universal strain thresholds or complete cancer-cell constitutive laws.

**V2 status:** inherited source record; not independently re-fetched in this revision.

## S30

**Bastianello et al. — Mechanical stress during confined migration causes aberrant mitoses and c-MYC amplification** (2024). peer-reviewed primary experimental study.

Source: https://air.unimi.it/retrieve/dd21f6fc-5335-4270-b5dd-c5c7144e0c5c/pnas.202404551.pdf

DOI: `10.1073/pnas.2404551121`.

**Prior audit access:** author-institution full PDF; abstract, results and methods inspected; no numerical figure data digitized.

**Supported scope:** Microfluidic confinement, live imaging and molecular observations connect mitotic confinement with chromosome-segregation defects and oncogenic alterations in studied systems.

**Limit:** Does not supply a universal deformation-to-mutation equation or validate the proposed simulator.

**V2 status:** inherited source record; not independently re-fetched in this revision.

