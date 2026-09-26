# Virtual cell infrastructure: research and implementation boundary

Access date for the sources below: **2026-09-25, America/Los_Angeles**.
This note supports infrastructure choices for both physical cell-response models
and gene-expression response models. It reports no model training, experimental
calibration, biological validation, or installed/pinned external model.
Subsequent local implementation and synthetic learning results are recorded in
[PROTOTYPE_REPORT.md](PROTOTYPE_REPORT.md); they do not change these source scopes.

## Two training tasks, with explicit observables

The same provenance and evaluation infrastructure can support two task families:

| Task | Example input | Example target | Required interpretation |
|---|---|---|---|
| Physical cell response | Local concentration, geometry, time, intervention | Uptake amount, secretion rate, or measured growth response | Species, SI units, interval, response law, and balance account |
| Gene-expression response | Control expression, cell context, perturbation | Post-perturbation expression or its distribution | Assay, feature identities, normalization, observation time, and population definition |

The first implemented fixtures can use synthetic physical responses while the
manifest contract remains usable for either family. Synthetic training examples
test infrastructure and reproduce specified equations; they do not establish
how an experimental cell responds. Dataset and model qualification remain scoped
to the declared observable and context.

These are engineering choices informed by the sources below. No inspected source
establishes that an expression predictor can directly determine a molar exchange
law, growth law, or mechanical response for this simulator.

## Transport and learned-model boundary

The work targets `src/cellsim_v2/transport.py` for the physical environment and
`src/cellsim_v2/training.py` for training-data and immutable campaign contracts.
Consult `IMPLEMENTATION_STATUS.md` for the implemented and exercised subset;
the additional contract fields and adapters discussed here are design guidance.

Transport owns field amounts and the acceptance of cell-field transfers. A cell
model receives observations over a declared time interval and proposes effects
with explicit meanings. An instantaneous `mol/s` rate and an integrated `mol`
amount require different handling. Accepted exchange must debit the donor and
credit the receiver, or identify a documented source/sink ledger account.

Expression counts, normalized expression, assay intensities, and latent vectors
retain their observation semantics. They cannot be assigned to molar inventories.
A future expression-to-physical-response mapping needs its own model identity,
training evidence, units, applicability limits, and evaluation. Until such a law
exists, an expression predictor can operate alongside the physical simulation
without controlling its material exchanges.

Processes must return proposals without mutating their input state. Retrying a
coupling step also requires replay of model-private state, random state, and any
integrator/event history. A process-shaped interface alone does not prove replay.

## Minimum training and inference record

The following fields guide future dataset templates and adapters; they are not a
claim that every field is enforced by the current Python implementation.

| Area | Fields and policy |
|---|---|
| Dataset identity | Source/accession, artifact hashes, reuse terms, acquisition/protocol metadata, experimental unit, donor/batch/context, exclusions, uncertainty |
| Observable | `modality`, `observable_id`, `unit`, `observation_operator_id`, feature IDs/order, matrix representation, preprocessing identity |
| Time | `prediction_kind` (`endpoint` or `trajectory`), input/target acquisition times, interval units, intervention timing, supported prediction horizon |
| Pairing | `pairing_policy` (`unpaired_population`, `paired_observations`, or `longitudinal`), `pair_id` when meaningful, `trajectory_id`, experimental-unit relationship, control-matching policy |
| Split | Explicit record assignments, protected grouping fields, held-out dimensions, control availability, frozen assignment hash, evaluation role |
| Model | Source/config/weights hashes, feature/preprocessing hashes, fit-data identity, supported contexts/inputs, output meaning, checkpoint/private-state requirements |
| Evaluation | Metric definitions and versions, baseline identities, acceptance criteria, frozen candidate identity, cohort counts, failures and exclusions |

An endpoint predictor estimates the response at a specified assay time. Repeatedly
applying it does not establish a dynamic simulator. A trajectory task needs
observations that identify its temporal semantics and an evaluation of accumulated
rollout error. A sequence index or generative-model integration variable must not
be silently relabeled as experimental time.

Unpaired single-cell assays generally compare sampled populations under stated
conditions. A control row must not be presented as the measured ancestor of a
perturbed row without pairing evidence. For longitudinal observations, keep all
correlated observations from the protected unit together. Record ambiguous or
missing pairing information explicitly.

## Split and campaign identity

Experimental-unit separation and generalization dimensions answer different
questions. First prevent leakage from correlated observations of a protected
unit. Then state whether evaluation holds out perturbations, cell contexts,
donors/batches, schedules, or a specified combination.

For example, holding out a gene perturbation within a known cell context differs
from predicting perturbation responses in a context for which only unperturbed
controls are available. The latter may allow context controls at inference while
withholding every perturbed response in that context. Record these rights rather
than using the word "unseen" without defining what the model may observe.

