from pathlib import Path
root=Path(r"E:\ntnu_mesh_optimization_20261030")
src=root/"mesh_queue_worker_20261031.py"
out=root/"mesh_queue_worker_mixed_dt_20261031.py"
assert not out.exists()
s=src.read_text(encoding="utf8")
def rep(old,new):
 global s
 assert s.count(old)==1,(old[:80],s.count(old))
 s=s.replace(old,new,1)
rep("DT=0.0001\n","DT=0.0001\nPILOT_SELECTION=R/'m11_dt_selection.json'\n")
rep('abs(setup.get("dt_s",0)-DT)<1e-12','abs(setup.get("dt_s",0)-.0001)<1e-12')
rep('def source_for(stage,previous):\n origin=verify_input(stage)',
'''def source_for(stage,previous):
 origin=verify_input(stage)
 selection=ctrl.read(PILOT_SELECTION)
 if stage[0]=="M11" and selection.get("approved_for_continuation_pilot") is True:
  p=Path(selection["directory"])
  assert p.parent==R and p.name.startswith("M11_G10_M_dt0002_GPU_pilot_")
  assert ctrl.sha(p/"final.sim")==selection["final_sim_sha256"]
  done=ctrl.read(p/"completed.json");exit=ctrl.read(p/"exit.json")
  assert done["status"]=="target_reached" and exit["returncode"]==0 and exit["source_unchanged"] is True
  assert abs(done["time_s"]-.6052)<1e-8
  rows=read_rows(p/"history.csv")
  assert len(rows)==71 and all(abs(float(x["dt_s"])-.0002)<1e-12 for x in rows)
  return p/"final.sim",rows,done["time_s"]''')
rep('if len(allrows)<4000:return None',
'''n=int(round(.2/DT))
  if len(allrows)<2*n:return None''')
rep('range(2000)]\n   curr=[keys.get(round(t-.2+(i+1)*DT,7)) for i in range(2000)]',
'''range(n)]
   curr=[keys.get(round(t-.2+(i+1)*DT,7)) for i in range(n)]''')
rep('def run_stage(token,stage,index,prior):\n name,internal,cells,_=stage',
'''def run_stage(token,stage,index,prior):
 global DT
 name,internal,cells,_=stage
 DT=.0002 if name=="M11" and ctrl.read(PILOT_SELECTION).get("approved_for_continuation_pilot") is True else .0001''')
rep('assert 0<src_t<3.591', 'assert 0<src_t<3.591 and abs(round(src_t/DT)*DT-src_t)<1e-7 or (name=="M11" and abs(src_t-.6052)<1e-8 and abs(DT-.0002)<1e-12)')
rep('stage=STAGES[idx]\n   status,out=run_stage(token,stage,idx,previous)',
'''stage=STAGES[idx]
   status,out=run_stage(token,stage,idx,previous)''')
out.write_text(s,encoding="utf8")
compile(s,str(out),'exec')
print("wrote",out,"bytes",out.stat().st_size)
