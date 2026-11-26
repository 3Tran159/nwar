"""Recover the exact checkpoint prefix; retain every discarded raw sample on disk."""
from common import *
from pre_w04 import PRE,calm_folders,calm_values
from pre_balance import balance_seed
from worker import native
import shutil

def main():
 assert not native(),'Wait for scene preparation to finish'
 prepared=read(PRE/'scene_preparation.json');assert prepared.get('status')=='ready'
 folders=calm_folders();parent=folders[-1];out=Path(prepared['folder']);time_s=prepared['source_time_s'];source=Path(prepared['source'])
 assert source.parent==parent and out.resolve().is_relative_to(PRE.resolve())
 assert read(out/'source_identity.json')['sha256']==sha(source)
 assert prepared['checkpoint_sha256']==sha(out/'final.sim')
 assert read(parent/'stage_result.json').get('source_unchanged') is True
 assert read(out/'stage_result.json').get('exit_code')==0 and read(out/'scene_receipt.json').get('steps_advanced')==0
 assert not (parent/'history_cutoff.json').exists(),'Already recovered'
 checkpoint_rows={}
 for name in ['history.csv','conservation.csv','mass_balance.csv','boundary_flux.csv','field_health.csv','gauges.csv','vof_substeps.csv']:
  data=rows(parent/name)
  if not data:continue
  key=next(k for k in ('time_s','physical_time_s') if k in data[0])
  selected=[r for r in data if abs(float(r[key])-time_s)<1e-8]
  assert selected,'Missing checkpoint data: '+name
  with (out/name).open('x',encoding='utf8',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=list(data[0]));writer.writeheader();writer.writerows(selected)
  checkpoint_rows[name]=len(selected)
 raw=rows(parent/'history.csv');tail_time=float(raw[-1]['time_s'])
 setup=read(parent/'setup.json');setup.update(postprocessing_only=True,scene_source=str(source));write(out/'setup.json',setup)
 cutoff=dict(time_s=time_s,checkpoint=str(source),checkpoint_sha256=sha(source),reason='Recovery after the display-client connection reset',
             original_history_end_s=tail_time,discarded_steps=round((tail_time-time_s)/.0004),raw_files_preserved=True,scene_setup=str(out),at=now())
 write(parent/'history_cutoff.json',cutoff)
 write(out/'recovery_provenance.json',dict(**cutoff,source_history=str(parent/'history.csv'),source_history_sha256=sha(parent/'history.csv'),checkpoint_rows=checkpoint_rows))
 old=read(PRE/'calm_receipt.json');shutil.copy2(PRE/'calm_receipt.json',out/'previous_calm_receipt.json')
 receipt={**old,'passed':False,'checkpoint':str(out/'final.sim'),'checkpoint_sha256':prepared['checkpoint_sha256'],'checkpoint_time_s':time_s,
          'completed':read(out/'completed.json'),'pending':'Resume calm stabilization from saved fields with native scenes',
          'scene_preparation':prepared,'recovery':cutoff,'history_folders':list(map(str,folders+[out]))}
 write(PRE/'calm_receipt.json',receipt)
 write(PRE/'continuation.json',dict(folders=list(map(str,folders+[out])),updated_at=now(),recovery=cutoff))
 balance=balance_seed(calm_folders());values=calm_values()
 assert abs(balance['last_time_s']-time_s)<1e-8 and abs(values[-1,0]-time_s)<1e-8
 assert abs(balance['water_closure_error_m3'])<.25
 write(out/'recovery_ready.json',dict(passed=True,checkpoint=str(out/'final.sim'),time_s=time_s,balance=balance,raw_history_preserved=True))
 print(json.dumps(read(out/'recovery_ready.json')))

if __name__=='__main__':main()
