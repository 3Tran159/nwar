from pathlib import Path
import sys,json,math,py_compile
O=Path(__file__).resolve().parent
for path in [O/'cpu_calm_study.py',O/'calm_analysis.py',O.parent/'postbuild_w01_gci.py']:py_compile.compile(str(path),doraise=True)
import calm_analysis as a
def series(mode):
 rows=[]
 for i in range(1,3001):
  t=i*.0002;p=.006;v=.002;cl=.29
  if mode=='small':p+=1e-6*math.sin(2*math.pi*t/.02)
  if mode=='component_oscillation':
   d=.0001*math.sin(2*math.pi*t/.02);p+=d;v-=d
  if mode=='slow_drift':p+=.001*t
  if mode=='zero':p=0
  rows.append(dict(physical_time_s=t,CD=p+v,CL_total=cl,pressure_drag_N=p*3855.6,viscous_drag_N=v*3855.6))
 return rows
checks={mode:a.summarize(series(mode))['pass_stabilization'] for mode in ['constant','small','component_oscillation','slow_drift','zero']}
assert checks=={'constant':True,'small':True,'component_oscillation':False,'slow_drift':False,'zero':False},checks
(O/'calm_criterion_math_check.json').write_text(json.dumps(dict(pass_check=True,results=checks,criterion='Four individual coefficients; cancellation in total CD cannot hide unstable pressure/shear'),indent=2))
import cpu_calm_study as c
c.runner.state=lambda status,**kw:print(status,kw,flush=True)
source=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_calm_start_r1\final.sim')
out,d=c.flow('calm_smoke_CPU8',source,.587,.588,.0002,10,317277,pilot=True)
done=c.read(out/'completed.json');audit=c.read(out/'calm_audit.json')
assert done['steps']==5 and audit['incident_wave_height_m']==0 and audit['GPU_count']==0
result=dict(pass_check=True,steps=done['steps'],source_time_s=.587,dt_s=.0002,calm_audit=audit,flow_diagnostics=d,workers=8,gpu=False,purpose='Execution and restart check only; not a convergence result')
c.write(O/'calm_cpu_smoke_result.json',result)
print(json.dumps(result),flush=True)
