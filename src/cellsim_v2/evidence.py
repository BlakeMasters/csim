"""Exact-reference-case evidence lookup, NOT an online fidelity controller.

No domain interpolation, uncertainty guarantee, biological validation, or solver run.
Matching a stored numerical case is deliberately weaker than qualifying a new state.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
from pathlib import Path
from .state import identifier,number


@dataclass(frozen=True)
class CaseEvidence:
    solver_id: str
    execution_fingerprint: str
    case_fingerprint: str
    qoi: str
    unit: str
    measured_error: float
    measured_total_seconds: float
    artifact_path: str
    artifact_sha256: str

    def validate(self,root: Path) -> None:
        for key in (self.solver_id,self.execution_fingerprint,self.case_fingerprint,self.qoi,self.unit):
            identifier(key,"evidence key")
        number(self.measured_error,"measured error",minimum=0)
        number(self.measured_total_seconds,"cost",minimum=0)
        root=root.resolve()
        file=(root/self.artifact_path).resolve()
        if not file.is_relative_to(root) or not file.is_file():
            raise ValueError("evidence artifact missing or outside root")
        if hashlib.sha256(file.read_bytes()).hexdigest()!=self.artifact_sha256:
            raise ValueError("evidence hash mismatch")


@dataclass(frozen=True)
class Selection:
    status: str
    solver_id: str | None
    reason: str
    biological_qualification: str = "none"


def lookup_reference_case(records: list[CaseEvidence],root: Path, *,
                          execution_fingerprint: str,case_fingerprint: str,
                          qoi: str,unit: str,tolerance: float) -> Selection:
    number(tolerance,"tolerance",minimum=0)
    for value in (execution_fingerprint,case_fingerprint,qoi,unit):
        identifier(value,"request value")
    for record in records:
        record.validate(root)  # malformed evidence is an error, never a silent fallback
    eligible=[r for r in records if
        r.execution_fingerprint==execution_fingerprint and r.case_fingerprint==case_fingerprint
        and r.qoi==qoi and r.unit==unit and r.measured_error<=tolerance]
    if not eligible:
        return Selection("unqualified",None,"no matching verified artifact for this exact numerical case")
    winner=min(eligible,key=lambda r:(r.measured_total_seconds,r.solver_id))
    return Selection("reference_case_match",winner.solver_id,
                     "advisory lookup of a recorded case; no unseen-state or biological guarantee")
