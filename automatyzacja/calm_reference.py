"""Explicit immutable calm references; historical runs never silently rebase."""
from common import *

PRE = DATA/'PRE_W04_20261102'
REFERENCE_FILE = PRE/'reference_acceptance.json'
REFERENCE_ID = 'C01_PRE_W04_20261102'


def local_reference_enabled():
    plan = read(HERE/'campaign_followup.json')
    return plan.get('reference_mode') == 'prepared_calm' and plan.get('reference_id') == REFERENCE_ID


def prepared_reference(verify=False):
    receipt = read(REFERENCE_FILE)
    if not receipt.get('passed') or receipt.get('reference_id') != REFERENCE_ID:
        return None
    if verify:
        if sha(Path(receipt['checkpoint'])) != receipt['checkpoint_sha256']:
            raise ValueError('Frozen new C01 checkpoint changed')
        if sha(SOURCE) != SOURCE_SHA:
            raise ValueError('Archived original C01 changed')
    return receipt


def reference_for(entry=None, verify=False):
    spec = (entry or {}).get('spec', {})
    ref_id = spec.get('reference_id') or spec.get('mesh_profile', {}).get('reference_id')
    if ref_id:
        receipt = prepared_reference(verify)
        if ref_id != REFERENCE_ID or receipt is None:
            raise ValueError('The run calm reference is unavailable')
        return receipt
    receipt = read(CALM/'C01_final_acceptance_20261101.json')
    return dict(receipt, reference_id='C01_original', name='C01 (original)')


def force_reference_for(entry=None, verify=False):
    receipt = reference_for(entry, verify)
    if not receipt.get('project_primary_settled'):
        raise ValueError('Calm reference has not been accepted')
    cl = number(receipt.get('normalized_CL_hydro')); cd = number(receipt.get('normalized_CD_total'))
    if cl is None or cd is None:
        raise ValueError('Missing accepted calm coefficients')
    return dict(name=receipt['name'], reference_id=receipt['reference_id'], CL=cl, CD=cd,
                L_N=cl*3855.6, D_N=cd*3855.6, coefficient_denominator_N=3855.6,
                checkpoint_sha256=receipt['checkpoint_sha256'], lift_convention='hydrodynamic_lift_v1')


def active_force_reference():
    entry = dict(spec=dict(reference_id=REFERENCE_ID)) if local_reference_enabled() and prepared_reference() else None
    return force_reference_for(entry)


