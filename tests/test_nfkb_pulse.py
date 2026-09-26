"""Exploratory delayed-pulse basis remains causal to future stimuli."""
from __future__ import annotations

import unittest

from cellsim_v2.nfkb_pulse import pulse_design, pulse_feature_names


class NFkBPulseTests(unittest.TestCase):
    def test_pulse_rises_after_switch_and_future_order_is_causal(self):
        first = pulse_design((0, 1, 2, 3), 1, 24.0, 90.0, 120.0)
        second = pulse_design((0, 1, 3, 2), 1, 24.0, 90.0, 120.0)
        self.assertEqual(len(first), 83)
        self.assertEqual(len(first[0]), len(pulse_feature_names()))
        early_index = pulse_feature_names().index("early:high:TNF-alpha")
        self.assertEqual(first[0][early_index], 0.0)
        self.assertGreater(first[4][early_index], 0.0)
        self.assertEqual(first[:40], second[:40])
        self.assertNotEqual(first[40], second[40])


if __name__ == "__main__":
    unittest.main()
