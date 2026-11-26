"""Two independent wave-only cases, each from its own flat calm start. CPU1.
Explicit user authorization 31 Oct: run waves while preparing the next foil mesh.
No changes to held C01/foil-wave campaign or existing queue. No duplicate retry.
"""
from pathlib import Path
from datetime import datetime
import sys,os,json,uuid
R=Path(r'E:\ntnu_mesh_optimization_20261030');W=R/'wave_surface_only'
sys.path[:0]=[str(R),str(W)]
import owned_experiment_runtime_20261031 as rt
import run_zero_start_cpu1_stage_20261031 as z
OUT=W/'evening_independent_L20_baseline_fine_20261031'
SOURCE=W/'WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c/input.sim'
LOCKS=[R/'parallel_cpu_20261031/auxiliary.lock',W/'wave_inlet.lock',W/'wave_mesh_comparison.lock']
TOKEN=uuid.uuid4().hex
STATUS=W/'evening_wave_current.json'
def state(status,**kw):
 rt.write(STATUS,{'status':status,'at':rt.now(),'controller_pid':os.getpid(),**kw})
def main():
 assert datetime.now().date()==datetime(2026,10,31).date()
 assert not OUT.exists() and not any(l.exists() for l in LOCKS),'Previous or live wave attempt exists'
 assert rt.resource_problem() is None
 assert rt.read(R/'plan.json')['parallel_execution']['authorized']
 assert rt.read(rt.F/'campaign_hold.json').get('active') is True
 assert rt.sha(SOURCE)=='0b422d8c395f985212c056ed5434a92551cc1ded79a178539b3782ce123a59f0'
 mine=[]
 try:
  for lk in LOCKS:
   with lk.open('x',encoding='utf-8') as f:json.dump({'pid':os.getpid(),'token':TOKEN,'kind':'independent_nofoil_cpu1_evening','at':rt.now()},f)
   mine.append(lk)
  OUT.mkdir()
  rt.write(OUT/'plan.json',{'created':rt.now(),'cases':['L20_H500_baseline','L20_H500_fine'],'workers':1,'dt_s':.001,'inner':10,'calm_steps':400,'wave_steps':2200,'old_wave_hold_preserved':True,'new_mesh_each_calm_from_zero':True,'validation':'bounded propagation evidence, not automatic acceptance'})
  for tag in ('baseline','fine'):
   assert datetime.now().date()==datetime(2026,10,31).date(),'No new start beyond authorized day'
   mesh,cells,val=z.mesh_info('L20',tag)
   calm=OUT/'calm'/('L20_'+tag)
   state('starting_calm',case='L20_H500_'+tag,directory=str(calm))
   env={'NTNU_NOFOIL_OUT':str(calm),'NTNU_NOFOIL_DT':'.001','NTNU_NOFOIL_STEPS':'400','NTNU_NOFOIL_CELLS':str(cells),'NTNU_NOFOIL_MESH':str(mesh),'NTNU_NOFOIL_WATER_M3':str(val['total_volume_m3']*.8)}
   rt.stage(calm,SOURCE,W/'CalmZeroPerMesh_20261031.java',env,workers=1,mask=1<<22,budget_s=1800,protect_main=True,phase='calm')
   assert rt.read(calm/'completed.json').get('status')=='target_reached'
   z.verify_calm(calm,'L20',tag,val)
   wave=OUT/'waves'/('L20_H500_'+tag)
   state('starting_wave',case='L20_H500_'+tag,directory=str(wave),calm_source=str(calm/'calm_pilot_final.sim'))
   env={'NTNU_NOFOIL_WAVE_OUT':str(wave),'NTNU_NOFOIL_CELLS':str(cells),'NTNU_NOFOIL_LAMBDA':'20','NTNU_NOFOIL_H':'.5','NTNU_NOFOIL_WATER_M3':str(val['total_volume_m3']*.8),'NTNU_NOFOIL_XMIN':'-35','NTNU_NOFOIL_XMAX':'45','NTNU_NOFOIL_WAVE_PERIOD_S':str(20/23.612),'NTNU_NOFOIL_WAVE_STEPS':'2200'}
   rt.stage(wave,calm/'calm_pilot_final.sim',W/'WaveFromOwnCalm_20261031.java',env,workers=1,mask=1<<22,budget_s=4200,protect_main=True,phase='waves')
   done=rt.read(wave/'completed.json');assert done.get('status')=='target_reached'
   state('bounded_wave_saved_not_validated',case='L20_H500_'+tag,directory=str(wave),time_s=done['time_s'],steps=done['steps'])
  state('two_cases_saved_pending_wave_analysis',directory=str(OUT))
 except BaseException as ex:
  state('needs_review_no_automatic_retry',directory=str(OUT),error=rt.guard.redact(str(ex))[:500]);raise
 finally:
  for lk in reversed(mine):
   if rt.read(lk).get('token')==TOKEN:lk.unlink()
if __name__=='__main__':main()
