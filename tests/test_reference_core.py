from __future__ import annotations
from dataclasses import replace
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import random
import os
import subprocess
import sys
import tempfile
import unittest

from cellsim_v2.state import (Cell,AmountField,World,Update,LedgerEntry,
                              total_amount,balance,number,time_fraction)
from cellsim_v2.kernels import (linear_contact,euler_decay,transfer_to_cell,
    divide_retained_slot,periodic_diffusion,radial_constant_uptake)
from cellsim_v2.scheduler import Process,WindowStepper
from cellsim_v2.checkpoint import save_checkpoint,load_checkpoint,canonical_bytes,encode_world
from cellsim_v2.evidence import CaseEvidence,lookup_reference_case

ALL=frozenset({"cells","fields","ledger","events"})

def field_world():
    return World(fields={"x":AmountField("x",(1.0,),(1.0,))})

def pair(reverse=False,distance=1.5):
    cells=[Cell("a",(0.,0.,0.),4*math.pi/3),Cell("b",(distance,0.,0.),4*math.pi/3)]
    return World(cells={c.id:c for c in reversed(cells) if reverse}) if reverse else World(cells={c.id:c for c in cells})

def stepper(dt=F(1,2),window=F(1,2)):
    return WindowStepper([Process("decay",dt,frozenset({"fields","ledger"}),
                                  lambda w,h:euler_decay(w,"x",0.1,h))],window)


class TimingTests(unittest.TestCase):
    def test_zero_duration_is_noop(self):
        w=field_world(); old=w.clone(); stepper().advance(w,F(0)); self.assertEqual(w,old)
    def test_exact_endpoint_two_updates(self):
        w=field_world(); stepper().advance(w,F(1)); self.assertAlmostEqual(w.fields["x"].amounts_mol[0],0.95**2,places=14)
        self.assertEqual(w.time_s,F(1)); self.assertEqual(w.step,2)
    def test_partial_final_interval(self):
        w=field_world(); stepper().advance(w,F(3,4)); self.assertAlmostEqual(w.fields["x"].amounts_mol[0],0.95*0.975,places=14)
    def test_nonzero_start(self):
        w=field_world(); w.time_s=F(5); stepper().advance(w,F(6)); self.assertAlmostEqual(w.fields["x"].amounts_mol[0],0.95**2,places=14)
    def test_backwards_rejected(self):
        w=field_world(); w.time_s=F(2)
        with self.assertRaises(ValueError): stepper().advance(w,F(1))
    def test_zero_process_step_rejected(self):
        with self.assertRaises(ValueError): stepper(dt=F(0))
    def test_negative_process_step_rejected(self):
        with self.assertRaises(ValueError): stepper(dt=F(-1))
    def test_zero_window_rejected(self):
        with self.assertRaises(ValueError): stepper(window=F(0))
    def test_nonfinite_time_rejected(self):
        for x in (math.nan,math.inf,-math.inf):
            with self.subTest(x=x),self.assertRaises(ValueError): stepper().advance(field_world(),x)
    def test_aligned_segmentation_preserves_result(self):
        a,b=field_world(),field_world(); s=stepper(); s.advance(a,F(1)); s.advance(b,F(1,2)); s.advance(b,F(1)); self.assertEqual(a,b)
    def test_multi_process_subcycling(self):
        w=World(fields={"x":AmountField("x",(1.,),(1.,)),"y":AmountField("y",(1.,),(1.,))})
        ps=[Process("x",F(1,2),frozenset({"fields","ledger"}),lambda w,h:euler_decay(w,"x",0.1,h)),
            Process("y",F(1,4),frozenset({"fields","ledger"}),lambda w,h:euler_decay(w,"y",0.2,h))]
        WindowStepper(ps,F(1)).advance(w,F(1)); self.assertAlmostEqual(w.fields["x"].amounts_mol[0],0.95**2,places=14)
        self.assertAlmostEqual(w.fields["y"].amounts_mol[0],0.95**4,places=14)
    def test_undeclared_write_rejected_without_mutation(self):
        w=field_world(); original=w.clone()
        p=Process("bad",F(1),frozenset(),lambda w,h:euler_decay(w,"x",0.1,h))
        with self.assertRaises(PermissionError): WindowStepper([p],F(1)).advance(w,F(1))
        self.assertEqual(w,original)
    def test_snapshot_mutation_rejected(self):
        w=field_world(); original=w.clone()
        def bad(state,h):
            state.step=99
            return Update()
        with self.assertRaises(PermissionError): WindowStepper([Process("bad",F(1),ALL,bad)],F(1)).advance(w,F(1))
        self.assertEqual(w,original)
    def test_whole_failing_window_rolls_back(self):
        w=field_world(); old=w.clone()
        good=Process("good",F(1),ALL,lambda w,h:euler_decay(w,"x",0.1,h))
        def fail(w,h): raise ValueError("deliberate failure")
        with self.assertRaises(ValueError): WindowStepper([good,Process("bad",F(1),ALL,fail)],F(1)).advance(w,F(1))
        self.assertEqual(w,old)
    def test_duplicate_process_names_rejected(self):
        p=Process("p",F(1),ALL,lambda w,h:Update())
        with self.assertRaises(ValueError): WindowStepper([p,p],F(1))
    def test_empty_stepper_advances_clock_only(self):
        w=field_world(); WindowStepper([],F(1)).advance(w,F(2)); self.assertEqual(w.time_s,F(2))
        self.assertEqual(w.fields["x"].amounts_mol,(1.,))


