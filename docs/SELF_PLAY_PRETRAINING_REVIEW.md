# Self-play pretraining: evidence and a scoped simulator experiment

**Status:** research review and proposed experiment; no training implemented or run.
Sources accessed **2026-09-25, America/Los_Angeles**. This review concerns
*Self-Play Pretraining with Zero Data*, arXiv:2609.30063v1, submitted 2026-09-24.
The inspected primary material is a preprint, not independent reproduction.

## What the paper actually studies

The learner minimizes mean next-byte cross-entropy on executed program outputs.
Generator training combines KL-regularized policy gradients, replay importance
weighting, and reward-weighted supervised updates. Mutations participate in
learner/supervised updates but are excluded from policy gradients.

Its generator reward is

\[
r_i=\left|\left\langle\nabla_\theta L(y_i;\theta_e),
P_e\odot(\theta_{\lfloor e/2\rfloor}-\theta_e)\right\rangle\right|,
\qquad P_e=\frac{\mathrm{lr}}{\sqrt{\hat v_e}+\epsilon}.
\]

This measures absolute gradient alignment with an AdamW-preconditioned lookback
direction; it is not simply high loss or measured downstream improvement.
Natural data supply no main self-play gradients, but DCLM/DNA validation selects
hyperparameters. Results fit retrospective model/checkpoint/ensemble frontiers,
using effective compute `K * parameters * tokens`; maximum training budget is
34.36B tokens. Transfer improves across modalities; PCFG remains stronger on
text/code. DNA evaluation predicts encoded sequence symbols, not cell responses.
Separate downstream pretraining uses natural-data gradients and reports faster
warm-start learning, excluding self-play cost. The authors state generated
structure cannot supply contingent facts about the real world.
[Primary paper, sections 2-3, 6, appendices A-B](https://arxiv.org/html/2609.30063v1).

## Available artifacts and inspection depth

| Source | Inspected material | What is available and its limits |
|---|---|---|
| [Primary HTML](https://arxiv.org/html/2609.30063v1) and [PDF](https://arxiv.org/pdf/2609.30063) | Method, objectives, results, discussion, evaluation, reward ablations, pool construction; PDF compute axes and downstream cost note | Supports the method summary above; no experiment was reproduced locally. |
| [Author checkpoint release](https://huggingface.co/nourya-cohen/solomonoff-paper) | Model card, model-size table, release scope | Two initially random, independently parameterized transformers use byte sequences; the learner release is Llama-style, vocabulary 256, context 4096, with sizes from 98,496 to 24,388,096 parameters. Generator weights, optimizer states, and training code are omitted. Only ladder seeds reaching at least 8192 rounds are included, so release availability alone cannot establish the outcome of every attempted run. |
| [Author repository](https://github.com/nourya-aliz/self_play_pretraining) and [reproduction guide](https://github.com/nourya-aliz/self_play_pretraining/blob/main/REPRODUCING.md) | README and detailed reproduction instructions | Provides evaluation/figure tooling. Some curves, including downstream pretraining, are supplied as scored data; the guide does not provide an end-to-end training reproduction. The older Solomonoff-Figures URL redirects here. No package or model build was tested or pinned. |

## Applicability to this project

The following is our proposed adaptation, with no demonstrated benefit yet.
The useful hypothesis is that choosing informative simulation conditions can
improve a surrogate's learning under a fixed total cost. The current conservative
transport and synthetic fixture provide a small, auditable environment in which
to test that hypothesis.

The literal paper generates byte-producing programs and trains byte predictors.
Our proposed curriculum would choose typed simulation configurations and train a
model for a named physical observable. That changes the search space, supervision,
reward, and model architecture. It should be named an adapted simulator curriculum
unless a separate implementation reproduces the paper's actual method.

For physical responses, generated examples can reveal structure in the equations
we supply and locate difficult regimes within their declared domain. Their
scientific validity is limited by those equations and subsequent independent
verification. For expression responses, a conservative field simulator supplies
no gene-regulatory or assay mapping by itself. Experimentally grounded cell
contexts and measurements remain necessary for biological transfer claims.

No learned proposal may alter authoritative molar amounts directly. It must pass
through the same unit, domain, donor-availability, and paired-transfer checks as
other cell-field proposals. Good predictive loss alone does not establish a
conservative rollout or permit expression values to become uptake rates.

## Proposed first offline experiment

1. **Define the target.** Predict a one-step cell uptake increment in mol under
   the existing synthetic law. Record input features, interval, process order,
   parameter domain, and observation operator. Use the analytic law as a positive
   control. The present law is cheap enough that surrogate speed benefit is an
   open question; learning it is initially an infrastructure experiment.
2. **Freeze evaluation before adaptive generation.** Create disjoint development
   and final condition families. Group every cell/frame sharing an environment
   into the same experimental unit. Keep final cases, targets, and scores outside
   the curriculum's observations. A validation probe used in the reward is
   development data, even if its file or code calls it a holdout.
3. **Establish cheap controls.** Compare fixed stratified sampling, uniform random
   sampling, and a deterministic coverage rule before a learned selector. Give
   every arm the same model architecture, allowed information, label budget,
   numerical precision, and measured total-cost budget. Include the exact law,
   no-change, and a training-only mean-increment predictor where meaningful.
4. **Constrain the generator.** Select from a reviewed finite configuration pool:
   concentrations, uptake parameters, boundary schedules, and supported fixed-grid
   settings. Reject invalid stability/amount demands and record them. Do not let
   the generator write arbitrary Python or change physics, observation mappings,
   cohort assignments, acceptance tolerances, or reference answers.
5. **Use a separately named reward.** Initially measure improvement on a fixed
   development probe per measured cost. Compare against coverage and shuffled
   rewards to detect mere selection overhead or spurious correlation. Reusing a
   probe can overfit it, so reserve distinct validation data for selecting the
   final selector and learner. Only a later arm should investigate the paper's
   exact gradient-alignment reward and required optimizer/lookback state.
6. **Freeze, evaluate, and retain failures.** Freeze learner, selector, source,
   preprocessing, ordered features, split, and evaluation identity. Stop all
   updates during the final campaign. Report per-regime and worst-case errors,
   constraint failures, coverage, and rollout drift in addition to mean error.
   Include random seeds and every failed or aborted attempt in the record.
7. **Charge the full cost.** Count candidate generation, simulation labels,
   generator/reward computation, discarded work, learner updates, tuning,
   evaluation, inference, and persistence. Report cold starts and amortization
   explicitly. Fewer consumed examples do not alone establish lower total cost.

## Existing support and missing pieces

`tools/prepare_training_fixture.py` generates grouped physical trajectories.
`src/cellsim_v2/training.py` checks declared groups and artifacts and freezes a
campaign against a trusted digest. The subsequent `train_response_baseline.py`
runner fits and freezes simple synthetic increment predictors; see
[BASELINE_PROTOTYPE.md](BASELINE_PROTOTYPE.md). Adaptive generation, reward
learning, campaign access control and biological data authentication remain open.

A future experiment needs a finite candidate registry, append-only acquisition
history, explicit development-probe roles, resource accounting, and a learner
checkpoint format that includes optimizer, RNG, and selector state. Keep these
additions offline until fixed-model inference and conservative acceptance have
their own evidence. The final campaign identity must bind the selected curriculum
as well as its learner, rather than relying only on a mutable run name.

## Relationship to contrastive distillation and calibrated decisions

The separate [RLCD review](RLCD_REVIEW.md) addresses contrastive distillation.
For any eventual preference experiment, labels should come from independent
criteria: verified numerical error, conservation, supported applicability, or
matched experimental measurements. A model's self-endorsement is not an
independent scientific preference label.

Calibrated acceptance/abstention is a separate downstream decision problem. It
requires evidence for false acceptance and coverage on untouched conditions.
Neither a useful curriculum nor a preferred response establishes that calibration.
These are distinct future experiments, with separate frozen evidence and costs.
