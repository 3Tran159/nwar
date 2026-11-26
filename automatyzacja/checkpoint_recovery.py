"""Explicit, audited checkpoint recovery with immutable failed-run evidence."""
from common import *
import shutil

AUTH = HERE/'qa/w04_recovery_authorization_20261103.json'
PARENT = 'af9f6dd4b3c04e1f'
EXPECTED_ERROR = 'java.lang.IllegalStateException: Unphysical free surface at gauge x=-0.5: eta=1.0020820588919461'
IO_PARENT = 'e67f6677541f4629'
IO_AUTH = HERE/'qa/w04_progress_io_recovery_authorization_20261103.json'
RESTART_PARENT = '3236a97d5d8f46d2'
RESTART_AUTH = HERE/'qa/night_topup_20261103/w06_restart_recovery_authorization_20261104.json'
RESTART_EVIDENCE = HERE/'qa/night_topup_20261103/w06_planned_restart_20261104.json'
RESET_PARENT = '3b75bb329a1e4b6d'
RESET_AUTH = HERE/'qa/w06_connection_reset_recovery_authorization_20261104.json'
RESET_EVIDENCE = HERE/'qa/w06_connection_reset_20261104.json'
IO_ERROR = 'java.nio.file.AccessDeniedException: E:\\ntnu_mesh_optimization_20261030\\nwar_automation_20261102\\runs\\W04_20261103_084458_e67f66\\progress.json.tmp -> E:\\ntnu_mesh_optimization_20261030\\nwar_automation_20261102\\runs\\W04_20261103_084458_e67f66\\progress.json'
EVIDENCE = ('source_identity.json', 'stage_result.json', 'wave_setup_audit.json',
            'native_C01_rho_readback.json', 'wave_density_audit.json', 'macro_error.json',
            'latest_checkpoint.json')

def transport_failure(folder):
    stage=read(folder/'stage_result.json')
    if (stage.get('exit_code')!=1 or stage.get('source_unchanged') is not True
            or stage.get('controller_reason') is not None or (folder/'completed.json').exists()
            or (folder/'STOP').exists() or (folder/'macro_error.txt').exists()):
        return False
    macro_error=read(folder/'macro_error.json')
    error=macro_error.get('error','')
    if error and 'Connection reset' not in error and not (
            'NullPointerException' in error and 'ClientServerObject.getProperties()' in error):
        return False
    log=folder/'star.log'
    if not log.is_file():return False
    with log.open('rb') as stream:
        stream.seek(max(0,log.stat().st_size-65536))
        log_tail=stream.read()
    if b'Connection reset by peer' in log_tail:
        return True
    # Some STAR clients omit "by peer" when the remote call reports the reset.
    return ('java.net.SocketException: Connection reset' in error
            and 'star.base.neo.NeoClient.executeRemoteMethod' in macro_error.get('stack_trace','')
            and b'Connection reset' in log_tail)


def auto_authorization(parent_id):
    return DATA/'recovery_views'/('w04b_auto_'+parent_id)/'authorization.json'


def policy(parent_id):
    if parent_id==PARENT:return AUTH,EXPECTED_ERROR,PARENT+'_t11p8000'
    if parent_id==IO_PARENT:return IO_AUTH,IO_ERROR,IO_PARENT+'_t13p6408'
    if parent_id==RESTART_PARENT:
        return RESTART_AUTH,read(RESTART_EVIDENCE).get('macro_error',{}).get('error'),RESTART_PARENT+'_t6p4000'
    if parent_id==RESET_PARENT:
        return RESET_AUTH,read(RESET_EVIDENCE).get('macro_error'),RESET_PARENT+'_t11p8200'
    if isinstance(parent_id,str) and len(parent_id)==16 and all(c in '0123456789abcdef' for c in parent_id):
        path=auto_authorization(parent_id)
        if path.is_file():return path,read(path).get('error'),path.parent.name
    raise ValueError('Recovery authorization does not cover this parent')


def prefix_csv(source, target, end):
    """Copy exact original rows through the saved boundary, with no interpolation."""
    with Path(source).open(encoding='utf-8-sig', newline='') as f:
        reader=csv.DictReader(f);fields=reader.fieldnames
        kept=[r for r in reader if float(r['time_s'])<=end+1e-8]
    if not kept or abs(float(kept[-1]['time_s'])-end)>1e-7:
        raise ValueError('Checkpoint has no exact history endpoint')
    with Path(target).open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader();writer.writerows(kept)
    return len(kept)


