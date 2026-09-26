"""Closed, data-only expression graph for an illustrative NF-kB response step.

This represents the response recurrence already implemented by NfkbEpisode.
It does not encode the episode's material transfers, schedule, or biology.
"""
from __future__ import annotations

import hashlib
import json
import math
import re


SCHEMA = "cellsim-symbolic-response/1"
SCOPE = "illustrative_nfkb_proxy_not_biologically_calibrated"
MAX_NODES = 64
MAX_DEPTH = 16
MAX_JSON_BYTES = 32768
_ID = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
_UNITS = {"1", "mol", "mol/m^3", "min"}
_SOURCES = {
    "stimulus_concentration_mol_m3": ("mol/m^3", "nonnegative"),
    "payload_amount_mol": ("mol", "nonnegative"),
    "previous_nuclear_proxy": ("1", "nonnegative"),
    "previous_feedback": ("1", "nonnegative"),
    "previous_reporter_index": ("1", "nonnegative"),
    "step_min": ("min", "positive"),
    "stimulus_half_response_mol_m3": ("mol/m^3", "positive"),
    "feedback_strength": ("1", "nonnegative"),
    "payload_half_effect_mol": ("mol", "positive"),
    "nuclear_relaxation_min": ("min", "positive"),
    "feedback_relaxation_min": ("min", "positive"),
    "reporter_relaxation_min": ("min", "positive"),
}
_OUTPUTS = {"nuclear_proxy", "feedback", "reporter_index"}


