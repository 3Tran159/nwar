"""User-defined diagnostic waves, serialized after the pinned campaign."""
from common import *
import re

REGISTRY = HERE/'custom_waves.json'
SEQUENCE = ['W04','W05','W06','W07']


def dimensions(H, L):
    if isinstance(H, bool) or isinstance(L, bool):
        raise ValueError('Enter numeric wave height and wavelength.')
    H, L = number(H), number(L)
    if H is None or L is None or not (.25 <= H <= 1.5 and 15 <= L <= 40):
        raise ValueError('Supported range: height 0.25–1.50 m; wavelength 15–40 m.')
    return H, L


def registered():
    result = []
    for item in read(REGISTRY).get('cases', []):
        if not re.fullmatch(r'CUSTOM[0-9]{3,}', item.get('id', '')):
            raise ValueError('Invalid custom wave identifier.')
        H, L = dimensions(item.get('H'), item.get('L'))
        result.append(dict(id=item['id'], H=H, L=L))
    return result


def parameters(case_id):
    return next(((c['H'], c['L']) for c in registered() if c['id'] == case_id), None)


def register(H, L):
    H, L = dimensions(H, L)
    cases = registered()
    existing = next((c for c in cases if c['H'] == H and c['L'] == L), None)
    if existing:
        return existing['id']
    index = max([int(c['id'][6:]) for c in cases] or [0])+1
    case = dict(id=f'CUSTOM{index:03d}', H=H, L=L)
    write(REGISTRY, dict(cases=cases+[case], updated_at=now()))
    return case['id']


def catalog_entries():
    from wave_profiles import approved_profile
    scan = read(HERE/'short_wave_scan.json').get('cases', [])
    aliases = {c['case_id'] for c in scan if c.get('case_id') and c.get('queue_label')}
    hidden=set(read(HERE/'short_wave_scan.json').get('hidden_custom_case_ids',[]))
    custom = [dict(**c, title='Custom wave · five cycles; evaluate cycles 2–5',
                 T=period(c['L']), custom=True, ready=bool(approved_profile(c['id'])),
                 blocker='Requires the accepted PRE checkpoint.', existing=None,
                 scientific='diagnostic', dt=.0004) for c in registered() if c['id'] not in aliases|hidden]
    cards = []
    for item in scan:
        label = item.get('queue_label')
        if not label:
            continue
        h,l = item['height_m'],item['wavelength_m']
        authorized = label=='W04b' and item.get('launch_authorized') is True and (h,l)==(1.5,10.)
        reviewed = (item.get('launch_authorized') is True
                    and (label,h,l) in (('W04c',1.5,20.),('W04e',1.5,15.),('W04g',1.5,25.),('W04h',.75,15.),('W04k',.25,15.)))
        cards.append(dict(id=label,H=h,L=l,T=period(l),dt=.0004,existing=None,
                          title='Short-wave diagnostic · nominal forcing beyond Stokes limit' if authorized else item.get('title','Fixed-height wavelength scan'),
                          scientific='diagnostic',short_wave_diagnostic=authorized,
                          ready=bool((authorized or reviewed) and approved_profile(label)),
                          blocker=item['reason']))
    return cards+custom


def submit(H, L, request_key):
    dimensions(H, L)
    if not isinstance(request_key, str) or not 8 <= len(request_key) <= 100:
        raise ValueError('Missing request identifier.')
    # Retry of a completed HTTP request must not add a case or another job.
    previous = next((j for j in jobs() if j['request_key'] == request_key), None)
    if previous:
        if not previous['spec'].get('custom') or dimensions(H,L) != (previous['spec']['H'],previous['spec']['L']):
            raise ValueError('This request identifier belongs to different wave conditions.')
        return previous['id']
    return enqueue(register(H, L), request_key=request_key, mpi_processes=1)


def campaign_complete(campaign_id, entries, proof, sequence=SEQUENCE):
    for case in sequence:
        candidates = [j for j in entries if j['case_id']==case and j['spec'].get('campaign_id')==campaign_id and not j['spec'].get('smoke')]
        if not candidates:
            return False
        j = max(candidates, key=lambda j:j['created'])
        validation, review = proof(j)
        if not (j['status']=='completed' and validation.get('project_accepted') is True
                and validation.get('run_verification')=='passed' and review.get('health',{}).get('ok') is True
                and __import__('cycle_policy').accepted_cycles(review.get('cycles',{}))):
            return False
    return True


def release_next():
    """Called by the existing panel loop; never clears a pause or restarts a worker."""
    entries=jobs()
    pending=sorted((j for j in entries if j['status']=='deferred' and j['spec'].get('custom')),key=lambda j:j['created'])
    if not pending:
        return None
    from pre_w04 import PRE
    if any(p.exists() for p in STOPS+SOLVER_LOCKS+OTHER_LOCKS+[DATA/'PAUSE',DATA/'STOP',PRE/'STOP']):
        return None
    owner=read(DATA/'worker.lock');pre=read(PRE/'state.json')
    if any(o.get('birth') and birth(o.get('pid'))==o['birth'] for o in (owner,pre)):
        return None
    if any(j['status'] in ('queued','running','preflight','pausing') for j in entries):
        return None
    j=pending[0];wait=j['spec'].get('wait_for_campaign_id')
    def proof(entry):
        return read(DATA/'validations'/(entry['id']+'.json')),read(Path(entry['folder'])/'independent_cycle_review.json')
    if wait:
        plan=read(HERE/'campaign_followup.json')
        if plan.get('id')!=wait or not plan.get('sequence') or not campaign_complete(wait,entries,proof,plan['sequence']):
            return None
    from worker import native
    if j['spec'].get('allow_approved_cpu'):
        from cpu_coexistence import check
        try:check(launch=False)
        except (ValueError,RuntimeError):return None
    elif native():
        return None
    # Atomically promote only this one job; the serial worker performs full preflight.
    with connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        if conn.execute("SELECT 1 FROM jobs WHERE status IN ('queued','running','preflight','pausing')").fetchone():
            return None
        changed=conn.execute("UPDATE jobs SET status='queued',updated=?,message=? WHERE id=? AND status='deferred'",(now(),'Waiting for verified serial launch.',j['id'])).rowcount
    if changed:
        event('custom_wave_released',id=j['id'],case=j['case_id'],after_campaign=wait)
        return j['id']
    return None
