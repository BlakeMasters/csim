"""Deterministic offline baselines for the synthetic uptake response fixture.

These JSON artifacts predict one cell's next amount; they are not executable
cell models or conservative Update proposals. No field debit, collective
overdraw check, biological calibration, or independent solver is provided.
Nearest neighbors use train-only range scaling and uniform mean increments.
Constant training dimensions are ignored in distance but still flag range
extrapolation. That flag is a diagnostic, not an error estimate or certificate.
"""
from __future__ import annotations

import hashlib
import json
import math


FEATURE_IDS = (
    "extracellular_concentration_mol_m3", "vmax_mol_s", "km_mol_m3", "dt_s",
)
FEATURE_UNITS = ("mol/m^3", "mol/s", "mol/m^3", "s")
_LAW_SCOPE = "Exact synthetic generator law; not an independent solver or biological model."
_BASE_FIELDS = {
    "schema_version", "model_id", "kind", "training_sample_ids", "training_count",
    "preprocessing_sha256",
}


def _json_value(value):
    if value is None or type(value) in (str, int, bool):
        return
    if type(value) is float and math.isfinite(value):
        return
    if type(value) is list:
        for item in value:
            _json_value(item)
        return
    if type(value) is dict and all(type(key) is str for key in value):
        for item in value.values():
            _json_value(item)
        return
    raise ValueError("response artifacts and rows must contain finite JSON values")


def _object(value, keys, label):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError(f"{label} must contain exactly {sorted(keys)}")


def _text(value, label):
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{label} must be a nonempty string without surrounding whitespace")
    return value


def _number(value, label, *, positive=False):
    if type(value) not in (int, float):
        raise ValueError(f"{label} must be a real number")
    try:
        value = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} must be representable as a finite float") from exc
    if not math.isfinite(value) or value < 0 or (positive and value == 0):
        raise ValueError(f"{label} must be finite and {'positive' if positive else 'nonnegative'}")
    return value


def _digest(value):
    _json_value(value)
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _training_identity(value):
    ids, count = value["training_sample_ids"], value["training_count"]
    if type(ids) is not list or not ids:
        raise ValueError("training_sample_ids must be a nonempty array")
    for sample_id in ids:
        _text(sample_id, "training sample_id")
    if ids != sorted(set(ids)):
        raise ValueError("training sample IDs must be unique and sorted")
    if type(count) is not int or count != len(ids):
        raise ValueError("training_count must match training_sample_ids")
    return ids


def _row_inputs(row):
    _json_value(row)
    if type(row) is not dict or "inputs" not in row or "dt_s" not in row:
        raise ValueError("response row requires inputs and dt_s")
    values = row["inputs"]
    _object(values, (*FEATURE_IDS[:3], "cell_amount_mol"), "row inputs")
    features = [
        _number(values["extracellular_concentration_mol_m3"], "extracellular concentration"),
        _number(values["vmax_mol_s"], "vmax"),
        _number(values["km_mol_m3"], "Km", positive=True),
        _number(row["dt_s"], "dt_s"),
    ]
    return features, _number(values["cell_amount_mol"], "current cell amount")


def _mean(values):
    """Nonnegative mean without overflowing a representable sum of means."""
    maximum = max(values)
    if maximum == 0:
        return 0.0
    value = maximum * (math.fsum(item / maximum for item in values) / len(values))
    value = _number(value, "mean amount increment")
    if value == 0:
        raise ValueError("positive mean amount increment underflow is unsupported")
    return value


def _scaled(features, preprocessing):
    output = []
    for value, minimum, span, constant in zip(
            features, preprocessing["minimums"], preprocessing["ranges"],
            preprocessing["constant_features"]):
        scaled = 0.0 if constant else (value - minimum) / span
        if not math.isfinite(scaled):
            raise ValueError("normalized feature is not representable as a finite float")
        output.append(scaled)
    return output


