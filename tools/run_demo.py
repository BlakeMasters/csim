#!/usr/bin/env python3
"""Bookkeeping/transport/contact demonstration. No cancer interpretation."""
from __future__ import annotations
from dataclasses import asdict
from fractions import Fraction as F
import hashlib,json,math,random,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from cellsim_v2.state import Cell,AmountField,World,total_amount
from cellsim_v2.kernels import linear_contact,transfer_to_cell,divide_retained_slot
from cellsim_v2.checkpoint import save_checkpoint,load_checkpoint,encode_world,canonical_bytes


def run():
    w=World(cells={'a':Cell('a',(0.,0.,0.),4*math.pi/3),
                   'b':Cell('b',(1.5,0.,0.),4*math.pi/3)},
            fields={'tracer':AmountField.from_concentrations('tracer',(1.,1.),(1.,9.))})
    all_writes=frozenset({'cells','fields','ledger','events'})
    before=total_amount(w,'tracer')
    linear_contact(w,0.1).commit(w,all_writes)
    transfer_to_cell(w,'tracer',1,'a',0.25).commit(w,all_writes)
    vol=sum(c.volume_m3 for c in w.cells.values())
    divide_retained_slot(w,'a',0.2).commit(w,all_writes)
    rng=random.Random(1)
    with tempfile.TemporaryDirectory() as d:
        p=Path(d)/'world.json'; save_checkpoint(p,w,rng,'synthetic-demo/2')
        restored,_,_=load_checkpoint(p,'synthetic-demo/2')
    return {'label':'synthetic numerical bookkeeping demonstration; not microtumor',
        'biological_validation':False,'cell_slots_after_division':len(w.cells),
        'amount_before_mol':before,'amount_after_mol':total_amount(w,'tracer'),
        'volume_change_m3':sum(c.volume_m3 for c in w.cells.values())-vol,
        'checkpoint_roundtrip_equal':restored==w,
        'final_state_sha256':hashlib.sha256(canonical_bytes(encode_world(w))).hexdigest()}

if __name__=='__main__': print(json.dumps(run(),indent=2))
