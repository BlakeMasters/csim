"""Version 0 typed, data-only symbolic IR for two synthetic rule motifs.

This closed subset losslessly represents runnable synthetic concentration
switches and gated same-species saturable transfers. It lowers back to the
existing ruleset, whose pure interpreter owns execution and accepted history.
No arbitrary expressions, generated Python, biology qualification, or new
mechanism is introduced by this representation.
"""
from __future__ import annotations

import json

from .biological_rules import rule_readiness, validate_ruleset
from .training import dataset_digest


_TOP = {"schema_version", "kind", "id", "execution", "context", "source_refs",
        "symbols", "statements", "ruleset_sha256"}
_SYMBOLS = {"cells", "species", "compartments"}
_COMPARTMENT = {"id", "kind", "owner", "amount_unit", "volume_unit"}
_INPUT = {"quantity", "species_id", "compartment_id", "unit"}
_SWITCH = {"id", "kind", "cell_ids", "species_id", "input", "effect",
           "parameters", "description"}
_TRANSFER = _SWITCH | {"gate"}
_SWITCH_EFFECT = {"kind", "states", "initial_state", "state_unit", "commit"}
_TRANSFER_EFFECT = {"kind", "species_id", "source_compartment_id",
                    "destination_compartment_id", "rate_unit",
                    "integrated_amount_unit", "accounting"}


def _keys(value: object, expected: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} must contain exactly {sorted(expected)}")
    return value


