"""Author-backed nominal dose labels stay distinct from synthetic amount fluxes."""
from __future__ import annotations

import unittest

from cellsim_v2.nfkb_metadata import nominal_dose_schedule


class NFkBMetadataTests(unittest.TestCase):
    def test_exact_author_code_to_nominal_extracellular_dose(self):
        self.assertEqual(
            [item["nominal_extracellular_ng_ml"] for item in
             nominal_dose_schedule((0, 1, 2, 3), 1)],
            [90.0, 3.0, 400.0, 1.0],
        )
        self.assertEqual(
            [item["nominal_extracellular_ng_ml"] for item in
             nominal_dose_schedule((4, 5, 6, 7), 2)],
            [30.0, 0.2, 100.0, 0.1],
        )
        self.assertEqual(
            [item["nominal_extracellular_ng_ml"] for item in
             nominal_dose_schedule((8, 9, 10, 11), 3)],
            [3.0, 0.05, 12.5, 0.01],
        )

    def test_fm_control_does_not_invent_ligand_dose(self):
        control = nominal_dose_schedule((12, 12, 12, 12), 1)
        self.assertTrue(all(item["ligand"] is None and
                            item["nominal_extracellular_ng_ml"] is None
                            for item in control))


if __name__ == "__main__":
    unittest.main()
