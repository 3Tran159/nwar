from pathlib import Path
import json,time,os,shutil,py_compile,datetime
O=Path(__file__).resolve().parent
old=O/'force_stabilization_20261029/calm_pilot_G10_F_r1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
# The owned pilot has already demonstrated that 0.2 ms exceeds the interface CFL screen.
deadline=time.time()+600
while (O/'cpu_calm_study.lock').exists() or not (old/'exit.json').exists():
 if time.time()>deadline:raise RuntimeError('Owned pilot did not save and stop within ten minutes')
 time.sleep(3)
exitinfo=read(old/'exit.json');done=read(old/'completed.json');audit=read(old/'calm_audit.json')
assert exitinfo['returncode']==0 and exitinfo['source_unchanged']
assert done['status']=='stopped_by_marker' and audit['GPU_count']==0 and audit['incident_wave_height_m']==0
assert (old/'EXPORT_OK.json').exists() and (old/'final.sim').exists()
warm=dict(mesh='G10_F',source=str(old/'final.sim'),time_s=done['time_s'],reason='Retain the computed calm mapped-field relaxation. 0.2 ms pilot exceeded the interface CFL screen; continue at 0.1 ms and verify before accepting production timestep.',requested_dt_s=.0001,original_source_preserved=True)
(O/'calm_warm_restart.json').write_text(json.dumps(warm,indent=2))
p=O/'cpu_calm_study.py';shutil.copy2(p,O/'cpu_calm_before_CFL_warm_restart.py.txt');t=p.read_text()
def sub(a,b):
 global t
 assert t.count(a)==1,a
 t=t.replace(a,b)
sub("start=verified['source_checkpoint_time_s'];dt=.0002","""start=verified['source_checkpoint_time_s'];dt=.0001
 start_times={m:start for m in LEVELS}
 warm=read(O/'calm_warm_restart.json')
 sources['G10_F']=Path(warm['source']);start_times['G10_F']=warm['time_s']
 if not sources['G10_F'].is_file():raise RuntimeError('Saved warm fine reference missing')""")
sub("out,d=flow('calm_pilot_'+m+'_r'+str(attempt+1),sources[m],start,start+.01,dt,10,cells[m],pilot=True)","out,d=flow('calm_pilot_'+m+'_continued_r'+str(attempt+1),sources[m],start_times[m],start_times[m]+.004,dt,10,cells[m],pilot=True)")
sub("dt/=2**max(1,math.ceil(math.log2(1.1*worst)))","""dt/=2**max(1,math.ceil(math.log2(1.1*worst)))
  # Keep all computed relaxation fields when reducing dt; calm-water comparisons need stationarity, not a common wave phase.
  for m in LEVELS:
   sources[m]=pilots[m]/'final.sim';start_times[m]=read(pilots[m]/'completed.json')['time_s']""")
p.write_text(t,encoding='utf-8');py_compile.compile(str(p),doraise=True)
plan=read(O/'study_plan.json');plan.update(common_timestep_candidate_s=.0001,calm_pilot_duration_s=.004,reuse_computed_pilot_fields_on_dt_change=True)
(O/'study_plan.json').write_text(json.dumps(plan,indent=2))
print('Restarting CPU22 queue from saved fine fields at',warm['time_s'],flush=True)
import subprocess; raise SystemExit(subprocess.call([os.sys.executable,str(p)],creationflags=subprocess.CREATE_NO_WINDOW))
