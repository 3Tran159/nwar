"""Read-only derived summary of saved STAR audit CSV. Never alters raw data."""
import csv,json,math,statistics
from pathlib import Path
from datetime import datetime
root=Path(r'E:\ntnu_mesh_optimization_20261030\approved_wave_plan_20261101\forcing_audit')
inp=root/'wave_R4V'/'forcing_and_fields.csv'
out=root/'derived_spatial_summary.json'
cols=['Damping Boundary Distance (m)','Forcing Boundary Distance (m)','Damping Strength Indicator','Forcing Strength Indicator','VOF Wave Damping Factor']
bands=[(-1e9,-15),(-15,-5),(-5,5),(5,15),(15,25),(25,1e9)]
stats={x:{'n':0,'u_min':None,'u_max':None,'alpha_min':None,'alpha_max':None,'pressure_min':None,'pressure_max':None} for x in [f'{a}:{b}' for a,b in bands]}
invalid={k:0 for k in cols};valid={k:0 for k in cols}
xmin=float('inf');xmax=float('-inf');zmin=float('inf');zmax=float('-inf');n=0
def update(rec,k,v):
 if v is None or not math.isfinite(v):return
 rec[k+'_min']=v if rec[k+'_min'] is None else min(rec[k+'_min'],v)
 rec[k+'_max']=v if rec[k+'_max'] is None else max(rec[k+'_max'],v)
with inp.open(newline='',encoding='utf-8-sig') as f:
 for row in csv.DictReader(f):
  n+=1
  x=float(row['X (m)']);z=float(row['Z (m)'])
  xmin=min(xmin,x);xmax=max(xmax,x);zmin=min(zmin,z);zmax=max(zmax,z)
  for k in cols:
   v=float(row[k])
   if not math.isfinite(v) or abs(v)>1e300:invalid[k]+=1
   else:valid[k]+=1
  for lo,hi in bands:
   if lo<=x<hi:
    rec=stats[f'{lo}:{hi}'];rec['n']+=1
    update(rec,'u',float(row['Velocity[i] (m/s)']))
    update(rec,'alpha',float(row['Volume Fraction of water']))
    update(rec,'pressure',float(row['Pressure (Pa)']))
    break
result={'at':datetime.now().astimezone().isoformat(),'source_csv':str(inp),'rows':n,'x_range_m':[xmin,xmax],'z_range_m':[zmin,zmax],'forcing_fields_invalid_sentinel_count':invalid,'forcing_fields_valid_count':valid,'spatial_cell_sample_summary_unweighted':stats,'interpretation':'Cells are not volume-weighted. Sentinel >1e300 is not a physical forcing value; absence of valid values cannot prove forcing is zero.'}
tmp=out.with_suffix('.json.tmp')
tmp.write_text(json.dumps(result,indent=2,allow_nan=False),encoding='utf-8')
tmp.replace(out)
print(json.dumps({'rows':n,'x_range_m':[xmin,xmax],'valid_forcing_values':valid,'output':str(out)}))
