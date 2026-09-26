"""Typed adapter for the supplied sequential-stimulus p65 reporter matrix.

Only the author-documented columns are interpreted. Response values are the
author-supplied normalized reporter signal, not molecule amounts or a drug
response. This module uses the standard library; loading MATLAB v5 is the
optional CLI's responsibility.
"""
from __future__ import annotations

from hashlib import sha256
from itertools import permutations
import math


VARIABLE = "scmatcomb_norm"
MATLAB_COLUMNS = {"trace": [1, 83], "condition": 167,
                  "stimuli": [168, 171], "dose_tier": 172}
TIME_MIN = tuple(range(0, 493, 6))
SWITCH_TIMES_MIN = (0, 120, 240, 360)
LIGANDS = ("TNF-alpha", "IL-1beta", "LPS", "PAM2CSK4")
DOSE_TIERS = {1: "high", 2: "mid", 3: "low"}
_ABBREVIATION = dict(zip(LIGANDS, "TILP"))
SPLIT_SPEC = "nfkb-sequence-holdout-v1|sha256-sort|16-4-4"


def _integer(value: object, label: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{label} must be an integer")
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} must be an integer") from exc
    if not math.isfinite(number) or not number.is_integer():
        raise ValueError(f"{label} must be a finite integer")
    return int(number)


def decode_stimulus_code(code: object, dose_tier: object) -> str | None:
    """Decode author MATLAB code; 12 is printed as FM, with unknown ligand."""
    value = _integer(code, "stimulus code")
    dose = _integer(dose_tier, "dose tier")
    if dose not in DOSE_TIERS:
        raise ValueError("dose tier must be 1, 2, or 3")
    if value == 12:
        return None
    first = 4 * (dose - 1)
    if not first <= value < first + 4:
        raise ValueError("stimulus code and dose tier disagree")
    return LIGANDS[value - first]


def sequence_key(ligands: tuple[str, ...] | list[str]) -> str:
    if len(ligands) != 4 or set(ligands) != set(LIGANDS):
        raise ValueError("sequence must be one permutation of the four ligands")
    return "".join(_ABBREVIATION[item] for item in ligands)


def frozen_sequence_split() -> dict[str, str]:
    """Predeclared order-group split; every dose of an order shares its group."""
    keys = [sequence_key(p) for p in permutations(LIGANDS)]
    ranked = sorted(keys, key=lambda key: sha256(
        (SPLIT_SPEC + "|" + key).encode("ascii")).digest())
    return {key: ("development" if rank < 16 else
                  "validation" if rank < 20 else "evaluation")
            for rank, key in enumerate(ranked)}


def adapt_source_row(row: object, *, source_sha256: str,
                     source_row_1based: int) -> dict:
    """Keep the exact matrix row key and null out nonfinite trace samples."""
    if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(
            ch not in "0123456789abcdef" for ch in source_sha256):
        raise ValueError("source_sha256 must be lower-case SHA-256 hex")
    if type(source_row_1based) is not int or source_row_1based < 1:
        raise ValueError("source row must be a positive one-based integer")
    if len(row) != 172:
        raise ValueError("source row must have exactly 172 MATLAB columns")
    condition = _integer(row[166], "condition ID")
    dose = _integer(row[171], "dose tier")
    if not 1 <= condition <= 75 or dose not in DOSE_TIERS:
        raise ValueError("condition or dose tier outside the supplied matrix")
    expected_dose = (condition - 1) // 25 + 1
    if dose != expected_dose:
        raise ValueError("condition ID and dose tier disagree")
    codes = tuple(_integer(row[index], "stimulus code")
                  for index in range(167, 171))
    ligands = tuple(decode_stimulus_code(code, dose) for code in codes)
    is_control = condition in (25, 50, 75)
    if is_control != (codes == (12, 12, 12, 12)):
        raise ValueError("FM control condition and stimulus codes disagree")
    if not is_control and set(ligands) != set(LIGANDS):
        raise ValueError("four-stimulus condition must contain each ligand once")
    values: list[float | None] = []
    nonfinite: list[dict] = []
    for index in range(83):
        value = float(row[index])
        if math.isfinite(value):
            values.append(value)
        else:
            values.append(None)
            nonfinite.append({"matlab_column_1based": index + 1,
                              "kind": ("NaN" if math.isnan(value) else
                                       "+Inf" if value > 0 else "-Inf")})
    key = None if is_control else sequence_key(ligands)
    return {
        "row_key": f"sha256:{source_sha256}:{VARIABLE}:row:{source_row_1based}",
        "source_row_1based": source_row_1based,
        "condition_id": condition,
        "stimulus_codes": list(codes),
        "ligand_sequence": list(ligands),
        "sequence_key": key,
        "dose_tier_code": dose,
        "dose_tier": DOSE_TIERS[dose],
        "author_control_label": "FM" if is_control else None,
        "values": values,
        "nonfinite_trace_samples": nonfinite,
    }