class StateTests(unittest.TestCase):
    def test_clone_independence(self):
        w=pair(); c=w.clone(); c.cells["a"].volume_m3=1; self.assertNotEqual(w,c)
    def test_duplicate_birth_is_atomic(self):
        w=pair(); old=w.clone(); d=Update(replace_cells={"a":replace(w.cells["a"],position_m=(99,0,0))},births=(w.cells["b"],))
        with self.assertRaises(ValueError): d.commit(w,ALL)
        self.assertEqual(w,old)
    def test_invalid_replacement_is_atomic(self):
        w=pair(); old=w.clone()
        with self.assertRaises(ValueError): Update(replace_cells={"a":replace(w.cells["a"],volume_m3=-1)}).commit(w,ALL)
        self.assertEqual(w,old)
    def test_unknown_removal_rejected(self):
        with self.assertRaises(ValueError): Update(removals=("missing",)).commit(pair(),ALL)
    def test_remove_and_rebirth_same_id_rejected(self):
        w=pair()
        with self.assertRaises(ValueError): Update(removals=("a",),births=(w.cells["a"],)).commit(w,ALL)
    def test_mutating_update_after_commit_cannot_mutate_world(self):
        w=pair(); d=Update(replace_cells={"a":replace(w.cells["a"],position_m=(1,0,0))}); d.commit(w,ALL)
        d.replace_cells["a"].volume_m3=99; self.assertNotEqual(w.cells["a"].volume_m3,99)
    def test_nonfinite_position_rejected(self):
        w=pair(); w.cells["a"].position_m=(math.nan,0,0)
        with self.assertRaises(ValueError): w.validate()
    def test_zero_volume_rejected(self):
        with self.assertRaises(ValueError): AmountField("x",(1.,),(0.,)).validate()
    def test_negative_amount_rejected(self):
        with self.assertRaises(ValueError): AmountField("x",(-1.,),(1.,)).validate()
    def test_bool_number_rejected(self):
        with self.assertRaises(TypeError): number(True,"x")
    def test_bool_time_rejected(self):
        with self.assertRaises(TypeError): time_fraction(True)
    def test_inconsistent_field_key_rejected(self):
        with self.assertRaises(ValueError): World(fields={"x":AmountField("y",(1.,),(1.,))}).validate()


