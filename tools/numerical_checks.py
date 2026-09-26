#!/usr/bin/env python3
"""Small analytic comparisons with fixed, synthetic parameters; no biological data."""
from __future__ import annotations
import math
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"src"))
from cellsim_v2.state import AmountField
from cellsim_v2.kernels import periodic_diffusion,radial_constant_uptake


def run() -> dict:
    decay=[]
    for h in (0.2,0.1,0.05,0.025):
        n=round(1/h); value=1.
        for _ in range(n): value*=1-0.7*h
        decay.append({"dt":h,"steps":n,"absolute_error":abs(value-math.exp(-0.7))})
    decay_orders=[math.log(decay[i]['absolute_error']/decay[i+1]['absolute_error'],2) for i in range(len(decay)-1)]
    diffusion=[]
    for n in (16,32,64):
        dx=1/n; D=0.2; T=0.05; max_dt=0.1*dx*dx/D
        steps=math.ceil(T/max_dt); dt=T/steps
        x=[(i+0.5)*dx for i in range(n)]
        initial=tuple(1+0.25*math.sin(2*math.pi*r) for r in x)
        f=AmountField.from_concentrations('tracer',initial,(dx,)*n)
        m0=math.fsum(f.amounts_mol)
        for _ in range(steps): f=periodic_diffusion(f,dx,1.,D,dt)
        exact=[1+0.25*math.exp(-4*math.pi**2*D*T)*math.sin(2*math.pi*r) for r in x]
        err=math.sqrt(math.fsum((a-b)**2 for a,b in zip(f.concentrations_mol_m3,exact))/n)
        diffusion.append({"n":n,"dx":dx,"dt":dt,"steps":steps,"l2_error":err,"mass_error":abs(math.fsum(f.amounts_mol)-m0)})
    d_orders=[math.log(diffusion[i]['l2_error']/diffusion[i+1]['l2_error'],2) for i in range(len(diffusion)-1)]
    radial=[]
    for n in (8,16,32,64):
        r,c=radial_constant_uptake(n,1.,1.,0.3,1.)
        exact=[1-0.3*(1-x*x)/6 for x in r]
        radial.append({"n":n,"max_error":max(abs(a-b) for a,b in zip(c,exact)),"minimum_concentration":min(c)})
    r_orders=[math.log(radial[i]['max_error']/radial[i+1]['max_error'],2) for i in range(len(radial)-1)]
    passed=(all(0.9<o<1.2 for o in decay_orders) and all(1.8<o<2.2 for o in d_orders)
            and all(1.8<o<2.2 for o in r_orders) and max(r['mass_error'] for r in diffusion)<1e-12)
    return {"status":"pass" if passed else "fail","biological_validation":False,
      "tolerances":"Engineering regression limits for these synthetic cases only.",
      "decay":{"equation":"dc/dt=-0.7 c, c(0)=1, T=1","rows":decay,"observed_orders":decay_orders},
      "periodic_diffusion":{"equation":"c_t=0.2 c_xx; c(x,0)=1+0.25 sin(2 pi x), L=1,T=.05",
        "study":"Joint dx,dt refinement with dt proportional to dx^2; not an isolated spatial-order proof.",
        "rows":diffusion,"observed_orders":d_orders},
      "radial_steady":{"equation":"D Laplacian(c)-q=0, c(R)=cb; D=R=cb=1,q=.3",
        "rows":radial,"observed_orders":r_orders}}

if __name__=='__main__':
    import json
    report=run(); print(json.dumps(report,indent=2)); raise SystemExit(0 if report['status']=='pass' else 1)
