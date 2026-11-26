from pathlib import Path
H=Path(__file__).resolve().parent;O=H/'gci_w01a_20261030'
old=(H/'gci_m09_20261030/study_controller.py').read_text()
gci=old[old.index('def gci('):old.index('def main():')]
head="""from pathlib import Path
import sys,math,csv
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.deps'))
import numpy as np
from scipy.optimize import brentq
MESHES=['W01a','G10_M','G10_F']
"""
extra=r'''
def load_history(paths):
 allrows=[]
 for p in paths:
  with Path(p).open(encoding='utf-8-sig') as f:
   for row in csv.DictReader(f):
    row={k:float(v) for k,v in row.items()}
    if 'physical_time_s' not in row:row['physical_time_s']=row['time_s']
    allrows.append(row)
 # Restart overlap must not be counted twice.
 by_time={round(r['physical_time_s'],10):r for r in allrows}
 return [by_time[k] for k in sorted(by_time)]
def window(data,key,lo,hi,period):
 tt=np.array([r['physical_time_s'] for r in data]);yy=np.array([r[key] for r in data])
 if lo<tt[0]-1e-9 or hi>tt[-1]+1e-9:raise ValueError('Window not fully covered by saved samples')
 mask=(tt>lo)&(tt<hi);t=np.r_[lo,tt[mask],hi];y=np.interp(t,tt,yy)
 if len(t)<100 or not np.all(np.isfinite(y)):raise ValueError('Insufficient/nonfinite periodic samples')
 dur=hi-lo;mean=float(np.trapezoid(y,t)/dur);phase=2*np.pi*t/period
 c=2*np.trapezoid(y*np.cos(phase),t)/dur;ss=2*np.trapezoid(y*np.sin(phase),t)/dur
 return dict(mean=mean,amplitude=float(np.hypot(c,ss)),phase_deg=float(np.degrees(np.arctan2(-ss,c))),peak_to_peak=float(y.max()-y.min()))
def summarize(data,end,period,cycles=3):
 result={}
 for key in ['CD','CL_total','pressure_drag_N','viscous_drag_N']:
  full=window(data,key,end-cycles*period,end,period)
  each=[window(data,key,end-(cycles-j)*period,end-(cycles-j-1)*period,period) for j in range(cycles)]
  result[key]=dict(full=full,cycles=each)
  for metric in ['mean','amplitude']:
   vals=[v[metric] for v in each];shift=max(abs(vals[j+1]-vals[j]) for j in range(len(vals)-1))
   result[key][metric+'_cycle_shift_abs']=shift
   result[key][metric+'_cycle_shift_pct']=100*shift/max(abs(full[metric]),1e-12)
 return result
def flat_metrics(summary):
 return {key+'_'+metric:values['full'][metric] for key,values in summary.items() for metric in ['mean','amplitude']}
def phase_difference(a,b):return (a-b+180)%360-180
'''
(O/'wave_analysis.py').write_text(head+gci+extra,encoding='utf-8')
p=O/'ContinueWaveGCI.java';t=p.read_text().replace('s.getNumberOfGpgpus()!=1','s.getNumberOfGpgpus()!=0').replace('One active GPU required','CPU-only execution required for mesh GCI')
p.write_text(t,encoding='utf-8')
print('Prepared periodic analysis and enforced CPU-only flow macro')
