"""Versioned author-backed nominal stimulus dose labels.

Values describe nominal extracellular feeding medium in the Wang et al.
sequential-stimulus study. They do not specify intracellular exposure,
delivered amount, or the synthetic reservoir quantities in this package.
"""
from __future__ import annotations

from .nfkb_observed import DOSE_TIERS, LIGANDS, decode_stimulus_code


PAPER_SOURCE = {
    "title": "NF-kappaB memory coordinates transcriptional responses to dynamic inflammatory stimuli",
    "journal_version": "Cell Reports 40:111159 (2022-08-16)",
    "doi": "10.1016/j.celrep.2022.111159",
    "pdf_url": "https://taylab.uchicago.edu/uploads/9/1/8/0/91804060/PIIS2211124722009688.pdf",
    "section": "STAR Methods / Stimulus conditions",
    "pdf_page_1based": 19,
    "extracted_text_lines": [1048, 1054],
}
AUTHOR_CODE_SOURCE = {
    "url": "https://raw.githubusercontent.com/tay-lab/Sequential_NF-kB_stim/c4f448e1cc4444f4b9d721d4cf27eaf5e899ca40/f1and2_supps.m",
    "commit_sha1": "c4f448e1cc4444f4b9d721d4cf27eaf5e899ca40",
    "git_blob_sha1": "71c42bb228f1ae24cc41dd3bb1ba9474b8000dfc",
    "sha256": "e2569f822c2bd511d08b8a99a71faae141cae5fb5434728ccc9c141b0ae7b588",
    "code_lines_dose_tier": [74, 80],
    "code_lines_ligand_codes": [428, 469],
}
NOMINAL_EXTRACELLULAR_NG_ML = {
    "TNF-alpha": (90.0, 30.0, 3.0),
    "IL-1beta": (3.0, 0.2, 0.05),
    "LPS": (400.0, 100.0, 12.5),
    "PAM2CSK4": (1.0, 0.1, 0.01),
}


def nominal_dose_schedule(stimulus_codes: tuple[int, ...] | list[int],
                          dose_tier: int) -> list[dict]:
    """Map all four author codes to reported feeding-medium concentrations."""
    if type(dose_tier) is not int or dose_tier not in DOSE_TIERS:
        raise ValueError("author dose tier must be 1, 2, or 3")
    if len(stimulus_codes) != 4 or any(type(code) is not int
                                      for code in stimulus_codes):
        raise ValueError("four integral author stimulus codes required")
    ligands = [decode_stimulus_code(code, dose_tier)
               for code in stimulus_codes]
    if ligands != [None] * 4 and set(ligands) != set(LIGANDS):
        raise ValueError("author schedule must be a four-ligand permutation or FM control")
    return [{"time_min": index * 120,
             "stimulus_code": code,
             "ligand": ligand,
             "dose_tier_code": dose_tier,
             "dose_tier": DOSE_TIERS[dose_tier],
             "nominal_extracellular_ng_ml": (
                 NOMINAL_EXTRACELLULAR_NG_ML[ligand][dose_tier - 1]
                 if ligand is not None else None),
             "unit": "ng/mL" if ligand is not None else None}
            for index, (code, ligand) in enumerate(zip(stimulus_codes, ligands))]
