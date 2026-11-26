"""CUSTOM004/W04j: export or explicitly finish its saved five-cycle request."""
import argparse
from contextlib import closing
import hashlib
import json
import math
from pathlib import Path
import re
import sqlite3
from urllib.request import Request,urlopen

from export_custom_pair import inspect_case,read,records
from export_w04i import export_wave

CASE='CUSTOM004'
LABEL='W04j'


def entries(data):
    with closing(sqlite3.connect((data/'queue.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        return [dict(r,spec=json.loads(r['spec']))for r in db.execute('SELECT * FROM jobs ORDER BY created DESC')]


def select(jobs):
    result=next((j for j in jobs if j['case_id']==CASE and not j['spec'].get('smoke')),None)
    if result is None:raise ValueError('No CUSTOM004 save was found.')
    if (result['spec'].get('H'),result['spec'].get('L'))!=(.5,15.):
        raise ValueError('CUSTOM004 dimensions differ from the confirmed H=0.5 m / wavelength=15 m.')
    return result


def workspace(root):
    config=read(root/'launcher.json')
    if config.get('release')not in('2602','2606'):raise ValueError('Unsupported STAR workspace.')
    return (Path(config['workspace_root'])/config['release']/'data').resolve()


def health(folder):
    _,rows=records(folder/'history.csv')
    limits={'max_CFL':(0,25),'interface_CFL':(0,2.2),'max_speed_m_s':(0,50),
            'alpha_min':(-.00001,1.00001),'alpha_max':(-.00001,1.00001),
            'p_min_Pa':(-1e7,1e7),'p_max_Pa':(-1e7,1e7)}
    for row in rows:
        for field,(lo,hi)in limits.items():
            value=float(row[field])
            if not math.isfinite(value)or not lo<=value<=hi:raise ValueError('Numerical health failed: '+field)
        fx,fp,fv=(float(row[k])for k in('Fx_N','Fx_pressure_N','Fx_viscous_N'))
        if not all(map(math.isfinite,(fx,fp,fv)))or abs(fx-fp-fv)>1e-5*max(1,abs(fx)):
            raise ValueError('Force balance failed.')
        if not math.isfinite(float(row['water_volume_m3']))or float(row['water_volume_m3'])<=0:
            raise ValueError('Water inventory failed.')
    if abs(float(rows[-1]['water_volume_m3'])-float(rows[0]['water_volume_m3']))>.8:
        raise ValueError('Water inventory change exceeds the existing reserve.')


def saved_pause(entry,jobs,data):
    manifest,folders,sim=inspect_case(entry,{j['id']:j for j in jobs},data)
    folder=folders[-1]
    done=read(folder/'completed.json');stage=read(folder/'stage_result.json')
    if (entry['status']!='paused'or done.get('status')!='paused_saved'
            or stage.get('exit_code')!=0 or stage.get('source_unchanged')is not True
            or not manifest['saved_final_verified']or any(folder.glob('macro_error.*'))):
        raise ValueError('Resume requires a clean saved pause; failures remain on HOLD.')
    for segment in folders:health(segment)
    with sim.open('rb')as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    if digest!=manifest['checkpoint']['expected_sha256']:raise ValueError('Saved SIM checksum differs.')
    if done.get('complete_cycles',0)>=5:raise ValueError('Five cycles are already saved; export and review them.')
    return manifest,sim


def resume(root):
    data=workspace(root);jobs=entries(data);latest=select(jobs)
    # A repeated click never creates another solver request.
    if latest['spec'].get('glhf_finish_custom004'):
        return 'The continuation already exists: '+latest['status']+'. Check the dashboard; no duplicate was created.'
    if latest.get('request_key','').startswith('glhf_CUSTOM004_finish_five_'):
        return 'The continuation already exists: '+latest['status']+'. No duplicate was created.'
    manifest,source=saved_pause(latest,jobs,data)
    if any(j['status']in('queued','deferred','preflight','running','pausing')for j in jobs):
        raise ValueError('Another queue job is active or waiting. Its queue is unchanged.')
    if (data/'STOP').exists()or (Path(latest['folder'])/'STOP_ALL').exists():raise ValueError('A manual STOP is present.')
    url=read(data/'server.json').get('url','')
    if not re.fullmatch(r'http://127\.0\.0\.1:\d+',url):raise ValueError('Open the existing GLHF dashboard first.')
    with urlopen(url+'/',timeout=15)as response:
        match=re.search(r'name="nwar-token" content="([^"]+)"',response.read().decode('utf8'))
    if not match:raise ValueError('Dashboard token is unavailable; refresh the dashboard.')
    def post(route,payload):
        req=Request(url+route,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-NWAR-Token':match[1],'Origin':url})
        with urlopen(req,timeout=60)as response:return json.load(response)
    key='glhf_CUSTOM004_finish_five_'+latest['id']
    response=post('/api/resume',dict(id=latest['id'],request_key=key));identifier=response['id']
    new=next(j for j in entries(data)if j['id']==identifier);spec=new['spec']
    if (spec.get('parent_id')!=latest['id']or spec.get('mode')!='resume'
            or spec.get('source_sha')!=manifest['checkpoint']['expected_sha256']
            or Path(spec['source']).resolve()!=source.resolve()or spec.get('target_complete_cycles')!=5
            or spec.get('analysis_cycle_numbers')!=[2,3,4,5]or spec.get('stop_kind')!='five_cycles'):
        raise ValueError('Queued continuation differs from the reviewed five-cycle request.')
    if new['status']=='deferred':
        with closing(sqlite3.connect(data/'queue.sqlite'))as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute("UPDATE jobs SET status='queued',message=? WHERE id=? AND status='deferred' AND request_key=?",
                ('W04j / CUSTOM004: continue the saved fields and phase to five complete cycles.',identifier,key)).rowcount
            if changed!=1:raise ValueError('Continuation changed before dispatch.')
            db.commit()
    post('/api/continue',{})
    return f"CUSTOM004 / W04j queued from {manifest['checkpoint']['time_s']:.4f} s. Target: 5 complete cycles, analyze 2-5. Confirm fresh physical-time samples in the dashboard."


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['export','finish']);parser.add_argument('root',type=Path);parser.add_argument('--log',type=Path);args=parser.parse_args()
    import sys
    if args.log:
        log=args.log.open('a',encoding='utf8',buffering=1)
        class Tee:
            def __init__(self,stream):self.stream=stream
            def write(self,value):self.stream.write(value);log.write(value)
            def flush(self):self.stream.flush();log.flush()
        sys.stdout=Tee(sys.stdout);sys.stderr=Tee(sys.stderr)
    try:
        root=args.root.resolve()
        if args.action=='export':export_wave(root,(root/'GLHF_exports').resolve(),select,LABEL)
        else:print(resume(root),flush=True)
    except Exception as error:
        print('HOLD: '+str(error),flush=True);raise SystemExit(1)
