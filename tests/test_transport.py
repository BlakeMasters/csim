"""Synthetic transport contracts; no measured cell parameters are used."""
from dataclasses import FrozenInstanceError
from fractions import Fraction
import math
import unittest

from cellsim_v2.state import AmountField, Cell, World, total_amount
from cellsim_v2.scheduler import Process, WindowStepper
from cellsim_v2.transport import (
    BoundaryFlux, CellUptake, RectilinearGrid3D, diffusion_step,
    diffusion_timestep_limit_s, saturable_uptake_step,
)


ALL = frozenset({"cells", "fields", "ledger", "events"})


def world_for(grid, concentrations=None):
    values = concentrations if concentrations is not None else (1.0,) * grid.voxel_count
    return World(fields={"tracer": AmountField.from_concentrations(
        "tracer", tuple(values), grid.volumes_m3)})


class GridTests(unittest.TestCase):
    def test_index_centers_volumes_and_location(self):
        grid = RectilinearGrid3D((1, 3), (2, 4), (5, 6), origin_m=(-1, 2, 3))
        self.assertEqual(grid.shape, (2, 2, 2))
        self.assertEqual(grid.voxel_count, 8)
        self.assertEqual(grid.flat_index(1, 0, 1), 5)
        self.assertEqual(grid.indices(5), (1, 0, 1))
        self.assertEqual(grid.volumes_m3, (10, 30, 20, 60, 12, 36, 24, 72))
        self.assertEqual(grid.center_m(5), (1.5, 3, 11))
        for voxel in range(grid.voxel_count):
            self.assertEqual(grid.locate(grid.center_m(voxel)), voxel)
        self.assertEqual(grid.locate((-1, 2, 3)), 0)
        self.assertEqual(grid.locate((0, 4, 8)), 7)
        self.assertEqual(grid.locate((3, 8, 14)), 7)

    def test_immutable_geometry_copies_mutable_inputs(self):
        widths = [1, 2]
        grid = RectilinearGrid3D(widths, [3], [4])
        widths[0] = 99
        self.assertEqual(grid.x_widths_m, (1, 2))
        with self.assertRaises(FrozenInstanceError):
            grid.origin_m = (1, 2, 3)

    def test_invalid_geometry_rejected(self):
        for widths in ((), (0,), (-1,), (math.nan,), (math.inf,), (True,)):
            with self.subTest(widths=widths), self.assertRaises((ValueError, TypeError)):
                RectilinearGrid3D(widths, (1,), (1,))
        for origin in ((1, 2), (0, 0, math.inf), (False, 0, 0)):
            with self.subTest(origin=origin), self.assertRaises((ValueError, TypeError)):
                RectilinearGrid3D((1,), (1,), (1,), origin)
        for widths in ((1e200, 1e200, 1e200), (1e-200, 1e-200, 1e-200)):
            with self.subTest(widths=widths), self.assertRaises(ValueError):
                RectilinearGrid3D(*(tuple([x]) for x in widths))
        with self.assertRaises(ValueError):
            RectilinearGrid3D((1,), (1,), (1,), (1e100, 0, 0))

    def test_invalid_indices_and_points_rejected(self):
        grid = RectilinearGrid3D((1,), (1,), (1,))
        for index in (-1, 1, True, 0.0):
            with self.subTest(index=index), self.assertRaises((ValueError, TypeError)):
                grid.indices(index)
        for point in ((-1e-12, 0, 0), (1.0001, 0, 0), (0, 0), (True, 0, 0), (math.nan, 0, 0)):
            with self.subTest(point=point), self.assertRaises((ValueError, TypeError)):
                grid.locate(point)
        with self.assertRaises((ValueError, TypeError)):
            grid.flat_index(0, True, 0)

    def test_distorted_represented_geometry_is_rejected(self):
        # At this origin, nominal widths of 3 become represented spans of 4.
        # Distinct coordinates alone cannot certify the requested geometry.
        with self.assertRaisesRegex(ValueError, "represent"):
            RectilinearGrid3D((3., 3.), (1.,), (1.,), (1e16, 0., 0.))


