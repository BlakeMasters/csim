"""Synthetic NF-kappa-B episode with finite shared paracrine-mediator exchange.

The mediator has no asserted molecular identity. It is a separate tracked
amount ledger wrapped around an unchanged NfkbEpisode or SeededNfkbEpisode.
Pre-step mediator concentration affects private nuclear proxy only after a
validated core transition; newly secreted material is sensed next interval.
"""
from __future__ import annotations

import copy
from dataclasses import replace
from fractions import Fraction
import hashlib
import json
import math

from .checkpoint import canonical_bytes, decode_world, encode_world
from .nfkb_episode import GRID, POSITIONS_M, NfkbEpisode
from .seeded_nfkb_episode import SeededNfkbEpisode
from .state import AmountField, Cell, LedgerEntry, Update, World, number, total_amount


FORMAT = "cellsim-coupled-nfkb-arena/1"
MEDIATOR = "generic_paracrine_mediator"
_ACTION_KEYS = {
    "kind", "interval_start_min", "interval_end_min", "core_action",
    "secretion_quantity_type", "secretion_rates_mol_min_by_cell",
    "clearance_quantity_type", "clearance_rate_min_inv",
}
_CONFIG_KEYS = {
    "cell_count", "horizon_steps", "step_min", "seed",
    "initial_mediator_inventory_mol_per_cell", "mediator_gain_min_inv",
    "mediator_half_response_mol_m3",
}


class CoupledRejected(ValueError):
    """Rejected proposal leaves core, mediator amounts and seed state unchanged."""


def mediator_secretion_update(world: World, transfers_mol_by_cell: dict[str, float]) -> Update:
    """Pure paired cell-inventory to field amount transfer proposal."""
    world.validate()
    if (type(transfers_mol_by_cell) is not dict or
            set(transfers_mol_by_cell) != set(world.cells) or
            set(world.fields) != {MEDIATOR}):
        raise ValueError("mediator secretion identities or field mismatch")
    transfers = {cid: number(transfers_mol_by_cell[cid],
                             f"{cid} mediator transfer", minimum=0)
                 for cid in world.cells}
    replacements = {}
    for cid, transfer in transfers.items():
        cell = world.cells[cid]
        before = cell.amounts_mol.get(MEDIATOR, 0.0)
        if transfer > before:
            raise ValueError("secretion exceeds finite cell inventory")
        amounts = dict(cell.amounts_mol)
        amounts[MEDIATOR] = number(before - transfer,
                                   f"{cid} mediator inventory", minimum=0)
        replacements[cid] = replace(cell, amounts_mol=amounts)
    field = world.fields[MEDIATOR]
    after_field = number(field.amounts_mol[0] + math.fsum(transfers.values()),
                         "mediator field after secretion", minimum=0)
    return Update(replace_cells=replacements,
                  replace_fields={MEDIATOR: replace(field,
                                                    amounts_mol=(after_field,))})


def mediator_clearance_update(world: World, integrated_clearance_mol: float) -> Update:
    """Pure field-to-tracked-waste boundary debit proposal."""
    world.validate()
    clearance = number(integrated_clearance_mol,
                       "integrated mediator clearance", minimum=0)
    field = world.fields[MEDIATOR]
    if clearance > field.amounts_mol[0]:
        raise ValueError("mediator clearance exceeds field inventory")
    return Update(
        replace_fields={MEDIATOR: replace(
            field, amounts_mol=(number(field.amounts_mol[0] - clearance,
                                       "mediator field after clearance", minimum=0),))},
        ledger=((LedgerEntry(MEDIATOR, -clearance, "boundary",
                             "tracked_mediator_waste"),) if clearance else ()),
    )


