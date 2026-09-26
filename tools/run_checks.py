#!/usr/bin/env python3
"""Run tests and synthetic numerical checks; emit a fresh evidence directory."""
from __future__ import annotations
import argparse,datetime,hashlib,io,json,os,platform,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tools')]
from numerical_checks import run as numerical_run
from transport_checks import run as transport_run
from run_demo import run as demo_run

class RecordedResult(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs); self.records=[]
    def addSuccess(self,test):
        super().addSuccess(test); self.records.append({'test':test.id(),'outcome':'pass'})
    def addFailure(self,test,err):
        super().addFailure(test,err); self.records.append({'test':test.id(),'outcome':'fail'})
    def addError(self,test,err):
        super().addError(test,err); self.records.append({'test':test.id(),'outcome':'error'})
    def addSkip(self,test,reason):
        super().addSkip(test,reason); self.records.append({'test':test.id(),'outcome':'skip','reason':reason})


def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--output',type=Path); args=p.parse_args()
    if args.output:
        output=args.output.resolve(); output.mkdir(parents=True,exist_ok=False)
    else:
        (ROOT/'runs').mkdir(exist_ok=True)
        output=Path(tempfile.mkdtemp(prefix='checks_',dir=ROOT/'runs'))
    stream=io.StringIO(); suite=unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
    result=unittest.TextTestRunner(stream=stream,verbosity=2,resultclass=RecordedResult).run(suite)
    (output/'tests.log').write_text(stream.getvalue(),encoding='utf-8')
    numerical=numerical_run(); transport=transport_run(); demo=demo_run()
    # A fresh interpreter repeats the demo. This checks the demonstration only.
    env=dict(os.environ); env['PYTHONDONTWRITEBYTECODE']='1'
    child=subprocess.run([sys.executable,str(ROOT/'tools/run_demo.py')],capture_output=True,text=True,env=env,check=True,timeout=30)
    fresh=json.loads(child.stdout)
    fresh_match=fresh==demo
    fingerprint=hashlib.sha256()
    for path in sorted([*ROOT.glob('src/**/*.py'),*ROOT.glob('tests/*.py'),*ROOT.glob('tools/*.py')]):
        fingerprint.update(path.relative_to(ROOT).as_posix().encode()); fingerprint.update(path.read_bytes())
    summary={'package':'cellular_sim_build_v2','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
      'python':sys.version,'platform':platform.platform(),'source_test_tool_sha256':fingerprint.hexdigest(),
      'tests_run':result.testsRun,'passed':result.testsRun-len(result.failures)-len(result.errors)-len(result.skipped),
      'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
      'records':result.records,'numerical_checks_passed':numerical['status']=='pass',
      'transport_3d_checks_passed':transport['status']=='pass',
      'fresh_interpreter_demo_equal':fresh_match,'biological_validation_performed':False,
      'external_engines_run':[],'scope':'Reference kernels and contracts only; not original API conformance.'}
    for name,obj in [('results.json',summary),('numerical_checks.json',numerical),
                     ('transport_checks.json',transport),('demo.json',demo)]:
        (output/name).write_text(json.dumps(obj,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='records'},indent=2))
    print('Evidence directory:',output)
    return 0 if result.wasSuccessful() and numerical['status']=='pass' and transport['status']=='pass' and fresh_match else 1

if __name__=='__main__': raise SystemExit(main())
