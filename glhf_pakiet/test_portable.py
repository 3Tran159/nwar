"""Offline integration checks, run only in disposable portable QA workspaces."""
import sys,os,json,ast,hashlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(os.environ['NWAR_WORKSPACE'])/'app'))
from common import *
from portable_config import BASE,WORK,RELEASE,installation
from wave_profiles import approved_profile
from pre_w04 import PRE,calm_folders,snapshot
from pre_lineage import prepared_lineage
import portable_runtime as rt
import numpy,scipy,matplotlib,tkinter,ssl

assert 'QA' in str(WORK), 'Tests must use isolated QA workspace'
assert jobs()==[], 'Do not test an existing queue'
checks={}
for file in HERE.glob('*.py'):ast.parse(file.read_text(encoding='utf8'),filename=file.name)
checks['application_syntax']=True
checks['portable_dependencies']=dict(numpy=numpy.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,sqlite=sqlite3.sqlite_version,tcl=tkinter.TclVersion,ssl=ssl.OPENSSL_VERSION)
profile=approved_profile('W04',verify=True)
assert profile and profile['source_sha']=='d86beded68b41f5e6ce324a93cea39177dbe93fff516af10d33a71761528b85a'
assert sha(SOURCE)==SOURCE_SHA
ref=read(CALM/'C01_final_acceptance_20261101.json')
assert sha(CALM/'history.csv')==ref['history_sha256']
assert ref['project_primary_settled'] is True
last,good,links=prepared_lineage(read(PRE/'calm_receipt.json'),calm_folders())
assert good and last.resolve()==Path(profile['source']).resolve() and all(l['ok'] for l in links)
checks['C01_and_PRE_hashes_and_full_lineage']=dict(ok=True,links=len(links),C01_sha256=SOURCE_SHA,PRE_sha256=profile['source_sha'])
prep=snapshot();assert prep['active'] is False and prep['receipt']['passed'] is True
checks['PRE_archive_inactive']=True
cat=catalog();assert [c['id'] for c in cat]==['W04','W05','W06','W07'] and all(c['ready'] for c in cat)
assert (cat[0]['H'],cat[0]['L'])==(1.5,38.99857691441418)
checks['approved_catalog']=True
args,install=rt.launch_arguments(Path(profile['source']),HERE/'NwarWave.java')
assert install['release']==RELEASE and args[args.index('-np')+1]=='1' and args[args.index('-gpgpu')+1]=='auto:1'
for args2 in [(2,True),(1,False)]:
    try:rt.launch_arguments(SOURCE,HERE/'NwarWave.java',*args2)
    except ValueError:pass
    else:raise AssertionError('Unsafe process setting accepted')
checks['version_and_one_GPU_process']=dict(release=RELEASE,build=install['build'])
from worker import resource_processes,preflight
with patch.object(rt.guard,'processes',return_value={123:(1,'starccm+.exe')}),patch.object(rt.subprocess,'Popen',side_effect=AssertionError('No native solver may start')) as launch:
    try:resource_processes({})
    except ValueError:pass
    else:raise AssertionError('Foreign solver was not blocked')
    assert launch.call_count==0
checks['foreign_solver_blocks_without_launch']=True
try:rt.stage(WORK/'outside-runs',SOURCE,HERE/'NwarWave.java')
except ValueError as e:assert 'outside' in str(e)
else:raise AssertionError('Path containment not enforced')
with patch.dict(os.environ,{'NWAR_POD_KEY':'synthetic-test-key'}):
    assert 'synthetic-test-key' not in rt.redact('synthetic-test-key -podkey synthetic-test-key')
checks['path_containment_and_secret_redaction']=True
with patch.object(rt.Path,'exists',return_value=False),patch.object(rt.shutil,'disk_usage',return_value=type('Usage',(),{'free':30*rt.GIB})()):
    for available in (8*rt.GIB,12*rt.GIB,16*rt.GIB):
        with patch.object(rt,'free_memory',return_value=available):assert rt.resource_problem() is None
    with patch.object(rt,'free_memory',return_value=8*rt.GIB-1):
        assert rt.resource_problem()=='At least 8 GiB free RAM is required.'
    with patch.object(rt,'free_memory',return_value=8*rt.GIB),patch.object(rt.shutil,'disk_usage',return_value=type('Usage',(),{'free':25*rt.GIB-1})()):
        assert 'storage' in rt.resource_problem()
with patch.object(rt.Path,'exists',return_value=True):assert rt.resource_problem()=='Pause/STOP is present.'
checks['free_RAM_boundary_8_GiB_and_other_resource_guards']=True
from custom_waves import submit,dimensions,release_next
for H,L in [(1.50001,40),(1.5,40.00001),(.249,30),(1,19.999),(True,30),('NaN',30)]:
    try:dimensions(H,L)
    except ValueError:pass
    else:raise AssertionError('Invalid dimensions accepted')
jid=submit(1.5,40,'portable-qa-request-0001');assert submit(1.5,40,'portable-qa-request-0001')==jid
j=job(jid);assert j['status']=='deferred' and j['spec']['wait_for_campaign_id'] is None and j['spec']['mpi_processes']==1
assert j['spec']['source']==profile['source'] and j['spec']['H']==1.5 and j['spec']['L']==40
with patch('worker.native',return_value=[(123,'starccm+.exe')]):assert release_next() is None
with patch('worker.native',return_value=[]):assert release_next()==jid
assert job(jid)['status']=='queued';update(jid,status='cancelled',message='QA only; never launched')
checks['custom_bounds_idempotency_and_serial_release']=True
fid=enqueue('W04',request_key='portable-qa-w04-0001');j=job(fid)
assert j['spec']['source']==profile['source'] and not j['spec'].get('allow_approved_cpu')
update(fid,status='cancelled',message='QA only; never launched')
checks['fresh_W04_uses_accepted_PRE']=True
assert not (DATA/'worker.lock').exists()
assert not list(RUNS.iterdir())
checks['no_solver_started']=True
out=dict(passed=True,at=now(),release=RELEASE,checks=checks)
write(WORK/'offline_checks.json',out);print(json.dumps(out,ensure_ascii=True))