def _validate_preprocessing(preprocessing):
    _json_value(preprocessing)
    _object(preprocessing, {
        "schema_version", "feature_ids", "feature_units", "minimums", "maxima", "ranges",
        "constant_features", "training_sample_ids", "training_count", "constant_dimension_policy",
    }, "preprocessing")
    if preprocessing["schema_version"] != "1":
        raise ValueError("unsupported preprocessing schema_version")
    if preprocessing["feature_ids"] != list(FEATURE_IDS) or preprocessing["feature_units"] != list(FEATURE_UNITS):
        raise ValueError("preprocessing feature order or units do not match the response contract")
    if preprocessing["constant_dimension_policy"] != "ignore_in_distance_but_flag_extrapolation":
        raise ValueError("unsupported constant dimension policy")
    _training_identity(preprocessing)
    for key in ("minimums", "maxima", "ranges", "constant_features"):
        if type(preprocessing[key]) is not list or len(preprocessing[key]) != len(FEATURE_IDS):
            raise ValueError(f"preprocessing {key} must match the feature dimension")
    for index in range(len(FEATURE_IDS)):
        minimum = _number(preprocessing["minimums"][index], "feature minimum", positive=index == 2)
        maximum = _number(preprocessing["maxima"][index], "feature maximum", positive=index == 2)
        span = _number(preprocessing["ranges"][index], "feature range")
        constant = preprocessing["constant_features"][index]
        if maximum < minimum or span != maximum - minimum:
            raise ValueError("feature range does not match its minimum/maximum")
        if type(constant) is not bool or constant != (span == 0):
            raise ValueError("constant feature flag does not match its range")


def _validate_model(model, preprocessing):
    _json_value(model)
    if type(model) is not dict:
        raise ValueError("model must be a JSON object")
    kind = model.get("kind")
    if kind in ("no_change", "training_mean_increment", "synthetic_uptake_law"):
        extra = {"mean_increment_mol"} if kind == "training_mean_increment" else (
            {"evidence_scope"} if kind == "synthetic_uptake_law" else set())
        expected_id = kind
    elif kind == "knn":
        extra = {"k", "effective_k", "training_examples"}
        if type(model.get("k")) is not int or model["k"] <= 0:
            raise ValueError("nearest-neighbor k must be a positive integer")
        expected_id = f"knn_k{model['k']}"
    else:
        raise ValueError("unsupported response model kind")
    _object(model, _BASE_FIELDS | extra, "model")
    if model["schema_version"] != "1" or model["model_id"] != expected_id:
        raise ValueError("unsupported response schema_version or model_id")
    ids = _training_identity(model)
    if ids != preprocessing["training_sample_ids"]:
        raise ValueError("model and preprocessing training sample IDs differ")
    if model["preprocessing_sha256"] != _digest(preprocessing):
        raise ValueError("model/preprocessing digest mismatch")
    if kind == "training_mean_increment":
        _number(model["mean_increment_mol"], "mean increment")
    elif kind == "synthetic_uptake_law":
        if model["evidence_scope"] != _LAW_SCOPE:
            raise ValueError("synthetic control must retain its generator-law evidence scope")
    elif kind == "knn":
        if type(model["effective_k"]) is not int or model["effective_k"] != min(model["k"], len(ids)):
            raise ValueError("effective_k does not match k and the training count")
        examples = model["training_examples"]
        if type(examples) is not list or len(examples) != len(ids):
            raise ValueError("training_examples must match the training count")
        for sample_id, example in zip(ids, examples):
            _object(example, ("sample_id", "scaled_features", "increment_mol"), "training example")
            if example["sample_id"] != sample_id:
                raise ValueError("training example IDs do not match training_sample_ids")
            features = example["scaled_features"]
            if type(features) is not list or len(features) != len(FEATURE_IDS):
                raise ValueError("training example feature dimension mismatch")
            for index, value in enumerate(features):
                value = _number(value, "scaled training feature")
                if value > 1 or (preprocessing["constant_features"][index] and value != 0):
                    raise ValueError("scaled training features must lie in their fitted range")
            _number(example["increment_mol"], "training example increment")


