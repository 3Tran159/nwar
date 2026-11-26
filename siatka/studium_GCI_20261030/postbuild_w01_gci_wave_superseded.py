from pathlib import Path
import os,sys,time,json,subprocess,shutil,datetime
import build_w01_gci as b
O=b.OUT;SOURCE=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_calm_start_r1\checkpoint_startup_t0.020.sim')
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
 if b.sha(SOURCE)!=expected:raise RuntimeError('Source checkpoint differs from handoff')
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
 b.write(O/'verified_starting_states.json',{'source_checkpoint_time_s':.02,'sources':starts,'mesh_cells':{m:f['meshes'][m]['cells'] for m in starts},'domain_x_m':[-35,45],'original_checkpoint_unchanged':True,'status':'geometry_and_mapping_verified_wave_startup_definition_pending'})
 state('geometry_and_mapping_verified_pending_W01a_wave_startup',starting_states=starts,reason='Handoff explicitly has wave inactive and ramp under audit. A frozen tested inlet-wave startup and matched phase windows are required before launching wave GCI.')
if __name__=='__main__':
 try:main()
 except BaseException as e:state('needs_review',error=str(e));raise
