from pathlib import Path
import sys,math,csv
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'.deps'))
import numpy as np
from scipy.optimize import brentq
MESHES=['W01a','G10_M','G10_F']
def gci(values,area,cells):
 # Inputs coarse, medium, fine. Only the x-z plane is refined: h=sqrt(A/N).
 h=[math.sqrt(area[m]/cells[m]) for m in MESHES];f3,f2,f1=values;e21=f2-f1;e32=f3-f2;r21=h[1]/h[2];r32=h[0]/h[1]
 result={'phi_coarse_medium_fine':values,'h_coarse_medium_fine_m':h,'r21':r21,'r32':r32}
 if abs(e21)<1e-15 or abs(e32)<1e-15:return dict(result,status='differences_unresolved')
 if e21*e32<=0:return dict(result,status='oscillatory_no_standard_monotone_GCI')
 ratio=e32/e21
 def fun(p):return math.exp(p*math.log(r21))*math.expm1(p*math.log(r32))/math.expm1(p*math.log(r21))-ratio
 if fun(.001)*fun(12)>=0:return dict(result,status='no_positive_observed_order_in_0.001_to_12')
 p=brentq(fun,.001,12);ext=f1+(f1-f2)/math.expm1(p*math.log(r21))
 absolute_fine=1.25*abs(e21)/math.expm1(p*math.log(r21))
 absolute_medium=1.25*abs(e32)/math.expm1(p*math.log(r32))
 result.update(status='GCI_estimate_pending_nuisance_checks',observed_p=p,extrapolated=ext,GCI_fine_abs=absolute_fine,GCI_fine_pct=100*absolute_fine/abs(f1),GCI_medium_abs=absolute_medium,GCI_medium_pct=100*absolute_medium/abs(f2),GCI_W01a_abs=absolute_medium*math.exp(p*math.log(r32)),GCI_W01a_pct=100*absolute_medium*math.exp(p*math.log(r32))/abs(f3),asymptotic_ratio=absolute_medium/(math.exp(p*math.log(r21))*absolute_fine),order_caution=p>4)
 return result

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
