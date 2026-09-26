"""Exploratory two-onset reduced reporter basis for delayed pulses.

This is a descriptive candidate family, not NF-κB molecular kinetics. Its
evaluation orders had already been exposed through an earlier model run.
"""
from __future__ import annotations

import math

from .nfkb_observed import (
    DOSE_TIERS, LIGANDS, SWITCH_TIMES_MIN, TIME_MIN,
    decode_stimulus_code,
)


def pulse_feature_names() -> tuple[str, ...]:
    names = ["intercept", "dose_mid", "dose_low"]
    for kind in ("early", "late", "step"):
        for dose in (1, 2, 3):
            for ligand in LIGANDS:
                names.append(f"{kind}:{DOSE_TIERS[dose]}:{ligand}")
    for current in LIGANDS:
        for prior in LIGANDS:
            names.append(f"prior:{current}:{prior}")
    return tuple(names)


def _pulse(age_min: int, tau_min: float) -> float:
    ratio = age_min / tau_min
    return ratio * math.exp(1.0 - ratio)


def pulse_design(stimulus_codes: tuple[int, ...] | list[int], dose_tier: int,
                 tau_early_min: float, tau_late_min: float,
                 tau_prior_min: float) -> tuple[tuple[float, ...], ...]:
    if len(stimulus_codes) != 4 or dose_tier not in DOSE_TIERS:
        raise ValueError("four author codes and one valid dose tier required")
    ligands = tuple(decode_stimulus_code(code, dose_tier)
                    for code in stimulus_codes)
    if set(ligands) != set(LIGANDS):
        raise ValueError("four distinct ligands required")
    if any(not math.isfinite(value) or value <= 0 for value in
           (tau_early_min, tau_late_min, tau_prior_min)):
        raise ValueError("all pulse and prior time constants must be positive finite")
    if tau_late_min <= tau_early_min:
        raise ValueError("late pulse must follow early pulse")
    decay = math.exp(-6.0 / tau_prior_min)
    prior = [0.0] * 4
    rows = []
    for sample, minute in enumerate(TIME_MIN):
        if sample:
            prior = [value * decay for value in prior]
        phase = min(minute // 120, 3)
        current = LIGANDS.index(ligands[phase])
        if minute in SWITCH_TIMES_MIN and phase:
            departing = LIGANDS.index(ligands[phase - 1])
            prior[departing] += 1.0
        age = minute - SWITCH_TIMES_MIN[phase]
        early = _pulse(age, tau_early_min)
        late = _pulse(age, tau_late_min)
        row = [1.0, float(dose_tier == 2), float(dose_tier == 3)]
        for value in (early, late, 1.0):
            for dose in (1, 2, 3):
                for ligand_index in range(4):
                    row.append(value if dose_tier == dose and current == ligand_index else 0.0)
        for ligand_index in range(4):
            for history_index in range(4):
                row.append(prior[history_index] if current == ligand_index else 0.0)
        rows.append(tuple(row))
    return tuple(rows)