class DiffusionTests(unittest.TestCase):
    def test_closed_diffusion_preserves_scaled_amounts_and_concentration_bounds(self):
        # Fixed dimensionless case: scaling all lengths by L and D by L^2
        # leaves the Euler concentration update at the same dt unchanged.
        reference = None
        for length_scale in (1e-3, 1., 1e3):
            widths = tuple(length_scale * value for value in (1., 2., 0.75))
            grid = RectilinearGrid3D(widths, (1.5 * length_scale, 0.5 * length_scale),
                                     (0.8 * length_scale, 1.2 * length_scale))
            diffusivity = 0.1 * length_scale**2
            dt = 0.2 * diffusion_timestep_limit_s(grid, diffusivity)
            for concentration_scale in (1e-18, 1., 1e18):
                with self.subTest(length_scale=length_scale,
                                  concentration_scale=concentration_scale):
                    initial = tuple(concentration_scale * (1. + (7 * i % 11) / 10.)
                                    for i in range(grid.voxel_count))
                    world = world_for(grid, initial)
                    before = world.clone()
                    proposal = diffusion_step(world, grid, "tracer", diffusivity, dt)
                    self.assertEqual(world, before)
                    self.assertEqual(proposal.ledger, ())
                    proposal.commit(world, ALL)
                    after = world.fields["tracer"].concentrations_mol_m3
                    normalized = tuple(value / concentration_scale for value in after)
                    if reference is None:
                        reference = normalized
                    for actual, expected in zip(normalized, reference):
                        self.assertTrue(math.isclose(actual, expected, rel_tol=2e-14))
                    self.assertGreaterEqual(min(normalized), min(initial) / concentration_scale - 2e-14)
                    self.assertLessEqual(max(normalized), max(initial) / concentration_scale + 2e-14)
                    self.assertTrue(math.isclose(total_amount(world, "tracer"),
                                                  total_amount(before, "tracer"),
                                                  rel_tol=2e-14, abs_tol=0.))

    def test_unequal_voxel_face_amount_is_paired(self):
        grid = RectilinearGrid3D((1, 3), (2,), (4,))
        world = world_for(grid, (1, 0))
        original = world.clone()
        proposal = diffusion_step(world, grid, "tracer", 1, 0.1)
        self.assertEqual(world, original)
        self.assertEqual(proposal.ledger, ())
        proposal.commit(world, ALL)
        self.assertEqual(world.fields["tracer"].amounts_mol, (7.6, 0.4))
        self.assertEqual(total_amount(world, "tracer"), 8)
        limit = diffusion_timestep_limit_s(grid, 1)
        self.assertLess(limit, 2)
        self.assertTrue(math.isclose(limit, 2, rel_tol=1e-13))

    def test_constant_concentration_on_unequal_volumes_is_stationary(self):
        grid = RectilinearGrid3D((1, 2), (2, 3), (3, 4))
        world = world_for(grid)
        original = world.clone()
        diffusion_step(world, grid, "tracer", 1, 0.05).commit(world, ALL)
        self.assertEqual(world, original)

    def test_three_dimensions_and_closed_boundaries(self):
        grid = RectilinearGrid3D((1,) * 3, (1,) * 3, (1,) * 3)
        values = [0.] * grid.voxel_count
        center = grid.flat_index(1, 1, 1)
        values[center] = 1
        world = world_for(grid, values)
        diffusion_step(world, grid, "tracer", 1, 0.1).commit(world, ALL)
        amounts = world.fields["tracer"].amounts_mol
        self.assertAlmostEqual(amounts[center], 0.4)
        neighbors = {grid.flat_index(1 + i, 1 + j, 1 + k) for i, j, k in
                     ((-1, 0, 0), (1, 0, 0), (0, -1, 0), (0, 1, 0), (0, 0, -1), (0, 0, 1))}
        self.assertTrue(all(amounts[index] == 0.1 for index in neighbors))
        self.assertEqual(sum(value != 0 for value in amounts), 7)
        self.assertAlmostEqual(total_amount(world, "tracer"), 1)
        self.assertAlmostEqual(diffusion_timestep_limit_s(grid, 1), 1 / 6)

    def test_stability_uses_smallest_volume_and_all_faces(self):
        grid = RectilinearGrid3D((1,) * 3, (1,) * 3, (1,) * 3)
        world = world_for(grid)
        original = world.clone()
        with self.assertRaisesRegex(ValueError, "stability"):
            diffusion_step(world, grid, "tracer", 1, 0.2)
        self.assertEqual(world, original)
        uneven = RectilinearGrid3D((0.1, 10), (1,), (1,))
        with self.assertRaisesRegex(ValueError, "stability"):
            diffusion_step(world_for(uneven), uneven, "tracer", 1, 0.51)

    def test_exact_stability_limit_retains_nonnegative_amounts(self):
        grid = RectilinearGrid3D((1,) * 3, (1,) * 3, (1,) * 3)
        values = [0.] * grid.voxel_count
        values[grid.flat_index(1, 1, 1)] = 1
        world = world_for(grid, values)
        diffusion_step(world, grid, "tracer", 1,
                       diffusion_timestep_limit_s(grid, 1)).commit(world, ALL)
        self.assertGreaterEqual(min(world.fields["tracer"].amounts_mol), 0)
        self.assertAlmostEqual(total_amount(world, "tracer"), 1)

    def test_returned_stability_limit_is_safe_for_decimal_grid_and_amount_scales(self):
        grid = RectilinearGrid3D((0.1,) * 3, (0.1,) * 3, (0.1,) * 3)
        dt = diffusion_timestep_limit_s(grid, 1.)
        for amount in (1e-24, 1e-12, 1., 1e12, 1e24):
            with self.subTest(amount=amount):
                amounts = [0.] * grid.voxel_count
                amounts[grid.flat_index(1, 1, 1)] = amount
                world = World(fields={"tracer": AmountField("tracer", tuple(amounts), grid.volumes_m3)})
                proposal = diffusion_step(world, grid, "tracer", 1., dt)
                proposal.commit(world, ALL)
                self.assertGreaterEqual(min(world.fields["tracer"].amounts_mol), 0.)
                self.assertTrue(math.isclose(total_amount(world, "tracer"), amount,
                                             rel_tol=1e-14, abs_tol=0.))

    def test_inward_boundary_flux_area_and_ledger(self):
        grid = RectilinearGrid3D((1, 2), (2, 3), (4, 5))
        world = world_for(grid, (0,) * grid.voxel_count)
        original = world.clone()
        proposal = diffusion_step(world, grid, "tracer", 0, 0.1,
                                  (BoundaryFlux(0, "upper", 2),))
        self.assertEqual(world, original)
        proposal.commit(world, ALL)
        self.assertAlmostEqual(total_amount(world, "tracer"), 9)
        self.assertEqual(len(world.ledger), 1)
        self.assertEqual(world.ledger[0].kind, "boundary")
        self.assertAlmostEqual(world.ledger[0].change_mol, 9)
        self.assertEqual(world.fields["tracer"].amounts_mol[grid.flat_index(0, 0, 0)], 0)
        self.assertAlmostEqual(world.fields["tracer"].amounts_mol[grid.flat_index(1, 1, 1)], 3)

    def test_six_boundary_faces_account_once_at_edges_and_corners(self):
        grid = RectilinearGrid3D((1., 2., 1.5), (1., 0.5, 2.), (2., 1., 0.75))
        fluxes = tuple(BoundaryFlux(axis, side, 0.1 * (1 + 2 * axis + (side == "upper")))
                       for axis in range(3) for side in ("lower", "upper"))
        dt = 0.25
        first = world_for(grid, (0.,) * grid.voxel_count)
        reverse = first.clone()
        proposal = diffusion_step(first, grid, "tracer", 0., dt, fluxes)
        self.assertEqual(total_amount(first, "tracer"), 0.)
        proposal.commit(first, ALL)
        diffusion_step(reverse, grid, "tracer", 0., dt, reversed(fluxes)).commit(reverse, ALL)
        self.assertEqual(first, reverse)
        self.assertEqual(len(first.ledger), 6)
        expected = []
        for voxel in range(grid.voxel_count):
            indices = grid.indices(voxel)
            widths = (grid.x_widths_m[indices[0]], grid.y_widths_m[indices[1]],
                      grid.z_widths_m[indices[2]])
            integrated = [flux.inward_mol_m2_s * grid.volumes_m3[voxel] / widths[flux.axis] * dt
                          for flux in fluxes
                          if indices[flux.axis] == (0 if flux.side == "lower"
                                                    else grid.shape[flux.axis] - 1)]
            expected.append(math.fsum(integrated))
        self.assertEqual(expected[grid.flat_index(1, 1, 1)], 0.)
        for actual, amount in zip(first.fields["tracer"].amounts_mol, expected):
            self.assertTrue(math.isclose(actual, amount, rel_tol=2e-15,
                                         abs_tol=1e-15))
        expected_total = math.fsum(expected)
        self.assertTrue(math.isclose(total_amount(first, "tracer"), expected_total,
                                      rel_tol=2e-15))
        self.assertTrue(math.isclose(math.fsum(entry.change_mol for entry in first.ledger),
                                      expected_total, rel_tol=2e-15))

    def test_late_boundary_overflow_rejects_entire_proposal(self):
        grid = RectilinearGrid3D((1., 1.), (2.,), (1.,))
        world = world_for(grid, (1., 0.))
        before = world.clone()
        with self.assertRaisesRegex(ValueError, "integrated boundary amount"):
            diffusion_step(world, grid, "tracer", 0., 2.,
                           (BoundaryFlux(0, "lower", 0.125),
                            BoundaryFlux(0, "upper", 1e308)))
        self.assertEqual(world, before)

    def test_each_exterior_face_uses_its_area(self):
        grid = RectilinearGrid3D((2,), (3,), (5,))
        for axis, area in enumerate((15, 10, 6)):
            for side in ("lower", "upper"):
                with self.subTest(axis=axis, side=side):
                    world = world_for(grid, (0,))
                    diffusion_step(world, grid, "tracer", 0, 0.25,
                                   (BoundaryFlux(axis, side, 2),)).commit(world, ALL)
                    self.assertEqual(total_amount(world, "tracer"), area * 0.5)

    def test_bad_boundary_contracts_rejected(self):
        for args in ((True, "lower", 1), (3, "lower", 1), (0, "periodic", 1),
                     (0, "lower", -1), (0, "lower", math.nan), (0, "lower", True)):
            with self.subTest(args=args), self.assertRaises((ValueError, TypeError)):
                BoundaryFlux(*args)
        grid = RectilinearGrid3D((1,), (1,), (1,))
        for boundaries in ((BoundaryFlux(0, "lower", 1),) * 2, ({"flux": 1},)):
            with self.subTest(boundaries=boundaries), self.assertRaises((ValueError, TypeError)):
                diffusion_step(world_for(grid), grid, "tracer", 0, 1, boundaries)

    def test_positive_diffusion_and_boundary_underflow_rejected(self):
        grid = RectilinearGrid3D((1., 1.), (1.,), (1.,))
        world = world_for(grid, (1e-200, 0.))
        original = world.clone()
        with self.assertRaisesRegex(ValueError, "underflow"):
            diffusion_step(world, grid, "tracer", 1e-200, 1e100)
        self.assertEqual(world, original)
        with self.assertRaisesRegex(ValueError, "underflow"):
            diffusion_step(world, grid, "tracer", 0., 1e-200,
                           (BoundaryFlux(0, "lower", 1e-200),))
        self.assertEqual(world, original)

    def test_zero_time_or_diffusion_and_single_voxel(self):
        grid = RectilinearGrid3D((1,), (1,), (1,))
        world = world_for(grid)
        for diffusivity, dt in ((1, 0), (0, 1), (1, 1)):
            original = world.clone()
            diffusion_step(world, grid, "tracer", diffusivity, dt).commit(world, ALL)
            self.assertEqual(world, original)
        self.assertEqual(diffusion_timestep_limit_s(grid, 1), math.inf)

    def test_bad_parameters_geometry_species_and_nonfinite_computation(self):
        grid = RectilinearGrid3D((1,), (1,), (1,))
        world = world_for(grid)
        for diffusivity, dt in ((-1, 1), (1, -1), (True, 1), (1, False), (math.nan, 1), (1, math.inf)):
            with self.subTest(diffusivity=diffusivity, dt=dt), self.assertRaises((ValueError, TypeError)):
                diffusion_step(world, grid, "tracer", diffusivity, dt)
        for species in ("missing", "", True):
            with self.subTest(species=species), self.assertRaises((ValueError, TypeError)):
                diffusion_step(world, grid, species, 1, 0.1)
        world.fields["tracer"].volumes_m3 = (2,)
        with self.assertRaisesRegex(ValueError, "volume"):
            diffusion_step(world, grid, "tracer", 1, 0.1)
        tiny = RectilinearGrid3D((1e-100,), (1e-100,), (1e-100,))
        overflow = World(fields={"tracer": AmountField("tracer", (1e100,), tiny.volumes_m3)})
        with self.assertRaises(ValueError):
            diffusion_step(overflow, tiny, "tracer", 0, 1)


