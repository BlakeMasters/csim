"""Pure, offline synthetic continuous response memory (H02 reference slice).

The dimensionless state obeys dm/dt = (g(u) - m) / tau for a concentration u
held constant on each accepted interval. Here g(u) = intercept + slope * u.
The declared synthetic response index is offset + scale * m at the interval
end. This is an exact constant-input scalar relaxation update, not an oxygen
law, measured assay, conservative material transfer, or biological model.

Callers must split input changes at known interval boundaries. The returned
state is a replacement proposal only; this module does not own transactions,
physical amounts, division, solver rollback, or checkpoint file durability.
"""
from __future__ import annotations

import hashlib
import json
import math


_MODEL_KEYS = {"schema_version", "kind", "model_id", "context_id",
               "evidence_scope", "units", "parameters"}
_PARAMETER_KEYS = {"tau_s", "target_intercept", "target_slope_m3_per_mol",
                   "observation_offset", "observation_scale"}
_UNITS = {"time": "s", "exposure_concentration": "mol/m^3", "memory": "1",
          "target_slope": "m^3/mol", "observation": "1"}
_STATE_KEYS = {"schema_version", "model_id", "model_digest_sha256", "context_id",
               "entity_id", "accepted_time_s", "memory", "memory_unit",
               "initial_time_s", "initial_memory", "initialization"}
_INITIALIZATION_KEYS = {"kind", "source_id"}


def _keys(value: object, expected: set[str], label: str) -> dict:
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label} must contain exactly {sorted(expected)}")
    return value