def check_authorization(parent):
    auth_path,expected_error,_=policy(parent['id']);auth=read(auth_path)
    if auth_path==auto_authorization(parent['id']):
        folder=Path(parent['folder']);ck=read(folder/'latest_checkpoint.json')
        checkpoint=(folder/ck.get('file','')).resolve()
        if not (parent['case_id']=='W04b' and parent['status']=='failed' and auth.get('parent_id')==parent['id']
                and transport_failure(folder) and ck.get('healthy') is True and ck.get('step',0)>0
                and ck.get('time_s')==auth.get('source_time_s') and ck['time_s']>parent['spec']['source_time']
                and checkpoint.parent==folder.resolve() and checkpoint.name.startswith('checkpoint_t')
                and checkpoint.is_file() and checkpoint.stat().st_size>=400_000_000
                and sha(checkpoint)==auth.get('checkpoint_sha256')
                and sha(Path(parent['spec']['source']))==parent['spec']['source_sha']):
            raise ValueError('W04b automatic recovery checkpoint differs from verified evidence')
        return auth,ck,checkpoint
    restart=parent['id']==RESTART_PARENT
    reset=parent['id']==RESET_PARENT
    case,surface_limit=('W06',1.0) if restart or reset else ('W04',1.5)
    allowed_status=('failed','needs_attention') if reset else ('failed',)
    if not (auth.get('authorized') is True and auth.get('parent_id')==parent['id']
            and auth.get('case_id')==parent['case_id']==case and parent['status'] in allowed_status
            and auth.get('surface_limit_m')==surface_limit and auth.get('other_guards_unchanged') is True
            and auth.get('four_repeatable_cycles_required') is True):
        raise ValueError('Explicit checkpoint recovery authorization missing or mismatched')
    folder=Path(parent['folder']);ck=read(folder/'latest_checkpoint.json')
    macro_error=read(folder/'macro_error.json')
    if not expected_error or macro_error.get('error')!=expected_error:
        raise ValueError('Recovery authorization does not cover this failure')
    stage=read(folder/'stage_result.json')
    if restart:
        evidence=read(RESTART_EVIDENCE)
        pinned=evidence.get('checkpoint',{})
        if not (auth.get('restart_evidence_sha256')==sha(RESTART_EVIDENCE)
                and evidence.get('job_id')==parent['id']
                and evidence.get('windows_system_event',{}).get('shutdown_type')=='restart'
                and evidence.get('macro_error')==macro_error
                and auth.get('source_time_s')==pinned.get('time_s')
                and auth.get('checkpoint_sha256')==pinned.get('observed_sha256')
                and (folder/ck['file']).resolve()==Path(pinned['path']).resolve()
                and not stage and not (folder/'completed.json').exists()
                and not (folder/'macro_error.txt').exists()
                and parent['spec'].get('target_complete_cycles')==5):
            raise ValueError('Checkpoint recovery differs from the reviewed Windows restart')
    elif stage.get('exit_code')!=1 or stage.get('source_unchanged') is not True:
        raise ValueError('Unexpected original solver exit/source identity')
    if reset:
        evidence=read(RESET_EVIDENCE)
        pinned=evidence.get('checkpoint',{})
        if not (auth.get('failure_evidence_sha256')==sha(RESET_EVIDENCE)
                and evidence.get('job_id')==parent['id'] and evidence.get('stage')==stage
                and evidence.get('csv_health',{}).get('ok') is True and pinned.get('csv_match') is True
                and auth.get('source_time_s')==pinned.get('time_s')
                and auth.get('checkpoint_sha256')==pinned.get('sha256')
                and (folder/ck['file']).resolve()==Path(pinned['path']).resolve()
                and not (folder/'completed.json').exists() and not (folder/'macro_error.txt').exists()
                and parent['spec'].get('target_complete_cycles')==5):
            raise ValueError('Checkpoint recovery differs from the reviewed STAR connection reset')
    if ck.get('healthy') is not True or abs(ck.get('time_s',-1)-auth['source_time_s'])>1e-7:
        raise ValueError('Saved checkpoint time/health differs from authorization')
    checkpoint=(folder/ck['file']).resolve()
    if checkpoint.parent!=folder.resolve() or sha(checkpoint)!=auth['checkpoint_sha256']:
        raise ValueError('Saved checkpoint identity differs from authorization')
    if sha(Path(parent['spec']['source']))!=parent['spec']['source_sha']:
        raise ValueError('Original source identity changed')
    return auth,ck,checkpoint