def _text(value: object, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a nonempty string without surrounding whitespace")
    return value


def _array(value: object, label: str, *, nonempty: bool = True) -> list:
    if type(value) is not list or (nonempty and not value):
        raise ValueError(f"{label} must be {'a nonempty' if nonempty else 'an'} array")
    return value


def _identifiers(value: object, label: str) -> list[str]:
    items = _array(value, label)
    for item in items:
        _text(item, label + " ID")
    if len(set(items)) != len(items):
        raise ValueError(f"duplicate {label} ID")
    return items


def _json_copy(value: object) -> object:
    try:
        return json.loads(json.dumps(value, allow_nan=False))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("symbolic IR requires finite JSON data") from exc


def _symbol_tables(symbols: object) -> tuple[set[str], set[str], dict[str, str]]:
    symbols = _keys(symbols, _SYMBOLS, "symbols")
    cells, species, compartments = set(), set(), {}
    for cell in _array(symbols["cells"], "cells"):
        _keys(cell, {"id", "kind"}, "cell declaration")
        if cell["kind"] != "cell":
            raise ValueError("unsupported cell kind")
        cid = _text(cell["id"], "cell ID")
        if cid in cells:
            raise ValueError("duplicate cell identity")
        cells.add(cid)
    for material in _array(symbols["species"], "species"):
        _keys(material, {"id", "amount_unit", "concentration_unit"}, "species declaration")
        sid = _text(material["id"], "species ID")
        if sid in species:
            raise ValueError("duplicate species identity")
        if material["amount_unit"] != "mol" or material["concentration_unit"] != "mol/m^3":
            raise ValueError("unsupported species units")
        species.add(sid)
    roles = set()
    for compartment in _array(symbols["compartments"], "compartments"):
        _keys(compartment, _COMPARTMENT, "compartment declaration")
        cid = _text(compartment["id"], "compartment ID")
        role = _text(compartment["kind"], "compartment kind")
        if cid in compartments or role in roles:
            raise ValueError("ambiguous compartment identity or ownership")
        if role not in ("extracellular_field", "cell_inventory"):
            raise ValueError("unsupported compartment kind")
        expected_owner = "world" if role == "extracellular_field" else "selected_cell"
        if (compartment["owner"] != expected_owner or compartment["amount_unit"] != "mol" or
                compartment["volume_unit"] != "m^3"):
            raise ValueError("compartment ownership or units do not match the supported roles")
        compartments[cid] = role
        roles.add(role)
    if roles != {"extracellular_field", "cell_inventory"}:
        raise ValueError("one extracellular field and one cell-inventory role are required")
    return cells, species, compartments


def _validate_statement(statement: object, cells: set[str], species: set[str],
                        compartments: dict[str, str]) -> None:
    if type(statement) is not dict:
        raise ValueError("statement must be an object")
    kind = statement.get("kind")
    if kind not in ("concentration_switch", "saturable_transfer"):
        raise ValueError(f"unsupported symbolic statement kind {kind}")
    _keys(statement, _SWITCH if kind == "concentration_switch" else _TRANSFER,
          "symbolic statement")
    _text(statement["id"], "statement ID")
    _text(statement["description"], "statement description")
    selected = _identifiers(statement["cell_ids"], "selected cell")
    if not set(selected) <= cells:
        raise ValueError("statement references undefined cell identity")
    sid = _text(statement["species_id"], "statement species ID")
    if sid not in species:
        raise ValueError("statement references undefined species identity")
    read = _keys(statement["input"], _INPUT, "concentration input")
    read_compartment = _text(read["compartment_id"], "input compartment ID")
    if (read["quantity"] != "concentration" or read["species_id"] != sid or
            read["unit"] != "mol/m^3" or
            compartments.get(read_compartment) != "extracellular_field"):
        raise ValueError("input must read this species concentration from the extracellular field")
    effect = statement["effect"]
    if kind == "concentration_switch":
        _keys(effect, _SWITCH_EFFECT, "switch effect")
        if (effect["kind"] != "event_state_replacement" or
                effect["states"] != ["on", "off"] or
                effect["initial_state"] not in ("on", "off") or
                effect["state_unit"] != "1" or
                effect["commit"] != "accepted_window_only"):
            raise ValueError("unsupported switch effect")
    else:
        _keys(effect, _TRANSFER_EFFECT, "material transfer effect")
        source = _text(effect["source_compartment_id"], "transfer source compartment ID")
        destination = _text(effect["destination_compartment_id"],
                            "transfer destination compartment ID")
        if (effect["kind"] != "paired_integrated_amount_transfer" or
                effect["species_id"] != sid or
                source != read_compartment or
                compartments.get(source) != "extracellular_field" or
                compartments.get(destination) != "cell_inventory" or
                effect["rate_unit"] != "mol/s" or
                effect["integrated_amount_unit"] != "mol" or
                effect["accounting"] != "source_debit_destination_credit"):
            raise ValueError("unsupported or unpaired material transfer effect")


def _lower_unchecked(ir: dict) -> dict:
    rules = []
    for statement in ir["statements"]:
        rule = {"id": statement["id"], "kind": statement["kind"],
                "cell_ids": _json_copy(statement["cell_ids"]),
                "species": statement["species_id"],
                "parameters": _json_copy(statement["parameters"]),
                "description": statement["description"]}
        if statement["kind"] == "concentration_switch":
            rule["initial_state"] = statement["effect"]["initial_state"]
        else:
            rule["gate"] = _json_copy(statement["gate"])
        rules.append(rule)
    return {"schema_version": "1", "id": ir["id"], "runnable": True,
            "execution_mode": "synthetic", "context": _json_copy(ir["context"]),
            "source_refs": _json_copy(ir["source_refs"]), "rules": rules}


def validate_symbolic(ir: object) -> dict:
    """Check closed syntax, identities, units, effects, readiness and lowering.

    This static check cannot certify a biological law or runtime amount safety.
    """
    ir = _keys(ir, _TOP, "symbolic IR")
    _json_copy(ir)  # reject non-JSON and nonfinite values before semantic checks
    if ir["schema_version"] != "0" or ir["kind"] != "cellsim_symbolic_ir":
        raise ValueError("unsupported symbolic IR schema or kind")
    _text(ir["id"], "symbolic IR ID")
    execution = _keys(ir["execution"], {"mode", "runnable"}, "execution declaration")
    if execution != {"mode": "synthetic", "runnable": True}:
        raise ValueError("symbolic IR v0 only admits runnable synthetic rules")
    digest = ir["ruleset_sha256"]
    if type(digest) is not str or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
        raise ValueError("ruleset_sha256 must be a lowercase SHA-256 hex digest")
    cells, species, compartments = _symbol_tables(ir["symbols"])
    statements = _array(ir["statements"], "statements")
    statement_ids, used_cells, used_species = set(), set(), set()
    for statement in statements:
        _validate_statement(statement, cells, species, compartments)
        if statement["id"] in statement_ids:
            raise ValueError("duplicate symbolic statement ID")
        statement_ids.add(statement["id"])
        used_cells.update(statement["cell_ids"])
        used_species.add(statement["species_id"])
    if cells != used_cells or species != used_species:
        raise ValueError("symbol declarations must match referenced identities exactly")
    ruleset = validate_ruleset(_lower_unchecked(ir))
    readiness = rule_readiness(ruleset)
    if not readiness["runnable"]:
        raise ValueError("unresolved executable symbolic rule: " + "; ".join(readiness["issues"]))
    if readiness["ruleset_sha256"] != digest:
        raise ValueError("lowered ruleset digest differs from declared history identity")
    return _json_copy(ir)


def from_ruleset(ruleset: dict) -> dict:
    """Encode a runnable synthetic ruleset without changing its interpreter meaning."""
    ruleset = validate_ruleset(ruleset)
    readiness = rule_readiness(ruleset)
    if (ruleset["execution_mode"] != "synthetic" or not ruleset["runnable"] or
            not readiness["runnable"]):
        raise ValueError("source ruleset must be runnable and synthetic")
    cells = sorted({cid for rule in ruleset["rules"] for cid in rule["cell_ids"]})
    species = sorted({rule["species"] for rule in ruleset["rules"]})
    if not cells:
        raise ValueError("source ruleset selects no cells")
    field_id, inventory_id = "extracellular-field", "cell-inventory"
    statements = []
    for rule in ruleset["rules"]:
        statement = {"id": rule["id"], "kind": rule["kind"],
                     "cell_ids": _json_copy(rule["cell_ids"]), "species_id": rule["species"],
                     "input": {"quantity": "concentration", "species_id": rule["species"],
                               "compartment_id": field_id, "unit": "mol/m^3"},
                     "parameters": _json_copy(rule["parameters"]),
                     "description": rule["description"]}
        if rule["kind"] == "concentration_switch":
            statement["effect"] = {"kind": "event_state_replacement",
                                   "states": ["on", "off"],
                                   "initial_state": rule["initial_state"],
                                   "state_unit": "1", "commit": "accepted_window_only"}
        else:
            statement["effect"] = {"kind": "paired_integrated_amount_transfer",
                                   "species_id": rule["species"],
                                   "source_compartment_id": field_id,
                                   "destination_compartment_id": inventory_id,
                                   "rate_unit": "mol/s", "integrated_amount_unit": "mol",
                                   "accounting": "source_debit_destination_credit"}
            statement["gate"] = _json_copy(rule["gate"])
        statements.append(statement)
    ir = {"schema_version": "0", "kind": "cellsim_symbolic_ir", "id": ruleset["id"],
          "execution": {"mode": "synthetic", "runnable": True},
          "context": _json_copy(ruleset["context"]),
          "source_refs": _json_copy(ruleset["source_refs"]),
          "symbols": {"cells": [{"id": cid, "kind": "cell"} for cid in cells],
                      "species": [{"id": sid, "amount_unit": "mol",
                                   "concentration_unit": "mol/m^3"} for sid in species],
                      "compartments": [
                          {"id": field_id, "kind": "extracellular_field", "owner": "world",
                           "amount_unit": "mol", "volume_unit": "m^3"},
                          {"id": inventory_id, "kind": "cell_inventory", "owner": "selected_cell",
                           "amount_unit": "mol", "volume_unit": "m^3"}]},
          "statements": statements, "ruleset_sha256": readiness["ruleset_sha256"]}
    return validate_symbolic(ir)


def to_ruleset(ir: dict) -> dict:
    """Lower the checked subset back to the existing executable ruleset."""
    checked = validate_symbolic(ir)
    return validate_ruleset(_lower_unchecked(checked))


def canonical_digest(ir: dict) -> str:
    """Hash the complete validated symbolic IR, including explicit type data."""
    return dataset_digest(validate_symbolic(ir))


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def parse_symbolic_json(text: str) -> dict:
    """Parse strict JSON and validate; no code evaluation or expression support."""
    if type(text) is not str:
        raise ValueError("symbolic JSON input must be text")
    try:
        value = json.loads(text, object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid symbolic JSON") from exc
    return validate_symbolic(value)