class MechanicsDivisionTests(unittest.TestCase):
    def test_equal_pair_preserves_midpoint(self):
        w=pair(); linear_contact(w,0.1).commit(w,ALL)
        self.assertAlmostEqual((w.cells["a"].position_m[0]+w.cells["b"].position_m[0])/2,0.75,places=14)
    def test_entity_order_independent(self):
        a,b=pair(),pair(True); linear_contact(a,0.1).commit(a,ALL); linear_contact(b,0.1).commit(b,ALL); self.assertEqual(a,b)
    def test_nonoverlap_no_motion(self):
        w=pair(distance=3); old=w.clone(); linear_contact(w,0.1).commit(w,ALL); self.assertEqual(w,old)
    def test_coincident_centers_explicit_error(self):
        with self.assertRaises(ValueError): linear_contact(pair(distance=0),0.1)
    def test_unequal_drag_preserves_drag_weighted_center(self):
        w=pair(); w.cells["b"].drag_Ns_per_m=2
        before=sum(c.drag_Ns_per_m*c.position_m[0] for c in w.cells.values())
        linear_contact(w,0.1).commit(w,ALL)
        self.assertAlmostEqual(sum(c.drag_Ns_per_m*c.position_m[0] for c in w.cells.values()),before,places=14)
    def test_division_volume_amount_balance(self):
        w=pair(); w.cells["a"].amounts_mol={"x":2.}; oldv=sum(c.volume_m3 for c in w.cells.values())
        divide_retained_slot(w,"a",0.5).commit(w,ALL)
        self.assertAlmostEqual(sum(c.volume_m3 for c in w.cells.values()),oldv,places=14)
        self.assertEqual(total_amount(w,"x"),2.); self.assertEqual(len(w.events),1)
    def test_repeated_division_unique_ids(self):
        w=World(cells={"a":Cell("a",(0,0,0),1.)})
        for _ in range(3): divide_retained_slot(w,"a").commit(w,ALL)
        self.assertEqual(len(w.cells),4); self.assertEqual(len({e.id for e in w.events}),3)
        self.assertAlmostEqual(sum(c.volume_m3 for c in w.cells.values()),1.)
    def test_division_preserves_center_for_equal_daughters(self):
        w=World(cells={"a":Cell("a",(2,0,0),1.)}); divide_retained_slot(w,"a",0.6).commit(w,ALL)
        self.assertAlmostEqual(sum(c.position_m[0]*c.volume_m3 for c in w.cells.values()),2.)
    def test_stale_division_cannot_be_recommitted(self):
        w=World(cells={"a":Cell("a",(0,0,0),1.)}); d=divide_retained_slot(w,"a"); d.commit(w,ALL); old=w.clone()
        with self.assertRaises(ValueError): d.commit(w,ALL)
        self.assertEqual(w,old)
    def test_negative_contact_dt_rejected(self):
        with self.assertRaises(ValueError): linear_contact(pair(),-1)


