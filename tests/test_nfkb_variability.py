"""Finite-only source-row dispersion is not a simulated noise law."""
from __future__ import annotations

import unittest

from cellsim_v2.nfkb_variability import finite_percentile_bands


class NFkBVariabilityTests(unittest.TestCase):
    def test_nonfinite_values_do_not_enter_percentiles_or_counts(self):
        rows = ((0.0, 1.0), (2.0, float("inf")), (4.0, 3.0))
        bands = finite_percentile_bands(rows)
        self.assertEqual(bands["finite_count"], [3, 2])
        for name, expected in (("p10", (0.4, 1.2)),
                               ("p50", (2.0, 2.0)),
                               ("p90", (3.6, 2.8))):
            for actual, target in zip(bands[name], expected):
                self.assertAlmostEqual(actual, target)

    def test_all_missing_time_remains_null(self):
        bands = finite_percentile_bands(((0.0, float("nan")),
                                         (2.0, float("-inf"))))
        self.assertEqual(bands["finite_count"], [2, 0])
        self.assertIsNone(bands["p50"][1])


if __name__ == "__main__":
    unittest.main()
