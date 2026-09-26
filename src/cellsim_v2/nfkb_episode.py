"""Bounded NF-kappa-B-inspired synthetic response with paired environment transfers.

The response states are dimensionless proxies, not molecular concentrations or
fitted kinetics. Author ligand codes can label an externally supplied schedule;
no physical dose is inferred from those codes. The amount-bearing environment
is a separate synthetic reference with finite stimulus and payload reservoirs.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math

from .checkpoint import canonical_bytes, decode_world, encode_world
from .state import AmountField, Cell, LedgerEntry, Update, World, number, total_amount
from .transport import CellUptake, RectilinearGrid3D, saturable_uptake_step


FORMAT = "cellsim-nfkb-illustrative-episode/1"
STIMULUS = "synthetic_stimulus"
PAYLOAD = "generic_inhibitor_payload"
LIGAND_CODES = frozenset({"T", "I", "L", "P", "FM"})
GRID = RectilinearGrid3D((0.5,), (0.5,), (0.5,))
POSITIONS_M = (
    (0.1, 0.1, 0.1), (0.4, 0.1, 0.1), (0.1, 0.4, 0.1),
    (0.1, 0.1, 0.4), (0.4, 0.4, 0.4),
)
DEFAULT_PARAMETERS = {
    "nuclear_relaxation_min": 18.0,
    "feedback_relaxation_min": 45.0,
    "reporter_relaxation_min": 12.0,
    "stimulus_half_response_mol_m3": 0.25,
    "feedback_strength": 1.0,
    "payload_half_effect_mol": 0.01,
    "payload_uptake_km_mol_m3": 0.2,
}
_CONFIG_KEYS = {
    "cell_count", "horizon_steps", "step_min",
    "initial_stimulus_reservoir_mol", "initial_payload_reservoir_mol",
}
_ACTION_KEYS = {
    "kind", "interval_start_min", "interval_end_min", "stimulus_code",
    "stimulus_admin_quantity_type", "stimulus_admin_mol",
    "stimulus_withdraw_quantity_type", "stimulus_withdraw_mol",
    "payload_admin_quantity_type", "payload_admin_mol",
    "payload_uptake_quantity_type", "payload_uptake_actions",
}
_UPTAKE_KEYS = {
    "kind", "quantity_type", "cell_id", "model_id", "model_digest_sha256",
    "interval_start_min", "interval_end_min", "rate_mol_min",
}


class NfkbRejected(ValueError):
    """A proposal failed without changing any accepted state or clock."""


def _parameters(values: object) -> dict[str, float]:
    if values is None:
        values = DEFAULT_PARAMETERS
    if type(values) is not dict or set(values) != set(DEFAULT_PARAMETERS):
        raise ValueError("NF-kB proxy parameters must contain the declared keys")
    return {key: number(values[key], key, minimum=0 if key == "feedback_strength" else None,
                        positive=key != "feedback_strength")
            for key in DEFAULT_PARAMETERS}


def environment_transfer_update(world: World, *, stimulus_admin_mol: float,
                                stimulus_withdraw_mol: float,
                                payload_admin_mol: float) -> Update:
    """Pure World-side proposal for finite reservoir/field/waste pairing.

    The matching reservoir debit and waste credit are validated and published
    by ``NfkbEpisode.step``. World ledger entries identify the physical boundary
    changes, while the wrapper validates the total including external stores.
    """
    world.validate()
    admin_stim = number(stimulus_admin_mol, "stimulus administration", minimum=0)
    withdraw = number(stimulus_withdraw_mol, "stimulus withdrawal", minimum=0)
    admin_payload = number(payload_admin_mol, "payload administration", minimum=0)
    stim_field = world.fields[STIMULUS]
    payload_field = world.fields[PAYLOAD]
    if withdraw > stim_field.amounts_mol[0]:
        raise ValueError("stimulus withdrawal exceeds finite field inventory")
    stim_after = number(stim_field.amounts_mol[0] - withdraw + admin_stim,
                        "stimulus field after transfer", minimum=0)
    payload_after = number(payload_field.amounts_mol[0] + admin_payload,
                           "payload field after transfer", minimum=0)
    entries = []
    if admin_stim:
        entries.append(LedgerEntry(STIMULUS, admin_stim, "boundary", "finite_stimulus_reservoir"))
    if withdraw:
        entries.append(LedgerEntry(STIMULUS, -withdraw, "boundary", "tracked_stimulus_waste"))
    if admin_payload:
        entries.append(LedgerEntry(PAYLOAD, admin_payload, "boundary", "finite_payload_reservoir"))
    fields = {}
    if admin_stim or withdraw:
        fields[STIMULUS] = replace(stim_field, amounts_mol=(stim_after,))
    if admin_payload:
        fields[PAYLOAD] = replace(payload_field, amounts_mol=(payload_after,))
    return Update(replace_fields=fields, ledger=tuple(entries))


class NfkbEpisode:
    """One to five identified cells in one synthetic fixed 3D voxel."""

    def __init__(self, *, cell_count: int = 1, horizon_steps: int = 82,
                 step_min: float = 6.0, parameters: dict | None = None,
                 initial_stimulus_reservoir_mol: float = 0.5,
                 initial_payload_reservoir_mol: float = 0.1):
        if type(cell_count) is not int or not 1 <= cell_count <= 5:
            raise ValueError("cell_count must be an integer in [1, 5]")
        if type(horizon_steps) is not int or not 1 <= horizon_steps <= 1000:
            raise ValueError("horizon_steps must be an integer in [1, 1000]")
        step = number(step_min, "step_min", positive=True)
        initial_stim = number(initial_stimulus_reservoir_mol,
                              "initial stimulus reservoir", minimum=0)
        initial_payload = number(initial_payload_reservoir_mol,
                                 "initial payload reservoir", minimum=0)
        self._config = {
            "cell_count": cell_count, "horizon_steps": horizon_steps,
            "step_min": step,
            "initial_stimulus_reservoir_mol": initial_stim,
            "initial_payload_reservoir_mol": initial_payload,
        }
        self._parameters = _parameters(parameters)
        self._step_min = Fraction(str(step))
        self._cell_ids = tuple(f"cell_{i}" for i in range(1, cell_count + 1))
        self._model_ids = {cid: f"nfkb-proxy-v1:{cid}" for cid in self._cell_ids}
        self._model_digests = {
            cid: hashlib.sha256(canonical_bytes({
                "model_id": self._model_ids[cid], "parameters": self._parameters,
            })).hexdigest() for cid in self._cell_ids
        }
        self._accepted: tuple[World, dict, dict, float, str | None, int]
        self.reset()

    def _initial_accepted(self) -> tuple[World, dict, dict, float, str | None, int]:
        world = World(
            cells={cid: Cell(cid, POSITIONS_M[i], 1e-6)
                   for i, cid in enumerate(self._cell_ids)},
            fields={species: AmountField(species, (0.0,), GRID.volumes_m3)
                    for species in (STIMULUS, PAYLOAD)},
        )
        states = {cid: {
            "cell_id": cid, "model_id": self._model_ids[cid],
            "model_digest_sha256": self._model_digests[cid],
            "accepted_time_min": 0.0,
            "nuclear_proxy": 0.0, "feedback": 0.0, "reporter_index": 0.0,
        } for cid in self._cell_ids}
        stores = {
            STIMULUS: self._config["initial_stimulus_reservoir_mol"],
            PAYLOAD: self._config["initial_payload_reservoir_mol"],
        }
        return world, states, stores, 0.0, None, 0

    def _response_parameters_for(self, cell_id: str) -> dict[str, float]:
        """Per-cell response hook; the deterministic reference uses one law."""
        return self._parameters

    def reset(self) -> dict:
        self._accepted = self._initial_accepted()
        return self.observe()

    def observe(self) -> dict:
        world, states, stores, waste, code, steps = self._accepted
        terminated = steps >= self._config["horizon_steps"]
        return {
            "time_min": float(world.time_s / 60),
            "next_time_min": None if terminated else float(world.time_s / 60 + self._step_min),
            "stimulus_code": code,
            "field": {species: {
                "amount_mol": world.fields[species].amounts_mol[0],
                "concentration_mol_m3": world.fields[species].concentrations_mol_m3[0],
            } for species in (STIMULUS, PAYLOAD)},
            "reservoir_amounts_mol": copy.deepcopy(stores),
            "waste_stimulus_amount_mol": waste,
            "cells": [{
                "cell_id": cid, "model_id": self._model_ids[cid],
                "model_digest_sha256": self._model_digests[cid],
                "position_m": list(world.cells[cid].position_m),
                "payload_amount_mol": world.cells[cid].amounts_mol.get(PAYLOAD, 0.0),
                "nuclear_proxy": states[cid]["nuclear_proxy"],
                "feedback": states[cid]["feedback"],
                "reporter_index": states[cid]["reporter_index"],
            } for cid in self._cell_ids],
            "remaining_steps": self._config["horizon_steps"] - steps,
            "terminated": terminated,
        }

    def make_action(self, *, stimulus_code: str | None = None,
                    stimulus_admin_mol: float = 0.0,
                    stimulus_withdraw_mol: float = 0.0,
                    payload_admin_mol: float = 0.0,
                    payload_uptake_rates_mol_min_by_cell: dict[str, float] | None = None) -> dict:
        world, _, _, _, _, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise NfkbRejected("episode is terminated")
        if payload_uptake_rates_mol_min_by_cell is None:
            payload_uptake_rates_mol_min_by_cell = {cid: 0.0 for cid in self._cell_ids}
        if (type(payload_uptake_rates_mol_min_by_cell) is not dict or
                set(payload_uptake_rates_mol_min_by_cell) != set(self._cell_ids)):
            raise NfkbRejected("payload rates require exactly one cell identity each")
        if stimulus_code is not None and stimulus_code not in LIGAND_CODES:
            raise NfkbRejected("unsupported author stimulus code")
        try:
            admin_stim = number(stimulus_admin_mol, "stimulus administration", minimum=0)
            withdraw = number(stimulus_withdraw_mol, "stimulus withdrawal", minimum=0)
            admin_payload = number(payload_admin_mol, "payload administration", minimum=0)
            rates = {cid: number(payload_uptake_rates_mol_min_by_cell[cid],
                                 f"{cid} payload uptake rate", minimum=0)
                     for cid in self._cell_ids}
        except (ValueError, TypeError) as exc:
            raise NfkbRejected(str(exc)) from exc
        start = float(world.time_s / 60)
        end = float(world.time_s / 60 + self._step_min)
        return {
            "kind": "nfkb_environment_interval",
            "interval_start_min": start, "interval_end_min": end,
            "stimulus_code": stimulus_code,
            "stimulus_admin_quantity_type": "integrated_amount_mol",
            "stimulus_admin_mol": admin_stim,
            "stimulus_withdraw_quantity_type": "integrated_amount_mol",
            "stimulus_withdraw_mol": withdraw,
            "payload_admin_quantity_type": "integrated_amount_mol",
            "payload_admin_mol": admin_payload,
            "payload_uptake_quantity_type": "rate_mol_min",
            "payload_uptake_actions": [{
                "kind": "cell_payload_uptake",
                "quantity_type": "rate_mol_min",
                "cell_id": cid, "model_id": self._model_ids[cid],
                "model_digest_sha256": self._model_digests[cid],
                "interval_start_min": start, "interval_end_min": end,
                "rate_mol_min": rates[cid],
            } for cid in self._cell_ids],
        }

    def make_scheduled_action(self, *, sequence_key: str,
                              stimulus_admin_mol_per_switch: float = 0.125,
                              payload_start_min: float = 120.0,
                              payload_admin_mol_at_start: float = 0.0,
                              payload_uptake_rates_mol_min_by_cell: dict[str, float] | None = None) -> dict:
        """Emit a typed action for a verified four-code 120-minute schedule.

        The caller supplies the exact author-code sequence. This helper does
        not infer physical dose from its letters and exposes no future target
        in ``observe``. The payload protocol is separate and synthetic.
        """
        if (type(sequence_key) is not str or len(sequence_key) != 4 or
                set(sequence_key) != {"T", "I", "L", "P"}):
            raise NfkbRejected("sequence must be a four-ligand T/I/L/P permutation")
        start = number(payload_start_min, "payload start minute", minimum=0)
        try:
            admin_stim = number(stimulus_admin_mol_per_switch,
                                "stimulus amount per switch", minimum=0)
            admin_payload = number(payload_admin_mol_at_start,
                                   "payload amount at start", minimum=0)
        except (TypeError, ValueError) as exc:
            raise NfkbRejected(str(exc)) from exc
        if Fraction(120) % self._step_min != 0 or Fraction(str(start)) % self._step_min != 0:
            raise NfkbRejected("schedule switch/payload start must align with episode step")
        world, _, _, _, _, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise NfkbRejected("episode is terminated")
        time = world.time_s / 60
        switch = time in (0, 120, 240, 360)
        code = sequence_key[int(time / 120)] if switch else None
        withdraw = world.fields[STIMULUS].amounts_mol[0] if switch else 0.0
        if payload_uptake_rates_mol_min_by_cell is None or time < Fraction(str(start)):
            rates = {cid: 0.0 for cid in self._cell_ids}
        else:
            rates = payload_uptake_rates_mol_min_by_cell
        return self.make_action(
            stimulus_code=code,
            stimulus_admin_mol=admin_stim if switch else 0.0,
            stimulus_withdraw_mol=withdraw,
            payload_admin_mol=admin_payload if time == Fraction(str(start)) else 0.0,
            payload_uptake_rates_mol_min_by_cell=rates,
        )

    def _validate_action(self, action: object) -> tuple[float, float, float, str | None, tuple]:
        if type(action) is not dict or set(action) != _ACTION_KEYS:
            raise ValueError("NF-kB action must contain exactly the typed fields")
        world, _, _, _, _, _ = self._accepted
        start = float(world.time_s / 60)
        end = float(world.time_s / 60 + self._step_min)
        if (action["interval_start_min"] != start or
                action["interval_end_min"] != end):
            raise ValueError("NF-kB action clock interval differs from accepted clock")
        if action["kind"] != "nfkb_environment_interval":
            raise ValueError("unsupported NF-kB action kind")
        if (action["stimulus_admin_quantity_type"] != "integrated_amount_mol" or
                action["stimulus_withdraw_quantity_type"] != "integrated_amount_mol" or
                action["payload_admin_quantity_type"] != "integrated_amount_mol" or
                action["payload_uptake_quantity_type"] != "rate_mol_min"):
            raise ValueError("NF-kB action quantity type mismatch")
        code = action["stimulus_code"]
        if code is not None and code not in LIGAND_CODES:
            raise ValueError("unsupported author stimulus code")
        admin_stim = number(action["stimulus_admin_mol"], "stimulus administration", minimum=0)
        withdraw = number(action["stimulus_withdraw_mol"], "stimulus withdrawal", minimum=0)
        admin_payload = number(action["payload_admin_mol"], "payload administration", minimum=0)
        rows = action["payload_uptake_actions"]
        if type(rows) not in (tuple, list) or len(rows) != len(self._cell_ids):
            raise ValueError("payload rates require exactly one cell identity each")
        seen = set()
        laws = []
        for row in rows:
            if type(row) is not dict or set(row) != _UPTAKE_KEYS:
                raise ValueError("invalid typed payload uptake action")
            cid = row["cell_id"]
            if cid not in self._model_ids or cid in seen:
                raise ValueError("payload uptake cell identity mismatch")
            seen.add(cid)
            if (row["kind"] != "cell_payload_uptake" or
                    row["quantity_type"] != "rate_mol_min" or
                    row["model_id"] != self._model_ids[cid] or
                    row["model_digest_sha256"] != self._model_digests[cid]):
                raise ValueError("payload uptake model identity mismatch")
            if row["interval_start_min"] != start or row["interval_end_min"] != end:
                raise ValueError("payload uptake clock interval mismatch")
            rate = number(row["rate_mol_min"], "payload uptake rate", minimum=0)
            laws.append(CellUptake(cid, rate / 60.0,
                                   self._parameters["payload_uptake_km_mol_m3"]))
        return admin_stim, withdraw, admin_payload, code, tuple(laws)

    def step(self, action: dict) -> dict:
        world, states, stores, waste, old_code, steps = self._accepted
        if steps >= self._config["horizon_steps"]:
            raise NfkbRejected("episode is terminated")
        try:
            admin_stim, withdraw, admin_payload, code, laws = self._validate_action(action)
            if admin_stim > stores[STIMULUS]:
                raise ValueError("stimulus administration exceeds finite reservoir")
            if admin_payload > stores[PAYLOAD]:
                raise ValueError("payload administration exceeds finite reservoir")
            candidate = world.clone()
            environment_transfer_update(
                candidate, stimulus_admin_mol=admin_stim,
                stimulus_withdraw_mol=withdraw,
                payload_admin_mol=admin_payload,
            ).commit(candidate, frozenset({"fields", "ledger"}))
            before_payload = {cid: world.cells[cid].amounts_mol.get(PAYLOAD, 0.0)
                              for cid in self._cell_ids}
            saturable_uptake_step(
                candidate, GRID, PAYLOAD, laws, float(self._step_min * 60)
            ).commit(candidate, frozenset({"cells", "fields"}))
            transfers = {cid: candidate.cells[cid].amounts_mol.get(PAYLOAD, 0.0)
                         - before_payload[cid] for cid in self._cell_ids}
            replacement_states = {}
            dt = float(self._step_min)
            stim_concentration = candidate.fields[STIMULUS].concentrations_mol_m3[0]
            drive = stim_concentration / (self._parameters["stimulus_half_response_mol_m3"]
                                          + stim_concentration)
            for cid in self._cell_ids:
                p = self._response_parameters_for(cid)
                previous = states[cid]
                payload_amount = candidate.cells[cid].amounts_mol.get(PAYLOAD, 0.0)
                inhibition = (1.0 + p["feedback_strength"] * previous["feedback"]
                              + payload_amount / p["payload_half_effect_mol"])
                nuclear_target = drive / inhibition
                nuclear = (previous["nuclear_proxy"] +
                           (nuclear_target - previous["nuclear_proxy"]) *
                           -math.expm1(-dt / p["nuclear_relaxation_min"]))
                feedback = (previous["feedback"] +
                            (previous["nuclear_proxy"] - previous["feedback"]) *
                            -math.expm1(-dt / p["feedback_relaxation_min"]))
                reporter = (previous["reporter_index"] +
                            (previous["nuclear_proxy"] - previous["reporter_index"]) *
                            -math.expm1(-dt / p["reporter_relaxation_min"]))
                if not (0 <= nuclear <= 1 and feedback >= 0 and reporter >= 0 and
                        all(map(math.isfinite, (nuclear, feedback, reporter)))):
                    raise ValueError("nonfinite or unsupported NF-kB proxy state")
                replacement_states[cid] = {
                    **previous, "accepted_time_min": float(world.time_s / 60 + self._step_min),
                    "nuclear_proxy": nuclear, "feedback": feedback,
                    "reporter_index": reporter,
                }
            replacement_stores = {
                STIMULUS: number(stores[STIMULUS] - admin_stim,
                                 "remaining stimulus reservoir", minimum=0),
                PAYLOAD: number(stores[PAYLOAD] - admin_payload,
                                "remaining payload reservoir", minimum=0),
            }
            replacement_waste = number(waste + withdraw, "stimulus waste", minimum=0)
            stim_before = math.fsum((stores[STIMULUS], total_amount(world, STIMULUS), waste))
            stim_after = math.fsum((replacement_stores[STIMULUS],
                                   total_amount(candidate, STIMULUS), replacement_waste))
            payload_before = math.fsum((stores[PAYLOAD], total_amount(world, PAYLOAD)))
            payload_after = math.fsum((replacement_stores[PAYLOAD], total_amount(candidate, PAYLOAD)))
            stim_residual = stim_after - stim_before
            payload_residual = payload_after - payload_before
            paired_payload_residual = (math.fsum(transfers.values()) -
                                       (world.fields[PAYLOAD].amounts_mol[0] + admin_payload
                                        - candidate.fields[PAYLOAD].amounts_mol[0]))
            max_residual = max(abs(stim_residual), abs(payload_residual),
                               abs(paired_payload_residual))
            if max_residual > 1e-12:
                raise ValueError("unpaired NF-kB environment amount transfer")
            candidate.time_s = world.time_s + self._step_min * 60
            candidate.step = steps + 1
            candidate.validate()
        except (ValueError, TypeError, PermissionError, OverflowError) as exc:
            raise NfkbRejected(str(exc)) from exc
        self._accepted = (candidate, replacement_states, replacement_stores,
                          replacement_waste, code if code is not None else old_code,
                          steps + 1)
        return {
            "observation": self.observe(),
            "terminated": steps + 1 >= self._config["horizon_steps"],
            "info": {
                "interval_start_min": float(world.time_s / 60),
                "interval_end_min": float(candidate.time_s / 60),
                "sampled_stimulus_concentration_mol_m3": stim_concentration,
                "payload_transfers_mol_by_cell": transfers,
                "ledger": {
                    "stimulus": {
                        "reservoir_debit_mol": admin_stim,
                        "field_admin_credit_mol": admin_stim,
                        "field_withdraw_debit_mol": withdraw,
                        "waste_credit_mol": withdraw,
                        "signed_total_residual_mol": stim_residual,
                    },
                    "payload": {
                        "reservoir_debit_mol": admin_payload,
                        "field_admin_credit_mol": admin_payload,
                        "cell_credits_mol_by_cell": transfers,
                        "signed_total_residual_mol": payload_residual,
                        "signed_paired_transfer_residual_mol": paired_payload_residual,
                    },
                },
                "maximum_amount_residual_mol": max_residual,
            },
        }

    def checkpoint(self) -> dict:
        world, states, stores, waste, code, steps = self._accepted
        payload = json.loads(canonical_bytes({
            "format": FORMAT, "configuration": self._config,
            "parameters": self._parameters, "world": encode_world(world),
            "response_states_by_cell": states,
            "reservoir_amounts_mol": stores,
            "waste_stimulus_amount_mol": waste,
            "stimulus_code": code, "accepted_steps": steps,
        }))
        return {"payload": payload,
                "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}

    @classmethod
    def from_checkpoint(cls, checkpoint: object) -> "NfkbEpisode":
        if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
            raise ValueError("invalid NF-kB checkpoint wrapper")
        payload = checkpoint["payload"]
        expected = {"format", "configuration", "parameters", "world",
                    "response_states_by_cell", "reservoir_amounts_mol",
                    "waste_stimulus_amount_mol", "stimulus_code", "accepted_steps"}
        if type(payload) is not dict or set(payload) != expected:
            raise ValueError("invalid NF-kB checkpoint payload")
        if hashlib.sha256(canonical_bytes(payload)).hexdigest() != checkpoint["sha256"]:
            raise ValueError("NF-kB checkpoint hash mismatch")
        if payload["format"] != FORMAT:
            raise ValueError("unsupported NF-kB checkpoint format")
        config = payload["configuration"]
        if type(config) is not dict or set(config) != _CONFIG_KEYS:
            raise ValueError("invalid NF-kB checkpoint configuration")
        episode = cls(**config, parameters=payload["parameters"])
        world = decode_world(payload["world"])
        states = copy.deepcopy(payload["response_states_by_cell"])
        stores = copy.deepcopy(payload["reservoir_amounts_mol"])
        waste = number(payload["waste_stimulus_amount_mol"], "stimulus waste", minimum=0)
        code = payload["stimulus_code"]
        steps = payload["accepted_steps"]
        if type(steps) is not int or not 0 <= steps <= config["horizon_steps"]:
            raise ValueError("invalid NF-kB accepted step count")
        if code is not None and code not in LIGAND_CODES:
            raise ValueError("invalid NF-kB stimulus code")
        if (world.step != steps or world.time_s != steps * episode._step_min * 60 or
                set(world.cells) != set(episode._cell_ids) or
                set(world.fields) != {STIMULUS, PAYLOAD} or world.events):
            raise ValueError("NF-kB checkpoint physical identity or clock mismatch")
        if any(world.fields[species].volumes_m3 != GRID.volumes_m3
               for species in (STIMULUS, PAYLOAD)):
            raise ValueError("NF-kB checkpoint field geometry mismatch")
        for index, cid in enumerate(episode._cell_ids):
            cell = world.cells[cid]
            if (cell.position_m != POSITIONS_M[index] or cell.volume_m3 != 1e-6 or
                    cell.parent_id is not None or cell.division_count != 0 or
                    set(cell.amounts_mol) - {PAYLOAD}):
                raise ValueError("NF-kB checkpoint cell geometry or material mismatch")
        if type(stores) is not dict or set(stores) != {STIMULUS, PAYLOAD}:
            raise ValueError("invalid NF-kB finite reservoir identities")
        stores = {species: number(stores[species], "reservoir amount", minimum=0)
                  for species in (STIMULUS, PAYLOAD)}
        if type(states) is not dict or set(states) != set(episode._cell_ids):
            raise ValueError("NF-kB checkpoint private state identities mismatch")
        for cid in episode._cell_ids:
            state = states[cid]
            if (type(state) is not dict or set(state) != {
                    "cell_id", "model_id", "model_digest_sha256", "accepted_time_min",
                    "nuclear_proxy", "feedback", "reporter_index"} or
                    state["cell_id"] != cid or
                    state["model_id"] != episode._model_ids[cid] or
                    state["model_digest_sha256"] != episode._model_digests[cid] or
                    state["accepted_time_min"] != float(world.time_s / 60)):
                raise ValueError("NF-kB checkpoint private state or clock mismatch")
            for key in ("nuclear_proxy", "feedback", "reporter_index"):
                number(state[key], key, minimum=0)
            if state["nuclear_proxy"] > 1:
                raise ValueError("NF-kB checkpoint nuclear proxy out of range")
        stimulus_total = math.fsum((stores[STIMULUS], total_amount(world, STIMULUS), waste))
        payload_total = math.fsum((stores[PAYLOAD], total_amount(world, PAYLOAD)))
        if (abs(stimulus_total - config["initial_stimulus_reservoir_mol"]) > 1e-12 or
                abs(payload_total - config["initial_payload_reservoir_mol"]) > 1e-12):
            raise ValueError("NF-kB checkpoint finite amount balance mismatch")
        episode._accepted = (world, states, stores, waste, code, steps)
        return episode