class ChemistryTests(unittest.TestCase):
    def test_concentration_conversion_unequal_volumes(self):
        f=AmountField.from_concentrations("x",(1.,1.),(1.,9.)); w=World(fields={"x":f})
        self.assertEqual(total_amount(w,"x"),10.)
        f2=AmountField.from_concentrations("x",(0.5,1.5),(1.,9.)); w2=World(fields={"x":f2})
        self.assertEqual(total_amount(w2,"x"),14.); self.assertEqual(balance(w,w2,"x").absolute_error_mol,4.)
    def test_unaccounted_amount_change_rejected(self):
        w=field_world(); old=w.clone()
        with self.assertRaises(ValueError): Update(replace_fields={"x":AmountField("x",(2.,),(1.,))}).commit(w,ALL)
        self.assertEqual(w,old)
    def test_declared_source_accepted(self):
        w=field_world(); Update(replace_fields={"x":AmountField("x",(2.,),(1.,))},
            ledger=(LedgerEntry("x",1.,"source","test source"),)).commit(w,ALL); self.assertEqual(total_amount(w,"x"),2.)
    def test_absolute_error_nonnegative(self):
        w=field_world(); after=w.clone(); after.fields["x"].amounts_mol=(0.5,)
        self.assertEqual(balance(w,after,"x").absolute_error_mol,0.5)
        self.assertEqual(balance(w,after,"x").signed_residual_mol,-0.5)
    def test_transfer_conserves(self):
        w=field_world(); w.cells["a"]=Cell("a",(0,0,0),1.)
        transfer_to_cell(w,"x",0,"a",0.25).commit(w,ALL)
        self.assertEqual(total_amount(w,"x"),1.); self.assertEqual(w.cells["a"].amounts_mol["x"],0.25)
    def test_transfer_overdraw_rejected(self):
        w=field_world(); w.cells["a"]=Cell("a",(0,0,0),1.)
        with self.assertRaises(ValueError): transfer_to_cell(w,"x",0,"a",2.)
    def test_negative_voxel_rejected(self):
        with self.assertRaises(ValueError): transfer_to_cell(field_world(),"x",-1,"a",0.)
    def test_unstable_decay_rejected(self):
        with self.assertRaises(ValueError): euler_decay(field_world(),"x",2.,1.)
    def test_diffusion_conserves_mass(self):
        f=AmountField("x",(1.,2.,3.,4.),(1.,)*4); g=periodic_diffusion(f,1.,1.,1.,0.1)
        self.assertAlmostEqual(sum(g.amounts_mol),10.,places=14)
    def test_constant_diffusion_state_unchanged(self):
        f=AmountField("x",(1.,)*4,(1.,)*4); self.assertEqual(periodic_diffusion(f,1.,1.,1.,0.1),f)
    def test_diffusion_positivity(self):
        f=AmountField("x",(1.,0.,0.,0.),(1.,)*4)
        self.assertGreaterEqual(min(periodic_diffusion(f,1.,1.,1.,0.5).amounts_mol),0.)
    def test_unstable_diffusion_rejected(self):
        with self.assertRaises(ValueError): periodic_diffusion(AmountField("x",(1.,)*4,(1.,)*4),1.,1.,1.,0.51)
    def test_nonuniform_diffusion_rejected(self):
        with self.assertRaises(ValueError): periodic_diffusion(AmountField("x",(1.,)*4,(1.,2.,1.,1.)),1.,1.,1.,0.1)
    def test_radial_zero_uptake_uniform(self):
        _,c=radial_constant_uptake(8,1.,1.,0.,2.); self.assertLess(max(abs(x-2) for x in c),1e-12)
    def test_radial_negative_regime_rejected(self):
        with self.assertRaises(ValueError): radial_constant_uptake(8,1.,1.,100.,1.)
    def test_radial_refinement_reduces_error(self):
        errors=[]
        for n in (8,16,32):
            r,c=radial_constant_uptake(n,1.,1.,0.3,1.)
            errors.append(max(abs(v-(1.-0.3*(1.-x*x)/6.)) for x,v in zip(r,c)))
        self.assertGreater(errors[0]/errors[1],3.5); self.assertGreater(errors[1]/errors[2],3.5)


