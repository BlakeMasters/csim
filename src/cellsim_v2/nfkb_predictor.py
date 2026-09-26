"""Read-only prediction from one frozen reduced NF-κB reporter candidate."""
from __future__ import annotations

import math

from .nfkb_observed import (
    DOSE_TIERS, SWITCH_TIMES_MIN, TIME_MIN, causal_design,
    decode_stimulus_code, feature_names,
)
from .nfkb_metadata import PAPER_SOURCE, nominal_dose_schedule


def _sha256_hex(value: object, label: str) -> str:
    if (type(value) is not str or len(value) != 64 or
            any(ch not in "0123456789abcdef" for ch in value)):
        raise ValueError(f"{label} must be lower-case SHA-256 hex")
    return value


def predict_frozen(frozen: dict, stimulus_codes: tuple[int, ...] | list[int],
                   dose_tier: int, *, frozen_candidate_sha256: str) -> dict:
    """Emit 83 reporter predictions without fitting or touching observations.

    Only source-backed four-ligand permutations and the author's three
    categorical dose tiers are accepted. Coefficients are phenomenological
    response coordinates; this API has no drug or molecular-kinetic inputs.
    """
    if type(frozen) is not dict or frozen.get("schema_version") != "cellsim-nfkb-frozen-state-space/1":
        raise ValueError("unsupported frozen candidate schema")
    candidate_sha = _sha256_hex(frozen_candidate_sha256,
                                "frozen candidate hash")
    source_sha = _sha256_hex(frozen.get("source_matrix_sha256"),
                             "source matrix hash")
    observed_sha = _sha256_hex(frozen.get("observed_artifact_sha256"),
                               "observed artifact hash")
    if frozen.get("feature_names") != list(feature_names()):
        raise ValueError("frozen feature contract differs from predictor")
    model = frozen.get("model")
    if type(model) is not dict or model.get("kind") != "state_space":
        raise ValueError("frozen state-space model required")
    weights = model.get("weights")
    if type(weights) is not list or len(weights) != len(feature_names()) or any(
            type(value) not in (int, float) or not math.isfinite(value)
            for value in weights):
        raise ValueError("frozen weights are missing or nonfinite")
    if type(dose_tier) is not int or dose_tier not in DOSE_TIERS:
        raise ValueError("dose tier must be one of author categories 1, 2, 3")
    if len(stimulus_codes) != 4 or any(type(code) is not int
                                      for code in stimulus_codes):
        raise ValueError("four integral author stimulus codes required")
    ligands = [decode_stimulus_code(code, dose_tier)
               for code in stimulus_codes]
    design = causal_design(stimulus_codes, dose_tier,
                           float(model["tau_fast_min"]),
                           float(model["tau_slow_min"]))
    predictions = [sum(coefficient * feature
                       for coefficient, feature in zip(weights, row))
                   for row in design]
    if not all(math.isfinite(value) for value in predictions):
        raise ValueError("predicted reporter is nonfinite")
    return {
        "schema_version": "cellsim-nfkb-frozen-prediction/1",
        "model_kind": "causal_reduced_reporter_state_space",
        "observable": "author_normalized_p65_nuclear_cytoplasmic_reporter",
        "unit": "dimensionless",
        "time_min": list(TIME_MIN),
        "switch_times_min": list(SWITCH_TIMES_MIN),
        "stimulus_codes": list(stimulus_codes),
        "ligand_sequence": ligands,
        "dose_tier_code": dose_tier,
        "dose_tier": DOSE_TIERS[dose_tier],
        "predicted_reporter": predictions,
        "frozen_candidate_sha256": candidate_sha,
        "source_matrix_sha256": source_sha,
        "observed_artifact_sha256": observed_sha,
        "nominal_stimulus_schedule": nominal_dose_schedule(
            stimulus_codes, dose_tier),
        "nominal_dose_source": PAPER_SOURCE,
        "drug_response": None,
    }
