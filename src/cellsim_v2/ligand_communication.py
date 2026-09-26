"""Synthetic two-cell secretion into a field and non-consuming field sensing.

The sender transfers a finite tracked amount of one synthetic species into its
voxel. The receiver's dimensionless H02 response memory samples the accepted
pre-step field concentration; it does not bind or consume the species. This is
an explicit discrete staging choice, not receptor kinetics or a biological law.
All amounts and private response state publish only after both proposals pass.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, replace
from fractions import Fraction
import hashlib
import json
import math

from .checkpoint import canonical_bytes, decode_world, encode_world
from .response_memory import (
    advance_response, create_relaxation_model, initialize_response,
)
from .state import AmountField, Cell, Update, World, identifier, number, total_amount
from .transport import RectilinearGrid3D


FORMAT = "cellsim-synthetic-ligand-communication/1"
SPECIES = "synthetic_ligand"
SENDER_ID = "sender"
RECEIVER_ID = "receiver"
GRID = RectilinearGrid3D((0.5,), (0.5,), (0.5,))
_ACTION_KEYS = {
    "kind", "quantity_type", "source_cell_id", "species", "context_id",
    "model_digest_sha256", "interval_start_s", "interval_end_s", "rate_mol_s",
}
_CONFIG_KEYS = {"horizon_steps", "step_s", "initial_sender_amount_mol"}


class LigandRejected(ValueError):
    """No accepted world, private memory, or stage clock changed."""


@dataclass(frozen=True)
class SecretionRate:
    """Cell-to-field amount rate in mol/s, not integrated mol or concentration."""

    source_cell_id: str
    species: str
    rate_mol_s: float

    def __post_init__(self) -> None:
        identifier(self.source_cell_id, "secretion source cell")
        identifier(self.species, "secretion species")
        object.__setattr__(self, "rate_mol_s", number(
            self.rate_mol_s, "secretion rate", minimum=0,
        ))


def secretion_step(world: World, grid: RectilinearGrid3D,
                   secretion: SecretionRate, dt_s: float) -> Update:
    """Pure paired source-cell debit and containing-voxel credit.

    A positive rate whose integrated amount vanishes at float precision, a
    demand beyond the finite cell inventory, or an unrepresentable debit/credit
    is rejected. No amount is clipped and no external ledger entry is needed.
    """
    if not isinstance(grid, RectilinearGrid3D):
        raise TypeError("secretion requires RectilinearGrid3D")
    if not isinstance(secretion, SecretionRate):
        raise TypeError("secretion requires SecretionRate")
    dt = number(dt_s, "secretion interval", minimum=0)
    world.validate()
    if secretion.source_cell_id not in world.cells:
        raise ValueError("unknown secretion source cell")
    if secretion.species not in world.fields:
        raise ValueError("missing secretion field species")
    source = world.cells[secretion.source_cell_id]
    field = world.fields[secretion.species]
    if field.volumes_m3 != grid.volumes_m3:
        raise ValueError("secretion field volumes differ from the fixed grid")
    voxel = grid.locate(source.position_m)
    if dt == 0 or secretion.rate_mol_s == 0:
        return Update()
    amount = number(secretion.rate_mol_s * dt, "integrated secretion amount", minimum=0)
    if amount == 0:
        raise ValueError("positive integrated secretion amount underflow")
    available = source.amounts_mol.get(secretion.species, 0.0)
    if amount > available:
        raise ValueError("secretion exceeds finite source cell inventory")
    remaining = number(available - amount, "remaining source amount", minimum=0)
    credited = number(field.amounts_mol[voxel] + amount, "credited field amount", minimum=0)
    if remaining == available or credited == field.amounts_mol[voxel]:
        raise ValueError("secretion amount is unrepresentable at current precision")
    source_amounts = dict(source.amounts_mol)
    source_amounts[secretion.species] = remaining
    field_amounts = list(field.amounts_mol)
    field_amounts[voxel] = credited
    return Update(
        replace_cells={secretion.source_cell_id: replace(source, amounts_mol=source_amounts)},
        replace_fields={secretion.species: replace(field, amounts_mol=tuple(field_amounts))},
    )


class LigandCommunicationEpisode:
    """Single-threaded, fixed-topology synthetic sender/receiver episode."""

    def __init__(self, *, horizon_steps: int = 3, step_s: float = 0.5,
                 initial_sender_amount_mol: float = 0.1):
        if type(horizon_steps) is not int or not 1 <= horizon_steps <= 10000:
            raise ValueError("horizon_steps must be an integer in [1, 10000]")
        step = number(step_s, "step_s", positive=True)
        amount = number(initial_sender_amount_mol, "initial sender amount", minimum=0)
        if not math.isfinite(float(Fraction(str(step)) * horizon_steps)):
            raise ValueError("episode horizon is not finite")
        self._config = {
            "horizon_steps": horizon_steps,
            "step_s": step,
            "initial_sender_amount_mol": amount,
        }
        self._step_fraction = Fraction(str(step))
        self._model = create_relaxation_model(
            model_id="synthetic-ligand-sensor-v1",
            context_id="synthetic-ligand-context-v1",
            tau_s=0.5,
            target_intercept=0.0,
            target_slope_m3_per_mol=1.0,
        )
        self._accepted: tuple[World, dict, int]
        self.reset()

    def _initial_accepted(self) -> tuple[World, dict, int]:
        world = World(
            cells={
                SENDER_ID: Cell(SENDER_ID, GRID.center_m(0), 1e-6,
                                {SPECIES: self._config["initial_sender_amount_mol"]}),
                RECEIVER_ID: Cell(RECEIVER_ID, GRID.center_m(0), 1e-6),
            },
            fields={SPECIES: AmountField(SPECIES, (0.0,), GRID.volumes_m3)},
        )
        response = initialize_response(
            self._model, entity_id=RECEIVER_ID, initial_memory=0.0,
            accepted_time_s=0.0,
            initialization_provenance={
                "kind": "declared_synthetic_initial_state",
                "source_id": "ligand_communication/v1",
            },
        )
        return world, response, 0

    def reset(self) -> dict:
        self._accepted = self._initial_accepted()
        return self.observe()

    def observe(self) -> dict:
        """Current shared field plus receiver's accepted private response."""
        world, response, steps = self._accepted
        terminated = steps >= self._config["horizon_steps"]
        return {
            "time_s": float(world.time_s),
            "next_time_s": None if terminated else float(world.time_s + self._step_fraction),
            "field_concentration_mol_m3": world.fields[SPECIES].concentrations_mol_m3[0],
            "sender_amount_mol": world.cells[SENDER_ID].amounts_mol.get(SPECIES, 0.0),
            "receiver_amount_mol": world.cells[RECEIVER_ID].amounts_mol.get(SPECIES, 0.0),
            "receiver_memory": response["memory"],
            "memory_unit": "1",
            "remaining_steps": self._config["horizon_steps"] - steps,
            "terminated": terminated,
        }

    def make_action(self, rate_mol_s: float) -> dict:
        world, response, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise LigandRejected("episode is terminated")
        try:
            rate = number(rate_mol_s, "secretion rate", minimum=0)
        except (ValueError, TypeError) as exc:
            raise LigandRejected(str(exc)) from exc
        return {
            "kind": "finite_cell_to_field_secretion",
            "quantity_type": "rate_mol_s",
            "source_cell_id": SENDER_ID,
            "species": SPECIES,
            "context_id": response["context_id"],
            "model_digest_sha256": response["model_digest_sha256"],
            "interval_start_s": float(world.time_s),
            "interval_end_s": float(world.time_s + self._step_fraction),
            "rate_mol_s": rate,
        }

    def _validate_action(self, action: object) -> float:
        if type(action) is not dict or set(action) != _ACTION_KEYS:
            raise ValueError("action must contain exactly the typed secretion fields")
        world, response, _ = self._accepted
        if (action["kind"] != "finite_cell_to_field_secretion" or
                action["quantity_type"] != "rate_mol_s"):
            raise ValueError("unsupported secretion action type")
        if (action["source_cell_id"] != SENDER_ID or action["species"] != SPECIES or
                action["context_id"] != response["context_id"] or
                action["model_digest_sha256"] != response["model_digest_sha256"]):
            raise ValueError("secretion action identity mismatch")
        start = number(action["interval_start_s"], "interval start", minimum=0)
        end = number(action["interval_end_s"], "interval end", minimum=0)
        if start != float(world.time_s) or end != float(world.time_s + self._step_fraction):
            raise ValueError("secretion action interval differs from accepted clock")
        return number(action["rate_mol_s"], "secretion rate", minimum=0)

    def step(self, action: dict) -> dict:
        world, response, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise LigandRejected("episode is terminated")
        start = world.time_s
        end = start + self._step_fraction
        try:
            rate = self._validate_action(action)
            sensed = world.fields[SPECIES].concentrations_mol_m3[0]
            response_result = advance_response(
                self._model, copy.deepcopy(response),
                exposure_concentration_mol_m3=sensed, end_time_s=float(end),
            )
            candidate = world.clone()
            proposal = secretion_step(candidate, GRID,
                                      SecretionRate(SENDER_ID, SPECIES, rate),
                                      float(self._step_fraction))
            proposal.commit(candidate, frozenset({"cells", "fields"}))
            balance_error = abs(total_amount(candidate, SPECIES) - total_amount(world, SPECIES))
            if balance_error > 1e-12:
                raise ValueError("secretion changed the closed amount total")
            if candidate.cells[RECEIVER_ID].amounts_mol != world.cells[RECEIVER_ID].amounts_mol:
                raise ValueError("non-consuming sensing altered receiver inventory")
            candidate.time_s = end
            candidate.step = steps + 1
            candidate.validate()
            if response_result["state"]["accepted_time_s"] != float(end):
                raise ValueError("receiver response clock differs from field clock")
            transferred = (world.cells[SENDER_ID].amounts_mol.get(SPECIES, 0.0)
                           - candidate.cells[SENDER_ID].amounts_mol.get(SPECIES, 0.0))
        except (ValueError, TypeError, PermissionError) as exc:
            raise LigandRejected(str(exc)) from exc
        self._accepted = (candidate, response_result["state"], steps + 1)
        return {
            "observation": self.observe(),
            "terminated": steps + 1 >= self._config["horizon_steps"],
            "info": {
                "response_observation": response_result["observations"][0],
                "sensed_pre_step_concentration_mol_m3": sensed,
                "sense_sample_time_s": float(start),
                "sense_interval_end_s": float(end),
                "secretion_interval_start_s": float(start),
                "secretion_interval_end_s": float(end),
                "integrated_transfer_mol": transferred,
                "absolute_balance_error_mol": balance_error,
            },
        }

    def checkpoint(self) -> dict:
        world, response, steps = self._accepted
        payload = {
            "format": FORMAT,
            "configuration": copy.deepcopy(self._config),
            "model": copy.deepcopy(self._model),
            "response_state": copy.deepcopy(response),
            "world": encode_world(world),
            "accepted_steps": steps,
        }
        payload = json.loads(canonical_bytes(payload))
        return {"payload": payload,
                "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}

    @classmethod
    def from_checkpoint(cls, checkpoint: object) -> "LigandCommunicationEpisode":
        if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
            raise ValueError("invalid ligand checkpoint wrapper")
        payload = checkpoint["payload"]
        if type(payload) is not dict or set(payload) != {
                "format", "configuration", "model", "response_state", "world", "accepted_steps"}:
            raise ValueError("invalid ligand checkpoint payload")
        if hashlib.sha256(canonical_bytes(payload)).hexdigest() != checkpoint["sha256"]:
            raise ValueError("ligand checkpoint hash mismatch")
        if payload["format"] != FORMAT:
            raise ValueError("unsupported ligand checkpoint format")
        config = payload["configuration"]
        if type(config) is not dict or set(config) != _CONFIG_KEYS:
            raise ValueError("invalid ligand checkpoint configuration")
        episode = cls(**config)
        if payload["model"] != episode._model:
            raise ValueError("ligand response model mismatch")
        world = decode_world(payload["world"])
        response = copy.deepcopy(payload["response_state"])
        steps = payload["accepted_steps"]
        if type(steps) is not int or not 0 <= steps <= episode._config["horizon_steps"]:
            raise ValueError("invalid ligand accepted step count")
        initial_world = episode._accepted[0]
        if (world.step != steps or world.time_s != steps * episode._step_fraction or
                set(world.cells) != {SENDER_ID, RECEIVER_ID} or
                set(world.fields) != {SPECIES} or
                world.fields[SPECIES].volumes_m3 != GRID.volumes_m3 or
                world.ledger or world.events):
            raise ValueError("ligand physical state or clock mismatch")
        for cid in (SENDER_ID, RECEIVER_ID):
            cell = world.cells[cid]
            initial = initial_world.cells[cid]
            if (cell.position_m != initial.position_m or
                    cell.volume_m3 != initial.volume_m3 or
                    cell.drag_Ns_per_m != initial.drag_Ns_per_m or
                    cell.parent_id != initial.parent_id or
                    cell.division_count != initial.division_count or
                    set(cell.amounts_mol) - {SPECIES}):
                raise ValueError("ligand physical cell state mismatch")
        if world.cells[RECEIVER_ID].amounts_mol.get(SPECIES, 0.0) != 0:
            raise ValueError("sensing cannot create receiver ligand inventory")
        if (type(response) is not dict or response.get("entity_id") != RECEIVER_ID or
                response.get("accepted_time_s") != float(world.time_s) or
                response.get("initial_time_s") != 0.0 or
                response.get("initial_memory") != 0.0):
            raise ValueError("ligand private response identity or clock mismatch")
        advance_response(episode._model, response,
                         exposure_concentration_mol_m3=0.0,
                         end_time_s=float(world.time_s))
        if abs(total_amount(world, SPECIES) - episode._config["initial_sender_amount_mol"]) > 1e-12:
            raise ValueError("ligand checkpoint closed amount mismatch")
        episode._accepted = (world, response, steps)
        return episode