class CheckpointTests(unittest.TestCase):
    def test_world_rng_private_roundtrip(self):
        w=pair(); w.time_s=F(3,7); rng=random.Random(99); rng.random()
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"state.json"; save_checkpoint(p,w,rng,"fixture/1",{"history":[1.,2.]})
            other,r,private=load_checkpoint(p,"fixture/1")
            self.assertEqual(w,other); self.assertEqual([rng.random() for _ in range(4)],[r.random() for _ in range(4)])
            self.assertEqual(private,{"history":[1.,2.]})
    def test_private_state_must_be_dictionary(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(TypeError):
                save_checkpoint(Path(d)/"s.json",pair(),random.Random(1),"a",[1,2])
    def test_checkpoint_continues_in_fresh_interpreter(self):
        w=field_world(); stepper().advance(w,F(1,2)); rng=random.Random(712)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"checkpoint.json"; save_checkpoint(p,w,rng,"restart-fixture")
            stepper().advance(w,F(1)); expected_random=[rng.random() for _ in range(3)]
            script="""
import json,sys
from fractions import Fraction as F
from pathlib import Path
from cellsim_v2.checkpoint import load_checkpoint,encode_world
from cellsim_v2.kernels import euler_decay
from cellsim_v2.scheduler import Process,WindowStepper
w,rng,_=load_checkpoint(Path(sys.argv[1]),'restart-fixture')
p=Process('decay',F(1,2),frozenset({'fields','ledger'}),lambda w,h:euler_decay(w,'x',0.1,h))
WindowStepper([p],F(1,2)).advance(w,F(1))
print(json.dumps({'world':encode_world(w),'draws':[rng.random() for _ in range(3)]}))
"""
            env=dict(os.environ); env['PYTHONPATH']=str(Path(__file__).resolve().parents[1]/'src'); env['PYTHONDONTWRITEBYTECODE']='1'
            result=subprocess.run([sys.executable,'-c',script,str(p)],capture_output=True,text=True,env=env,check=True,timeout=15)
            payload=json.loads(result.stdout)
            self.assertEqual(payload['world'],json.loads(canonical_bytes(encode_world(w))))
            self.assertEqual(payload['draws'],expected_random)
    def test_hash_corruption_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"state.json"; save_checkpoint(p,pair(),random.Random(1),"a")
            data=json.loads(p.read_text()); data["payload"]["world"]["step"]=20; p.write_text(json.dumps(data))
            with self.assertRaises(ValueError): load_checkpoint(p,"a")
    def test_fingerprint_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"state.json"; save_checkpoint(p,pair(),random.Random(1),"a")
            with self.assertRaises(ValueError): load_checkpoint(p,"b")
    def test_failed_save_preserves_existing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"state.json"; save_checkpoint(p,pair(),random.Random(1),"a"); before=p.read_bytes()
            with self.assertRaises(ValueError): save_checkpoint(p,pair(),random.Random(1),"a",{"nan":math.nan})
            self.assertEqual(p.read_bytes(),before)
    def test_continuation_matches_aligned_uninterrupted(self):
        a,b=field_world(),field_world(); stepper().advance(a,F(1)); stepper().advance(b,F(1,2))
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"s.json"; save_checkpoint(p,b,random.Random(1),"fixed steps")
            b,_,_=load_checkpoint(p,"fixed steps"); stepper().advance(b,F(1)); self.assertEqual(a,b)


class EvidenceTests(unittest.TestCase):
    def args(self):
        return dict(execution_fingerprint="e",case_fingerprint="c",qoi="l2",unit="mol/m3",tolerance=0.01)
    def record(self,p,**kwargs):
        p.write_text("synthetic test artifact; not qualification")
        values=dict(solver_id="cpu",execution_fingerprint="e",case_fingerprint="c",qoi="l2",unit="mol/m3",
          measured_error=0.001,measured_total_seconds=1.,artifact_path=p.name,artifact_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        return CaseEvidence(**(values|kwargs))
    def test_missing_evidence_unqualified(self):
        r=lookup_reference_case([],Path('.'),**self.args()); self.assertEqual(r.status,"unqualified"); self.assertEqual(r.biological_qualification,"none")
    def test_nonfinite_metric_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=self.record(root/'a',measured_error=math.nan)
            with self.assertRaises(ValueError): lookup_reference_case([r],root,**self.args())
    def test_only_exact_case_match_eligible(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=self.record(root/'a'); result=lookup_reference_case([r],root,**self.args())
            self.assertEqual(result.status,"reference_case_match"); self.assertEqual(result.biological_qualification,"none")
            args=self.args()|{"case_fingerprint":"unseen"}; self.assertEqual(lookup_reference_case([r],root,**args).status,"unqualified")
    def test_units_must_match(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=self.record(root/'a',unit="mol"); self.assertEqual(lookup_reference_case([r],root,**self.args()).status,"unqualified")
    def test_missing_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=self.record(root/'a'); (root/'a').unlink()
            with self.assertRaises(ValueError): lookup_reference_case([r],root,**self.args())
    def test_changed_artifact_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=self.record(root/'a'); (root/'a').write_text('changed')
            with self.assertRaises(ValueError): lookup_reference_case([r],root,**self.args())
    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); r=self.record(root/'a'); sub=root/'child'; sub.mkdir()
            r=replace(r,artifact_path='../a')
            with self.assertRaises(ValueError): lookup_reference_case([r],sub,**self.args())
    def test_negative_tolerance_rejected(self):
        with self.assertRaises(ValueError): lookup_reference_case([],Path('.'),**(self.args()|{"tolerance":-1.}))
    def test_eligible_lookup_uses_recorded_cost(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); a=self.record(root/'a',solver_id='expensive',measured_total_seconds=3.)
            b=self.record(root/'b',solver_id='cheap',measured_total_seconds=1.)
            self.assertEqual(lookup_reference_case([a,b],root,**self.args()).solver_id,'cheap')

if __name__=='__main__':
    unittest.main(verbosity=2)