class UptakeTests(unittest.TestCase):
    def test_saturation_zero_half_and_near_maximum(self):
        grid = RectilinearGrid3D((1, 1, 1), (1,), (1,))
        world = world_for(grid, (0, 1, 1e9))
        world.cells = {str(i): Cell(str(i), grid.center_m(i), 0.001) for i in range(3)}
        laws = tuple(CellUptake(str(i), 0.1, 1) for i in range(3))
        original = world.clone()
        proposal = saturable_uptake_step(world, grid, "tracer", laws, 1)
        self.assertEqual(world, original)
        proposal.commit(world, ALL)
        self.assertEqual(world.cells["0"].amounts_mol.get("tracer", 0), 0)
        self.assertEqual(world.cells["1"].amounts_mol["tracer"], 0.05)
        self.assertAlmostEqual(world.cells["2"].amounts_mol["tracer"], 0.1, places=9)
        self.assertAlmostEqual(total_amount(world, "tracer"), total_amount(original, "tracer"))
        self.assertEqual(world.ledger, [])

    def test_transfer_pairs_field_debit_with_cell_credit(self):
        grid = RectilinearGrid3D((2,), (3,), (4,))
        world = world_for(grid, (2,))
        world.cells["a"] = Cell("a", grid.center_m(0), 0.01, {"tracer": 3, "other": 7})
        saturable_uptake_step(world, grid, "tracer", (CellUptake("a", 3, 1),), 0.5).commit(world, ALL)
        self.assertEqual(world.fields["tracer"].amounts_mol, (47,))
        self.assertEqual(world.cells["a"].amounts_mol, {"tracer": 4, "other": 7})

    def test_competing_demand_is_simultaneous_and_order_independent(self):
        grid = RectilinearGrid3D((1,), (1,), (1,))
        a = world_for(grid)
        a.cells = {cid: Cell(cid, grid.center_m(0), 0.1) for cid in ("a", "b")}
        b = a.clone()
        laws = (CellUptake("a", 0.6, 1), CellUptake("b", 0.4, 1))
        saturable_uptake_step(a, grid, "tracer", laws, 1).commit(a, ALL)
        saturable_uptake_step(b, grid, "tracer", tuple(reversed(laws)), 1).commit(b, ALL)
        self.assertEqual(a, b)
        self.assertEqual(a.cells["a"].amounts_mol["tracer"], 0.3)
        self.assertEqual(a.cells["b"].amounts_mol["tracer"], 0.2)
        self.assertEqual(a.fields["tracer"].amounts_mol, (0.5,))

    def test_collective_overdraw_rejected_without_mutation(self):
        grid = RectilinearGrid3D((1,), (1,), (1,))
        world = world_for(grid)
        world.cells = {cid: Cell(cid, grid.center_m(0), 0.1) for cid in ("a", "b")}
        original = world.clone()
        with self.assertRaisesRegex(ValueError, "demand"):
            saturable_uptake_step(world, grid, "tracer",
                                 (CellUptake("a", 1.5, 1), CellUptake("b", 1.5, 1)), 1)
        self.assertEqual(world, original)

    def test_positive_uptake_underflow_is_rejected_without_mutation(self):
        grid = RectilinearGrid3D((1.,), (1.,), (1.,))
        for concentration, vmax, km, dt in ((1e-200, 1e200, 1e200, 1.),
                                           (1., 1e-300, 1., 1e-100),
                                           (1e-200, 1e-200, 1., 1.)):
            with self.subTest(concentration=concentration, vmax=vmax, km=km, dt=dt):
                world = world_for(grid, (concentration,))
                world.cells["a"] = Cell("a", grid.center_m(0), 0.1)
                original = world.clone()
                with self.assertRaisesRegex(ValueError, "underflow"):
                    saturable_uptake_step(world, grid, "tracer", (CellUptake("a", vmax, km),), dt)
                self.assertEqual(world, original)
        large = RectilinearGrid3D((1e100,), (1e100,), (1e100,))
        world = World(fields={"tracer": AmountField("tracer", (1e-200,), large.volumes_m3)},
                      cells={"a": Cell("a", large.center_m(0), 1.)})
        with self.assertRaisesRegex(ValueError, "concentration underflow"):
            saturable_uptake_step(world, large, "tracer", (CellUptake("a", 1., 1.),), 1.)

    def test_bad_laws_cells_and_dt_rejected(self):
        for args in (("", 1, 1), ("a", -1, 1), ("a", 1, 0), ("a", 1, -1),
                     ("a", True, 1), ("a", 1, math.nan), ("a", math.inf, 1)):
            with self.subTest(args=args), self.assertRaises((ValueError, TypeError)):
                CellUptake(*args)
        grid = RectilinearGrid3D((1,), (1,), (1,))
        world = world_for(grid)
        world.cells["a"] = Cell("a", grid.center_m(0), 0.1)
        for laws in ((CellUptake("missing", 1, 1),), (CellUptake("a", 1, 1),) * 2, ({"cell_id": "a"},)):
            with self.subTest(laws=laws), self.assertRaises((ValueError, TypeError)):
                saturable_uptake_step(world, grid, "tracer", laws, 0.1)
        for dt in (-1, True, math.nan):
            with self.subTest(dt=dt), self.assertRaises((ValueError, TypeError)):
                saturable_uptake_step(world, grid, "tracer", (), dt)
        world.cells["a"].position_m = (2, 0, 0)
        with self.assertRaises(ValueError):
            saturable_uptake_step(world, grid, "tracer", (CellUptake("a", 0, 1),), 0)

    def test_zero_step_is_noop(self):
        grid = RectilinearGrid3D((1,), (1,), (1,))
        world = world_for(grid)
        world.cells["a"] = Cell("a", grid.center_m(0), 0.1)
        original = world.clone()
        saturable_uptake_step(world, grid, "tracer", (CellUptake("a", 1, 1),), 0).commit(world, ALL)
        self.assertEqual(world, original)

    def test_scheduler_rolls_back_diffusion_before_failed_uptake(self):
        grid = RectilinearGrid3D((1, 1), (1,), (1,))
        world = world_for(grid, (1, 0))
        world.cells["a"] = Cell("a", grid.center_m(1), 0.1)
        original = world.clone()
        processes = [
            Process("diffusion", Fraction(1, 10), frozenset({"fields"}),
                    lambda w, dt: diffusion_step(w, grid, "tracer", 1, dt)),
            Process("uptake", Fraction(1, 10), frozenset({"cells", "fields"}),
                    lambda w, dt: saturable_uptake_step(w, grid, "tracer", (CellUptake("a", 100, 1),), dt)),
        ]
        with self.assertRaisesRegex(ValueError, "demand"):
            WindowStepper(processes, Fraction(1, 10)).advance(world, Fraction(1, 10))
        self.assertEqual(world, original)
