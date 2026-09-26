#!/usr/bin/env python3
"""Validate dataset declarations or freeze/verify an offline evaluation campaign.

Files are hashed, never executed. Keep the digest emitted by freeze in a trusted
record and supply it to verify; reading it from the current campaign file cannot
detect replacement of that file. Contracts and integrity do not qualify biology.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from cellsim_v2.training import dataset_digest, freeze_campaign, validate_dataset, verify_campaign


def _unique_pairs(pairs):
    values = {}
    for key, value in pairs:
        if key in values:
            raise ValueError(f"duplicate JSON key: {key}")
        values[key] = value
    return values


def _nonfinite(value):
    raise ValueError(f"nonfinite JSON number: {value}")


def _finite_float(raw):
    value = float(raw)
    if not math.isfinite(value):
        _nonfinite(raw)
    return value


def _load_json(path: Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_unique_pairs,
                       parse_constant=_nonfinite, parse_float=_finite_float)
    if not isinstance(value, dict):
        raise ValueError("JSON document must be an object")
    return value


def _artifact_reference(root: Path, relative: str) -> dict:
    """Check confinement before opening bytes; runtime rechecks the resulting hash."""
    root = Path(root).resolve()
    if not root.is_dir():
        raise ValueError("artifact root must be an existing directory")
    path = PurePosixPath(relative)
    if (not relative or relative.strip() != relative or relative == "."
            or path.is_absolute() or PureWindowsPath(relative).drive
            or "\\" in relative or ":" in relative or ".." in path.parts
            or path.as_posix() != relative):
        raise ValueError("artifact path must be a normalized relative path")
    resolved = (root / relative).resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError("artifact path resolves outside the root")
    if not resolved.is_file():
        raise ValueError("artifact path must name a file")
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return {"path": relative, "sha256": digest.hexdigest()}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (("validate", "Check dataset declarations and artifact hashes"),
                            ("freeze", "Create a new campaign snapshot"),
                            ("verify", "Check an existing campaign against its trusted digest")):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--manifest", type=Path, required=True)
        command.add_argument("--root", type=Path, help="Artifact root; defaults to manifest.parent")
        if name == "freeze":
            command.add_argument("--candidate-id", required=True)
            command.add_argument("--model", required=True, help="Model artifact path relative to root")
            command.add_argument("--preprocessing", required=True,
                                 help="Preprocessing artifact path relative to root")
            command.add_argument("--evaluation", type=Path, required=True,
                                 help="JSON metric, observable_id, unit, baseline_ids declaration")
            command.add_argument("--output", type=Path, required=True,
                                 help="New campaign file; existing paths are rejected")
        elif name == "verify":
            command.add_argument("--campaign", type=Path, required=True)
            command.add_argument("--expected-digest", required=True,
                                 help="Trusted SHA-256 emitted by the original freeze")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        manifest = _load_json(args.manifest)
        root = args.root if args.root is not None else args.manifest.parent
        result = {"biological_qualification": "none"}
        if args.command == "validate":
            validated = validate_dataset(manifest, root)
            result.update(status="valid", dataset_sha256=dataset_digest(validated))
        elif args.command == "freeze":
            # Both files are read only after checking relative path confinement.
            model = _artifact_reference(root, args.model)
            preprocessing = _artifact_reference(root, args.preprocessing)
            frozen = freeze_campaign(
                args.output, manifest=manifest, root=root, candidate_id=args.candidate_id,
                model_artifact=model, preprocessing_artifact=preprocessing,
                evaluation=_load_json(args.evaluation),
            )
            result.update(status="frozen", campaign_sha256=frozen["campaign_sha256"],
                          dataset_sha256=frozen["campaign"]["dataset_sha256"], output=str(args.output.resolve()))
        else:
            frozen = verify_campaign(args.campaign, manifest=manifest, root=root,
                                     expected_digest=args.expected_digest)
            result.update(status="verified", campaign_sha256=frozen["campaign_sha256"],
                          dataset_sha256=frozen["campaign"]["dataset_sha256"])
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (OSError, ValueError, TypeError, RuntimeError) as error:
        print(json.dumps({"status": "error", "error": f"{type(error).__name__}: {error}"},
                         sort_keys=True, allow_nan=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