def accept_prepared_reference():
    """Promote only a clean, twice-stable saved PRE, with independent checks."""
    night = read(HERE/'night_campaign.json')
    night_allowed = (night.get('enabled') is True and night.get('fallback_at') and
                     datetime.now().astimezone() >= datetime.fromisoformat(night['fallback_at']))
    if not local_reference_enabled() and not night_allowed:
        raise ValueError('Local calm reference is not authorized')
    if REFERENCE_FILE.exists():
        receipt = prepared_reference(verify=True)
        if receipt is None:
            raise ValueError('Existing reference receipt requires review; never overwrite it')
        return receipt
    from pre_w04 import calm_folders, calm_values, endpoint_convergence
    from pre_balance import balance_seed, water_readiness
    from prepare_w04_geometry import OUT
    state = read(PRE/'state.json')
    if state.get('birth') and birth(state.get('pid')) == state['birth']:
        return dict(passed=False, pending='PRE controller still active')
    folders = calm_folders(); folder = folders[-1]; process = read(folder/'process.json')
    if birth(process.get('pid')):
        return dict(passed=False, pending='PRE solver still exiting')
    markers = [p for p in STOPS+[PRE/'STOP', DATA/'PAUSE', folder/'STOP'] if p.exists()]
    if markers:
        raise ValueError('Pause/STOP preserved: '+str(markers))
    done = read(folder/'completed.json'); stage = read(folder/'stage_result.json')
    if done.get('status') not in ('stable_reference_mismatch', 'calm_gate_passed'):
        raise ValueError('PRE has not completed the two stability checks')
    values = calm_values(); checks = endpoint_convergence(values)
    last = checks[-1] if checks else {}
    native = read(folder/'settling_check.json')
    removed = read(folder/'global_ramp_completed.json')
    balance = balance_seed(folders); water = water_readiness(folders, balance)
    geometry = read(OUT/'geometry_receipt.json'); protected = read(OUT/'protected_receipt.json')
    checkpoint = folder/'final.sim'; latest = read(folder/'latest_checkpoint.json')
    scenes = read(folder/'scene_retention.json')
    gates = dict(
        independent_stability=last.get('consecutive_stable', 0) >= 2 and last.get('stable') is True and last.get('eligible') is True,
        native_stability=native.get('pass') is True and native.get('consecutive_passes', 0) >= 2 and abs(native.get('time_s',-1)-done['time_s']) < 1e-7,
        clean_solver_exit=stage.get('exit_code') == 0 and stage.get('source_unchanged') is True and not read(folder/'macro_error.json'),
        checkpoint_saved=checkpoint.is_file() and checkpoint.stat().st_size > 400_000_000,
        endpoint=bool(len(values)) and abs(float(values[-1,0])-done['time_s']) < 1e-7 and abs(last.get('time_s',-1)-done['time_s']) < 1e-7 and abs(latest.get('time_s',-1)-done['time_s']) < 1e-7 and Path(latest.get('path','')).resolve() == checkpoint.resolve(),
        water_ready=water['ready'], water_balance=abs(balance['water_closure_error_m3']) < .25,
        startup_momentum_source_removed=removed.get('momentum_source_option') == 'NONE' and removed.get('extra_force_active') is False,
        original_C01_preserved=sha(SOURCE) == SOURCE_SHA,
        geometry=geometry.get('passed') is True and protected.get('passed') is True and geometry.get('cells') == 572176 and geometry.get('mesh_sha256') == protected.get('mesh_sha256') == sha(OUT/'geometry/mesh.CGNS'),
        scenes_preserved=scenes.get('preserved') is True and scenes.get('scene_count',0) >= 30)
    if not all(gates.values()):
        raise ValueError('New C01 acceptance failed: '+str([k for k,v in gates.items() if not v]))
    from pre_lineage import prepared_lineage
    _, lineage_ok, links = prepared_lineage(dict(initialization='whole_domain_momentum_ramp',gates=gates), folders)
    if not lineage_ok:
        raise ValueError('PRE checkpoint provenance failed')
    receipt = dict(passed=True, project_primary_settled=True, at=now(), reference_id=REFERENCE_ID,
        name='C01 (PRE W04)', reference_policy='Stable expanded-domain calm; original C01 comparison is diagnostic only, per user instruction.',
        checkpoint=str(checkpoint), checkpoint_sha256=sha(checkpoint), checkpoint_time_s=done['time_s'],physical_time_s=done['time_s'],
        normalized_CL_hydro=last['CL_mean'], normalized_CD_total=last['CD_mean'], reference_window_s=.2,
        reference_window_s_bounds=[done['time_s']-.2,done['time_s']], lift_convention='hydrodynamic_lift_v1',
        gates=gates, final_check=last, independent_endpoint_checks=checks, native_check=native, completed=done, balance=balance, water_readiness=water,
        original_C01=str(SOURCE),original_C01_sha256=SOURCE_SHA, original_C01_comparison_passed=last.get('compatible',False),
        cells=geometry['cells'],mesh_sha256=geometry['mesh_sha256'],initialization='whole_domain_momentum_ramp',
        history_folders=list(map(str,folders)),source_links=links,scenes=scenes,
        history_sha256={str(p/'history.csv'):sha(p/'history.csv') for p in folders})
    write(REFERENCE_FILE, receipt)
    return receipt


if __name__ == '__main__':
    result = accept_prepared_reference()
    print(json.dumps({k:result.get(k) for k in ('passed','pending','reference_id','checkpoint','checkpoint_time_s','normalized_CL_hydro','normalized_CD_total')},ensure_ascii=False))
