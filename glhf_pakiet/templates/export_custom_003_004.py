"""Read-only, checksum-verified export of GLHF CUSTOM003 and CUSTOM004."""
import argparse,hashlib,json,math,re,shutil,sqlite3,sys,tempfile,zipfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from export_custom_pair import inspect_case,add_file,read,EVIDENCE

WAVES={'CUSTOM003':('W04i',1.,15.),'CUSTOM004':('W04j',.5,15.)}
C01='9af4857b948e0494088b5421f8ede100e66344fc2631cc00030406640d7cc295'
MIN_SIM_BYTES=400_000_000
EXTRA=('field_history_segments.json','history_cutoff.json','prior_history_provenance.json',
       'macro_error.json','controller_failure.json','native_recovery.json')

def select(entries,case):
 entry=next((j for j in entries if j['case_id']==case and not j['spec'].get('smoke')),None)
 if entry is None:raise ValueError('No '+case+' run exists in the configured GLHF workspace.')
 label,h,l=WAVES[case]
 if (entry['spec'].get('H'),entry['spec'].get('L'))!=(h,l):
  raise ValueError(case+' dimensions differ from '+label+': H='+str(h)+' m, wavelength='+str(l)+' m.')
 return entry

def saved_state(path):
 with path.open('rb')as f:
  head=f.read(1024);offset=re.search(rb"'StatePosition'\s*:\s*(\d+)",head)
  if not offset:raise ValueError('Missing native SIM state position.')
  f.seek(int(offset[1]));state=f.read(32*1024**2)
 number=rb'([-+0-9.eE]+)'
 solutions=re.findall(rb"(?m)^\{[^\r\n]*'ClassName'\s*:\s*'star.common.Solution'[^\r\n]*'PhysicalTime'\s*:\s*"+number,state)
 views=re.findall(rb"(?m)^\{[^\r\n]*'ClassName'\s*:\s*'star.post.CurrentSolutionView'[^\r\n]*$",state)
 if len(solutions)!=1 or len(views)!=1:raise ValueError('Ambiguous native SIM physical time.')
 t=float(solutions[0]);view_t=float(re.search(rb"'PhysicalTime'\s*:\s*"+number,views[0])[1])
 if not math.isfinite(t)or abs(t-view_t)>1e-7:raise ValueError('Native saved times disagree.')
 return dict(time_s=t,step=int(re.search(rb"'TimeStep'\s*:\s*(\d+)",views[0])[1]),
  scenes=len(re.findall(rb"'ClassName'\s*:\s*'star.vis.Scene'",state)),
  wave_numbers=[float(v)for v in re.findall(rb"'WaveNumber'\s*:\s*"+number,state)],
  dt_values=[float(v)for v in re.findall(rb"'TimeStepValue'\s*:\s*"+number,state)])

