from pathlib import Path
import json,csv,statistics,math
R=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029');OUT=Path(__file__).resolve().parent
D=json.loads((OUT/'evidence.json').read_text(encoding='utf-8'))
result={}
for m in ['M04','M06','M07']:
 q=D['topology'][m];result[m]={'topology':q,'definition':D['mesh_definition_evidence'][m]}
ns={'M04':'temporal_order_20261029/T04_M04_SO_dt1ms_inner10_r1','M06':'M06_until_settled_r1','M07':'configured_mesh_20261029/M07_SO1ms_inner10_r1','M09':'matched_endpoint_20261029/M09_SO_common_t2040_r1'}
for m,n in ns.items():
 p=R/n;case={};result.setdefault(m,{})['restart']=case
 for name in ['final.sim','history.csv','setup.json','completed.json']:
  f=p/name;case[name]={'path':str(f),'exists':f.exists(),'bytes':f.stat().st_size if f.exists() else None}
  if f.exists() and f.suffix=='.json':case[name]['data']=json.loads(f.read_text(encoding='utf-8-sig'))
 if (p/'history.csv').exists():
  with (p/'history.csv').open(encoding='utf-8-sig') as f:rr=list(csv.DictReader(f))
  case['history_header']=list(rr[-1]);case['history_last']=rr[-1]
(OUT/'gci_reuse_inspection.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
for m,v in result.items():
 print(m);print(json.dumps(v,indent=2)[:22000])
print('2D size ratios: ',math.sqrt(251605/138468),math.sqrt(481635/251605))
