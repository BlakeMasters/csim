#!/usr/bin/env python3
"""Predict an author-coded NF-κB reporter schedule from frozen weights only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.nfkb_predictor import predict_frozen


def _reject_constant(value: str):
    raise ValueError(f"nonfinite JSON constant {value}")


def run(candidate: Path, codes: tuple[int, int, int, int], dose_tier: int,
        *, overlay: Path | None = None,
        condition_id: int | None = None) -> dict:
    raw = candidate.read_bytes()
    frozen = json.loads(raw, parse_constant=_reject_constant)
    result = predict_frozen(
        frozen, codes, dose_tier,
        frozen_candidate_sha256=hashlib.sha256(raw).hexdigest())
    if overlay is not None:
        if condition_id is None:
            raise ValueError("condition ID required with overlay verification")
        observed = json.loads(overlay.read_text(encoding="utf-8"),
                              parse_constant=_reject_constant)
        if observed["frozen_candidate_sha256"] != result["frozen_candidate_sha256"]:
            raise ValueError("overlay uses a different frozen candidate")
        condition = next((item for item in observed["conditions"]
                          if item["condition_id"] == condition_id), None)
        if condition is None:
            raise ValueError("condition ID absent from overlay")
        if (condition["stimulus_codes"] != result["stimulus_codes"] or
                condition["dose_tier_code"] != dose_tier):
            raise ValueError("requested schedule differs from selected overlay condition")
        stored = condition["model_prediction"]
        if stored is None or len(stored) != len(result["predicted_reporter"]):
            raise ValueError("stored prediction unavailable")
        difference = max(abs(a - b) for a, b in zip(
            stored, result["predicted_reporter"]))
        if difference >= 1e-12:
            raise ValueError("frozen predictor differs from stored overlay")
        result["overlay_verification"] = {
            "condition_id": condition_id,
            "overlay_sha256": hashlib.sha256(overlay.read_bytes()).hexdigest(),
            "max_abs_difference": difference,
            "accepted_tolerance": 1e-12,
            "status": "pass",
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--stimulus-codes", type=int, nargs=4,
                        metavar=("S1", "S2", "S3", "S4"), required=True)
    parser.add_argument("--dose-tier", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--verify-overlay", type=Path)
    parser.add_argument("--condition-id", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.candidate.resolve(), tuple(args.stimulus_codes),
                 args.dose_tier,
                 overlay=args.verify_overlay.resolve() if args.verify_overlay else None,
                 condition_id=args.condition_id)
    encoded = json.dumps(result, indent=2, ensure_ascii=False,
                         allow_nan=False) + "\n"
    if args.output:
        with args.output.resolve().open("x", encoding="utf-8") as stream:
            stream.write(encoded)
        print(json.dumps({"status": "pass", "output": str(args.output.resolve()),
                          "points": len(result["predicted_reporter"]),
                          "overlay_verification": result.get("overlay_verification")},
                         indent=2, allow_nan=False))
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
