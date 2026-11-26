from pathlib import Path
import csv,json,sys
H=Path(__file__).resolve().parent;sys.path.insert(0,str(H/'.deps'))
import numpy as np
R=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029\matched_endpoint_20261029\M09_SO_common_t2040_r1')
rows=list(csv.DictReader((R/'fluid_fields.csv').open()));co=np.array([float(r['Convective Courant Number']) for r in rows]);vf=np.array([float(r['Volume Fraction of water']) for r in rows])
summary={'saved_t_s':2.04,'saved_dt_s':.001,'cell_CFL_quantiles':dict(zip(['p50','p90','p95','p99','p999','max'],map(float,np.quantile(co,[.5,.9,.95,.99,.999,1])))),'interface_max_CFL':float(co[(vf>.01)&(vf<.99)].max()),'worst_CFL_cells':sorted(rows,key=lambda r:float(r['Convective Courant Number']),reverse=True)[:4]}
wall=list(csv.DictReader((R/'foil_fields.csv').open()));summary['yplus_over_1']=[r for r in wall if float(r['Wall Y+'])>1]
(H/'gci_m09_20261030/saved_M09_diagnostics.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
