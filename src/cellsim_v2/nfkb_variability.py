"""Descriptive finite-only percentiles across observed source rows."""
from __future__ import annotations

import math


def _percentile(sorted_values: list[float], probability: float) -> float | None:
    if not sorted_values:
        return None
    position = (len(sorted_values) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def finite_percentile_bands(rows: object) -> dict:
    """Return linear-interpolated p10/p50/p90 at each time, with counts.

    Nonfinite source entries are excluded only at their own time point.
    No uncertainty, exchangeability, or intrinsic-noise model is inferred.
    """
    if len(rows) == 0:
        raise ValueError("at least one source row required")
    width = len(rows[0])
    if width < 1 or any(len(row) != width for row in rows):
        raise ValueError("source rows must share a positive time width")
    result = {"p10": [], "p50": [], "p90": [], "finite_count": []}
    for time_index in range(width):
        values = sorted(float(row[time_index]) for row in rows
                        if math.isfinite(float(row[time_index])))
        result["finite_count"].append(len(values))
        for label, probability in (("p10", 0.10), ("p50", 0.50), ("p90", 0.90)):
            result[label].append(_percentile(values, probability))
    return result
