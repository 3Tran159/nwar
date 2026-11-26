"""Calm W01a: four coefficients, non-overlapping equal-duration settling windows."""
from pathlib import Path
import sys,math
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.deps'))
import numpy as np
from wave_analysis import gci,load_history
KEYS=['CD','CL','CD_pressure','CD_viscous']
CL_OFFSET=22.718189111947265/3855.6
WINDOW=.2
def coefficients(data):
 result=[]
 for row in data:
  r=dict(row);r['CL']=r['CL_total']-CL_OFFSET;r['CD_pressure']=r['pressure_drag_N']/3855.6;r['CD_viscous']=r['viscous_drag_N']/3855.6
  if abs(r['CD']-r['CD_pressure']-r['CD_viscous'])>max(1e-7,abs(r['CD'])*1e-5):raise ValueError('Drag components do not sum to total')
  result.append(r)
 return result
def summarize(data):
 data=coefficients(data);t=np.array([r['physical_time_s'] for r in data]);dt=float(np.median(np.diff(t)));n=round(WINDOW/dt)
 if n<10 or len(data)<2*n or abs(n*dt-WINDOW)>1e-8 or not np.allclose(np.diff(t[-2*n:]),dt,rtol=1e-5,atol=1e-9):raise ValueError('Missing or unequal time samples in settling windows')
 result={}
 for k in KEYS:
  y=np.array([r[k] for r in data[-2*n:]])
  if not np.all(np.isfinite(y)):raise ValueError('Nonfinite coefficient')
  prev=float(y[:n].mean());last=float(y[n:].mean());mean=float(y.mean())
  rms=[float(y[:n].std()),float(y[n:].std())];means=[prev,last]
  resolved=min(abs(prev),abs(last))>1e-8
  change=100*abs(last-prev)/max(abs(last),1e-30)
  rp=[100*v/max(abs(m),1e-30) for v,m in zip(rms,means)]
  result[k]=dict(mean=mean,previous_mean=prev,latest_mean=last,mean_change_abs=abs(last-prev),mean_change_pct=change,RMS_abs=rms,RMS_pct=rp,relative_test_resolved=resolved,pass_stabilization=resolved and change<.5 and max(rp)<.5)
 return dict(lift_convention='hydrodynamic_lift_v1',time_s=float(t[-1]),dt_s=dt,window_s=WINDOW,averaging_start_exclusive_s=float(t[-1]-2*WINDOW),quantities=result,pass_stabilization=all(v['pass_stabilization'] for v in result.values()))
def estimate(summaries,area,cells):
 levels=['W01a','G10_M','G10_F'];estimates={};noise={}
 for k in KEYS:
  values=[summaries[m]['quantities'][k]['mean'] for m in levels]
  delta=min(abs(values[i+1]-values[i]) for i in [0,1])
  # A repeat-window shift is a bias screen; RMS is conservatively retained without assuming independent samples.
  effects={m:max(summaries[m]['quantities'][k]['mean_change_abs'],*summaries[m]['quantities'][k]['RMS_abs']) for m in levels}
  noise[k]={'smallest_pair_difference':delta,'allowed_abs':.1*delta,'effects':effects,'pass':max(effects.values())<=.1*delta and delta>1e-14}
  estimates[k]=gci(values,area,cells)
 return estimates,noise
