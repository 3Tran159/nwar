"""Export an existing GLHF result or continue its verified saved state."""
import argparse
import csv
import getpass
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

from glhf_bundle import CASES, C01, PRE, SCHEMA, EVIDENCE, load_manifest, path_under

MIN_CHECKPOINT_BYTES = 400_000_000


def copy_checked(source, target):
    from common import sha
    expected = sha(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha(target) != expected or sha(source) != expected:
        raise ValueError('File changed while copying: ' + source.name)
    return dict(bytes=target.stat().st_size, sha256=expected)


def checkpoint_for(entry):
    from common import read, sha, tail
    folder = Path(entry['folder']).resolve()
    ck = read(folder/'latest_checkpoint.json')
    if ck.get('healthy') is not True or Path(ck.get('file', '')).name != ck.get('file'):
        raise ValueError('HOLD: no recorded healthy checkpoint')
    sim = (folder/ck['file']).resolve()
    if sim.parent != folder or sim.suffix.lower() != '.sim' or not sim.is_file() or sim.stat().st_size < MIN_CHECKPOINT_BYTES:
        raise ValueError('HOLD: checkpoint is missing, incomplete or outside its run')
    t = float(ck['time_s'])
    with (folder/'history.csv').open(encoding='utf-8-sig', newline='') as stream:
        matches = [row for row in csv.DictReader(stream) if abs(float(row['time_s'])-t) <= 1e-7]
    if len(matches) != 1 or int(matches[0]['step']) != int(ck['step']):
        raise ValueError('HOLD: checkpoint time and step do not match a force-history row')
    h = sha(sim)
    final_verified = None
    if sim.name == 'wave_pilot_final.sim':
        stage = read(folder/'stage_result.json')
        final = read(folder/'final_integrity.json')
        done = read(folder/'completed.json')
        end = float(tail(folder/'history.csv')[-1]['time_s'])
        final_verified = (stage.get('exit_code') == 0 and stage.get('source_unchanged') is True
                          and final.get('sha256') == h
                          and all(v is not None and abs(float(v)-t) <= 1e-7
                                  for v in (done.get('time_s'), final.get('time_s'), end)))
    return sim, dict(time_s=t, step=int(ck['step']), sha256=h, final_save_verified=final_verified)


def read_case(entry):
    from common import DATA, sha, SOURCE, read
    from portable_config import RELEASE
    from wave_profiles import verify_spec
    from analysis import segment_chain, analyze
    case = entry['case_id']
    profile = verify_spec(case, entry['spec'])
    if profile['source_sha'] != PRE or sha(SOURCE) != C01:
        raise ValueError('The GLHF run uses another PRE or C01 reference')
    chain = [p.resolve() for p in segment_chain(entry)]
    for i, part in enumerate(chain):
        if not part.is_relative_to(DATA.resolve()):
            raise ValueError('Run lineage leaves the selected GLHF workspace')
        identity = read(part/'identity.json')
        setup = read(part/'wave_setup_audit.json')
        if identity.get('release') not in (None, RELEASE):
            raise ValueError('Mixed STAR releases in the GLHF run')
        if (setup.get('scene_count') != 30 or setup.get('cells') != profile['cells']
                or setup.get('mesh_profile') != profile['id'] or setup.get('dt_s') != .0004
                or setup.get('H_m') != 1. or setup.get('lambda_m') != CASES[case]
                or setup.get('global_initialization') is not False
                or abs(float(setup['t0'])-profile['wave_origin_s']) > 1e-7):
            raise ValueError('Wave configuration or scene inventory differs from approved W05/W07')
        origin = read(part/'source_identity.json')
        source = Path(origin['path']).resolve()
        if i == 0:
            expected_source = Path(profile['source']).resolve()
            if source != expected_source or origin.get('sha256') != PRE:
                raise ValueError('The first segment does not descend from the approved PRE')
        else:
            previous = chain[i-1]
            anchor = read(previous/'glhf_resume.json')
            if source.parent != previous and source != Path(anchor.get('checkpoint', '')).resolve():
                raise ValueError('The continuation source is outside the preceding segment')
            prev_checkpoint = read(previous/'latest_checkpoint.json')
            if abs(float(prev_checkpoint['time_s'])-float(setup['begin_time_s'])) > 1e-7:
                raise ValueError('Segment start differs from the preceding saved checkpoint')
        if sha(source) != origin.get('sha256'):
            raise ValueError('A source checkpoint differs from its recorded checksum')
    result, _, _ = analyze(dict(entry['spec'], id=case), chain)
    return chain, result


def idle(entry, *, finishing=False):
    from common import DATA, SOLVER_LOCKS, OTHER_LOCKS, STOPS, birth, datetime, jobs, read
    from worker import native
    folder = Path(entry['folder'])
    proc = read(folder/'process.json')
    owner = read(DATA/'worker.lock')
    if native() or any(birth(pid) for pid in (proc.get('pid'), proc.get('controller_pid'), entry.get('controller_pid'), owner.get('pid'))):
        raise ValueError('Wait for STAR and the existing queue controller to finish')
    if finishing:
        stage = read(folder/'stage_result.json')
        done = read(folder/'completed.json')
        marker = folder/'STOP'
        archived_stop = (marker.exists() and entry['status']=='paused' and stage.get('exit_code')==0
                         and stage.get('source_unchanged') is True and done.get('status')=='paused_saved'
                         and stage.get('at') and marker.stat().st_size==0
                         and marker.stat().st_mtime <= datetime.fromisoformat(stage['at']).timestamp())
        if any(p.exists() for p in STOPS+OTHER_LOCKS+[DATA/'PAUSE']) or (marker.exists() and not archived_stop):
            raise ValueError('HOLD: a pause, STOP or foreign reservation is present')
        if any(j['id'] != entry['id'] and j['status'] in ('queued', 'deferred', 'preflight', 'running', 'pausing') for j in jobs()):
            raise ValueError('HOLD: the existing queue has other pending work')
    return [p for p in SOLVER_LOCKS if p.exists()]


def export(entry, chain, result, sim, checkpoint, destination):
    from common import DATA, now, write
    from portable_config import RELEASE
    output = Path(destination).resolve()/f"GLHF_{entry['case_id']}_{entry['id']}"
    if output.exists():
        previous = load_manifest(output)
        if previous['checkpoint']['sha256'] != checkpoint['sha256'] or previous['history_end_s'] != result['time_s']:
            raise ValueError('Existing export preserved. Select another export directory.')
        return output
    temp = output.with_name(output.name+'.partial-'+uuid.uuid4().hex[:8])
    files = {'checkpoint/latest.sim': copy_checked(sim, temp/'checkpoint/latest.sim')}
    if files['checkpoint/latest.sim']['sha256'] != checkpoint['sha256']:
        raise ValueError('Checkpoint changed after verification')
    segments = []
    for i, part in enumerate(chain):
        rel = f'segments/{i:03}'
        segments.append(rel)
        for name in sorted(EVIDENCE):
            source = part/name
            # Launch logs, settings and arbitrary failure text are intentionally excluded.
            if source.is_file() and name not in ('controller_failure.json', 'macro_error.json'):
                target = f'{rel}/{name}'
                files[target] = copy_checked(source, temp/target)
    validation = DATA/'validations'/(entry['id']+'.json')
    if validation.is_file():
        files['validation.json'] = copy_checked(validation, temp/'validation.json')
    write(temp/'manifest.json', dict(schema=SCHEMA, exported_at=now(), case_id=entry['case_id'],
          run_id=entry['id'], run_status=entry['status'], release=RELEASE,
          C01_sha256=C01, PRE_sha256=PRE, H_m=1., lambda_m=CASES[entry['case_id']], dt_s=.0004,
          history_end_s=result['time_s'], measured_cycles=result['cycles']['count'],
          checkpoint=dict(checkpoint, path='checkpoint/latest.sim', original_name=sim.name),
          segments=segments, files=files))
    load_manifest(temp)
    temp.rename(output)
    return output


def prefix(source, target, end, *, forces):
    with source.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames
        rows = [r for r in reader if float(r['time_s']) <= end+1e-8]
    tolerance = 1e-7 if forces else .0041
    if not rows or abs(float(rows[-1]['time_s'])-end) > tolerance:
        raise ValueError('History has no verified samples at the checkpoint boundary')
    with target.open('w', encoding='utf8', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def prepare_resume(entry, chain, checkpoint, sim):
    from common import DATA, now, read, sha, write
    from analysis import analyze, gauge_series
    import numpy as np
    view = DATA/'glhf_resume'/entry['id']
    receipt = view/'glhf_resume.json'
    if receipt.exists():
        verify_resume(receipt)
        return receipt
    temp = view.with_name(view.name+'.partial-'+uuid.uuid4().hex[:8])
    temp.mkdir(parents=True)
    for name in ('history.csv', 'gauges.csv'):
        prefix(chain[-1]/name, temp/name, checkpoint['time_s'], forces=name=='history.csv')
    for name in ('wave_setup_audit.json','source_identity.json','native_C01_rho_readback.json','wave_density_audit.json','latest_checkpoint.json'):
        shutil.copy2(chain[-1]/name, temp/name)
    joined = chain[:-1]+[temp]
    result, data, _ = analyze(dict(entry['spec'],id=entry['case_id']), joined)
    if not result['health']['ok'] or abs(result['time_s']-checkpoint['time_s']) > 1e-7:
        raise ValueError('HOLD: unhealthy checkpoint history')
    if not np.allclose(np.diff(data['time_s']), .0004, rtol=0, atol=1e-7):
        raise ValueError('HOLD: a force-history step is missing')
    gauge = gauge_series(joined,-.5)
    if (len(gauge)<2 or not np.isfinite(gauge).all() or np.max(np.abs(gauge[:,1]))>1.
            or np.any(np.diff(gauge[:,0])>.012)):
        raise ValueError('HOLD: discontinuous or unhealthy reference probe')
    if result['cycles']['count'] >= 5:
        raise ValueError('This checkpoint already has five measured cycles. Review the export.')
    source_identity = read(chain[-1]/'source_identity.json')
    evidence = {str(p/name): sha(p/name) for p in chain for name in ('history.csv','gauges.csv','source_identity.json','wave_setup_audit.json')}
    files = {p.name:sha(p) for p in temp.iterdir()}
    write(temp/'glhf_resume.json', dict(at=now(), case_id=entry['case_id'], parent_id=entry['id'],
          checkpoint=str(sim), checkpoint_sha256=checkpoint['sha256'], time_s=checkpoint['time_s'],
          segments=list(map(str,chain[:-1]+[view])), original_folder=str(chain[-1]),
          original_source=source_identity, original_exit_code=read(chain[-1]/'stage_result.json').get('exit_code'),
          raw_files=evidence, prefix_files=files, original_history_preserved=True))
    temp.rename(view)
    verify_resume(receipt)
    return receipt


def verify_resume(path):
    from common import DATA, read, sha
    path = Path(path).resolve()
    receipt = read(path)
    if (not receipt or receipt.get('case_id') not in CASES
            or path != (DATA/'glhf_resume'/receipt['parent_id']/'glhf_resume.json').resolve()
            or Path(receipt['segments'][-1]).resolve() != path.parent):
        raise ValueError('Invalid GLHF checkpoint receipt')
    original = Path(receipt['original_folder']).resolve()
    checkpoint = Path(receipt['checkpoint']).resolve()
    if (not original.is_relative_to(DATA.resolve()) or checkpoint.parent != original
            or any((original/n).exists() for n in ('macro_error.json','macro_error.txt'))
            or sha(checkpoint) != receipt['checkpoint_sha256']):
        raise ValueError('GLHF checkpoint identity changed')
    for raw, expected in receipt['raw_files'].items():
        f = Path(raw).resolve()
        if not f.is_relative_to(DATA.resolve()) or sha(f) != expected:
            raise ValueError('Original GLHF history changed')
    for name, expected in receipt['prefix_files'].items():
        if sha(path_under(path.parent,name)) != expected:
            raise ValueError('GLHF history prefix changed')
    return receipt


def finish(entry, chain, result, sim, checkpoint):
    from common import DATA, PYTHON, HERE, birth, connection, enqueue, job, now, read, sha, write
    from worker import rt
    from portable_config import settings
    folder = Path(entry['folder'])
    if checkpoint.get('final_save_verified') is False:
        raise ValueError('HOLD: the exported final SIM lacks clean-exit or checksum evidence')
    if entry['status'] in ('failed','cancelled') or not result['health']['ok']:
        raise ValueError('HOLD: failed, cancelled or unhealthy run')
    stage = read(folder/'stage_result.json')
    if (stage and stage.get('exit_code') != 0
            or any((folder/n).exists() for n in ('macro_error.json','macro_error.txt'))):
        raise ValueError('HOLD: solver error. Export was saved for review.')
    if result['cycles']['count'] >= 5 and abs(result['time_s']-checkpoint['time_s']) <= 1e-7:
        print('Five measured cycles already exist in the saved result. Check validation.')
        return
    locks = idle(entry, finishing=True)
    records = []
    for path in locks:
        owner = read(path)
        if (not owner.get('birth') or owner.get('pid') != entry.get('controller_pid')
                or owner['birth'] != entry.get('controller_birth') or owner.get('role') != 'nwar_wave'
                or birth(owner['pid']) or not owner.get('token')):
            raise ValueError('HOLD: reservation ownership cannot be verified')
        records.append(dict(path=str(path), sha256=sha(path), mtime_ns=path.stat().st_mtime_ns, owner=owner))
    if len({r['owner']['token'] for r in records}) > 1:
        raise ValueError('HOLD: reservations belong to different owners')
    if settings().get('license_mode') == 'pod' and not os.environ.get('NWAR_POD_KEY'):
        os.environ['NWAR_POD_KEY'] = getpass.getpass('STAR Power-on-Demand key for this session: ')
    rt.launch_arguments(sim,HERE/'NwarWave.java')
    problem = rt.resource_problem()
    if problem:
        raise ValueError(problem)
    receipt = prepare_resume(entry, chain, checkpoint, sim)
    idle(entry, finishing=True)
    audit = receipt.with_name('dispatch.json')
    write(audit, dict(at=now(), parent_id=entry['id'], checkpoint_sha256=checkpoint['sha256'], stale_locks=records))
    for record in records:
        path = Path(record['path'])
        if sha(path) != record['sha256'] or path.stat().st_mtime_ns != record['mtime_ns'] or birth(record['owner']['pid']):
            raise ValueError('Reservation changed during verification')
        path.unlink()
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if entry['status'] in ('running','preflight','needs_attention'):
            updated = conn.execute("UPDATE jobs SET status='interrupted',updated=?,message=? WHERE id=? AND status=?",
                                   (now(),'Original segment preserved. Verified GLHF continuation queued.',entry['id'],entry['status']))
            if updated.rowcount != 1:
                raise ValueError('Original run changed during preflight')
        ident = enqueue(entry['case_id'], 'resume', request_key='glhf_five_'+entry['id']+'_'+checkpoint['sha256'][:16],
                        conn=conn, glhf_recovery=receipt, mpi_processes=1)
    if job(ident)['status'] != 'queued':
        raise ValueError('The continuation request already exists. Review the current status.')
    log = DATA/'glhf_worker.log'
    with log.open('a',encoding='utf8') as stream:
        worker = subprocess.Popen([str(PYTHON),str(HERE/'worker.py'),'--only',ident],cwd=HERE,stdout=stream,stderr=stream,
                                  creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
    write(audit, dict(at=now(), parent_id=entry['id'], child_id=ident, worker_pid=worker.pid,
                      checkpoint_sha256=checkpoint['sha256'], stale_locks=records))
    print(f'{entry["case_id"]} queued as {ident} from t={checkpoint["time_s"]:.4f} s, target 5 measured cycles.')
    print('Check the GLHF dashboard for real progress. Export again after the final save.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('export','finish'))
    parser.add_argument('--case', choices=CASES, default='W05')
    parser.add_argument('--workspace', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    base = Path(__file__).resolve().parents[2]
    import json
    config = json.loads((base/'launcher.json').read_text(encoding='utf-8-sig'))
    work = (args.workspace or Path(config['workspace_root'])/config['release']).resolve()
    if not (work/'data/queue.sqlite').is_file():
        raise ValueError('The selected GLHF workspace has no existing NWAR queue')
    release = json.loads((work/'settings.json').read_text(encoding='utf-8-sig'))['release']
    if release not in ('2602','2606'):
        raise ValueError('Unsupported GLHF workspace release')
    os.environ.update(NWAR_PACKAGE_ROOT=str(base), NWAR_WORKSPACE=str(work), NWAR_STAR_RELEASE=release)
    from common import jobs
    entry = next((j for j in jobs() if j['case_id']==args.case and not j['spec'].get('smoke')
                  and (Path(j['folder'])/'history.csv').is_file()),None)
    if entry is None:
        raise ValueError('No real history exists for '+args.case)
    idle(entry)
    chain, result = read_case(entry)
    sim, checkpoint = checkpoint_for(entry)
    output = export(entry,chain,result,sim,checkpoint,args.output or base/'GLHF_exports')
    print(f'Export: {output}')
    print(f'Last saved SIM: t={checkpoint["time_s"]:.4f} s. Raw history: t={result["time_s"]:.4f} s.')
    if args.action == 'finish':
        finish(entry,chain,result,sim,checkpoint)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('HOLD: '+str(error), file=sys.stderr)
        raise SystemExit(1)