def fit_models(train_rows, *, ks=(1, 3, 5)) -> tuple[dict, dict]:
    """Fit JSON baseline artifacts only on explicit training rows.

    Targets must be nonnegative uptake increments. Each requested positive k
    yields knn_k{k}; effective_k=min(k, training_count) is recorded explicitly.
    IDs order rows and resolve distance ties; no ID, time, current amount, or
    held-out label enters a learned feature. The caller remains responsible for
    dataset/trajectory provenance and split grouping before calling this helper.
    """
    if type(train_rows) is not list or not train_rows:
        raise ValueError("train_rows must be a nonempty list")
    requested = tuple(ks)
    if any(type(k) is not int or k <= 0 for k in requested) or len(set(requested)) != len(requested):
        raise ValueError("ks must contain unique positive integers")
    samples, seen = [], set()
    for row in train_rows:
        features, current = _row_inputs(row)
        if row.get("split") != "train":
            raise ValueError("fit_models accepts only rows whose split is train")
        sample_id = _text(row.get("sample_id"), "sample_id")
        if sample_id in seen:
            raise ValueError("training sample_id must be unique")
        seen.add(sample_id)
        _object(row.get("targets"), ("cell_amount_mol",), "row targets")
        target = _number(row["targets"]["cell_amount_mol"], "target cell amount")
        increment = _number(target - current, "target uptake increment")
        samples.append((sample_id, features, increment))
    samples.sort(key=lambda item: item[0])
    minimums = [min(sample[1][index] for sample in samples) for index in range(len(FEATURE_IDS))]
    maxima = [max(sample[1][index] for sample in samples) for index in range(len(FEATURE_IDS))]
    ranges = [maximum - minimum for minimum, maximum in zip(minimums, maxima)]
    ids = [sample[0] for sample in samples]
    preprocessing = {
        "schema_version": "1", "feature_ids": list(FEATURE_IDS), "feature_units": list(FEATURE_UNITS),
        "minimums": minimums, "maxima": maxima, "ranges": ranges,
        "constant_features": [span == 0 for span in ranges],
        "constant_dimension_policy": "ignore_in_distance_but_flag_extrapolation",
        "training_sample_ids": ids, "training_count": len(ids),
    }
    common = {
        "schema_version": "1", "training_sample_ids": ids, "training_count": len(ids),
        "preprocessing_sha256": _digest(preprocessing),
    }
    models = {
        "no_change": {**common, "model_id": "no_change", "kind": "no_change"},
        "training_mean_increment": {
            **common, "model_id": "training_mean_increment", "kind": "training_mean_increment",
            "mean_increment_mol": _mean([sample[2] for sample in samples]),
        },
        "synthetic_uptake_law": {
            **common, "model_id": "synthetic_uptake_law", "kind": "synthetic_uptake_law",
            "evidence_scope": _LAW_SCOPE,
        },
    }
    for k in sorted(requested):
        model_id = f"knn_k{k}"
        models[model_id] = {
            **common, "model_id": model_id, "kind": "knn", "k": k, "effective_k": min(k, len(ids)),
            "training_examples": [
                {"sample_id": sample_id, "scaled_features": _scaled(features, preprocessing),
                 "increment_mol": increment}
                for sample_id, features, increment in samples
            ],
        }
    # Detach nested IDs shared during construction; callers can serialize each artifact.
    return json.loads(json.dumps(models, allow_nan=False)), json.loads(json.dumps(preprocessing, allow_nan=False))


def predict(model: dict, preprocessing: dict, row: dict) -> dict:
    """Predict an offline amount endpoint from inputs; target labels are unused.

    Validates exact artifact versions, shapes, units, finite values and matching
    preprocessing identity. No clipping, physical-state mutation, or guarantee
    under extrapolation is performed. Invalid/unrepresentable arithmetic raises.
    """
    _validate_preprocessing(preprocessing)
    _validate_model(model, preprocessing)
    features, current = _row_inputs(row)
    outside = any(value < lo or value > hi for value, lo, hi in
                  zip(features, preprocessing["minimums"], preprocessing["maxima"]))
    kind = model["kind"]
    if kind == "no_change":
        increment = 0.0
    elif kind == "training_mean_increment":
        increment = float(model["mean_increment_mol"])
    elif kind == "knn":
        query = _scaled(features, preprocessing)
        neighbors = []
        for example in model["training_examples"]:
            distance = math.dist(query, example["scaled_features"])
            if not math.isfinite(distance):
                raise ValueError("nearest-neighbor distance is not finite")
            neighbors.append((distance, example["sample_id"], example["increment_mol"]))
        neighbors.sort(key=lambda item: (item[0], item[1]))
        increment = _mean([item[2] for item in neighbors[:model["effective_k"]]])
    else:
        concentration, vmax, km, dt = features
        if concentration == 0 or vmax == 0 or dt == 0:
            increment = 0.0
        else:
            if concentration <= km:
                ratio = concentration / km
                saturation = ratio / (1 + ratio)
            else:
                saturation = 1 / (1 + km / concentration)
            rate = _number(vmax * saturation, "synthetic uptake rate")
            increment = _number(rate * dt, "synthetic uptake increment")
            if saturation == 0 or rate == 0 or increment == 0:
                raise ValueError("positive synthetic uptake underflow is unsupported")
    increment = _number(increment, "predicted increment")
    amount = _number(current + increment, "predicted amount")
    return {"amount_mol": amount, "increment_mol": increment, "outside_training_range": outside}