def evidence_files(parent_id):
    if parent_id==RESTART_PARENT:
        return tuple(name for name in EVIDENCE if name!='stage_result.json')
    auth=read(auto_authorization(parent_id))
    if auth and not auth.get('error'):
        return tuple(name for name in EVIDENCE if name!='macro_error.json')
    return EVIDENCE


def prepare(parent):
    from analysis import numeric_rows,health
    auth,ck,checkpoint=check_authorization(parent);original=Path(parent['folder'])
    h=health(numeric_rows(original/'history.csv'))
    if not h['ok']:raise ValueError('Another numerical guard prevents recovery')
    auth_path,_,view_name=policy(parent['id'])
    view=DATA/'recovery_views'/view_name
    receipt=view/'checkpoint_recovery.json'
    if receipt.exists():
        verify(receipt,parent_id=parent['id']);return receipt
    view.mkdir(parents=True,exist_ok=auth_path==auto_authorization(parent['id']))
    counts={n:prefix_csv(original/n,view/n,ck['time_s']) for n in ('history.csv','gauges.csv')}
    files=evidence_files(parent['id'])
    for name in files:
        shutil.copy2(original/name,view/name)
    record=dict(version=1,at=now(),parent_id=parent['id'],case_id=parent['case_id'],original_folder=str(original),
                view_folder=str(view),checkpoint=str(checkpoint),checkpoint_sha256=auth['checkpoint_sha256'],
                time_s=ck['time_s'],step=ck['step'],authorization=str(auth_path),authorization_sha256=sha(auth_path),
                original_exit_code=read(original/'stage_result.json').get('exit_code'),original_failure_retained=True,diagnostic_recovery=True,
                original_source_unchanged=True,
                discarded_from_continuation_only_after_s=ck['time_s'],raw_history_preserved=True,
                health=h,rows=counts,files={n:dict(original_sha256=sha(original/n),view_sha256=sha(view/n))
                                        for n in (*files,'history.csv','gauges.csv')})
    write(receipt,record);verify(receipt,parent_id=parent['id']);return receipt


def verify(receipt, *, parent_id=None, full=True):
    receipt=Path(receipt);r=read(receipt)
    if not r or (parent_id and parent_id!=r.get('parent_id')):
        raise ValueError('Unrecognized checkpoint recovery receipt')
    auth_path,_,view_name=policy(r.get('parent_id'))
    view=Path(r['view_folder']).resolve();original=Path(r['original_folder']).resolve()
    if view!=(DATA/'recovery_views'/view_name).resolve() or receipt.resolve()!=view/'checkpoint_recovery.json':
        raise ValueError('Unexpected recovery evidence location')
    if Path(r['authorization']).resolve()!=auth_path.resolve() or sha(auth_path)!=r['authorization_sha256']:
        raise ValueError('Recovery authorization changed')
    expected_files=set((*evidence_files(r['parent_id']),'history.csv','gauges.csv'))
    if set(r['files'])!=expected_files:
        raise ValueError('Incomplete or unexpected recovery evidence')
    for name,hashes in r['files'].items():
        if sha(view/name)!=hashes['view_sha256'] or sha(original/name)!=hashes['original_sha256']:
            raise ValueError('Recovery evidence changed: '+name)
    for name in ('history.csv','gauges.csv'):
        rr=tail(view/name)
        if not rr or abs(float(rr[-1]['time_s'])-r['time_s'])>1e-7:
            raise ValueError('Recovery prefix endpoint mismatch')
    if full:
        parent=job(r['parent_id']);auth,ck,checkpoint=check_authorization(parent)
        if original!=Path(parent['folder']).resolve() or Path(r['checkpoint']).resolve()!=checkpoint:
            raise ValueError('Recovery source path mismatch')
        if r['checkpoint_sha256']!=auth['checkpoint_sha256'] or abs(r['time_s']-ck['time_s'])>1e-7:
            raise ValueError('Recovery checkpoint mismatch')
        from analysis import numeric_rows,health
        if not health(numeric_rows(view/'history.csv'))['ok']:
            raise ValueError('Recovery prefix is numerically unhealthy')
    return r
