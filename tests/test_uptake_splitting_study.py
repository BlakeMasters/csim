"""Numerical evidence for a synthetic coupled 3D field/cell example."""
import unittest

from uptake_splitting_study import failure_injection, run


class UptakeSplittingStudyTests(unittest.TestCase):
    def test_declared_qoi_refines_and_closed_amounts_balance(self):
        result = run()
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["configuration"]["qoi"], "cell accumulated tracer amount at T, mol")
        self.assertEqual(result["configuration"]["grid_shape"], [2, 2, 2])
        self.assertFalse(result["independent_external_solver_run"])
        self.assertFalse(result["biological_validation"])
        self.assertEqual(result["engineering_limits"]["qoi_absolute_error_mol"], 5e-4)
        self.assertLess(result["control"]["rk4_step_halving_qoi_difference_mol"], 1e-10)
        for ordering in ("diffusion_then_uptake", "uptake_then_diffusion"):
            rows = result["refinement"][ordering]["rows"]
            self.assertGreaterEqual(len(rows), 3)
            self.assertTrue(all(row["minimum_amount_mol"] >= 0 for row in rows))
            self.assertTrue(all(row["absolute_balance_error_mol"] < 1e-12 for row in rows))
            errors = [row["absolute_qoi_error_mol"] for row in rows]
            self.assertTrue(all(a > b for a, b in zip(errors, errors[1:])))
            self.assertLess(errors[-1], errors[0] / 4)

    def test_window_error_is_separated_from_process_step_error(self):
        result = run()
        window_study = result["fixed_process_step_window_refinement"]
        self.assertEqual(window_study["process_step_s"], 1 / 128)
        process_study = result["fixed_window_process_step_refinement"]
        self.assertEqual(process_study["window_s"], 1 / 4)
        for order in ("diffusion_then_uptake", "uptake_then_diffusion"):
            windows = window_study["orderings"][order]["rows"]
            process_steps = process_study["orderings"][order]["rows"]
            self.assertEqual([row["window_s"] for row in windows], [1 / n for n in (4, 8, 16, 32)])
            self.assertEqual([row["process_step_s"] for row in process_steps],
                             [1 / n for n in (4, 8, 16, 32, 64, 128)])
            self.assertTrue(all(row["absolute_balance_error_mol"] < 1e-12
                                for row in windows + process_steps))
            self.assertLess(windows[-1]["absolute_qoi_error_mol"],
                            windows[0]["absolute_qoi_error_mol"])
            self.assertGreater(process_steps[-1]["absolute_qoi_error_mol"], 0)

    def test_overdraw_rejects_whole_window(self):
        result = failure_injection()
        self.assertTrue(result["rejected"])
        self.assertTrue(result["world_unchanged"])
        self.assertIn("demand", result["error"])


if __name__ == "__main__":
    unittest.main()
