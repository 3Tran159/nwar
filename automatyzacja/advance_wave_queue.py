"""One heartbeat step: PRE gate -> one wave -> verified four cycles -> next wave.

Dry-run by default. --apply uses the existing serial worker. Never clears STOP,
resumes a failure, changes a solver, or initializes fields.
"""
import argparse
from common import *
from cycle_policy import accepted_cycles
from pre_w04 import PRE, calm_folders
from worker import native, OWNER
from wave_profiles import approved_profile

PLAN = HERE/'campaign_followup.json'


def choose_case(sequence, entries, proof):
    for case in sequence:
        candidates = [j for j in entries if j['case_id'] == case and not j['spec'].get('smoke')]
        if not candidates:
            return dict(status='ready', case=case)
        j = max(candidates, key=lambda v: v['created'])
        if j['status'] == 'queued':
            return dict(status='queued', case=case, job_id=j['id'])
        if j['status'] in ('running', 'preflight', 'pausing'):
            return dict(status='waiting_wave', case=case, job_id=j['id'])
        if j['status'] != 'completed':
            return dict(status='blocked', case=case, job_id=j['id'], reason=j['status'])
        validation, review = proof(j)
        if not (validation.get('project_accepted') is True
                and validation.get('run_verification') == 'passed'
                and review.get('health', {}).get('ok') is True
                and accepted_cycles(review.get('cycles', {}))):
            return dict(status='blocked', case=case, job_id=j['id'], reason='Cycles 2–5 validation not accepted')
    return dict(status='complete')


def step(apply=False):
    plan = read(PLAN)
    if plan.get('enabled') is not True:
        return dict(status='disabled')
    prepared = plan.get('reference_mode') == 'prepared_calm'
    expected = ['W01','W02','W03','W04','W05','W06','W07'] if prepared else ['W04','W05','W06','W07']
    if not prepared and plan.get('route_authorization')=='user_20261103_W04_W06_W08':expected=['W04','W06']
    if not prepared and plan.get('route_authorization')=='user_20261103_W02_W03_before_W06':expected=['W04','W02','W03','W06']
    if plan.get('sequence') != expected:
        raise ValueError('Unexpected campaign sequence')
    markers = [str(p) for p in STOPS+[DATA/'PAUSE', PRE/'STOP'] if p.exists()]
    if markers:
        return dict(status='blocked', reason='Pause/STOP preserved', markers=markers)
    pre = read(PRE/'state.json')
    if pre.get('birth') and birth(pre.get('pid')) == pre['birth']:
        return dict(status='waiting_pre', phase=pre.get('status'))
    receipt = read(PRE/'calm_receipt.json')
    if prepared:
        from calm_reference import prepared_reference
        receipt = prepared_reference(verify=True) or {}
    if not ((prepared or pre.get('status') == 'ready_for_wave') and receipt.get('passed') is True):
        return dict(status='blocked', reason='PRE W04 not accepted', phase=pre.get('status'))
    gates = receipt.get('gates', {})
    final = receipt.get('final_check', {})
    if not gates or not all(v is True for v in gates.values()) or not (final.get('consecutive_stable',0)>=2 if prepared else final.get('wave_allowed') is True):
        return dict(status='blocked', reason='Incomplete PRE evidence')
    folder = calm_folders()[-1]
    done = read(folder/'completed.json'); stage = read(folder/'stage_result.json')
    if not (done.get('status') in (('stable_reference_mismatch','calm_gate_passed') if prepared else ('calm_gate_passed',)) and stage.get('exit_code') == 0
            and stage.get('source_unchanged') is True):
        return dict(status='blocked', reason='PRE final save not clean')
    rr = tail(folder/'history.csv')
    if not rr or abs(float(rr[-1]['time_s'])-done['time_s']) > 1e-7 or abs(receipt['checkpoint_time_s']-done['time_s']) > 1e-7:
        return dict(status='blocked', reason='PRE checkpoint/history mismatch')
    entries = jobs()
    def proof(j):
        return read(DATA/'validations'/(j['id']+'.json')), read(Path(j['folder'])/'independent_cycle_review.json')
    selected = [j for j in entries if j['spec'].get('campaign_id')==plan['id']] if plan.get('scope_jobs_to_campaign') else entries
    result = choose_case(plan['sequence'], selected, proof)
    # A separately queued custom wave does not undo completion of this campaign.
    if result['status'] == 'complete':
        if plan.get('route_authorization') in ('user_20261103_W04_W06_W08','user_20261103_W02_W03_before_W06'):
            from bichromatic import followup
            return followup(plan,apply)
        return result
    worker = read(OWNER)
    if worker.get('birth') and birth(worker.get('pid')) == worker['birth']:
        return dict(status='waiting_worker')
    processes = native()
    if plan.get('allow_approved_cpu'):
        from cpu_coexistence import check
        try:check(launch=False);processes=[]
        except (ValueError,RuntimeError):pass
    locks = [str(p) for p in SOLVER_LOCKS+OTHER_LOCKS if p.exists()]
    if processes or locks:
        return dict(status='waiting_resources', processes=processes, locks=locks)
    if result['status'] not in ('ready', 'queued'):
        return result
    if any(j['case_id'] not in plan['sequence'] and j['status'] in ('queued', 'running', 'preflight', 'pausing') for j in entries):
        return dict(status='blocked', reason='Another campaign has pending work')
    topup=plan.get('route_authorization')=='user_20261103_W02_W03_before_W06' and result['case'] in ('W02','W03')
    if topup:
        source=plan.get('continuation_sources',{}).get(result['case'],{})
        if not source.get('checkpoint') or sha(Path(source['checkpoint']))!=source.get('sha256'):
            return dict(status='blocked',case=result['case'],reason='Pinned continuation source changed')
        result.update(source=source['checkpoint'],source_time_s=source['time_s'],mode='extend',extra_cycles=1)
    else:
        profile = approved_profile(result['case'], verify=True)
        if not profile:
            return dict(status='blocked', reason='Wave profile not approved', case=result['case'])
        result['source'] = profile['source']
        result['source_time_s'] = profile['source_time']
    if apply:
        from server import ensure_worker, enable_report_updates
        if result['status'] == 'ready':
            if topup:
                result['job_id']=enqueue(result['case'],'extend',extra_cycles=1,parent_id=source.get('parent_id'),request_key=plan['id']+'_'+result['case']+'_cycle5_topup',mpi_processes=1)
                requested=job(result['job_id'])['spec']
                if Path(requested['source']).resolve()!=Path(source['checkpoint']).resolve() or requested['source_sha']!=source['sha256'] or abs(requested['source_time']-source['time_s'])>1e-7:
                    update(result['job_id'],status='cancelled',message='Source did not match the explicitly pinned continuation; solver not started.')
                    raise ValueError('Continuation source selection mismatch')
            else:
                result['job_id'] = enqueue(result['case'], request_key=plan['id']+'_'+result['case'])
        enable_report_updates()
        result.update(status='dispatched', worker_pid=ensure_worker())
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    result = dict(at=now(), applied=args.apply, **step(args.apply))
    if args.apply:
        write(HERE/'qa/campaign_followup_state.json', result)
    print(json.dumps(result, ensure_ascii=False))
