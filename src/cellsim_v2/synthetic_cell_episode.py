"""One deterministic synthetic cell episode with joint memory/amount acceptance.

This fixed-topology reference uses one 3D voxel and one cell. A rate action
selects the existing saturable, same-species field-to-cell transfer. Response
memory samples the accepted pre-step local concentration over the same interval.
Both proposals are computed on private copies and published together only after
physical balance, identity and clock checks succeed. No learner, biological
assay, stochastic state, external solver or arbitrary-code sandbox is supplied.
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
from .state import AmountField, Cell, World, total_amount
from .transport import CellUptake, RectilinearGrid3D, saturable_uptake_step


FORMAT = "cellsim-synthetic-cell-episode/1"
SPECIES = "synthetic_tracer"
CELL_ID = "cell-1"
KM_MOL_M3 = 0.5
GRID = RectilinearGrid3D((0.5,), (0.5,), (0.5,))
_ACTION_KEYS = {
    "kind", "quantity_type", "cell_id", "species", "context_id",
    "model_digest_sha256", "interval_start_s", "interval_end_s",
    "vmax_mol_s", "km_mol_m3",
}
_CONFIG_KEYS = {
    "initial_concentration_mol_m3", "initial_memory", "horizon_steps",
    "step_s", "target_response_index",
}


class EpisodeRejected(ValueError):
    """An action failed before any accepted episode state was published."""


def _finite_number(value: object, name: str, *, nonnegative: bool = False,
                   positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(result) or (nonnegative and result < 0) or (positive and result <= 0):
        raise ValueError(f"{name} must be finite and within its declared range")
    return result


def _configuration(*, initial_concentration_mol_m3: float,
                   initial_memory: float, horizon_steps: int, step_s: float,
                   target_response_index: float) -> dict:
    if type(horizon_steps) is not int or not 1 <= horizon_steps <= 10000:
        raise ValueError("horizon_steps must be an integer in [1, 10000]")
    config = {
        "initial_concentration_mol_m3": _finite_number(
            initial_concentration_mol_m3, "initial concentration", nonnegative=True),
        "initial_memory": _finite_number(initial_memory, "initial memory", nonnegative=True),
        "horizon_steps": horizon_steps,
        "step_s": _finite_number(step_s, "step_s", positive=True),
        "target_response_index": _finite_number(
            target_response_index, "target response index", nonnegative=True),
    }
    if not math.isfinite(float(Fraction(str(config["step_s"])) * horizon_steps)):
        raise ValueError("episode horizon is not representable as a finite float")
    return config


class SyntheticCellEpisode:
    """Small local episode; all mutable accepted state is held in one tuple.

    `diagnostic_score` is negative absolute error against an evaluator-owned
    synthetic response-index target. It is training feedback, not biological
    fitness, cell survival, numerical validity, or an independent test result.
    """

    def __init__(self, *, initial_concentration_mol_m3: float = 1.0,
                 initial_memory: float = 0.0, horizon_steps: int = 4,
                 step_s: float = 0.25, target_response_index: float = 0.5):
        self._config = _configuration(
            initial_concentration_mol_m3=initial_concentration_mol_m3,
            initial_memory=initial_memory, horizon_steps=horizon_steps,
            step_s=step_s, target_response_index=target_response_index,
        )
        self._step_fraction = Fraction(str(self._config["step_s"]))
        self._model = create_relaxation_model(
            model_id="synthetic-cell-episode-memory-v1",
            context_id="synthetic-cell-episode-context-v1",
            tau_s=0.5,
            target_intercept=0.0,
            target_slope_m3_per_mol=1.0,
        )
        self._accepted: tuple[World, dict, int]
        self.reset()

    def _initial_accepted(self) -> tuple[World, dict, int]:
        world = World(
            cells={CELL_ID: Cell(CELL_ID, GRID.center_m(0), 1e-6)},
            fields={SPECIES: AmountField.from_concentrations(
                SPECIES, (self._config["initial_concentration_mol_m3"],), GRID.volumes_m3,
            )},
        )
        response = initialize_response(
            self._model, entity_id=CELL_ID,
            initial_memory=self._config["initial_memory"], accepted_time_s=0.0,
            initialization_provenance={
                "kind": "declared_synthetic_initial_state",
                "source_id": "synthetic_cell_episode/v1",
            },
        )
        return world, response, 0

    def reset(self) -> dict:
        """Recreate the declared starting state and return a causal observation."""
        self._accepted = self._initial_accepted()
        return self.observe()

    def observe(self) -> dict:
        """Policy-visible accepted state; no evaluator target or model parameters."""
        world, response, steps = self._accepted
        terminated = steps >= self._config["horizon_steps"]
        return {
            "cell_id": CELL_ID,
            "species": SPECIES,
            "context_id": response["context_id"],
            "time_s": float(world.time_s),
            "next_time_s": None if terminated else float(world.time_s + self._step_fraction),
            "local_concentration_mol_m3": world.fields[SPECIES].concentrations_mol_m3[0],
            "accepted_memory": response["memory"],
            "memory_unit": "1",
            "cell_amount_mol": world.cells[CELL_ID].amounts_mol.get(SPECIES, 0.0),
            "remaining_steps": self._config["horizon_steps"] - steps,
            "terminated": terminated,
        }

    def make_action(self, vmax_mol_s: float) -> dict:
        """Bind a typed maximum-rate action to the current accepted interval."""
        world, response, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise EpisodeRejected("episode is terminated")
        try:
            vmax = _finite_number(vmax_mol_s, "vmax_mol_s", nonnegative=True)
        except ValueError as exc:
            raise EpisodeRejected(str(exc)) from exc
        return {
            "kind": "saturable_uptake_rate",
            "quantity_type": "vmax_mol_s",
            "cell_id": CELL_ID,
            "species": SPECIES,
            "context_id": response["context_id"],
            "model_digest_sha256": response["model_digest_sha256"],
            "interval_start_s": float(world.time_s),
            "interval_end_s": float(world.time_s + self._step_fraction),
            "vmax_mol_s": vmax,
            "km_mol_m3": KM_MOL_M3,
        }

    def _validate_action(self, action: object) -> float:
        if type(action) is not dict or set(action) != _ACTION_KEYS:
            raise ValueError("action must contain exactly the typed rate and identity fields")
        world, response, _ = self._accepted
        if (action["kind"] != "saturable_uptake_rate" or
                action["quantity_type"] != "vmax_mol_s"):
            raise ValueError("unsupported action kind or quantity type")
        if (action["cell_id"] != CELL_ID or action["species"] != SPECIES or
                action["context_id"] != response["context_id"] or
                action["model_digest_sha256"] != response["model_digest_sha256"]):
            raise ValueError("action identity mismatch")
        start = _finite_number(action["interval_start_s"], "interval start")
        end = _finite_number(action["interval_end_s"], "interval end")
        if start != float(world.time_s) or end != float(world.time_s + self._step_fraction):
            raise ValueError("action interval does not match the accepted clock")
        km = _finite_number(action["km_mol_m3"], "Km", positive=True)
        if km != KM_MOL_M3:
            raise ValueError("action Km does not match the fixed episode law")
        return _finite_number(action["vmax_mol_s"], "vmax_mol_s", nonnegative=True)

    def step(self, action: dict) -> dict:
        """Propose on copies, then publish physical and response state together."""
        world, response, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise EpisodeRejected("episode is terminated")
        start = world.time_s
        end = start + self._step_fraction
        try:
            vmax = self._validate_action(action)
            exposure = world.fields[SPECIES].concentrations_mol_m3[0]
            response_result = advance_response(
                self._model, copy.deepcopy(response),
                exposure_concentration_mol_m3=exposure, end_time_s=float(end),
            )
            candidate = world.clone()
            proposal = saturable_uptake_step(
                candidate, GRID, SPECIES,
                (CellUptake(CELL_ID, vmax, KM_MOL_M3),), float(self._step_fraction),
            )
            proposal.commit(candidate, frozenset({"cells", "fields"}))
            balance_error = abs(total_amount(candidate, SPECIES) - total_amount(world, SPECIES))
            if balance_error > 1e-12:
                raise ValueError("accepted transfer did not preserve the closed amount total")
            candidate.time_s = end
            candidate.step = steps + 1
            candidate.validate()
            if response_result["state"]["accepted_time_s"] != float(end):
                raise ValueError("response stage clock differs from physical interval")
            observed_response = response_result["observations"][0]["value"]
            diagnostic_score = -abs(observed_response - self._config["target_response_index"])
            if not math.isfinite(diagnostic_score):
                raise ValueError("diagnostic score is not finite")
            transfer = (candidate.cells[CELL_ID].amounts_mol.get(SPECIES, 0.0)
                        - world.cells[CELL_ID].amounts_mol.get(SPECIES, 0.0))
        except (ValueError, TypeError, PermissionError) as exc:
            raise EpisodeRejected(str(exc)) from exc
        self._accepted = (candidate, response_result["state"], steps + 1)
        return {
            "observation": self.observe(),
            "diagnostic_score": diagnostic_score,
            "terminated": steps + 1 >= self._config["horizon_steps"],
            "truncated": False,
            "info": {
                "score_role": "synthetic_training_feedback",
                "score_definition": "negative_absolute_response_index_error",
                "response_observation": response_result["observations"][0],
                "exposure_sample_time_s": float(start),
                "memory_interval_start_s": float(start),
                "memory_interval_end_s": float(end),
                "transfer_interval_start_s": float(start),
                "transfer_interval_end_s": float(end),
                "integrated_transfer_mol": transfer,
                "absolute_balance_error_mol": balance_error,
            },
        }

    def checkpoint(self) -> dict:
        """Return a complete JSON checkpoint for this deterministic wrapper."""
        world, response, steps = self._accepted
        payload = {
            "format": FORMAT,
            "configuration": copy.deepcopy(self._config),
            "model": copy.deepcopy(self._model),
            "response_state": copy.deepcopy(response),
            "world": encode_world(world),
            "accepted_steps": steps,
        }
        # Convert tuple-valued geometry to literal JSON lists before returning.
        payload = json.loads(canonical_bytes(payload))
        return {"payload": payload,
                "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}

    @classmethod
    def from_checkpoint(cls, checkpoint: object) -> "SyntheticCellEpisode":
        """Restore only a matching full wrapper state and aligned stage clocks."""
        if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
            raise ValueError("invalid synthetic episode checkpoint wrapper")
        payload = checkpoint["payload"]
        if type(payload) is not dict or set(payload) != {
                "format", "configuration", "model", "response_state", "world", "accepted_steps"}:
            raise ValueError("invalid synthetic episode checkpoint payload")
        if hashlib.sha256(canonical_bytes(payload)).hexdigest() != checkpoint["sha256"]:
            raise ValueError("synthetic episode checkpoint hash mismatch")
        if payload["format"] != FORMAT:
            raise ValueError("unsupported synthetic episode checkpoint format")
        config = payload["configuration"]
        if type(config) is not dict or set(config) != _CONFIG_KEYS:
            raise ValueError("invalid synthetic episode configuration")
        episode = cls(**config)
        if payload["model"] != episode._model:
            raise ValueError("synthetic episode model identity mismatch")
        world = decode_world(payload["world"])
        response = copy.deepcopy(payload["response_state"])
        steps = payload["accepted_steps"]
        if type(steps) is not int or not 0 <= steps <= episode._config["horizon_steps"]:
            raise ValueError("invalid accepted step count")
        cell = world.cells.get(CELL_ID)
        expected_cell = episode._accepted[0].cells[CELL_ID]
        if (world.step != steps or world.time_s != steps * episode._step_fraction or
                set(world.cells) != {CELL_ID} or set(world.fields) != {SPECIES} or
                world.fields[SPECIES].volumes_m3 != GRID.volumes_m3 or
                cell.position_m != expected_cell.position_m or
                cell.volume_m3 != expected_cell.volume_m3 or
                cell.drag_Ns_per_m != expected_cell.drag_Ns_per_m or
                cell.parent_id != expected_cell.parent_id or
                cell.division_count != expected_cell.division_count or
                set(cell.amounts_mol) - {SPECIES} or
                world.ledger or world.events):
            raise ValueError("checkpoint physical state or stage clock mismatch")
        if (response.get("entity_id") != CELL_ID or
                response.get("accepted_time_s") != float(world.time_s) or
                response.get("initial_time_s") != 0.0 or
                response.get("initial_memory") != episode._config["initial_memory"]):
            raise ValueError("checkpoint response identity or stage clock mismatch")
        # H02 validates complete model/context digest and state shape at this time.
        advance_response(episode._model, response,
                         exposure_concentration_mol_m3=0.0,
                         end_time_s=float(world.time_s))
        initial_total = GRID.volumes_m3[0] * episode._config["initial_concentration_mol_m3"]
        if abs(total_amount(world, SPECIES) - initial_total) > 1e-12:
            raise ValueError("checkpoint closed amount total mismatch")
        episode._accepted = (world, response, steps)
        return episode


def make_synthetic_episode(*, initial_concentration_mol_m3: float = 1.0,
                           initial_memory: float = 0.0, horizon_steps: int = 4,
                           step_s: float = 0.25,
                           target_response_index: float = 0.5) -> SyntheticCellEpisode:
    """Construct an explicit synthetic task; target stays out of observations."""
    return SyntheticCellEpisode(
        initial_concentration_mol_m3=initial_concentration_mol_m3,
        initial_memory=initial_memory, horizon_steps=horizon_steps,
        step_s=step_s, target_response_index=target_response_index,
    )
