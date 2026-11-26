"""Explicitly resume the verified GLHF W04f/CUSTOM002 save; never forge completion."""
import argparse
from contextlib import closing
import csv
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from urllib.request import Request,urlopen

PARENT='391d8afbdbb542af'
EXPECTED_SHA='42bfad6649b9be2cc6d235a000bc548c5e8416ea66bd7d229b3d651fe0f0e3be'
EXPECTED_TIME=13.914800000011667
KEY='glhf_W04f_CUSTOM002_391d8afbdbb542af_resume_five_cycles'


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def entries(database):
    with closing(sqlite3.connect(database.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        return [dict(r,spec=json.loads(r['spec'])) for r in db.execute('SELECT * FROM jobs ORDER BY created DESC')]


def verify(entry,data):
    folder=Path(entry['folder']).resolve()
    if not folder.is_relative_to((data/'runs').resolve()):raise ValueError('Unexpected run folder.')
    spec=entry['spec']
    done,stage,ck,integrity=[read(folder/name) for name in ('completed.json','stage_result.json','latest_checkpoint.json','final_integrity.json')]
    if (entry['id']!=PARENT or entry['case_id']!='CUSTOM002' or entry['status']!='paused'
            or (spec.get('H'),spec.get('L'))!=(1.5,30.) or done.get('status')!='paused_saved'
            or stage.get('exit_code')!=0 or stage.get('source_unchanged') is not True
            or ck.get('healthy') is not True or Path(ck['file']).name!=ck['file']
            or any(abs(float(item['time_s'])-EXPECTED_TIME)>1e-7 for item in (done,ck,integrity))
            or any(folder.glob('macro_error.*'))):raise ValueError('The saved W04f pause differs from the verified export.')
    source=folder/ck['file']
    before=source.stat()
    with source.open('rb') as stream:digest=hashlib.file_digest(stream,'sha256').hexdigest()
    after=source.stat()
    if digest!=EXPECTED_SHA or integrity.get('sha256')!=digest or (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
        raise ValueError('Saved checkpoint checksum changed.')
    with (folder/'history.csv').open(encoding='utf-8-sig',newline='') as stream:last=list(csv.DictReader(stream))[-1]
    if abs(float(last['time_s'])-EXPECTED_TIME)>1e-7 or int(last['step'])!=int(ck['step']):
        raise ValueError('Checkpoint does not match the final history step.')
    if done.get('complete_cycles',0)>=5:
        raise ValueError('Five cycles are already saved; review the new export before resuming.')
    return source


def resume(root):
    config=read(root/'launcher.json')
    work=(Path(config['workspace_root'])/config['release']).resolve()
    data=work/'data';database=data/'queue.sqlite'
    jobs=entries(database)
    previous=next((j for j in jobs if j['request_key']==KEY),None)
    if previous and previous['status'] not in ('queued','deferred'):
        return 'W04f continuation already exists: '+previous['status']+'. Check the dashboard; no duplicate was created.'
    newer=next((j for j in jobs if j['case_id']=='CUSTOM002' and j['id']!=PARENT
                and j['id']!=(previous or {}).get('id') and j['status'] not in ('failed','cancelled','preflight_blocked')),None)
    if newer:raise ValueError('A newer W04f run exists. Its state is preserved; use the dashboard.')
    parent=next(j for j in jobs if j['id']==PARENT)
    source=verify(parent,data)
    if any(j['status'] in ('queued','deferred','running','preflight','pausing') and j['id']!=(previous or {}).get('id') for j in jobs):
        raise ValueError('Another queue job is active or waiting.')
    if (data/'STOP').exists() or (Path(parent['folder'])/'STOP_ALL').exists():
        raise ValueError('A manual STOP is present.')
    owner=read(data/'server.json');url=owner.get('url','')
    if not re.fullmatch(r'http://127\.0\.0\.1:\d+',url):raise ValueError('Open the existing GLHF dashboard first.')
    with urlopen(url+'/',timeout=10) as response:
        token=re.search(r'name="nwar-token" content="([^"]+)"',response.read().decode('utf8')).group(1)
    def post(route,payload):
        request=Request(url+route,data=json.dumps(payload).encode(),headers={'Content-Type':'application/json','X-NWAR-Token':token,'Origin':url})
        with urlopen(request,timeout=45) as response:return json.load(response)
    if previous:ident=previous['id']
    else:ident=post('/api/resume',dict(id=PARENT,request_key=KEY))['id']
    # The older custom-wave dispatcher marks even explicit saved resumes deferred.
    # Promote only this inspected continuation, without changing any application code.
    current=next(j for j in entries(database) if j['id']==ident)
    spec=current['spec']
    if (spec.get('parent_id')!=PARENT or spec.get('mode')!='resume' or spec.get('source_sha')!=EXPECTED_SHA
            or Path(spec['source']).resolve()!=source.resolve() or spec.get('target_complete_cycles')!=5
            or spec.get('analysis_cycle_numbers')!=[2,3,4,5] or spec.get('stop_kind')!='five_cycles'):
        raise ValueError('Queued continuation differs from the verified five-cycle request.')
    if current['status']=='deferred':
        with closing(sqlite3.connect(database)) as db:
            db.execute('BEGIN IMMEDIATE')
            changed=db.execute("UPDATE jobs SET status='queued',message=? WHERE id=? AND status='deferred' AND request_key=?",
                ('W04f / CUSTOM002: verified resume from 13.9148 s; complete five measured cycles.',ident,KEY)).rowcount
            if changed!=1:raise ValueError('Continuation status changed before dispatch.')
            db.commit()
    post('/api/continue',{})
    return 'W04f queued from 13.9148 s. Target: five measured cycles; analyze 2-5. Job '+ident+'. Confirm that physical time increases.'


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    try:print(resume(args.root.resolve()),flush=True)
    except Exception as error:
        print('HOLD: '+str(error),flush=True)
        raise SystemExit(1)
