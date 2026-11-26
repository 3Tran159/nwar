"""Exercise only a fake child process, including the graceful stop/save contract."""
from pathlib import Path
from unittest.mock import patch
import os,sys,io,json,itertools
sys.path.insert(0,str(Path(os.environ['NWAR_WORKSPACE'])/'app'))
from common import *
import portable_runtime as rt
assert 'QA' in str(DATA)
source=DATA/'fake-source-for-unit-test.sim';source.write_bytes(b'unit test; not a real STAR simulation')
folder=RUNS/('fake-owned-runtime-test-'+uuid.uuid4().hex[:8]);assert not folder.exists()
seen={}
class FakeProcess:
    pid=99999999;returncode=0
    def __init__(self,args,**kw):
        seen.update(args=args,env=kw['env'],cwd=str(kw['cwd']))
        self.stdout=io.StringIO('test log with synthetic-test-key\n');self.calls=0
        write(folder/'completed.json',dict(status='paused_saved',time_s=5.8))
    def poll(self):
        self.calls+=1;return None if self.calls==1 else 0
with patch.object(rt,'resource_problem',return_value=None),patch.object(rt,'processes',return_value={}),patch.object(rt.subprocess,'Popen',FakeProcess),patch.object(rt.time,'sleep',return_value=None),patch.object(rt.time,'monotonic',side_effect=itertools.count(100.,.1)),patch.dict(os.environ,{'NWAR_POD_KEY':'synthetic-test-key'}):
    _,result=rt.stage(folder,source,HERE/'NwarWave.java',budget_s=0)
assert result['exit_code']==0 and result['source_unchanged'] is True and result['controller_reason']=='wall_budget'
assert (folder/'STOP').exists() and read(folder/'source_identity.json')['sha256']==sha(source)
assert sha(folder/'input.sim')==sha(source)
assert 'synthetic-test-key' not in (folder/'star.log').read_text(encoding='utf8')
assert seen['env']['NWAR_RUN_ROOT']==str(RUNS.resolve()) and seen['env']['NWAR_GLOBAL_STOP']==str(DATA/'STOP')
assert seen['args'][seen['args'].index('-np')+1]=='1'
assert source.read_bytes()==b'unit test; not a real STAR simulation'
out=dict(passed=True,real_solver_started=False,fake_process_only=True,source_preserved=True,copy_hash_verified=True,graceful_stop_marker=True,stage_receipt=True,logs_redacted=True,portable_isolation_environment=True)
write(DATA.parent/'runtime_checks.json',out);print(json.dumps(out))