def export_pair(root,output):
 config=read(root/'launcher.json');release=config['release']
 if release not in('2602','2606'):raise ValueError('Unsupported configured STAR workspace.')
 data=(Path(config['workspace_root'])/release/'data').resolve()
 with closing(sqlite3.connect((data/'queue.sqlite').as_uri()+'?mode=ro',uri=True))as db:
  db.row_factory=sqlite3.Row
  entries=[dict(r,spec=json.loads(r['spec']))for r in db.execute('SELECT * FROM jobs ORDER BY created DESC')]
 by_id={j['id']:j for j in entries};manifests={};paths={};expected={}
 for case,(label,h,l)in WAVES.items():
  entry=select(entries,case)
  manifest,folders,sim=inspect_case(entry,by_id,data)
  if sim.stat().st_size<MIN_SIM_BYTES:raise ValueError('Saved SIM is missing or truncated: '+case)
  native=saved_state(sim)
  if (manifest['original_C01_sha256']!=C01 or manifest['dt_s']!=.0004
      or abs(native['time_s']-manifest['checkpoint']['time_s'])>1e-7 or native['scenes']!=30
      or len(native['wave_numbers'])!=1 or abs(native['wave_numbers'][0]-math.tau/l)>1e-8
      or .0004 not in native['dt_values']):raise ValueError('Native SIM time, wave, scenes or reference differs: '+case)
  setup=read(folders[-1]/'wave_setup_audit.json')
  if native['step']-round(setup['begin_time_s']/.0004)!=manifest['checkpoint']['step']:
   raise ValueError('Native saved step differs from the CSV checkpoint: '+case)
  done=read(folders[-1]/'completed.json');review=read(folders[-1]/'independent_cycle_review.json')if(folders[-1]/'independent_cycle_review.json').is_file()else{}
  cycles=done.get('complete_cycles',review.get('cycles',{}).get('count'))
  manifest.update(display_id=label,release=release,files={},measured_cycles_reported=cycles,
   run_completed=bool(entry['status']=='completed'and(cycles or 0)>=5 and manifest['saved_final_verified']),
   native_saved_state=native,independent_acceptance_required_on_import=True,field_history_members={})
  manifests[case]=manifest
  for i,folder in enumerate(folders):
   for name in dict.fromkeys((*EVIDENCE,*EXTRA)):
    p=folder/name
    if p.is_file():paths[f'{case}/segments/{i:03}/{name}']=p
   fields=[]
   for p in [*folder.glob('*.simh'),*(folder/'native_solve').glob('*.simh')]:
    if any(p.samefile(previous)for previous in fields):continue
    fields.append(p)
    name=('native_'if p.parent.name=='native_solve'else'')+p.name
    relative=f'segments/{i:03}/{name}';paths[case+'/'+relative]=p
    manifest['field_history_members'][str(p.relative_to(folder))]=relative
  paths[case+'/'+manifest['checkpoint']['path']]=sim
  expected[case+'/'+manifest['checkpoint']['path']]=manifest['checkpoint']['expected_sha256']
  validation=data/'validations'/(entry['id']+'.json')
  if validation.is_file():paths[case+'/validation.json']=validation
  print(f"{case} -> {label}: H={h} m / wavelength={l} m; SIM {native['time_s']:.4f} s; reported cycles={cycles}; status={entry['status']}.",flush=True)
  if not manifest['run_completed']:print('Saved diagnostic: completion and acceptance are not assumed.',flush=True)
 if output.resolve().is_relative_to(data):raise ValueError('Choose an output folder outside solver data.')
 if any(not p.resolve().is_relative_to(data)for p in paths.values()):raise ValueError('Linked export evidence leaves the GLHF data folder.')
 output.mkdir(parents=True,exist_ok=True);size=sum(p.stat().st_size for p in paths.values())
 if shutil.disk_usage(output).free<size+128*1024**2:raise ValueError('Insufficient export storage: '+format(size/2**30,'.1f')+' GiB plus reserve required.')
 captured=datetime.now().astimezone();archive=output/f'GLHF_CUSTOM003_CUSTOM004_{captured:%Y%m%d_%H%M%S_%f}.zip'
 stamps={p:(p.stat().st_size,p.stat().st_mtime_ns)for p in paths.values()}
 with tempfile.TemporaryDirectory(prefix='W04i_W04j_export_',dir=output)as tmp:
  candidate=Path(tmp)/archive.name
  with zipfile.ZipFile(candidate,'x',allowZip64=True)as bundle:
   for member,p in paths.items():
    print('Packing '+member,flush=True);record=add_file(bundle,p,member)
    if expected.get(member)and record['sha256']!=expected[member]:raise ValueError('Saved SIM checksum differs from its receipt.')
    case,relative=member.split('/',1);manifests[case]['files'][relative]=record
   for case,manifest in manifests.items():bundle.writestr(case+'/manifest.json',json.dumps(manifest,indent=2))
   bundle.writestr('manifest.json',json.dumps(dict(kind='glhf_custom_pair_v1',captured_at=captured.isoformat(),cases=manifests,
        queue_changed=False,solver_started=False),indent=2))
  if any((p.stat().st_size,p.stat().st_mtime_ns)!=stamp for p,stamp in stamps.items()):raise ValueError('Saved evidence changed; no final ZIP published.')
  print('Verifying ZIP and saved SIM checksums...',flush=True)
  with zipfile.ZipFile(candidate)as bundle:
   if bundle.testzip()is not None:raise ValueError('ZIP CRC check failed.')
   for case,manifest in manifests.items():
    member=case+'/'+manifest['checkpoint']['path']
    with bundle.open(member)as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=manifest['files'][manifest['checkpoint']['path']]['sha256']:raise ValueError('ZIP SIM checksum mismatch.')
  candidate.rename(archive)
 print('EXPORT COMPLETE: '+str(archive),flush=True)
 return archive

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('--log',type=Path);args=parser.parse_args()
 if args.log:
  log=args.log.open('a',encoding='utf8',buffering=1)
  class Tee:
   def __init__(self,stream):self.stream=stream
   def write(self,value):self.stream.write(value);log.write(value)
   def flush(self):self.stream.flush();log.flush()
  sys.stdout=Tee(sys.stdout);sys.stderr=Tee(sys.stderr)
 try:root=args.root.resolve();export_pair(root,(root/'GLHF_exports').resolve())
 except Exception as e:print('HOLD: '+str(e),flush=True);raise SystemExit(1)
