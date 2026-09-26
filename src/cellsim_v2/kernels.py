"""Explicitly limited reference laws; none is calibrated to a biological sample."""
from __future__ import annotations
from dataclasses import replace
import math
from .state import (AmountField, Cell, Event, LedgerEntry, Update, World, number)


def linear_contact(world: World, dt_s: float, stiffness_N_per_m: float = 0.5) -> Update:
    """Overdamped pair-spring Euler step; frozen positions and equal/opposite forces.

    O(N^2). Coincident centers have no unique normal and are rejected, not jittered.
    The stiffness is an illustrative parameter, not a cancer-cell constitutive law.
    """
    world.validate()
    number(dt_s, "dt", minimum=0)
    number(stiffness_N_per_m, "stiffness", minimum=0)
    if dt_s == 0 or stiffness_N_per_m == 0:
        return Update()
    ids = sorted(world.cells)
    forces = {cid: [0.0, 0.0, 0.0] for cid in ids}
    for i, aid in enumerate(ids):
        a = world.cells[aid]
        for bid in ids[i+1:]:
            b = world.cells[bid]
            d = tuple(a.position_m[k]-b.position_m[k] for k in range(3))
            distance = math.sqrt(math.fsum(v*v for v in d))
            if distance == 0:
                raise ValueError("coincident centers: contact normal undefined")
            overlap = a.radius_m + b.radius_m - distance
            if overlap <= 0:
                continue
            for k in range(3):
                f = stiffness_N_per_m*overlap*d[k]/distance
                forces[aid][k] += f
                forces[bid][k] -= f
    return Update(replace_cells={
        cid: replace(world.cells[cid], position_m=tuple(
            world.cells[cid].position_m[k]+dt_s*forces[cid][k]/world.cells[cid].drag_Ns_per_m
            for k in range(3))) for cid in ids})


def euler_decay(world: World, species: str, rate_per_s: float, dt_s: float) -> Update:
    number(rate_per_s, "decay rate", minimum=0)
    number(dt_s, "dt", minimum=0)
    if rate_per_s*dt_s > 1:
        raise ValueError("Euler decay positivity requires rate*dt <= 1")
    f = world.fields[species]
    updated = tuple(n*(1-rate_per_s*dt_s) for n in f.amounts_mol)
    change = math.fsum(updated)-math.fsum(f.amounts_mol)
    return Update(replace_fields={species: replace(f, amounts_mol=updated)},
                  ledger=(LedgerEntry(species, change, "sink", "declared first-order loss"),))


def transfer_to_cell(world: World, species: str, voxel: int, cid: str,
                     amount_mol: float) -> Update:
    """Finite material transfer; not a membrane kinetic law."""
    number(amount_mol, "transfer", minimum=0)
    f = world.fields[species]
    if type(voxel) is not int or not 0 <= voxel < len(f.amounts_mol):
        raise ValueError("voxel out of range")
    if amount_mol > f.amounts_mol[voxel]:
        raise ValueError("transfer exceeds available amount")
    a = list(f.amounts_mol)
    a[voxel] -= amount_mol
    cell = world.cells[cid]
    intracellular = dict(cell.amounts_mol)
    intracellular[species] = intracellular.get(species, 0)+amount_mol
    return Update(replace_fields={species: replace(f, amounts_mol=tuple(a))},
                  replace_cells={cid: replace(cell, amounts_mol=intracellular)})


def divide_retained_slot(world: World, cid: str, separation_m: float = 0.0) -> Update:
    """One storage slot retained + one new slot; halves volume and amounts.

    This is bookkeeping, not cytokinesis. The event carries the pre-split identity.
    Co-located children (default) must not be sent to contact until placed explicitly.
    """
    number(separation_m, "separation", minimum=0)
    old = world.cells[cid]
    event_number = old.division_count+1
    new_id = f"{cid}::daughter::{event_number}"
    event_id = f"{cid}::division::{event_number}"
    if new_id in world.cells or any(e.id == event_id for e in world.events):
        raise ValueError("division id collision; no automatic rename")
    left = dict(old.amounts_mol)
    for species in left:
        left[species] *= 0.5
    right = {s: old.amounts_mol[s]-left[s] for s in left}
    p1 = (old.position_m[0]-separation_m/2, *old.position_m[1:])
    p2 = (old.position_m[0]+separation_m/2, *old.position_m[1:])
    retained = replace(old, volume_m3=old.volume_m3/2, amounts_mol=left,
                       position_m=p1, division_count=event_number)
    child = Cell(new_id, p2, old.volume_m3-retained.volume_m3, right,
                 old.drag_Ns_per_m, parent_id=cid)
    return Update(replace_cells={cid: retained}, births=(child,),
                  events=(Event(event_id, str(world.time_s), "division", cid, (cid, new_id)),))


