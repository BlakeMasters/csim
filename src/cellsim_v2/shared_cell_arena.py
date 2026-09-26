"""One-to-five independently identified synthetic cells sharing one field voxel.

Each cell owns an amount inventory and a private H02 response state. Typed
maximum-rate actions are evaluated simultaneously against the same accepted
pre-step concentration by the existing conservative uptake kernel. Collective
overdraw rejects the whole interval; there is no hidden scarcity allocator.
This is a deterministic reference choice, not a tissue or biological model.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import math

from .checkpoint import canonical_bytes, decode_world, encode_world
from .response_memory import (
    advance_response, create_relaxation_model, initialize_response,
)
from .state import AmountField, Cell, World, number, total_amount
from .transport import CellUptake, RectilinearGrid3D, saturable_uptake_step


FORMAT = "cellsim-shared-cell-arena/1"
SPECIES = "synthetic_tracer"
KM_MOL_M3 = 0.5
GRID = RectilinearGrid3D((0.5,), (0.5,), (0.5,))
# Declared distinct positions inside the same voxel; no implicit jitter.
POSITIONS_M = (
    (0.1, 0.1, 0.1),
    (0.4, 0.1, 0.1),
    (0.1, 0.4, 0.1),
    (0.1, 0.1, 0.4),
    (0.4, 0.4, 0.4),
)
_ACTION_KEYS = {
    "kind", "quantity_type", "cell_id", "species", "context_id",
    "model_digest_sha256", "interval_start_s", "interval_end_s",
    "vmax_mol_s", "km_mol_m3",
}
_CONFIG_KEYS = {
    "cell_count", "horizon_steps", "step_s", "initial_concentration_mol_m3",
    "diagnostic_target_memory",
}


class ArenaRejected(ValueError):
    """A proposal failed without changing accepted shared or private state."""


class SharedCellArena:
    """Fixed-geometry reference with one independently identified model per cell."""

    def __init__(self, *, cell_count: int = 2, horizon_steps: int = 6,
                 step_s: float = 0.25, initial_concentration_mol_m3: float = 1.0,
                 diagnostic_target_memory: float = 0.5):
        if type(cell_count) is not int or not 1 <= cell_count <= 5:
            raise ValueError("cell_count must be an integer in [1, 5]")
        if type(horizon_steps) is not int or not 1 <= horizon_steps <= 8:
            raise ValueError("horizon_steps must be an integer in [1, 8]")
        step = number(step_s, "step_s", positive=True)
        concentration = number(initial_concentration_mol_m3, "initial concentration", minimum=0)
        target = number(diagnostic_target_memory, "diagnostic memory target", minimum=0)
        if not math.isfinite(float(Fraction(str(step)) * horizon_steps)):
            raise ValueError("arena horizon is not finite")
        self._config = {
            "cell_count": cell_count,
            "horizon_steps": horizon_steps,
            "step_s": step,
            "initial_concentration_mol_m3": concentration,
            "diagnostic_target_memory": target,
        }
        self._step_fraction = Fraction(str(step))
        self._cell_ids = tuple(f"cell_{i}" for i in range(1, cell_count + 1))
        # Separate identities permit a later per-cell model choice. This slice
        # deliberately gives each instance the same synthetic equation.
        self._models = {cid: create_relaxation_model(
            model_id=f"arena-memory-v1:{cid}",
            context_id=f"arena-context-v1:{cid}",
            tau_s=0.5, target_intercept=0.0,
            target_slope_m3_per_mol=1.0,
        ) for cid in self._cell_ids}
        self._accepted: tuple[World, dict[str, dict], int]
        self.reset()

    def _initial_accepted(self) -> tuple[World, dict[str, dict], int]:
        world = World(
            cells={cid: Cell(cid, POSITIONS_M[index], 1e-6)
                   for index, cid in enumerate(self._cell_ids)},
            fields={SPECIES: AmountField.from_concentrations(
                SPECIES, (self._config["initial_concentration_mol_m3"],),
                GRID.volumes_m3,
            )},
        )
        states = {cid: initialize_response(
            self._models[cid], entity_id=cid,
            initial_memory=0.05 * (index - 1), accepted_time_s=0.0,
            initialization_provenance={
                "kind": "declared_synthetic_initial_state",
                "source_id": f"shared_cell_arena/v1:{cid}",
            },
        ) for index, cid in enumerate(self._cell_ids, start=1)}
        return world, states, 0

    def reset(self) -> dict:
        self._accepted = self._initial_accepted()
        return self.observe()

    def observe(self) -> dict:
        world, states, steps = self._accepted
        terminated = steps >= self._config["horizon_steps"]
        return {
            "time_s": float(world.time_s),
            "next_time_s": None if terminated else float(world.time_s + self._step_fraction),
            "field_amount_mol": world.fields[SPECIES].amounts_mol[0],
            "field_concentration_mol_m3": world.fields[SPECIES].concentrations_mol_m3[0],
            "cells": [{
                "cell_id": cid,
                "model_id": states[cid]["model_id"],
                "context_id": states[cid]["context_id"],
                "position_m": list(world.cells[cid].position_m),
                "amount_mol": world.cells[cid].amounts_mol.get(SPECIES, 0.0),
                "memory": states[cid]["memory"],
            } for cid in self._cell_ids],
            "remaining_steps": self._config["horizon_steps"] - steps,
            "terminated": terminated,
        }

    def make_actions(self, rates_by_cell_id: dict[str, float]) -> tuple[dict, ...]:
        world, states, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise ArenaRejected("arena is terminated")
        if type(rates_by_cell_id) is not dict or set(rates_by_cell_id) != set(self._cell_ids):
            raise ArenaRejected("rates must contain exactly one value per cell")
        actions = []
        for cid in self._cell_ids:
            try:
                rate = number(rates_by_cell_id[cid], f"{cid} vmax", minimum=0)
            except (ValueError, TypeError) as exc:
                raise ArenaRejected(str(exc)) from exc
            actions.append({
                "kind": "saturable_uptake_rate",
                "quantity_type": "vmax_mol_s",
                "cell_id": cid,
                "species": SPECIES,
                "context_id": states[cid]["context_id"],
                "model_digest_sha256": states[cid]["model_digest_sha256"],
                "interval_start_s": float(world.time_s),
                "interval_end_s": float(world.time_s + self._step_fraction),
                "vmax_mol_s": rate,
                "km_mol_m3": KM_MOL_M3,
            })
        return tuple(actions)

    def _validate_actions(self, actions: object) -> tuple[CellUptake, ...]:
        if type(actions) not in (tuple, list) or len(actions) != len(self._cell_ids):
            raise ValueError("actions require exactly one typed rate per cell")
        world, states, _ = self._accepted
        seen = set()
        laws = []
        for action in actions:
            if type(action) is not dict or set(action) != _ACTION_KEYS:
                raise ValueError("action must contain exactly the typed rate fields")
            cid = action["cell_id"]
            if cid not in states or cid in seen:
                raise ValueError("actions require exactly one unique cell identity")
            seen.add(cid)
            if (action["kind"] != "saturable_uptake_rate" or
                    action["quantity_type"] != "vmax_mol_s" or
                    action["species"] != SPECIES or
                    action["context_id"] != states[cid]["context_id"] or
                    action["model_digest_sha256"] != states[cid]["model_digest_sha256"]):
                raise ValueError("arena action identity or quantity type mismatch")
            start = number(action["interval_start_s"], "interval start", minimum=0)
            end = number(action["interval_end_s"], "interval end", minimum=0)
            if start != float(world.time_s) or end != float(world.time_s + self._step_fraction):
                raise ValueError("arena action interval differs from accepted clock")
            km = number(action["km_mol_m3"], "Km", positive=True)
            if km != KM_MOL_M3:
                raise ValueError("arena action Km differs from fixed law")
            vmax = number(action["vmax_mol_s"], "vmax", minimum=0)
            laws.append(CellUptake(cid, vmax, km))
        if seen != set(self._cell_ids):
            raise ValueError("actions require exactly one unique cell identity")
        return tuple(laws)

    def step(self, actions: tuple[dict, ...] | list[dict]) -> dict:
        world, states, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise ArenaRejected("arena is terminated")
        start = world.time_s
        end = start + self._step_fraction
        try:
            laws = self._validate_actions(actions)
            exposure = world.fields[SPECIES].concentrations_mol_m3[0]
            response_results = {cid: advance_response(
                self._models[cid], copy.deepcopy(states[cid]),
                exposure_concentration_mol_m3=exposure,
                end_time_s=float(end),
            ) for cid in self._cell_ids}
            candidate = world.clone()
            saturable_uptake_step(candidate, GRID, SPECIES, laws,
                                 float(self._step_fraction)).commit(
                                     candidate, frozenset({"cells", "fields"}))
            balance_error = abs(total_amount(candidate, SPECIES) - total_amount(world, SPECIES))
            if balance_error > 1e-12:
                raise ValueError("arena changed the closed amount total")
            candidate.time_s = end
            candidate.step = steps + 1
            candidate.validate()
            replacement_states = {cid: result["state"]
                                  for cid, result in response_results.items()}
            if any(state["accepted_time_s"] != float(end)
                   for state in replacement_states.values()):
                raise ValueError("arena response and physical clocks differ")
            transfers = {cid: (candidate.cells[cid].amounts_mol.get(SPECIES, 0.0)
                               - world.cells[cid].amounts_mol.get(SPECIES, 0.0))
                         for cid in self._cell_ids}
            field_debit = (world.fields[SPECIES].amounts_mol[0]
                           - candidate.fields[SPECIES].amounts_mol[0])
            transfer_residual = math.fsum(transfers.values()) - field_debit
            if abs(transfer_residual) > 1e-12:
                raise ValueError("arena field debit and cell credits are not paired")
            score = -math.fsum(abs(replacement_states[cid]["memory"]
                                   - self._config["diagnostic_target_memory"])
                               for cid in self._cell_ids) / len(self._cell_ids)
            if not math.isfinite(score):
                raise ValueError("arena diagnostic score is not finite")
        except (ValueError, TypeError, PermissionError) as exc:
            raise ArenaRejected(str(exc)) from exc
        self._accepted = (candidate, replacement_states, steps + 1)
        return {
            "observation": self.observe(),
            "diagnostic_score": score,
            "terminated": steps + 1 >= self._config["horizon_steps"],
            "info": {
                "score_role": "synthetic_training_feedback",
                "transfers_mol_by_cell": transfers,
                "closed_amount_ledger": {
                    "field_debit_mol": field_debit,
                    "cell_credits_mol_by_cell": transfers,
                    "external_change_mol": 0.0,
                    "signed_transfer_residual_mol": transfer_residual,
                },
                "response_observations_by_cell": {
                    cid: response_results[cid]["observations"][0]
                    for cid in self._cell_ids},
                "absolute_balance_error_mol": balance_error,
                "sample_time_s": float(start),
                "interval_end_s": float(end),
            },
        }

    def checkpoint(self) -> dict:
        world, states, steps = self._accepted
        payload = {
            "format": FORMAT,
            "configuration": copy.deepcopy(self._config),
            "models_by_cell": copy.deepcopy(self._models),
            "response_states_by_cell": copy.deepcopy(states),
            "world": encode_world(world),
            "accepted_steps": steps,
        }
        payload = json.loads(canonical_bytes(payload))
        return {"payload": payload,
                "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}

    @classmethod
    def from_checkpoint(cls, checkpoint: object) -> "SharedCellArena":
        if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
            raise ValueError("invalid arena checkpoint wrapper")
        payload = checkpoint["payload"]
        if type(payload) is not dict or set(payload) != {
                "format", "configuration", "models_by_cell",
                "response_states_by_cell", "world", "accepted_steps"}:
            raise ValueError("invalid arena checkpoint payload")
        if hashlib.sha256(canonical_bytes(payload)).hexdigest() != checkpoint["sha256"]:
            raise ValueError("arena checkpoint hash mismatch")
        if payload["format"] != FORMAT:
            raise ValueError("unsupported arena checkpoint format")
        config = payload["configuration"]
        if type(config) is not dict or set(config) != _CONFIG_KEYS:
            raise ValueError("invalid arena checkpoint configuration")
        arena = cls(**config)
        if payload["models_by_cell"] != arena._models:
            raise ValueError("arena cell model identities mismatch")
        world = decode_world(payload["world"])
        states = copy.deepcopy(payload["response_states_by_cell"])
        steps = payload["accepted_steps"]
        if type(steps) is not int or not 0 <= steps <= arena._config["horizon_steps"]:
            raise ValueError("invalid arena accepted step count")
        if (world.step != steps or world.time_s != steps * arena._step_fraction or
                set(world.cells) != set(arena._cell_ids) or
                set(world.fields) != {SPECIES} or
                world.fields[SPECIES].volumes_m3 != GRID.volumes_m3 or
                world.ledger or world.events):
            raise ValueError("arena physical state or clock mismatch")
        initial_world = arena._accepted[0]
        for cid in arena._cell_ids:
            cell = world.cells[cid]
            initial = initial_world.cells[cid]
            if (cell.position_m != initial.position_m or
                    cell.volume_m3 != initial.volume_m3 or
                    cell.drag_Ns_per_m != initial.drag_Ns_per_m or
                    cell.parent_id != initial.parent_id or
                    cell.division_count != initial.division_count or
                    set(cell.amounts_mol) - {SPECIES}):
                raise ValueError("arena physical cell state mismatch")
        if type(states) is not dict or set(states) != set(arena._cell_ids):
            raise ValueError("arena private response identities mismatch")
        for index, cid in enumerate(arena._cell_ids, start=1):
            state = states[cid]
            if (type(state) is not dict or state.get("entity_id") != cid or
                    state.get("accepted_time_s") != float(world.time_s) or
                    state.get("initial_time_s") != 0.0 or
                    state.get("initial_memory") != 0.05 * (index - 1)):
                raise ValueError("arena private response state or clock mismatch")
            advance_response(arena._models[cid], state,
                             exposure_concentration_mol_m3=0.0,
                             end_time_s=float(world.time_s))
        initial_total = GRID.volumes_m3[0] * arena._config["initial_concentration_mol_m3"]
        if abs(total_amount(world, SPECIES) - initial_total) > 1e-12:
            raise ValueError("arena checkpoint closed amount mismatch")
        arena._accepted = (world, states, steps)
        return arena
