from pathlib import Path
import os,sys,time,json,subprocess,shutil,datetime
import build_w01_gci as b
O=b.OUT;SOURCE=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_calm_start_r1\final.sim')
def state(status,**kw):
 b.write(O/'study_state.json',dict(status=status,pid=os.getpid(),updated_at=datetime.datetime.now().astimezone().isoformat(),**kw));print(status,kw,flush=True)
def main():
 state('waiting_for_W01a_mesh_family')
 while True:
  if (O/'STOP').exists():raise RuntimeError('Study stop marker')
  v=b.read(O/'build_state.json')
  if v['status']=='needs_review':raise RuntimeError('Mesh build requires review: '+v['error'])
  if v['status']=='both_meshes_built_pending_family_audit':break
  time.sleep(20)
 state('auditing_W01a_actual_mesh_family')
 b.run_py(O/'audit_family.py',[],O/'family_audit.log',1800)
 f=b.read(O/'family_audit/family_audit.json')
 if not all(f['gates'].values()):raise RuntimeError('Actual refinement gates failed')
 manifest=b.read(O/'handoff/source_manifest.json')
 expected=[v['sha256'] for v in manifest if 'checkpoint_startup_t0.020.sim' in v['source']][0]
 if b.sha(SOURCE.parent/'checkpoint_startup_t0.020.sim')!=expected:raise RuntimeError('Original handoff checkpoint changed')
 done=b.read(SOURCE.parent/'completed.json');calm=b.read(SOURCE.parent/'requested_wave_audit.json')
 if done['status']!='stopped_by_marker' or abs(done['time_s']-.587)>1e-8 or calm['class']!='FlatVofWave' or calm['height_m']!=0:raise RuntimeError('Saved final calm checkpoint not as expected')
 expected=b.sha(SOURCE)
 b.write(O/'calm_source_identity.json',dict(path=str(SOURCE),sha256=expected,time_s=done['time_s'],source_requested_wave=calm,originals_preserved=True))
 os.environ['NTNU_MAP_EXPECTED_START']=str(done['time_s'])
 starts={'W01a':str(SOURCE)}
 for m in ['G10_M','G10_F']:
  out=O/('mapped_'+m);out.mkdir()
  shutil.copy2(SOURCE,out/'input.sim');assert b.sha(out/'input.sim')==expected
  cells=f['meshes'][m]['cells']
  os.environ.update(NTNU_MAP_OUT=str(out),NTNU_MAP_MESH=str(O/(m+'_raw')/'mesh_exact.CGNS'),NTNU_MAP_CELLS=str(cells))
  state('mapping_saved_W01a_fields',mesh=m,cells=cells)
  b.run_star(out/'input.sim',O/'MapW01Solution.java',out/'star.log',3600)
  mapped=b.read(out/'mapping_audit.json')
  if not mapped['pass'] or not (out/'mapped.sim').exists():raise RuntimeError('W01a mapping failed '+m)
  if b.sha(SOURCE)!=expected:raise RuntimeError('Source checkpoint changed')
  b.write(out/'source_identity.json',{'path':str(SOURCE),'sha256':expected,'original_unchanged':True,'CGNS_sha256':b.sha(O/(m+'_raw')/'mesh_exact.CGNS')})
  starts[m]=str(out/'mapped.sim')
 b.write(O/'verified_starting_states.json',{'source_checkpoint_time_s':done['time_s'],'sources':starts,'mesh_cells':{m:f['meshes'][m]['cells'] for m in starts},'domain_x_m':[-35,45],'original_checkpoint_unchanged':True,'status':'calm_geometry_and_mapping_verified'})
 state('calm_geometry_and_mapping_verified',starting_states=starts,source_time_s=done['time_s'],incident_wave_height_m=0)
if __name__=='__main__':
 try:
  import ctypes
  k=ctypes.windll.kernel32;k.GetCurrentProcess.restype=ctypes.c_void_p;k.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
  if not k.SetProcessAffinityMask(k.GetCurrentProcess(),16777212):raise RuntimeError('Affinity failed')
  main()
 except BaseException as e:state('needs_review',error=str(e));raise