Preprocessing, feature selection, and normalization policies must declare which
data they fit on. Hash the ordered features and fitted transformations. Hash the
dataset artifacts, split assignments, candidate, observation definition, and
evaluation configuration independently. A changed weight file or transformation
requires a new candidate identity even if its display name stays the same.

Freeze one candidate and the evaluation definition before final evaluation. Keep
holdout outcomes, rejected records, and failed runs. A refit after inspecting a
final holdout starts a new development cycle and requires a new final cohort.

## Baselines, failure, and cost

Physical surrogate comparisons should include the stated analytic/reference law,
a simple fixed rule, and the independently verified comparator when available.
Expression tasks should include available control/no-change and training-mean
baselines, with simple linear methods considered before expensive architectures.
Choose metrics for the scientific question: common expression similarity scores
can reward shared treatment effects while missing perturbation-specific changes.

Report per-context results, difficult conditions, failures, and abstention along
with aggregate error. Uncertainty estimates require their own evaluation; a small
ensemble spread or novelty score does not establish an error bound. Never clip
invalid physical amounts or hide unsupported inputs to improve apparent success.

Charge reference/data generation, preprocessing, unsuccessful work, training,
selection, loading, inference, evaluation, mapping, and persistence. Report the
actually exercised operating system, interpreter, device, numerical controls,
commands, test/tool/source identity, and artifact hashes. Synthetic throughput is
not evidence of whole-system scalability or training benefit on biological data.

## Inspected sources and limits

All links below were accessed on the date at the top. Access depth describes what
was inspected, and does not imply local installation or independent reproduction.

| Source | Access depth | Narrow support and limitation |
|---|---|---|
| [AnnData on-disk format](https://anndata.readthedocs.io/en/stable/fileformat-prose.html) | Official format documentation; relevant specification inspected | `obs`/`var`, aligned matrices/layers, and HDF5/Zarr provide a possible data interchange structure. The format does not authenticate cell identity, define assay units, or prevent split leakage. |
| [Arc STATE README](https://github.com/ArcInstitute/state/blob/main/README.md) | Official model repository documentation; preprocessing, training, inference, split, and license sections inspected | Documents H5AD inputs, feature preprocessing, context holdouts, and within-context perturbation holdouts. This is an adapter candidate; no release/build or weights were exercised. Its published code/model terms must be checked for the intended use before adoption. |
| [Arc 2026 Virtual Cell Challenge](https://arcinstitute.org/news/virtual-cell-challenge-2026) | Official benchmark announcement; task and evaluation sections inspected | Defines prediction in cell contexts with unperturbed controls available and perturbed responses withheld. Supports explicitly recording input rights and context transfer. It does not validate physical simulation or any local model. |
| [Systema study](https://www.nature.com/articles/s41587-025-02777-8) | Primary research article; main results and metric discussion inspected | Its ten-dataset comparison shows average-effect baselines can be competitive under common metrics and motivates perturbation-specific evaluation. Findings apply to the examined methods/tasks, not every virtual-cell model. |
| [Vivarium process tutorial](https://vivarium-core.readthedocs.io/en/latest/tutorials/write_process.html) | Official implementation documentation; process/port/update sections inspected | Supports explicit process ports and updates from unmodified input state. Its concentration examples do not establish our amount conservation, replay, or solver interoperability. |
| [BioFVM paper](https://academic.oup.com/bioinformatics/article/32/8/1256/1744374) | Primary paper abstract inspected; PMC full-text retrieval blocked | Describes 3D diffusive transport with cell/bulk sources and uptake, usable within larger simulations. No full-text numerical or biological claim is used to qualify this implementation. |
| [FiPy finite-volume discretization](https://pages.nist.gov/fipy/en/latest/numerical/discret.html) | Official NIST documentation verified during this project session; retrieved documentation dated 2026-09-18 | Supports face-based diffusion using diffusivity times face area divided by cell-center distance and default no-flux boundaries. The local explicit solver is limited to declared fixtures; this is not FiPy integration or a comparison against FiPy. |

## Staged next steps

1. Exercise fixed 3D conservative transport and one cell-field response interface
   with synthetic cases, failure injection, and preserved numerical evidence.
2. Freeze the dataset/split/campaign representation and export an auditable
   synthetic fixture with declared units, pairing, observations, and provenance.
3. Choose a measured observable and real dataset for each desired training task;
   inspect identity, access terms, controls, experimental units, and uncertainty.
4. Implement one offline comparator and one data adapter at a time. An optional
   AnnData adapter must verify feature and metadata mapping with real fixtures.
5. Evaluate simple baselines and freeze one candidate before final holdout use.
   Install/pin an external framework only after its actual build is exercised.
6. Consider learned physical proposals only after the response mapping and
   conservative acceptance path have independent evidence. Validate endpoint,
   trajectory, and coupled-rollout behavior according to their separate claims.

AnnData and STATE adapters, acquired biological datasets, trained models, and an
automatic expression-to-molar-rate mapping remain future work.