def _object(value: object, keys: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ValueError(f"{label} requires exactly {sorted(keys)}")
    return value


def _id(value: object, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise ValueError(f"{label} must be a bounded lowercase identifier")
    return value


def _number(value: object, label: str, domain: str = "finite") -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be a finite number") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} must be a finite number")
    if domain == "positive" and result <= 0:
        raise ValueError(f"{label} must be positive")
    if domain == "nonnegative" and result < 0:
        raise ValueError(f"{label} must be nonnegative")
    return result


def _binary_unit(op: str, left: str, right: str) -> str:
    if op == "add":
        if left != right:
            raise ValueError("add requires matching units")
        return left
    if op == "mul":
        if left == "1":
            return right
        if right == "1":
            return left
        raise ValueError("mul requires a dimensionless factor")
    if op == "div":
        if left == right:
            return "1"
        if right == "1":
            return left
        raise ValueError("div requires matching units or dimensionless divisor")
    raise ValueError("unsupported binary operation")


def validate_response_program(program: object) -> dict:
    """Validate closed syntax, sources, units, references and graph bounds."""
    program = _object(program, {"schema_version", "kind", "id", "scope",
                                "nodes", "outputs"}, "response program")
    try:
        encoded = json.dumps(program, sort_keys=True, separators=(",", ":"),
                             allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("response program requires finite JSON data") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise ValueError("response program exceeds JSON size limit")
    if (program["schema_version"] != SCHEMA or
            program["kind"] != "typed_expression_graph" or
            program["scope"] != SCOPE):
        raise ValueError("unsupported response program schema, kind or scope")
    _id(program["id"], "program ID")
    nodes = program["nodes"]
    if type(nodes) is not list or not 1 <= len(nodes) <= MAX_NODES:
        raise ValueError("response program node count out of bounds")
    units: dict[str, str] = {}
    depths: dict[str, int] = {}
    sources: set[str] = set()
    for node in nodes:
        if type(node) is not dict:
            raise ValueError("node must be an object")
        op = node.get("op")
        if op == "input":
            _object(node, {"id", "op", "unit", "source"}, "input node")
        elif op == "constant":
            _object(node, {"id", "op", "unit", "value"}, "constant node")
        elif op in ("add", "mul", "div"):
            _object(node, {"id", "op", "unit", "args"}, "binary node")
        elif op == "relax":
            _object(node, {"id", "op", "unit", "previous", "target",
                           "dt", "tau"}, "relax node")
        else:
            raise ValueError(f"unsupported response operation {op}")
        nid = _id(node["id"], "node ID")
        if nid in units:
            raise ValueError("duplicate response node ID")
        declared = node["unit"]
        if declared not in _UNITS:
            raise ValueError("unsupported response unit")
        refs: list[str] = []
        if op == "input":
            source = node["source"]
            if source not in _SOURCES or source in sources:
                raise ValueError("unknown or duplicate response input source")
            if declared != _SOURCES[source][0]:
                raise ValueError("input source unit mismatch")
            sources.add(source)
            inferred = declared
        elif op == "constant":
            _number(node["value"], "constant")
            inferred = declared
        elif op in ("add", "mul", "div"):
            args = node["args"]
            if type(args) is not list or len(args) != 2:
                raise ValueError("binary node requires two references")
            refs = [_id(arg, "node reference") for arg in args]
            if any(ref not in units for ref in refs):
                raise ValueError("unknown or forward response node reference")
            inferred = _binary_unit(op, units[refs[0]], units[refs[1]])
        else:
            refs = [_id(node[key], key + " reference")
                    for key in ("previous", "target", "dt", "tau")]
            if any(ref not in units for ref in refs):
                raise ValueError("unknown or forward response node reference")
            if (units[refs[0]] != units[refs[1]] or units[refs[2]] != "min" or
                    units[refs[3]] != "min"):
                raise ValueError("relax requires matching state units and minute times")
            inferred = units[refs[0]]
        if declared != inferred:
            raise ValueError("response node declared unit differs from inferred unit")
        depth = 1 + max((depths[ref] for ref in refs), default=0)
        if depth > MAX_DEPTH:
            raise ValueError("response graph depth exceeds limit")
        units[nid], depths[nid] = inferred, depth
    outputs = _object(program["outputs"], _OUTPUTS, "response outputs")
    for name, ref in outputs.items():
        if _id(ref, name + " output") not in units or units[ref] != "1":
            raise ValueError("response output requires a dimensionless node")
    return json.loads(encoded)


def _unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError(f"nonfinite JSON constant: {value}")


def parse_response_json(text: str) -> dict:
    """Strict JSON parse; no code evaluation, expressions or unknown operations."""
    if type(text) is not str or len(text.encode("utf-8")) > MAX_JSON_BYTES:
        raise ValueError("response JSON text missing or too large")
    try:
        value = json.loads(text, object_pairs_hook=_unique_pairs,
                           parse_constant=_reject_constant)
    except json.JSONDecodeError as exc:
        raise ValueError("invalid response JSON") from exc
    return validate_response_program(value)


def response_digest(program: dict) -> str:
    checked = validate_response_program(program)
    encoded = json.dumps(checked, sort_keys=True, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evaluate_response(program: dict, inputs: dict) -> dict[str, float]:
    """Purely evaluate one cell/interval; caller owns amount and state commits."""
    checked = validate_response_program(program)
    sources = {node["source"] for node in checked["nodes"] if node["op"] == "input"}
    if type(inputs) is not dict or set(inputs) != sources:
        raise ValueError("response inputs must match declared sources exactly")
    values: dict[str, float] = {}
    for node in checked["nodes"]:
        op = node["op"]
        if op == "input":
            source = node["source"]
            value = _number(inputs[source], source, _SOURCES[source][1])
        elif op == "constant":
            value = _number(node["value"], "constant")
        elif op in ("add", "mul", "div"):
            left, right = (values[ref] for ref in node["args"])
            if op == "add":
                value = left + right
            elif op == "mul":
                value = left * right
            else:
                if right == 0:
                    raise ValueError("response division by zero")
                value = left / right
        else:
            previous, target, dt, tau = (values[node[key]] for key in
                                         ("previous", "target", "dt", "tau"))
            if dt <= 0 or tau <= 0:
                raise ValueError("response relaxation times must be positive")
            value = previous + (target - previous) * -math.expm1(-dt / tau)
        values[node["id"]] = _number(value, node["id"])
    outputs = {name: values[ref] for name, ref in checked["outputs"].items()}
    if (not 0 <= outputs["nuclear_proxy"] <= 1 or
            outputs["feedback"] < 0 or outputs["reporter_index"] < 0):
        raise ValueError("response output outside illustrative state domain")
    return outputs


def nfkb_response_program() -> dict:
    """Canonical graph matching NfkbEpisode's illustrative recurrence."""
    def inp(nid: str, source: str, unit: str) -> dict:
        return {"id": nid, "op": "input", "source": source, "unit": unit}

    def binary(nid: str, op: str, unit: str, left: str, right: str) -> dict:
        return {"id": nid, "op": op, "unit": unit, "args": [left, right]}

    def relax(nid: str, previous: str, target: str, tau: str) -> dict:
        return {"id": nid, "op": "relax", "unit": "1", "previous": previous,
                "target": target, "dt": "step", "tau": tau}

    nodes = [
        inp("stimulus", "stimulus_concentration_mol_m3", "mol/m^3"),
        inp("half_response", "stimulus_half_response_mol_m3", "mol/m^3"),
        binary("drive_denominator", "add", "mol/m^3", "half_response", "stimulus"),
        binary("drive", "div", "1", "stimulus", "drive_denominator"),
        inp("strength", "feedback_strength", "1"),
        inp("old_feedback", "previous_feedback", "1"),
        binary("feedback_inhibition", "mul", "1", "strength", "old_feedback"),
        {"id": "one", "op": "constant", "unit": "1", "value": 1.0},
        binary("inhibition_base", "add", "1", "one", "feedback_inhibition"),
        inp("payload", "payload_amount_mol", "mol"),
        inp("payload_half", "payload_half_effect_mol", "mol"),
        binary("payload_inhibition", "div", "1", "payload", "payload_half"),
        binary("inhibition", "add", "1", "inhibition_base", "payload_inhibition"),
        binary("nuclear_target", "div", "1", "drive", "inhibition"),
        inp("old_nuclear", "previous_nuclear_proxy", "1"),
        inp("step", "step_min", "min"),
        inp("nuclear_tau", "nuclear_relaxation_min", "min"),
        relax("nuclear_next", "old_nuclear", "nuclear_target", "nuclear_tau"),
        inp("feedback_tau", "feedback_relaxation_min", "min"),
        relax("feedback_next", "old_feedback", "old_nuclear", "feedback_tau"),
        inp("old_reporter", "previous_reporter_index", "1"),
        inp("reporter_tau", "reporter_relaxation_min", "min"),
        relax("reporter_next", "old_reporter", "old_nuclear", "reporter_tau"),
    ]
    program = {"schema_version": SCHEMA, "kind": "typed_expression_graph",
               "id": "illustrative_nfkb_response_v1", "scope": SCOPE,
               "nodes": nodes,
               "outputs": {"nuclear_proxy": "nuclear_next", "feedback": "feedback_next",
                           "reporter_index": "reporter_next"}}
    return validate_response_program(program)
