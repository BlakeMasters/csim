"""Focused regressions for source-row identity, masks, and causal split/design."""
from __future__ import annotations

import itertools
import math
import unittest

from cellsim_v2.nfkb_observed import (
    adapt_source_row, causal_design, current_only_design, decode_stimulus_code,
    frozen_sequence_split, sequence_key,
)


class NFkBObservedTests(unittest.TestCase):
    def test_author_stimulus_codes_and_dose_tiers(self):
        for dose in (1, 2, 3):
            self.assertEqual(
                [decode_stimulus_code(4 * (dose - 1) + j, dose)
                 for j in range(4)],
                ["TNF-alpha", "IL-1beta", "LPS", "PAM2CSK4"],
            )
            self.assertIsNone(decode_stimulus_code(12, dose))
        with self.assertRaises(ValueError):
            decode_stimulus_code(4, 1)

    def test_nonfinite_observation_is_masked_with_exact_source_row(self):
        row = [0.2] * 172
        row[8] = float("nan")  # MATLAB trace column 9
        row[99] = float("inf")  # auxiliary column, not a trace
        row[166] = 1.0
        row[167:171] = [0.0, 1.0, 2.0, 3.0]
        row[171] = 1.0
        result = adapt_source_row(row, source_sha256="a" * 64,
                                  source_row_1based=1757)
        self.assertEqual(result["row_key"],
                         "sha256:" + "a" * 64 + ":scmatcomb_norm:row:1757")
        self.assertEqual(result["condition_id"], 1)
        self.assertEqual(result["dose_tier"], "high")
        self.assertIsNone(result["values"][8])
        self.assertEqual(result["nonfinite_trace_samples"],
                         [{"matlab_column_1based": 9, "kind": "NaN"}])
        self.assertTrue(math.isfinite(result["values"][7]))

    def test_split_keeps_each_order_together_across_doses(self):
        split = frozen_sequence_split()
        keys = {sequence_key(p) for p in itertools.permutations(
            ("TNF-alpha", "IL-1beta", "LPS", "PAM2CSK4"))}
        self.assertEqual(set(split), keys)
        self.assertEqual([list(split.values()).count(name)
                          for name in ("development", "validation", "evaluation")],
                         [16, 4, 4])

    def test_state_design_is_causal_to_future_stimulus_order(self):
        first = causal_design((0, 1, 2, 3), 1, 24.0, 120.0)
        second = causal_design((0, 1, 3, 2), 1, 24.0, 120.0)
        self.assertEqual(len(first), 83)
        self.assertEqual(first[:40], second[:40])  # 0 through 234 minutes
        self.assertNotEqual(first[40], second[40])  # third switch, 240 minutes

    def test_current_only_control_forgets_previous_ligands(self):
        first = current_only_design((0, 1, 2, 3), 1, 24.0)
        second = current_only_design((1, 0, 2, 3), 1, 24.0)
        self.assertEqual(len(first), 83)
        self.assertEqual(first[40], second[40])  # same current ligand at 240
        self.assertNotEqual(first[20], second[20])  # different current ligand


if __name__ == "__main__":
    unittest.main()