def _identifier(value: object, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a nonempty string without surrounding whitespace")
    return value


def _number(value: object, label: str, *, nonnegative: bool = False,
            positive: bool = False) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a finite real number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be finite") from exc
    if not math.isfinite(result) or (nonnegative and result < 0) or (positive and result <= 0):
        raise ValueError(f"{label} must be finite and within its declared range")
    return result


def _finite_result(value: float, label: str) -> float:
    if not math.isfinite(value):
        raise ValueError(f"{label} is not representable as a finite float")
    return value


def _model_digest(model: dict) -> str:
    canonical = json.dumps(model, sort_keys=True, separators=(",", ":"),
                           allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_model(model: object) -> dict:
    model = _keys(model, _MODEL_KEYS, "response model")
    if model["schema_version"] != "1" or model["kind"] != "synthetic_scalar_relaxation":
        raise ValueError("unsupported response model schema or kind")
    if model["evidence_scope"] != "synthetic_reference_only":
        raise ValueError("response model evidence scope must remain synthetic_reference_only")
    _identifier(model["model_id"], "model_id")
    _identifier(model["context_id"], "context_id")
    if _keys(model["units"], set(_UNITS), "response model units") != _UNITS:
        raise ValueError("response model units do not match the H02 contract")
    params = _keys(model["parameters"], _PARAMETER_KEYS, "response model parameters")
    _number(params["tau_s"], "tau_s", positive=True)
    for key in _PARAMETER_KEYS - {"tau_s"}:
        _number(params[key], key, nonnegative=True)
    return model


def create_relaxation_model(*, model_id: str, context_id: str, tau_s: float,
                            target_intercept: float, target_slope_m3_per_mol: float,
                            observation_offset: float = 0.0,
                            observation_scale: float = 1.0) -> dict:
    """Create a JSON-compatible definition with synthetic, explicit SI units."""
    model = {
        "schema_version": "1", "kind": "synthetic_scalar_relaxation",
        "model_id": model_id, "context_id": context_id,
        "evidence_scope": "synthetic_reference_only", "units": dict(_UNITS),
        "parameters": {
            "tau_s": tau_s, "target_intercept": target_intercept,
            "target_slope_m3_per_mol": target_slope_m3_per_mol,
            "observation_offset": observation_offset,
            "observation_scale": observation_scale,
        },
    }
    _validate_model(model)
    # Normalize all numeric values, making JSON identity stable across int/float inputs.
    model["parameters"] = {key: float(value) for key, value in model["parameters"].items()}
    return model


def _initialization(value: object) -> dict:
    value = _keys(value, _INITIALIZATION_KEYS, "initialization provenance")
    if value["kind"] != "declared_synthetic_initial_state":
        raise ValueError("initialization kind must be declared_synthetic_initial_state")
    _identifier(value["source_id"], "initialization source_id")
    return value


def initialize_response(model: dict, *, entity_id: str, initial_memory: float,
                        accepted_time_s: float, initialization_provenance: dict) -> dict:
    """Create explicit state; unknown prehistory requires a declared initializer."""
    _validate_model(model)
    _identifier(entity_id, "entity_id")
    memory = _number(initial_memory, "initial_memory", nonnegative=True)
    time_s = _number(accepted_time_s, "accepted_time_s", nonnegative=True)
    source = _initialization(initialization_provenance)
    return {
        "schema_version": "1", "model_id": model["model_id"],
        "model_digest_sha256": _model_digest(model),
        "context_id": model["context_id"], "entity_id": entity_id,
        "accepted_time_s": time_s, "memory": memory, "memory_unit": "1",
        "initial_time_s": time_s, "initial_memory": memory,
        "initialization": dict(source),
    }


def _validate_state(model: dict, state: object) -> dict:
    state = _keys(state, _STATE_KEYS, "response state")
    if state["schema_version"] != "1":
        raise ValueError("unsupported response state schema")
    if (state["model_id"] != model["model_id"] or
            state["model_digest_sha256"] != _model_digest(model) or
            state["context_id"] != model["context_id"]):
        raise ValueError("response model or context identity mismatch")
    _identifier(state["entity_id"], "entity_id")
    if state["memory_unit"] != "1":
        raise ValueError("response state memory_unit must be dimensionless (1)")
    accepted = _number(state["accepted_time_s"], "accepted_time_s", nonnegative=True)
    initial = _number(state["initial_time_s"], "initial_time_s", nonnegative=True)
    if accepted < initial:
        raise ValueError("accepted time precedes initialization time")
    _number(state["memory"], "memory", nonnegative=True)
    _number(state["initial_memory"], "initial_memory", nonnegative=True)
    _initialization(state["initialization"])
    return state


def advance_response(model: dict, state: dict, *,
                     exposure_concentration_mol_m3: float, end_time_s: float) -> dict:
    """Return a new state and endpoint observation for one constant-input interval.

    The input applies throughout [state.accepted_time_s, end_time_s). No future
    input is read. A zero-duration interval returns the same memory and time.
    """
    _validate_model(model)
    _validate_state(model, state)
    exposure = _number(exposure_concentration_mol_m3,
                       "exposure_concentration_mol_m3", nonnegative=True)
    end = _number(end_time_s, "end_time_s", nonnegative=True)
    start = float(state["accepted_time_s"])
    if end < start:
        raise ValueError("end time precedes accepted state time")
    elapsed = _finite_result(end - start, "elapsed time")
    params = model["parameters"]
    target = _finite_result(params["target_slope_m3_per_mol"] * exposure,
                            "relaxation target")
    target = _finite_result(params["target_intercept"] + target,
                            "relaxation target")
    memory = float(state["memory"])
    if elapsed:
        remaining = math.exp(-elapsed / params["tau_s"])
        memory = _finite_result(target + (memory - target) * remaining,
                                "updated memory")
    observation = _finite_result(params["observation_offset"] +
                                 params["observation_scale"] * memory,
                                 "synthetic response index")
    replacement = dict(state)
    replacement["initialization"] = dict(state["initialization"])
    replacement["accepted_time_s"] = end
    replacement["memory"] = memory
    return {"state": replacement,
            "observations": [{"name": "synthetic_response_index", "value": observation,
                              "unit": "1", "time_s": end}]}