def periodic_diffusion(field: AmountField, dx_m: float, area_m2: float,
                       diffusivity_m2_s: float, dt_s: float) -> AmountField:
    """Uniform finite-volume, nearest-face Euler diffusion on a periodic 1D ring."""
    field.validate()
    for x, name in ((dx_m,"dx"), (area_m2,"area")):
        number(x, name, positive=True)
    number(diffusivity_m2_s, "D", minimum=0)
    number(dt_s, "dt", minimum=0)
    n = len(field.amounts_mol)
    if n < 3:
        raise ValueError("periodic ring requires at least 3 voxels")
    if any(not math.isclose(v, dx_m*area_m2, rel_tol=1e-12, abs_tol=0.0)
           for v in field.volumes_m3):
        raise ValueError("this kernel requires uniform volumes dx*area")
    if diffusivity_m2_s*dt_s/dx_m**2 > 0.5:
        raise ValueError("explicit diffusion requires D*dt/dx^2 <= 0.5")
    c = field.concentrations_mol_m3
    increments = [0.0]*n
    for i in range(n):
        j = (i+1)%n
        amount = diffusivity_m2_s*area_m2/dx_m*(c[i]-c[j])*dt_s
        increments[i] -= amount
        increments[j] += amount
    result = replace(field, amounts_mol=tuple(a+d for a,d in zip(field.amounts_mol,increments)))
    result.validate()  # no silent negative clipping
    return result


def radial_constant_uptake(n: int, radius_m: float, diffusivity_m2_s: float,
                           uptake_mol_m3_s: float, boundary_mol_m3: float) -> tuple[tuple[float,...], tuple[float,...]]:
    """Steady radial FV sphere, constant uptake, central no-flux and surface Dirichlet.

    Uses a tridiagonal solve. Fixed geometry, no cells, no hypoxic transition rules.
    Negative concentration means the constant-uptake regime is invalid: reject it.
    """
    if type(n) is not int or n < 2:
        raise ValueError("need at least two shells")
    for x, name in ((radius_m,"R"),(diffusivity_m2_s,"D")):
        number(x,name,positive=True)
    number(uptake_mol_m3_s,"uptake",minimum=0)
    number(boundary_mol_m3,"boundary concentration",minimum=0)
    if boundary_mol_m3 - uptake_mol_m3_s*radius_m**2/(6*diffusivity_m2_s) < 0:
        raise ValueError("constant uptake would give negative center concentration")
    dr = radius_m/n
    a,b,c,rhs = [],[],[],[]
    for i in range(n):
        rl,rr = i*dr,(i+1)*dr
        vol = 4*math.pi/3*(rr**3-rl**3)
        gl = diffusivity_m2_s*4*math.pi*rl**2/dr if i else 0
        gr = diffusivity_m2_s*4*math.pi*rr**2/(dr/2 if i==n-1 else dr)
        a.append(-gl); b.append(gl+gr); c.append(-gr if i<n-1 else 0)
        rhs.append(-uptake_mol_m3_s*vol+(gr*boundary_mol_m3 if i==n-1 else 0))
    for i in range(1,n):
        factor = a[i]/b[i-1]
        b[i] -= factor*c[i-1]
        rhs[i] -= factor*rhs[i-1]
    solution = [0.0]*n
    solution[-1] = rhs[-1]/b[-1]
    for i in range(n-2,-1,-1):
        solution[i] = (rhs[i]-c[i]*solution[i+1])/b[i]
    for value in solution:
        number(value,"concentration",minimum=0)
    return tuple((i+0.5)*dr for i in range(n)), tuple(solution)
