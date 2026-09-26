"""Small declarative rule interpreter with explicit evidence and amount semantics.

Rules are JSON data, never Python expressions. Concentration switches annotate
discrete hypotheses in the existing event state; saturable transfers use the
reference conservative kernel. Qualification remains unqualified in every mode.
This is neither a reaction-network solver nor an SBML/PhysiCell implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
from pathlib import Path

from .state import Event, Update, World, identifier, number
from .training import dataset_digest
from .transport import CellUptake, RectilinearGrid3D, saturable_uptake_step


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f"{label} must contain exactly {sorted(expected)}")


def _text(value, label, *, nullable=False):
    if value is None and nullable:
        return
    identifier(value, label)
    if value.strip() != value:
        raise ValueError(f"{label} has surrounding whitespace")


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key}")
        result[key] = value
    return result


def _bad_constant(value):
    raise ValueError(f"nonfinite JSON constant {value}")


def load_ruleset(path: Path) -> dict:
    raw = json.loads(Path(path).read_text(encoding="utf-8"),
                     object_pairs_hook=_unique, parse_constant=_bad_constant)
    return validate_ruleset(raw)


def _parameter(value, unit, label, *, positive=False):
    _keys(value, ("value", "unit", "provenance", "source_ref", "uncertainty"), label)
    if value["unit"] != unit:
        raise ValueError(f"{label} unit must be {unit}; no implicit conversion")
    if value["provenance"] not in ("synthetic", "assumed", "measured", "unknown"):
        raise ValueError(f"{label} unsupported provenance")
    _text(value["source_ref"], f"{label} source_ref", nullable=True)
    if value["value"] is not None:
        number(value["value"], label, minimum=0, positive=positive)
        if value["provenance"] == "unknown":
            raise ValueError(f"{label} populated values need declared provenance")
        if value["provenance"] == "measured" and value["source_ref"] is None:
            raise ValueError(f"{label} measured declaration requires source_ref")
    if value["uncertainty"] is not None:
        raise ValueError("uncertainty model is not implemented; leave null and document evidence")


def validate_ruleset(value: dict) -> dict:
    """Validate planning or runnable rules; provenance declarations are not proof."""
    _keys(value, ("schema_version", "id", "runnable", "execution_mode", "context",
                  "source_refs", "rules"), "ruleset")
    # Canonical hashing rejects non-JSON values and nonfinite numbers recursively.
    dataset_digest(value)
    value = json.loads(json.dumps(value, allow_nan=False))
    if value["schema_version"] != "1" or type(value["runnable"]) is not bool:
        raise ValueError("unsupported ruleset version or runnable flag")
    _text(value["id"], "ruleset id")
    if value["execution_mode"] not in ("synthetic", "hypothesis"):
        raise ValueError("execution_mode must be synthetic or hypothesis")
    _keys(value["context"], ("cell_identity", "tissue", "scope"), "context")
    _text(value["context"]["scope"], "context scope")
    for key in ("cell_identity", "tissue"):
        _text(value["context"][key], key, nullable=True)
    if type(value["source_refs"]) is not list:
        raise ValueError("source_refs must be an array")
    for ref in value["source_refs"]:
        _text(ref, "source reference")
    if type(value["rules"]) is not list or not value["rules"]:
        raise ValueError("rules must be a nonempty array")
    by_id, ownership = {}, set()
    common = {"id", "kind", "cell_ids", "species", "parameters", "description"}
    for rule in value["rules"]:
        if type(rule) is not dict:
            raise ValueError("rule must be an object")
        kind = rule.get("kind")
        if kind not in ("concentration_switch", "saturable_transfer"):
            raise ValueError(f"unsupported rule kind {kind}")
        _keys(rule, common | ({"initial_state"} if kind == "concentration_switch" else {"gate"}), "rule")
        for name in ("id", "species", "description"):
            _text(rule[name], f"rule {name}")
        if rule["id"] in by_id:
            raise ValueError("duplicate rule id")
        by_id[rule["id"]] = rule
        if type(rule["cell_ids"]) is not list:
            raise ValueError("cell_ids must be an array")
        for cid in rule["cell_ids"]:
            _text(cid, "cell id")
        if len(set(rule["cell_ids"])) != len(rule["cell_ids"]):
            raise ValueError("duplicate cell id in rule")
        params = rule["parameters"]
        if kind == "concentration_switch":
            _keys(params, ("on_below", "off_above"), "switch parameters")
            if rule["initial_state"] not in ("on", "off"):
                raise ValueError("initial_state must be on or off")
            for key in params:
                _parameter(params[key], "mol/m^3", key)
            low, high = params["on_below"]["value"], params["off_above"]["value"]
            if low is not None and high is not None and low >= high:
                raise ValueError("on_below must be strictly below off_above")
        else:
            _keys(params, ("vmax", "km"), "transfer parameters")
            _parameter(params["vmax"], "mol/s", "vmax")
            _parameter(params["km"], "mol/m^3", "km", positive=True)
            if rule["gate"] is not None:
                _keys(rule["gate"], ("rule_id", "state"), "gate")
                _text(rule["gate"]["rule_id"], "gate rule_id")
                if rule["gate"]["state"] not in ("on", "off"):
                    raise ValueError("gate state must be on or off")
            for cid in rule["cell_ids"]:
                key = (cid, rule["species"])
                if key in ownership:
                    raise ValueError("multiple transfer rules own the same cell/species")
                ownership.add(key)
        if value["execution_mode"] == "synthetic":
            if any(p["provenance"] != "synthetic" for p in params.values()):
                raise ValueError("synthetic mode requires synthetic parameter provenance")
    for rule in by_id.values():
        gate = rule.get("gate")
        if gate is not None:
            switch = by_id.get(gate["rule_id"])
            if switch is None or switch["kind"] != "concentration_switch":
                raise ValueError("gate must reference a concentration switch")
            if not set(rule["cell_ids"]).issubset(switch["cell_ids"]):
                raise ValueError("gate switch does not cover transfer cell ids")
    return value


def rule_readiness(ruleset: dict) -> dict:
    ruleset = validate_ruleset(ruleset)
    issues = []
    if not ruleset["runnable"]:
        issues.append("ruleset is declared nonrunnable")
    for rule in ruleset["rules"]:
        if not rule["cell_ids"]:
            issues.append(f"{rule['id']}: cell selection is unset")
        for key, param in rule["parameters"].items():
            if param["value"] is None:
                issues.append(f"{rule['id']}.{key}: parameter value is unset")
    if ruleset["execution_mode"] == "hypothesis":
        for key in ("cell_identity", "tissue"):
            if ruleset["context"][key] is None:
                issues.append(f"context.{key} is unset")
    return {"ruleset_sha256": dataset_digest(ruleset), "runnable": not issues,
            "issues": issues, "execution_mode": ruleset["execution_mode"],
            "biological_qualification": "unqualified"}


@dataclass(frozen=True)
class RuleProposal:
    update: Update
    trace: tuple[dict, ...]
    ruleset_sha256: str


def _event_prefix(digest: str, rule_id: str) -> str:
    # A fixed-width token prevents valid IDs such as 'a' and 'a:b' overlapping.
    token = hashlib.sha256(rule_id.encode("utf-8")).hexdigest()
    return f"rule_state:{digest}:{token}:"


def _switch_state(world: World, digest: str, rule: dict, cid: str) -> str:
    prefix = _event_prefix(digest, rule["id"])
    state = rule["initial_state"]
    for event in world.events:
        if event.subject == cid and event.kind.startswith(prefix):
            if world.time_s < Fraction(event.time_s):
                raise ValueError("rule state event lies in the future")
            state = event.kind[len(prefix):]
            if state not in ("on", "off"):
                raise ValueError("invalid stored rule state")
    return state


def evaluate_rules(world: World, grid: RectilinearGrid3D, ruleset: dict,
                   dt_s: float) -> RuleProposal:
    """Return a pure combined proposal; caller commits with cells/fields/events.

    Switches all read the same pre-transfer world. Their newly computed states
    gate this interval's transfers. Multiple cells compete simultaneously per
    species; excessive demand rejects the complete proposal. Events become state
    only when the returned Update commits. No topology changes are supported.
    """
    ruleset = validate_ruleset(ruleset)
    readiness = rule_readiness(ruleset)
    if not readiness["runnable"]:
        raise ValueError("unresolved ruleset: " + "; ".join(readiness["issues"]))
    number(dt_s, "rule interval", positive=True)
    world.validate()
    digest = readiness["ruleset_sha256"]
    for rule in ruleset["rules"]:
        if rule["species"] not in world.fields:
            raise ValueError(f"missing signal field {rule['species']}")
        if world.fields[rule["species"]].volumes_m3 != grid.volumes_m3:
            raise ValueError("rule field volumes do not match grid")
        if not set(rule["cell_ids"]).issubset(world.cells):
            raise ValueError("rule selects unknown cells")
    states, traces, events = {}, [], []
    # Bind every selected cell on first acceptance, including transfer-only rules
    # and switches which remain at their initial state. A metadata edit changes
    # the digest too: continuation requires the identical complete definition.
    selected_cells = sorted({cid for rule in ruleset["rules"] for cid in rule["cell_ids"]})
    for cid in selected_cells:
        bindings = [event for event in world.events
                    if event.subject == cid and event.kind.startswith("rule_binding:")]
        for event in bindings:
            if event.kind != f"rule_binding:{digest}":
                raise ValueError("ruleset identity differs from accepted cell history; start a fresh context")
            if Fraction(event.time_s) > world.time_s:
                raise ValueError("rule binding event lies in the future")
        if not bindings:
            identity = json.dumps([digest, "binding", cid, str(world.time_s)])
            events.append(Event("rule:" + hashlib.sha256(identity.encode()).hexdigest(),
                                str(world.time_s), f"rule_binding:{digest}", cid))
    for rule in ruleset["rules"]:
        if rule["kind"] != "concentration_switch":
            continue
        field = world.fields[rule["species"]]
        for cid in sorted(rule["cell_ids"]):
            voxel = grid.locate(world.cells[cid].position_m)
            c = field.concentrations_mol_m3[voxel]
            number(c, "signal concentration", minimum=0)
            if field.amounts_mol[voxel] > 0 and c == 0:
                raise ValueError("signal concentration underflow")
            old = _switch_state(world, digest, rule, cid)
            low, high = (rule["parameters"][key]["value"] for key in ("on_below", "off_above"))
            state = "on" if c <= low else "off" if c >= high else old
            states[(rule["id"], cid)] = state
            traces.append({"rule_id": rule["id"], "cell_id": cid, "kind": rule["kind"],
                           "concentration_mol_m3": c, "previous_state": old, "state": state,
                           "changed": state != old})
            if state != old:
                identity = json.dumps([digest, rule["id"], cid, str(world.time_s), state])
                events.append(Event("rule:" + hashlib.sha256(identity.encode()).hexdigest(),
                                    str(world.time_s), _event_prefix(digest, rule["id"]) + state, cid))
    laws = {}
    for rule in ruleset["rules"]:
        if rule["kind"] != "saturable_transfer":
            continue
        for cid in sorted(rule["cell_ids"]):
            gate = rule["gate"]
            active = gate is None or states[(gate["rule_id"], cid)] == gate["state"]
            traces.append({"rule_id": rule["id"], "cell_id": cid, "kind": rule["kind"],
                           "species": rule["species"], "active": active})
            if active:
                laws.setdefault(rule["species"], []).append(CellUptake(
                    cid, rule["parameters"]["vmax"]["value"], rule["parameters"]["km"]["value"]))
    candidate = world.clone()
    for species, transfers in sorted(laws.items()):
        saturable_uptake_step(candidate, grid, species, transfers, dt_s).commit(
            candidate, frozenset({"cells", "fields"}))
    update = Update(
        replace_cells={cid: cell for cid, cell in candidate.cells.items() if cell != world.cells[cid]},
        replace_fields={name: field for name, field in candidate.fields.items() if field != world.fields[name]},
        events=tuple(events),
    )
    return RuleProposal(update, tuple(traces), digest)


def propose_rules(world: World, grid: RectilinearGrid3D, ruleset: dict, dt_s: float) -> Update:
    """Process-compatible entry point; persistent state is in accepted world events."""
    return evaluate_rules(world, grid, ruleset, dt_s).update
