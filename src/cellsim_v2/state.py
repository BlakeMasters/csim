"""SI-valued, amount-based state and single-threaded atomic updates.

The object graph is mutable for inspection, but processes receive deep copies.
Updates use full replacements, never ambiguous increments. This is not a sandbox.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction
import copy
import math
from typing import Any


def number(value: float, name: str, *, minimum: float | None = None,
           positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number, not {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")
    return float(value)


def time_fraction(value: int | float | str | Fraction) -> Fraction:
    if isinstance(value, bool):
        raise TypeError("boolean time is invalid")
    if isinstance(value, float):
        number(value, "time")
    result = Fraction(str(value)) if not isinstance(value, Fraction) else value
    if result < 0:
        raise ValueError("negative time")
    return result


def identifier(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a nonempty string")


@dataclass
class Cell:
    id: str
    position_m: tuple[float, float, float]
    volume_m3: float
    amounts_mol: dict[str, float] = field(default_factory=dict)
    drag_Ns_per_m: float = 1.0
    parent_id: str | None = None
    division_count: int = 0

    @property
    def radius_m(self) -> float:
        return (3.0 * self.volume_m3 / (4.0 * math.pi)) ** (1.0 / 3.0)

    def validate(self) -> None:
        identifier(self.id, "cell id")
        if len(self.position_m) != 3:
            raise ValueError("position must have three components")
        for x in self.position_m:
            number(x, "position")
        number(self.volume_m3, "cell volume", positive=True)
        number(self.drag_Ns_per_m, "drag", positive=True)
        if type(self.division_count) is not int or self.division_count < 0:
            raise ValueError("invalid division_count")
        if self.parent_id is not None:
            identifier(self.parent_id, "parent_id")
        for species, amount in self.amounts_mol.items():
            identifier(species, "species")
            number(amount, "intracellular amount", minimum=0)


@dataclass
class AmountField:
    species: str
    amounts_mol: tuple[float, ...]
    volumes_m3: tuple[float, ...]

    def validate(self) -> None:
        identifier(self.species, "species")
        if not self.amounts_mol or len(self.amounts_mol) != len(self.volumes_m3):
            raise ValueError("amounts and volumes need identical nonzero lengths")
        for amount, volume in zip(self.amounts_mol, self.volumes_m3):
            number(amount, "field amount", minimum=0)
            number(volume, "voxel volume", positive=True)

    @property
    def concentrations_mol_m3(self) -> tuple[float, ...]:
        self.validate()
        return tuple(n / v for n, v in zip(self.amounts_mol, self.volumes_m3))

    @classmethod
    def from_concentrations(cls, species: str, concentrations: tuple[float, ...],
                            volumes: tuple[float, ...]) -> "AmountField":
        if len(concentrations) != len(volumes):
            raise ValueError("concentration/volume length mismatch")
        for c in concentrations:
            number(c, "concentration", minimum=0)
        for v in volumes:
            number(v, "volume", positive=True)
        result = cls(species, tuple(c*v for c, v in zip(concentrations, volumes)),
                     tuple(volumes))
        result.validate()
        return result


@dataclass(frozen=True)
class LedgerEntry:
    species: str
    change_mol: float
    kind: str
    reason: str

    def validate(self) -> None:
        identifier(self.species, "species")
        number(self.change_mol, "ledger change")
        if self.kind not in {"boundary", "source", "sink", "reaction"}:
            raise ValueError("unsupported ledger category")
        identifier(self.reason, "ledger reason")


@dataclass(frozen=True)
class Event:
    id: str
    time_s: str
    kind: str
    subject: str
    related: tuple[str, ...] = ()

    def validate(self) -> None:
        for value in (self.id, self.kind, self.subject):
            identifier(value, "event value")
        time_fraction(self.time_s)
        for value in self.related:
            identifier(value, "related id")


@dataclass
class World:
    time_s: Fraction = Fraction(0)
    step: int = 0
    cells: dict[str, Cell] = field(default_factory=dict)
    fields: dict[str, AmountField] = field(default_factory=dict)
    ledger: list[LedgerEntry] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)

    def clone(self) -> "World":
        return copy.deepcopy(self)

    def validate(self) -> None:
        if not isinstance(self.time_s, Fraction) or self.time_s < 0:
            raise ValueError("world time must be a nonnegative Fraction")
        if type(self.step) is not int or self.step < 0:
            raise ValueError("step must be a nonnegative integer")
        for key, cell in self.cells.items():
            cell.validate()
            if key != cell.id:
                raise ValueError("cell dictionary key differs from cell id")
        for key, field_value in self.fields.items():
            field_value.validate()
            if key != field_value.species:
                raise ValueError("field key differs from species")
        seen = set()
        for event in self.events:
            event.validate()
            if event.id in seen:
                raise ValueError("duplicate event id")
            seen.add(event.id)
        for entry in self.ledger:
            entry.validate()

    def overwrite(self, validated: "World") -> None:
        # Single-threaded transaction boundary. Existing subobject handles become stale.
        candidate = validated.clone()
        candidate.validate()
        self.__dict__.update(candidate.__dict__)


def species_set(world: World) -> set[str]:
    return set(world.fields) | {s for c in world.cells.values() for s in c.amounts_mol}


def total_amount(world: World, species: str) -> float:
    terms = [c.amounts_mol.get(species, 0.0) for c in world.cells.values()]
    if species in world.fields:
        terms.extend(world.fields[species].amounts_mol)
    return math.fsum(terms)


@dataclass(frozen=True)
class Balance:
    before_mol: float
    after_mol: float
    expected_change_mol: float
    signed_residual_mol: float
    absolute_error_mol: float


def balance(before: World, after: World, species: str,
            expected_change_mol: float = 0.0) -> Balance:
    number(expected_change_mol, "expected change")
    a, b = total_amount(before, species), total_amount(after, species)
    residual = (b-a) - expected_change_mol
    return Balance(a, b, expected_change_mol, residual, abs(residual))


@dataclass
class Update:
    replace_cells: dict[str, Cell] = field(default_factory=dict)
    births: tuple[Cell, ...] = ()
    removals: tuple[str, ...] = ()
    replace_fields: dict[str, AmountField] = field(default_factory=dict)
    ledger: tuple[LedgerEntry, ...] = ()
    events: tuple[Event, ...] = ()

    def touched(self) -> set[str]:
        return ({"cells"} if self.replace_cells or self.births or self.removals else set()) |                ({"fields"} if self.replace_fields else set()) |                ({"ledger"} if self.ledger else set()) |                ({"events"} if self.events else set())

    def commit(self, world: World, allowed_writes: frozenset[str], *,
               atol_mol: float = 1e-18, rtol: float = 1e-12) -> None:
        """Preflight and balance-check a copy, then publish. No partial mutation."""
        world.validate()
        number(atol_mol, "atol", minimum=0)
        number(rtol, "rtol", minimum=0)
        if self.touched() - set(allowed_writes):
            raise PermissionError(f"undeclared write: {self.touched()-set(allowed_writes)}")
        candidate = world.clone()
        if len(set(self.removals)) != len(self.removals):
            raise ValueError("duplicate removal")
        if set(self.removals) & set(self.replace_cells):
            raise ValueError("cannot replace and remove the same cell")
        for cid, cell in self.replace_cells.items():
            if cid not in candidate.cells or cell.id != cid:
                raise ValueError("unknown replacement or id mismatch")
            candidate.cells[cid] = copy.deepcopy(cell)
        for cid in self.removals:
            if cid not in candidate.cells:
                raise ValueError("unknown removal")
            del candidate.cells[cid]
        birth_ids = [c.id for c in self.births]
        if len(set(birth_ids)) != len(birth_ids) or set(birth_ids) & set(world.cells):
            raise ValueError("duplicate or reused cell id")
        for cell in self.births:
            candidate.cells[cell.id] = copy.deepcopy(cell)
        for species, value in self.replace_fields.items():
            if species not in candidate.fields or species != value.species:
                raise ValueError("unknown field or field key mismatch")
            candidate.fields[species] = copy.deepcopy(value)
        candidate.ledger.extend(copy.deepcopy(self.ledger))
        candidate.events.extend(copy.deepcopy(self.events))
        candidate.validate()
        all_species = species_set(world) | species_set(candidate) | {e.species for e in self.ledger}
        for species in all_species:
            expected = math.fsum(e.change_mol for e in self.ledger if e.species == species)
            b = balance(world, candidate, species, expected)
            tolerance = atol_mol + rtol*max(abs(b.before_mol), abs(b.after_mol), abs(expected))
            if b.absolute_error_mol > tolerance:
                raise ValueError(f"unaccounted amount change for {species}: {b.signed_residual_mol}")
        world.overwrite(candidate)
