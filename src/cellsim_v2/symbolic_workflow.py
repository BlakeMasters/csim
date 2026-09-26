"""Closed, data-only protocol that lowers to existing NF-kB episode actions.

This represents a schedule and typed amount/rate effects. It does not encode
the episode's response equations, infer doses, or evaluate arbitrary syntax.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math

from .nfkb_episode import NfkbEpisode


SCHEMA = "cellsim.nfkb-action-protocol/1"
_TOP = {"schema", "kind", "initial_checkpoint_sha256", "episode_configuration",
        "response_model_refs", "stimulus_schedule", "stimulus_transfer",
        "stimulus_withdrawal", "payload_transfer", "payload_uptake"}
_CONFIG = {"cell_count", "horizon_steps", "step_min",
           "initial_stimulus_reservoir_mol", "initial_payload_reservoir_mol"}


def _exact(value: object, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{label} fields must be exactly {sorted(keys)}")
    return value


def _amount(value: object, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite nonnegative")
    return float(value)


def _digest(value: object, label: str) -> str:
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return value


def validate_protocol(program: object) -> dict:
    p = _exact(program, _TOP, "protocol")
    if p["schema"] != SCHEMA or p["kind"] != "nfkb_timed_amount_and_rate_effects":
        raise ValueError("unsupported protocol schema or kind")
    _digest(p["initial_checkpoint_sha256"], "initial checkpoint")
    config = _exact(p["episode_configuration"], _CONFIG, "episode configuration")
    if (type(config["cell_count"]) is not int or not 1 <= config["cell_count"] <= 5 or
            type(config["horizon_steps"]) is not int or not 1 <= config["horizon_steps"] <= 1000):
        raise ValueError("cell count or horizon outside protocol range")
    step = _amount(config["step_min"], "step_min")
    if step <= 0 or Fraction(120) % Fraction(str(step)) != 0:
        raise ValueError("120-minute switches must align with episode step")
    _amount(config["initial_stimulus_reservoir_mol"], "stimulus reservoir")
    _amount(config["initial_payload_reservoir_mol"], "payload reservoir")
    ids = [f"cell_{i}" for i in range(1, config["cell_count"] + 1)]
    refs = p["response_model_refs"]
    if type(refs) is not list or len(refs) != len(ids):
        raise ValueError("response model refs require every cell identity")
    for expected, ref in zip(ids, refs):
        ref = _exact(ref, {"cell_id", "model_id", "model_digest_sha256"}, "model ref")
        if ref["cell_id"] != expected or type(ref["model_id"]) is not str or not ref["model_id"]:
            raise ValueError("response model cell identity mismatch")
        _digest(ref["model_digest_sha256"], "response model")
    schedule = _exact(p["stimulus_schedule"],
                      {"quantity_type", "sequence_key", "switch_times_min"}, "schedule")
    sequence = schedule["sequence_key"]
    if (schedule["quantity_type"] != "author_categorical_code" or
            type(sequence) is not str or len(sequence) != 4 or
            set(sequence) != {"T", "I", "L", "P"} or
            schedule["switch_times_min"] != [0, 120, 240, 360]):
        raise ValueError("schedule must be four author T/I/L/P codes at 0/120/240/360 min")
    stim = _exact(p["stimulus_transfer"],
                  {"effect", "quantity_type", "species", "amount_mol_per_switch"},
                  "stimulus transfer")
    if (stim["effect"] != "reservoir_to_field" or
            stim["quantity_type"] != "integrated_amount_mol" or
            stim["species"] != "synthetic_stimulus"):
        raise ValueError("unsupported stimulus effect, species or quantity_type")
    _amount(stim["amount_mol_per_switch"], "stimulus amount")
    withdraw = _exact(p["stimulus_withdrawal"],
                      {"effect", "quantity_type", "species", "policy"},
                      "stimulus withdrawal")
    if (withdraw["effect"] != "field_to_waste" or
            withdraw["quantity_type"] != "integrated_amount_mol" or
            withdraw["species"] != "synthetic_stimulus" or
            withdraw["policy"] != "withdraw_current_field_at_switch"):
        raise ValueError("unsupported or unpaired stimulus withdrawal effect")
    payload = _exact(p["payload_transfer"],
                     {"effect", "quantity_type", "species", "start_min", "amount_mol"},
                     "payload transfer")
    if (payload["effect"] != "reservoir_to_field" or
            payload["quantity_type"] != "integrated_amount_mol" or
            payload["species"] != "generic_inhibitor_payload"):
        raise ValueError("unsupported payload effect, species or quantity_type")
    start = _amount(payload["start_min"], "payload start")
    if Fraction(str(start)) % Fraction(str(step)) != 0:
        raise ValueError("payload start must align with episode step")
    _amount(payload["amount_mol"], "payload amount")
    uptake = _exact(p["payload_uptake"],
                    {"effect", "quantity_type", "species", "start_min",
                     "rates_mol_min_by_cell"}, "payload uptake")
    if (uptake["effect"] != "field_to_cells" or
            uptake["quantity_type"] != "rate_mol_min" or
            uptake["species"] != "generic_inhibitor_payload" or
            uptake["start_min"] != start):
        raise ValueError("unsupported payload uptake effect, unit, species or start")
    rates = uptake["rates_mol_min_by_cell"]
    if type(rates) is not list or len(rates) != len(ids):
        raise ValueError("payload rates require every cell identity")
    for expected, row in zip(ids, rates):
        row = _exact(row, {"cell_id", "rate_mol_min"}, "cell rate")
        if row["cell_id"] != expected:
            raise ValueError("payload rate cell identity mismatch")
        _amount(row["rate_mol_min"], f"{expected} rate")
    return p


def _pairs(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        if key in out:
            raise ValueError(f"duplicate protocol JSON key: {key}")
        out[key] = value
    return out


def parse_protocol_json(source: str) -> dict:
    if type(source) is not str or len(source) > 100_000:
        raise ValueError("protocol JSON must be bounded text")
    p = json.loads(source, object_pairs_hook=_pairs,
                   parse_constant=lambda value: (_ for _ in ()).throw(
                       ValueError(f"nonfinite protocol JSON: {value}")))
    return validate_protocol(p)


def protocol_digest(program: dict) -> str:
    validate_protocol(program)
    raw = json.dumps(program, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def protocol_from_episode(episode: NfkbEpisode, *, sequence_key: str = "TIPL",
                          stimulus_amount_mol: float = 0.1,
                          payload_start_min: float = 120.0,
                          payload_amount_mol: float = 0.02,
                          rates_mol_min_by_cell: dict[str, float] | None = None) -> dict:
    checkpoint = episode.checkpoint()
    if checkpoint["payload"]["accepted_steps"] != 0:
        raise ValueError("protocol must bind to an initial accepted checkpoint")
    cells = episode.observe()["cells"]
    ids = [cell["cell_id"] for cell in cells]
    if rates_mol_min_by_cell is None:
        rates_mol_min_by_cell = {cid: 0.0 for cid in ids}
    if type(rates_mol_min_by_cell) is not dict or set(rates_mol_min_by_cell) != set(ids):
        raise ValueError("payload rates require exactly the episode cell identities")
    p = {
        "schema": SCHEMA, "kind": "nfkb_timed_amount_and_rate_effects",
        "initial_checkpoint_sha256": checkpoint["sha256"],
        "episode_configuration": checkpoint["payload"]["configuration"],
        "response_model_refs": [{"cell_id": c["cell_id"], "model_id": c["model_id"],
                                 "model_digest_sha256": c["model_digest_sha256"]} for c in cells],
        "stimulus_schedule": {"quantity_type": "author_categorical_code",
                              "sequence_key": sequence_key,
                              "switch_times_min": [0, 120, 240, 360]},
        "stimulus_transfer": {"effect": "reservoir_to_field",
                              "quantity_type": "integrated_amount_mol",
                              "species": "synthetic_stimulus",
                              "amount_mol_per_switch": stimulus_amount_mol},
        "stimulus_withdrawal": {"effect": "field_to_waste",
                                "quantity_type": "integrated_amount_mol",
                                "species": "synthetic_stimulus",
                                "policy": "withdraw_current_field_at_switch"},
        "payload_transfer": {"effect": "reservoir_to_field",
                             "quantity_type": "integrated_amount_mol",
                             "species": "generic_inhibitor_payload",
                             "start_min": payload_start_min,
                             "amount_mol": payload_amount_mol},
        "payload_uptake": {"effect": "field_to_cells", "quantity_type": "rate_mol_min",
                           "species": "generic_inhibitor_payload",
                           "start_min": payload_start_min,
                           "rates_mol_min_by_cell": [
                               {"cell_id": cid,
                                "rate_mol_min": rates_mol_min_by_cell[cid]} for cid in ids]},
    }
    return validate_protocol(p)


def lower_action(program: dict, episode: NfkbEpisode) -> dict:
    p = validate_protocol(program)
    checkpoint = episode.checkpoint()
    if checkpoint["payload"]["configuration"] != p["episode_configuration"]:
        raise ValueError("episode configuration differs from bound protocol")
    if (checkpoint["payload"]["accepted_steps"] == 0 and
            checkpoint["sha256"] != p["initial_checkpoint_sha256"]):
        raise ValueError("initial checkpoint does not match protocol")
    cells = episode.observe()["cells"]
    actual = [{"cell_id": c["cell_id"], "model_id": c["model_id"],
               "model_digest_sha256": c["model_digest_sha256"]} for c in cells]
    if actual != p["response_model_refs"]:
        raise ValueError("episode cell/model identity differs from bound protocol")
    rates = {row["cell_id"]: row["rate_mol_min"] for row in
             p["payload_uptake"]["rates_mol_min_by_cell"]}
    return episode.make_scheduled_action(
        sequence_key=p["stimulus_schedule"]["sequence_key"],
        stimulus_admin_mol_per_switch=p["stimulus_transfer"]["amount_mol_per_switch"],
        payload_start_min=p["payload_transfer"]["start_min"],
        payload_admin_mol_at_start=p["payload_transfer"]["amount_mol"],
        payload_uptake_rates_mol_min_by_cell=rates,
    )


def run_protocol(program: dict, episode: NfkbEpisode) -> dict:
    p = validate_protocol(program)
    if episode.checkpoint()["sha256"] != p["initial_checkpoint_sha256"]:
        raise ValueError("initial checkpoint does not match protocol")
    actions, transitions = [], []
    residual = 0.0
    while not episode.observe()["terminated"]:
        action = lower_action(p, episode)
        transition = episode.step(action)
        actions.append(action)
        transitions.append(transition)
        residual = max(residual, transition["info"]["maximum_amount_residual_mol"])
    return {"schema": "cellsim.nfkb-action-protocol-execution/1",
            "protocol_sha256": protocol_digest(p), "actions": actions,
            "transitions": transitions,
            "final_checkpoint_sha256": episode.checkpoint()["sha256"],
            "maximum_amount_residual_mol": residual}