class CoupledNfkbArena:
    """One to five identified cells coupled through one finite mediator voxel."""

    def __init__(self, *, cell_count: int = 3, horizon_steps: int = 82,
                 step_min: float = 6.0, seed: int | None = None,
                 initial_mediator_inventory_mol_per_cell: float = 0.01,
                 mediator_gain_min_inv: float = 0.02,
                 mediator_half_response_mol_m3: float = 0.01):
        inventory = number(initial_mediator_inventory_mol_per_cell,
                           "initial mediator inventory", minimum=0)
        gain = number(mediator_gain_min_inv, "mediator response gain", minimum=0)
        half = number(mediator_half_response_mol_m3,
                      "mediator half response concentration", positive=True)
        if seed is not None and (type(seed) is not int or not 0 <= seed < 2**64):
            raise ValueError("seed must be null or an unsigned 64-bit integer")
        core_args = dict(cell_count=cell_count, horizon_steps=horizon_steps,
                         step_min=step_min)
        self._core = (NfkbEpisode(**core_args) if seed is None
                      else SeededNfkbEpisode(seed=seed, **core_args))
        self._config = {
            "cell_count": cell_count, "horizon_steps": horizon_steps,
            "step_min": float(step_min), "seed": seed,
            "initial_mediator_inventory_mol_per_cell": inventory,
            "mediator_gain_min_inv": gain,
            "mediator_half_response_mol_m3": half,
        }
        self._cell_ids = tuple(f"cell_{index}" for index in range(1, cell_count + 1))
        self._volume_m3 = GRID.volumes_m3[0]
        self.reset()

    def reset(self) -> dict:
        self._core.reset()
        self._mediator_world = World(
            cells={cid: Cell(cid, POSITIONS_M[index], 1e-6,
                             amounts_mol={MEDIATOR: self._config[
                                 "initial_mediator_inventory_mol_per_cell"]})
                   for index, cid in enumerate(self._cell_ids)},
            fields={MEDIATOR: AmountField(MEDIATOR, (0.0,), GRID.volumes_m3)},
        )
        self._mediator_world.validate()
        self._waste_mol = 0.0
        self._accepted_steps = 0
        return self.observe()

    def observe(self) -> dict:
        observation = self._core.observe()
        field_amount = self._mediator_world.fields[MEDIATOR].amounts_mol[0]
        observation["field"][MEDIATOR] = {
            "amount_mol": field_amount,
            "concentration_mol_m3": field_amount / self._volume_m3,
        }
        for cell in observation["cells"]:
            cell["mediator_inventory_mol"] = self._mediator_world.cells[
                cell["cell_id"]].amounts_mol[MEDIATOR]
        observation["waste_mediator_amount_mol"] = self._waste_mol
        observation["accepted_steps"] = self._accepted_steps
        observation["seed"] = self._config["seed"]
        observation["mediator_model_id"] = "synthetic-paracrine-ledger-v1"
        return observation

    def make_action(self, *, core_action: dict | None = None,
                    secretion_rates_mol_min_by_cell: dict[str, float] | None = None,
                    clearance_rate_min_inv: float = 0.0) -> dict:
        observation = self.observe()
        if observation["terminated"]:
            raise CoupledRejected("episode is terminated")
        if core_action is None:
            core_action = self._core.make_action()
        if secretion_rates_mol_min_by_cell is None:
            secretion_rates_mol_min_by_cell = {cid: 0.0 for cid in self._cell_ids}
        if (type(secretion_rates_mol_min_by_cell) is not dict or
                set(secretion_rates_mol_min_by_cell) != set(self._cell_ids)):
            raise CoupledRejected("secretion rates require every cell identity")
        try:
            rates = {cid: number(secretion_rates_mol_min_by_cell[cid],
                                 f"{cid} secretion rate", minimum=0)
                     for cid in self._cell_ids}
            clearance = number(clearance_rate_min_inv, "clearance rate", minimum=0)
        except (TypeError, ValueError) as exc:
            raise CoupledRejected(str(exc)) from exc
        return {
            "kind": "coupled_nfkb_interval",
            "interval_start_min": observation["time_min"],
            "interval_end_min": observation["next_time_min"],
            "core_action": core_action,
            "secretion_quantity_type": "rate_mol_min",
            "secretion_rates_mol_min_by_cell": rates,
            "clearance_quantity_type": "first_order_rate_min_inverse",
            "clearance_rate_min_inv": clearance,
        }

    def make_scheduled_action(self, *, sequence_key: str,
                              secretion_rates_mol_min_by_cell: dict[str, float] | None = None,
                              clearance_rate_min_inv: float = 0.0,
                              stimulus_admin_mol_per_switch: float = 0.125,
                              payload_start_min: float = 120.0,
                              payload_admin_mol_at_start: float = 0.0,
                              payload_uptake_rates_mol_min_by_cell: dict[str, float] | None = None) -> dict:
        core_action = self._core.make_scheduled_action(
            sequence_key=sequence_key,
            stimulus_admin_mol_per_switch=stimulus_admin_mol_per_switch,
            payload_start_min=payload_start_min,
            payload_admin_mol_at_start=payload_admin_mol_at_start,
            payload_uptake_rates_mol_min_by_cell=payload_uptake_rates_mol_min_by_cell,
        )
        return self.make_action(
            core_action=core_action,
            secretion_rates_mol_min_by_cell=secretion_rates_mol_min_by_cell,
            clearance_rate_min_inv=clearance_rate_min_inv,
        )

    def _candidate_core(self):
        checkpoint = json.loads(json.dumps(self._core.checkpoint()))
        return (NfkbEpisode.from_checkpoint(checkpoint)
                if self._config["seed"] is None else
                SeededNfkbEpisode.from_checkpoint(checkpoint))

    def step(self, action: dict) -> dict:
        if self._accepted_steps >= self._config["horizon_steps"]:
            raise CoupledRejected("episode is terminated")
        try:
            if type(action) is not dict or set(action) != _ACTION_KEYS:
                raise ValueError("coupled action requires exactly the typed fields")
            before = self.observe()
            if (action["kind"] != "coupled_nfkb_interval" or
                    action["interval_start_min"] != before["time_min"] or
                    action["interval_end_min"] != before["next_time_min"]):
                raise ValueError("coupled action identity or clock mismatch")
            if (action["secretion_quantity_type"] != "rate_mol_min" or
                    action["clearance_quantity_type"] != "first_order_rate_min_inverse"):
                raise ValueError("coupled action quantity type mismatch")
            rates = action["secretion_rates_mol_min_by_cell"]
            if type(rates) is not dict or set(rates) != set(self._cell_ids):
                raise ValueError("secretion cell identities mismatch")
            rates = {cid: number(rates[cid], f"{cid} secretion rate", minimum=0)
                     for cid in self._cell_ids}
            clearance_rate = number(action["clearance_rate_min_inv"],
                                    "clearance rate", minimum=0)
            dt = self._config["step_min"]
            secretions = {cid: rates[cid] * dt for cid in self._cell_ids}
            # Only pre-step field is sensed or cleared. Current secretion
            # enters the field after that sample and acts next interval.
            pre_field = self._mediator_world.fields[MEDIATOR].amounts_mol[0]
            sampled_concentration = pre_field / self._volume_m3
            clearance = pre_field * -math.expm1(-clearance_rate * dt)
            if not 0 <= clearance <= pre_field:
                raise ValueError("mediator clearance exceeds field inventory")
            candidate_mediator = self._mediator_world.clone()
            mediator_clearance_update(candidate_mediator, clearance).commit(
                candidate_mediator, frozenset({"fields", "ledger"}))
            mediator_secretion_update(candidate_mediator, secretions).commit(
                candidate_mediator, frozenset({"cells", "fields"}))
            replacement_waste = number(self._waste_mol + clearance,
                                       "mediator waste amount", minimum=0)
            candidate = self._candidate_core()
            core_transition = candidate.step(action["core_action"])
            if sampled_concentration:
                drive = sampled_concentration / (
                    self._config["mediator_half_response_mol_m3"] +
                    sampled_concentration)
                fraction = -math.expm1(-self._config["mediator_gain_min_inv"]
                                       * drive * dt)
                private_core = candidate if self._config["seed"] is None else candidate._core
                world, states, stores, waste, code, steps = private_core._accepted
                replacement_states = copy.deepcopy(states)
                for cid in self._cell_ids:
                    nuclear = replacement_states[cid]["nuclear_proxy"]
                    boosted = number(nuclear + (1.0 - nuclear) * fraction,
                                     f"{cid} mediated nuclear proxy", minimum=0)
                    if boosted > 1:
                        raise ValueError("mediated nuclear proxy exceeds one")
                    replacement_states[cid]["nuclear_proxy"] = boosted
                private_core._accepted = (world, replacement_states, stores,
                                          waste, code, steps)
            before_total = math.fsum((total_amount(self._mediator_world, MEDIATOR),
                                      self._waste_mol))
            after_total = math.fsum((total_amount(candidate_mediator, MEDIATOR),
                                     replacement_waste))
            mediator_residual = after_total - before_total
            maximum_residual = max(abs(mediator_residual),
                                   core_transition["info"]["maximum_amount_residual_mol"])
            if maximum_residual > 1e-12:
                raise ValueError("coupled amount balance exceeds 1e-12 mol")
            candidate_mediator.time_s += Fraction(str(dt)) * 60
            candidate_mediator.step += 1
            candidate_mediator.validate()
            # Validate both complete private/physical checkpoints before
            # publishing the joint candidate. No state or seed is consumed by
            # rejected proposals.
            type(candidate).from_checkpoint(candidate.checkpoint())
            provisional = type(self)(**self._config)
            provisional._core = candidate
            provisional._mediator_world = candidate_mediator
            provisional._waste_mol = replacement_waste
            provisional._accepted_steps = self._accepted_steps + 1
            type(self).from_checkpoint(provisional.checkpoint())
        except Exception as exc:
            raise CoupledRejected(str(exc)) from exc
        self._core = candidate
        self._mediator_world = candidate_mediator
        self._waste_mol = replacement_waste
        self._accepted_steps += 1
        ledger = {
            "cell_inventory_debits_mol_by_cell": secretions,
            "field_secretion_credit_mol": math.fsum(secretions.values()),
            "field_clearance_debit_mol": clearance,
            "waste_clearance_credit_mol": clearance,
            "signed_total_residual_mol": mediator_residual,
        }
        for cid in self._cell_ids:
            ledger[f"{cid}_secretion_debit_mol"] = secretions[cid]
        return {
            "observation": self.observe(),
            "terminated": self._accepted_steps >= self._config["horizon_steps"],
            "info": {
                "interval_start_min": before["time_min"],
                "interval_end_min": self.observe()["time_min"],
                "sampled_mediator_concentration_mol_m3": sampled_concentration,
                "mediator_ledger": ledger,
                "core_ledger": core_transition["info"]["ledger"],
                "maximum_amount_residual_mol": maximum_residual,
            },
        }

    def checkpoint(self) -> dict:
        payload = json.loads(canonical_bytes({
            "format": FORMAT, "configuration": self._config,
            "core_checkpoint": self._core.checkpoint(),
            "mediator_world": encode_world(self._mediator_world),
            "mediator_waste_amount_mol": self._waste_mol,
            "accepted_steps": self._accepted_steps,
        }))
        return {"payload": payload,
                "sha256": hashlib.sha256(canonical_bytes(payload)).hexdigest()}

    @classmethod
    def from_checkpoint(cls, checkpoint: object) -> "CoupledNfkbArena":
        if type(checkpoint) is not dict or set(checkpoint) != {"payload", "sha256"}:
            raise ValueError("invalid coupled checkpoint wrapper")
        payload = checkpoint["payload"]
        required = {"format", "configuration", "core_checkpoint",
                    "mediator_world", "mediator_waste_amount_mol", "accepted_steps"}
        if type(payload) is not dict or set(payload) != required:
            raise ValueError("invalid coupled checkpoint payload")
        if hashlib.sha256(canonical_bytes(payload)).hexdigest() != checkpoint["sha256"]:
            raise ValueError("coupled checkpoint hash mismatch")
        if payload["format"] != FORMAT:
            raise ValueError("unsupported coupled checkpoint format")
        config = payload["configuration"]
        if type(config) is not dict or set(config) != _CONFIG_KEYS:
            raise ValueError("invalid coupled checkpoint configuration")
        restored = cls(**config)
        core = (NfkbEpisode.from_checkpoint(payload["core_checkpoint"])
                if config["seed"] is None else
                SeededNfkbEpisode.from_checkpoint(payload["core_checkpoint"]))
        if config["seed"] is not None and core._seed != config["seed"]:
            raise ValueError("coupled checkpoint seed identity mismatch")
        core_config = core._config if config["seed"] is None else core._core._config
        if any(core_config[key] != config[key]
               for key in ("cell_count", "horizon_steps", "step_min")):
            raise ValueError("coupled checkpoint core configuration mismatch")
        steps = payload["accepted_steps"]
        if (type(steps) is not int or not 0 <= steps <= config["horizon_steps"] or
                core.observe()["time_min"] != steps * config["step_min"]):
            raise ValueError("coupled checkpoint clock mismatch")
        mediator_world = decode_world(payload["mediator_world"])
        if (set(mediator_world.cells) != set(restored._cell_ids) or
                set(mediator_world.fields) != {MEDIATOR} or
                mediator_world.fields[MEDIATOR].volumes_m3 != GRID.volumes_m3 or
                mediator_world.time_s != Fraction(str(config["step_min"])) * 60 * steps or
                mediator_world.step != steps or mediator_world.events):
            raise ValueError("coupled checkpoint mediator world identity or clock mismatch")
        for index, cid in enumerate(restored._cell_ids):
            cell = mediator_world.cells[cid]
            if (cell.position_m != POSITIONS_M[index] or cell.volume_m3 != 1e-6 or
                    cell.parent_id is not None or cell.division_count != 0 or
                    set(cell.amounts_mol) != {MEDIATOR}):
                raise ValueError("coupled checkpoint mediator cell mismatch")
        waste = number(payload["mediator_waste_amount_mol"],
                       "mediator waste amount", minimum=0)
        total = math.fsum((total_amount(mediator_world, MEDIATOR), waste))
        expected = config["cell_count"] * config["initial_mediator_inventory_mol_per_cell"]
        if abs(total - expected) > 1e-12:
            raise ValueError("coupled checkpoint mediator amount mismatch")
        restored._core = core
        restored._mediator_world = mediator_world
        restored._waste_mol = waste
        restored._accepted_steps = steps
        return restored
