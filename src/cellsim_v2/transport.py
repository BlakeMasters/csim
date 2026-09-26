"""Fixed rectilinear 3D reference transport and one synthetic uptake interface.

Amounts (mol) remain authoritative. Internal face transfers use D*A/d between
cell centers; unlisted exterior faces are impermeable. Euler diffusion requires
dt * max_i(sum_j conductance_ij / volume_i) <= 1. Uptake samples the containing
voxel at the beginning of its process step and rejects collective overdraw.

These pure proposals have no fitted biological parameters, metabolism, moving
mesh, subvoxel membrane integration, advection, or independent-solver evidence.
Compose them with the existing explicitly ordered Lie-split WindowStepper.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, field, replace
import math
import sys
from typing import Iterable

from .state import AmountField, LedgerEntry, Update, World, identifier, number


_GEOMETRY_REL_TOL = 1e-12
_CFL_ROUNDOFF_MARGIN = 32 * sys.float_info.epsilon


def _positive(value: float, name: str) -> float:
    return number(value, name, positive=True)


def _represented_length(actual: float, nominal: float) -> None:
    if not math.isclose(actual, nominal, rel_tol=_GEOMETRY_REL_TOL, abs_tol=0.0):
        raise ValueError("represented coordinates distort the nominal grid geometry")


def _index(value: int, upper: int, name: str) -> int:
    if type(value) is not int or not 0 <= value < upper:
        raise ValueError(f"{name} must be an integer in [0, {upper})")
    return value


@dataclass(frozen=True)
class _Face:
    left: int
    right: int
    area_m2: float
    distance_m: float
    area_over_distance_m: float


@dataclass(frozen=True)
class RectilinearGrid3D:
    """Immutable orthogonal voxel geometry, x index varying fastest.

    Coordinates include both exterior boundaries. Exact internal edges belong
    to the voxel on their positive side; the maximum edge belongs to the last
    voxel. This convention applies to point sampling, not membrane geometry.
    Field volumes must match ``volumes_m3`` exactly; use that property when
    constructing AmountField. Represented edges, half-widths and adjacent center
    distances must match the nominal lengths within relative 1e-12 (zero
    absolute tolerance). Numerically unrepresentable geometry is refused.
    """

    x_widths_m: tuple[float, ...]
    y_widths_m: tuple[float, ...]
    z_widths_m: tuple[float, ...]
    origin_m: tuple[float, float, float] = (0.0, 0.0, 0.0)
    _edges: tuple[tuple[float, ...], ...] = field(init=False, repr=False)
    _centers: tuple[tuple[float, ...], ...] = field(init=False, repr=False)
    _volumes: tuple[float, ...] = field(init=False, repr=False)
    _faces: tuple[_Face, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        names = ("x_widths_m", "y_widths_m", "z_widths_m")
        for name in names:
            raw = getattr(self, name)
            if isinstance(raw, (str, bytes)):
                raise TypeError("axis widths must be a sequence of real numbers")
            values = tuple(_positive(x, name) for x in raw)
            if not values:
                raise ValueError("each grid axis needs at least one positive width")
            object.__setattr__(self, name, values)
        if len(self.origin_m) != 3:
            raise ValueError("origin must have three coordinates")
        object.__setattr__(self, "origin_m", tuple(number(x, "origin") for x in self.origin_m))
        edges, centers = [], []
        for widths, origin in zip(self._widths, self.origin_m):
            axis_edges, axis_centers = [origin], []
            for width in widths:
                edge = number(axis_edges[-1] + width, "grid edge")
                center = number(axis_edges[-1] + width / 2, "voxel center")
                if not axis_edges[-1] < center < edge:
                    raise ValueError("grid geometry cannot represent distinct edges and center")
                _represented_length(edge - axis_edges[-1], width)
                _represented_length(center - axis_edges[-1], width / 2)
                _represented_length(edge - center, width / 2)
                axis_edges.append(edge)
                axis_centers.append(center)
            edges.append(tuple(axis_edges))
            centers.append(tuple(axis_centers))
        object.__setattr__(self, "_edges", tuple(edges))
        object.__setattr__(self, "_centers", tuple(centers))
        volumes = tuple(_positive(x * y * z, "voxel volume")
                        for z in self.z_widths_m for y in self.y_widths_m for x in self.x_widths_m)
        object.__setattr__(self, "_volumes", volumes)
        faces = []
        for left in range(self.voxel_count):
            indices = self.indices(left)
            for axis in range(3):
                if indices[axis] == self.shape[axis] - 1:
                    continue
                adjacent = list(indices)
                adjacent[axis] += 1
                right = self.flat_index(*adjacent)
                area = self._face_area(indices, axis)
                distance = _positive(self._widths[axis][indices[axis]] / 2 +
                                     self._widths[axis][adjacent[axis]] / 2,
                                     "center distance")
                _represented_length(self._centers[axis][adjacent[axis]] -
                                    self._centers[axis][indices[axis]], distance)
                ratio = _positive(area / distance, "face area / center distance")
                faces.append(_Face(left, right, area, distance, ratio))
        object.__setattr__(self, "_faces", tuple(faces))

    @property
    def _widths(self) -> tuple[tuple[float, ...], ...]:
        return self.x_widths_m, self.y_widths_m, self.z_widths_m

    @property
    def shape(self) -> tuple[int, int, int]:
        return len(self.x_widths_m), len(self.y_widths_m), len(self.z_widths_m)

    @property
    def voxel_count(self) -> int:
        return math.prod(self.shape)

    @property
    def volumes_m3(self) -> tuple[float, ...]:
        return self._volumes

    def flat_index(self, i: int, j: int, k: int) -> int:
        nx, ny, nz = self.shape
        _index(i, nx, "x index")
        _index(j, ny, "y index")
        _index(k, nz, "z index")
        return i + nx * (j + ny * k)

    def indices(self, voxel: int) -> tuple[int, int, int]:
        _index(voxel, self.voxel_count, "voxel")
        nx, ny, _ = self.shape
        return voxel % nx, (voxel // nx) % ny, voxel // (nx * ny)

    def center_m(self, voxel: int) -> tuple[float, float, float]:
        i, j, k = self.indices(voxel)
        return self._centers[0][i], self._centers[1][j], self._centers[2][k]

    def locate(self, position_m: tuple[float, float, float]) -> int:
        if len(position_m) != 3:
            raise ValueError("position must have three components")
        indices = []
        for value, edges in zip(position_m, self._edges):
            value = number(value, "position")
            if value < edges[0] or value > edges[-1]:
                raise ValueError("cell position is outside the fixed transport grid")
            indices.append(min(bisect_right(edges, value) - 1, len(edges) - 2))
        return self.flat_index(*indices)

    def _face_area(self, indices: tuple[int, int, int], axis: int) -> float:
        other = [a for a in range(3) if a != axis]
        return _positive(self._widths[other[0]][indices[other[0]]] *
                         self._widths[other[1]][indices[other[1]]], "face area")


@dataclass(frozen=True)
class BoundaryFlux:
    """Uniform prescribed inward flux over one entire outer axis face.

    Units are mol/(m^2*s). Only nonnegative inflow is supported in this initial
    reference contract. Opposite faces may each supply an independently
    accounted flux; a face cannot occur twice in the same proposal.
    """

    axis: int
    side: str
    inward_mol_m2_s: float

    def __post_init__(self) -> None:
        _index(self.axis, 3, "boundary axis")
        if self.side not in ("lower", "upper"):
            raise ValueError("boundary side must be lower or upper")
        object.__setattr__(self, "inward_mol_m2_s",
                           number(self.inward_mol_m2_s, "inward boundary flux", minimum=0))


@dataclass(frozen=True)
class CellUptake:
    """Explicit per-cell saturable transfer: rate = vmax*c/(Km+c).

    vmax is in mol/s per cell; Km is in mol/m^3 and strictly positive. The same
    species is credited inside the cell; this is transport, not consumption or
    reaction stoichiometry. Parameters are supplied by the caller, never fitted
    or inferred here. No default biological parameter values are provided.
    """

    cell_id: str
    vmax_mol_s: float
    km_mol_m3: float

    def __post_init__(self) -> None:
        identifier(self.cell_id, "uptake cell id")
        object.__setattr__(self, "vmax_mol_s", number(self.vmax_mol_s, "vmax", minimum=0))
        object.__setattr__(self, "km_mol_m3", _positive(self.km_mol_m3, "Km"))


def _grid(grid: RectilinearGrid3D) -> None:
    if not isinstance(grid, RectilinearGrid3D):
        raise TypeError("transport requires RectilinearGrid3D")


def _field(world: World, grid: RectilinearGrid3D, species: str) -> tuple[AmountField, tuple[float, ...]]:
    _grid(grid)
    world.validate()
    identifier(species, "transport species")
    if species not in world.fields:
        raise ValueError("transport species has no field in this world")
    source = world.fields[species]
    if tuple(source.volumes_m3) != grid.volumes_m3:
        raise ValueError("field volumes must match transport grid volumes exactly")
    concentrations = tuple(number(n / v, "field concentration", minimum=0)
                           for n, v in zip(source.amounts_mol, grid.volumes_m3))
    if any(n > 0 and c == 0 for n, c in zip(source.amounts_mol, concentrations)):
        raise ValueError("positive field concentration underflow is unsupported")
    return source, concentrations


def diffusion_timestep_limit_s(grid: RectilinearGrid3D, diffusivity_m2_s: float) -> float:
    """Sufficient Euler positivity limit for the closed diffusion operator.

    The returned bound is 32 machine epsilons below the real-arithmetic row
    limit, rounded toward zero, to reserve roundoff room in face transfers.
    This is an engineering margin, not a proof for arbitrary floating-point
    magnitudes; unsupported arithmetic and negative results still reject.
    Nonnegative prescribed influx does not tighten the bound. A single voxel
    or zero diffusivity has no internal diffusion restriction (math.inf).
    """
    _grid(grid)
    diffusivity = number(diffusivity_m2_s, "diffusivity", minimum=0)
    if diffusivity == 0:
        return math.inf
    outgoing: list[list[float]] = [[] for _ in grid.volumes_m3]
    for face in grid._faces:
        # Use the same individual conductances as the transfer calculation.
        conductance = _positive(diffusivity * face.area_over_distance_m, "face conductance")
        outgoing[face.left].append(conductance)
        outgoing[face.right].append(conductance)
    rates = [_positive(math.fsum(values) / volume, "outgoing diffusion rate")
             for values, volume in zip(outgoing, grid.volumes_m3) if values]
    if not rates:
        return math.inf
    ideal_limit = _positive(1 / max(rates), "diffusion stability limit")
    return _positive(math.nextafter(ideal_limit * (1 - _CFL_ROUNDOFF_MARGIN), 0.),
                     "floating-point diffusion stability limit")


def diffusion_step(world: World, grid: RectilinearGrid3D, species: str,
                   diffusivity_m2_s: float, dt_s: float,
                   boundary_fluxes: Iterable[BoundaryFlux] = ()) -> Update:
    """Propose one conservative explicit diffusion step with optional influx.

    Every internal signed face amount is subtracted from one voxel and added
    to its neighbor. Boundary additions produce an equal integrated amount in
    the external ledger. Invalid steps are rejected without modifying world.
    Nonzero diffusion transfers or positive boundary additions that underflow
    to zero are unsupported and raise ValueError.
    """
    source, concentrations = _field(world, grid, species)
    dt = number(dt_s, "dt", minimum=0)
    diffusivity = number(diffusivity_m2_s, "diffusivity", minimum=0)
    limit = diffusion_timestep_limit_s(grid, diffusivity)
    if dt > limit:
        raise ValueError(f"explicit diffusion stability requires dt <= {limit!r} s")
    boundaries = tuple(boundary_fluxes)
    seen = set()
    for boundary in boundaries:
        if not isinstance(boundary, BoundaryFlux):
            raise TypeError("boundary fluxes must be BoundaryFlux values")
        key = boundary.axis, boundary.side
        if key in seen:
            raise ValueError("duplicate boundary face flux")
        seen.add(key)
    if dt == 0:
        return Update()
    increments: list[list[float]] = [[] for _ in source.amounts_mol]
    if diffusivity:
        for face in grid._faces:
            conductance = _positive(diffusivity * face.area_over_distance_m, "face conductance")
            difference = concentrations[face.left] - concentrations[face.right]
            amount = number(conductance * difference * dt,
                            "integrated internal face amount")
            if difference != 0 and amount == 0:
                raise ValueError("nonzero internal face amount underflow is unsupported")
            increments[face.left].append(-amount)
            increments[face.right].append(amount)
    ledger = []
    for boundary in sorted(boundaries, key=lambda b: (b.axis, b.side)):
        face_coordinate = 0 if boundary.side == "lower" else grid.shape[boundary.axis] - 1
        integrated = []
        for voxel in range(grid.voxel_count):
            indices = grid.indices(voxel)
            if indices[boundary.axis] == face_coordinate:
                amount = number(boundary.inward_mol_m2_s * grid._face_area(indices, boundary.axis) * dt,
                                "integrated boundary amount", minimum=0)
                if boundary.inward_mol_m2_s > 0 and amount == 0:
                    raise ValueError("positive boundary amount underflow is unsupported")
                increments[voxel].append(amount)
                integrated.append(amount)
        total = number(math.fsum(integrated), "total boundary amount", minimum=0)
        if total:
            ledger.append(LedgerEntry(species, total, "boundary",
                                     f"prescribed inward flux: axis {boundary.axis} {boundary.side}"))
    amounts = tuple(number(math.fsum([amount, *changes]), "updated field amount", minimum=0)
                    for amount, changes in zip(source.amounts_mol, increments))
    updated = replace(source, amounts_mol=amounts)
    updated.validate()
    return Update(replace_fields={species: updated}, ledger=tuple(ledger))


def saturable_uptake_step(world: World, grid: RectilinearGrid3D, species: str,
                         uptake_laws: Iterable[CellUptake], dt_s: float) -> Update:
    """Propose simultaneous point-sampled membrane transfers for selected cells.

    All demands use the same input field. Each selected cell may appear once.
    Collective voxel overdraw rejects the entire proposal; rates are never
    clipped or reduced to allocate scarce material. Reduce dt explicitly.
    Underflow of a positive concentration, saturation, rate, or integrated
    amount is unsupported and raises ValueError instead of disabling uptake.
    """
    source, concentrations = _field(world, grid, species)
    dt = number(dt_s, "dt", minimum=0)
    laws = tuple(uptake_laws)
    seen, located = set(), []
    for law in laws:
        if not isinstance(law, CellUptake):
            raise TypeError("uptake laws must be CellUptake values")
        if law.cell_id in seen:
            raise ValueError("duplicate cell uptake law")
        if law.cell_id not in world.cells:
            raise ValueError("uptake law refers to an unknown cell")
        seen.add(law.cell_id)
        located.append((law, grid.locate(world.cells[law.cell_id].position_m)))
    if dt == 0 or not laws:
        return Update()
    demands: list[list[float]] = [[] for _ in source.amounts_mol]
    transfers = []
    for law, voxel in sorted(located, key=lambda pair: pair[0].cell_id):
        concentration = concentrations[voxel]
        if concentration == 0 or law.vmax_mol_s == 0:
            continue
        # Equivalent saturation ratio with no overflowing Km+c sum.
        if concentration <= law.km_mol_m3:
            ratio = concentration / law.km_mol_m3
            saturation = ratio / (1 + ratio)
        else:
            saturation = 1 / (1 + law.km_mol_m3 / concentration)
        if saturation == 0:
            raise ValueError("positive uptake saturation underflow is unsupported")
        rate = number(law.vmax_mol_s * saturation, "cell uptake rate", minimum=0)
        amount = number(rate * dt, "cell uptake amount", minimum=0)
        if rate == 0 or amount == 0:
            raise ValueError("positive uptake rate or integrated amount underflow is unsupported")
        demands[voxel].append(amount)
        transfers.append((law.cell_id, amount))
    totals = tuple(number(math.fsum(values), "collective uptake demand", minimum=0) for values in demands)
    if any(demand > available for demand, available in zip(totals, source.amounts_mol)):
        raise ValueError("collective uptake demand exceeds available voxel amount; reduce dt")
    cells = {}
    for cell_id, amount in transfers:
        if amount == 0:
            continue
        cell = world.cells[cell_id]
        intracellular = dict(cell.amounts_mol)
        intracellular[species] = number(intracellular.get(species, 0.0) + amount,
                                        "updated intracellular amount", minimum=0)
        cells[cell_id] = replace(cell, amounts_mol=intracellular)
    updated = replace(source, amounts_mol=tuple(available - demand
                                               for available, demand in zip(source.amounts_mol, totals)))
    updated.validate()
    return Update(replace_cells=cells, replace_fields={species: updated})
