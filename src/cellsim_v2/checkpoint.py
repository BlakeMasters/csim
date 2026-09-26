"""Checked JSON checkpoints for World + random.Random + supplied JSON private state.

No pickle or executable payload. Restoring a third-party solver is NOT implemented.
A checksum detects corruption; it does not authenticate a malicious writer.
"""
from __future__ import annotations
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import random
import tempfile
from typing import Any
from .state import AmountField, Cell, Event, LedgerEntry, World

FORMAT = "cellsim-reference-checkpoint/2"


def canonical_bytes(data: Any) -> bytes:
    return json.dumps(data,sort_keys=True,separators=(",",":"),allow_nan=False).encode("utf-8")


def encode_world(world: World) -> dict:
    world.validate()
    return {"time_s":str(world.time_s),"step":world.step,
            "cells":{k:asdict(v) for k,v in world.cells.items()},
            "fields":{k:asdict(v) for k,v in world.fields.items()},
            "events":[asdict(e) for e in world.events],
            "ledger":[asdict(e) for e in world.ledger]}


def decode_world(d: dict) -> World:
    if set(d)!={"time_s","step","cells","fields","events","ledger"}:
        raise ValueError("unsupported world keys")
    cells={k:Cell(**(v | {"position_m":tuple(v["position_m"])})) for k,v in d["cells"].items()}
    fields={k:AmountField(v["species"],tuple(v["amounts_mol"]),tuple(v["volumes_m3"])) for k,v in d["fields"].items()}
    events=[Event(**(e | {"related":tuple(e["related"])})) for e in d["events"]]
    world=World(Fraction(d["time_s"]),d["step"],cells,fields,
                [LedgerEntry(**e) for e in d["ledger"]],events)
    world.validate()
    return world


def _tuples(value: Any) -> Any:
    return tuple(_tuples(v) for v in value) if isinstance(value,list) else value


def _check_private_json(value: Any) -> None:
    """Reject values whose Python shape would change on a JSON round-trip."""
    if type(value) is dict:
        for key, item in value.items():
            if type(key) is not str:
                raise ValueError("private state JSON keys must be strings")
            _check_private_json(item)
    elif type(value) is list:
        for item in value:
            _check_private_json(item)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("private state must contain only JSON-native values")


def save_checkpoint(path: Path, world: World, rng: random.Random,
                    execution_fingerprint: str, private_json: dict | None = None) -> None:
    if not isinstance(execution_fingerprint,str) or not execution_fingerprint:
        raise ValueError("execution fingerprint required")
    if private_json is not None and not isinstance(private_json,dict):
        raise TypeError("private state must be a JSON dictionary")
    _check_private_json({} if private_json is None else private_json)
    payload={"format":FORMAT,"execution_fingerprint":execution_fingerprint,
             "world":encode_world(world),"rng_state":rng.getstate(),
             "private_json":{} if private_json is None else private_json}
    raw=canonical_bytes(payload)  # fail before replacing any existing file
    wrapper={"payload":payload,"sha256":hashlib.sha256(raw).hexdigest()}
    data=canonical_bytes(wrapper)
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+".",suffix=".tmp",dir=path.parent)
    try:
        with os.fdopen(fd,"wb") as f:
            f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        # File fsync + atomic replace; power-loss directory durability is platform-specific.
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_checkpoint(path: Path, execution_fingerprint: str) -> tuple[World,random.Random,dict]:
    path=Path(path)
    if path.stat().st_size>10*1024*1024:
        raise ValueError("checkpoint exceeds reference reader's 10 MiB limit")
    def reject_constant(value: str):
        raise ValueError(f"nonfinite JSON number: {value}")
    wrapper=json.loads(path.read_text(encoding="utf-8"),parse_constant=reject_constant)
    if set(wrapper)!={"payload","sha256"}:
        raise ValueError("invalid checkpoint wrapper")
    p=wrapper["payload"]
    if hashlib.sha256(canonical_bytes(p)).hexdigest()!=wrapper["sha256"]:
        raise ValueError("checkpoint hash mismatch")
    if p.get("format")!=FORMAT or p.get("execution_fingerprint")!=execution_fingerprint:
        raise ValueError("checkpoint format or execution fingerprint mismatch")
    world=decode_world(p["world"])
    rng=random.Random(); rng.setstate(_tuples(p["rng_state"]))
    if not isinstance(p["private_json"],dict):
        raise ValueError("private state must be JSON object")
    return world,rng,p["private_json"]