def feature_names() -> tuple[str, ...]:
    names = ["intercept", "dose_mid", "dose_low"]
    for kind in ("fast", "slow"):
        for dose in (1, 2, 3):
            for ligand in LIGANDS:
                names.append(f"{kind}:{DOSE_TIERS[dose]}:{ligand}")
    for current in LIGANDS:
        for prior in LIGANDS:
            names.append(f"prior:{current}:{prior}")
    return tuple(names)


def causal_design(stimulus_codes: tuple[int, ...] | list[int], dose_tier: int,
                  tau_fast_min: float, tau_slow_min: float) -> tuple[tuple[float, ...], ...]:
    """Causal fast and prior-ligand memory basis on the author time grid.

    A ligand impulse enters fast state at its switch. When the next ligand
    arrives, the departing ligand enters a decaying prior-memory state. A
    linear observation map may be fitted over this fixed basis. These states
    are phenomenological, not NF-κB or IκB molecular concentrations.
    """
    if len(stimulus_codes) != 4:
        raise ValueError("four stimulus codes required")
    if dose_tier not in DOSE_TIERS:
        raise ValueError("invalid dose tier")
    ligands = tuple(decode_stimulus_code(code, dose_tier)
                    for code in stimulus_codes)
    if any(ligand is None for ligand in ligands) or set(ligands) != set(LIGANDS):
        raise ValueError("state basis supports four-ligand permutations only")
    if not math.isfinite(tau_fast_min) or tau_fast_min <= 0 or not math.isfinite(tau_slow_min) or tau_slow_min <= 0:
        raise ValueError("time constants must be positive and finite")
    fast_decay = math.exp(-6.0 / tau_fast_min)
    slow_decay = math.exp(-6.0 / tau_slow_min)
    fast = [0.0] * 4
    prior = [0.0] * 4
    rows = []
    for sample, minute in enumerate(TIME_MIN):
        if sample:
            fast = [value * fast_decay for value in fast]
            prior = [value * slow_decay for value in prior]
        phase = min(minute // 120, 3)
        current = LIGANDS.index(ligands[phase])
        if minute in SWITCH_TIMES_MIN:
            if phase:
                departing = LIGANDS.index(ligands[phase - 1])
                prior[departing] += 1.0
            fast[current] += 1.0
        features = [1.0, float(dose_tier == 2), float(dose_tier == 3)]
        for state in (fast, prior):
            for dose in (1, 2, 3):
                for j in range(4):
                    features.append(state[j] if dose_tier == dose else 0.0)
        for j in range(4):
            for k in range(4):
                features.append(prior[k] if current == j else 0.0)
        rows.append(tuple(features))
    return tuple(rows)


def current_only_design(stimulus_codes: tuple[int, ...] | list[int],
                        dose_tier: int, tau_fast_min: float) -> tuple[tuple[float, ...], ...]:
    """Control using current ligand, dose tier and time since switch only."""
    if len(stimulus_codes) != 4 or dose_tier not in DOSE_TIERS:
        raise ValueError("four stimulus codes and a valid dose tier required")
    ligands = tuple(decode_stimulus_code(code, dose_tier)
                    for code in stimulus_codes)
    if any(ligand is None for ligand in ligands):
        raise ValueError("FM control is outside current-ligand model")
    if not math.isfinite(tau_fast_min) or tau_fast_min <= 0:
        raise ValueError("fast time constant must be positive and finite")
    rows = []
    for minute in TIME_MIN:
        phase = min(minute // 120, 3)
        current = LIGANDS.index(ligands[phase])
        elapsed = minute - SWITCH_TIMES_MIN[phase]
        decay = math.exp(-elapsed / tau_fast_min)
        features = [1.0, float(dose_tier == 2), float(dose_tier == 3)]
        for dose in (1, 2, 3):
            for j in range(4):
                features.append(decay if dose_tier == dose and current == j else 0.0)
        rows.append(tuple(features))
    return tuple(rows)
