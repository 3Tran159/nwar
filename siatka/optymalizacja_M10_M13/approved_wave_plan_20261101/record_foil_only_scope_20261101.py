"""Record user's foil-only scope clarification. Metadata only; never launch CFD."""
from pathlib import Path
from datetime import datetime
import hashlib, json, os, uuid
R = Path(r'E:\ntnu_mesh_optimization_20261030')
A = R / 'approved_wave_plan_20261101'
expected = {
    R/'plan.json': 'd35c065508fcb46c6b6ac8ef8a5111efb8115b595876e41930de79fd3bd84da7',
    A/'stage_state.json': 'c7efe91ba7aac55d2400eb47361f25b763d8e60d1ab6c538d3b7c4beac4ee49c',
    A/'HANDOFF.md': 'b0723253ab5b4ff9de5b3dd9a987e175226b81bf22e229c4ceb7eca596b63742'
}
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))
now = datetime.now().astimezone()
token = uuid.uuid4().hex
lock = A/'scope_update.lock'
with lock.open('x', encoding='utf-8') as fh:
    json.dump({'pid': os.getpid(), 'at': now.isoformat(), 'token': token, 'role': 'metadata_scope_update_no_solver'}, fh)
changed = []
try:
    conflicts = [R/'m13_wave_gpu.lock', R/'recovery.lock', A/'implementation.lock', A/'forcing_audit.lock', A/'sensitivity.lock', R/'wave_surface_only/wave_inlet.lock', R/'parallel_cpu_20261031/auxiliary.lock']
    assert not any(p.exists() for p in conflicts), 'Another owner holds a stage lock; do not update concurrently'
    for p, digest in expected.items():
        assert sha(p) == digest, 'Metadata changed concurrently: ' + str(p)
    state, plan = read(A/'stage_state.json'), read(R/'plan.json')
    assert not state.get('implementation_in_progress'), 'Implementation in progress'
    assert sha(R/'AUTONOMOUS_RECOVERY_PROMPT.md') == plan['recovery_policy']['runbook_sha256']
    proofdir = R/'M13_wave_direct_20261031/M13_GPU_W20_H050_continuation_R4V_20261101'
    receipt, completed = read(proofdir/'stage_result.json'), read(proofdir/'completed.json')
    assert receipt['exit_code'] == 0 and receipt['source_unchanged'] is True
    assert completed['steps'] == 12000 and abs(completed['time_s'] - 13.9792) < 1e-7
    assert (proofdir/'wave_pilot_final.sim').is_file()
    event = {
        'recorded_at': now.isoformat(),
        'user_instruction': 'same testy siatek z fala tylko odpuszczamy, bedizemy jechac od razu te z platem, juz w01 poszlo z tego co wisze w nocy',
        'standalone_wave_only_mesh_tests_authorized': False,
        'standalone_wave_only_validation_prerequisite': False,
        'validation_scope': 'Existing M13 with foil: calm-wave comparability and forcing audit, matched dt sensitivity, then selected H/lambda cases',
        'W01_physical_condition': {'foil': True, 'H_m': 0.5, 'lambda_m': 20, 'cells': 309441, 'last_saved_time_s': completed['time_s'], 'path': str(proofdir), 'scientifically_validated': False},
        'legacy_C01_W01_queue_released': False,
        'current_forcing_review_gate_unchanged': True,
        'next_new_wave_conditions': [{'H_m': 0.25, 'lambda_m': 20}, {'H_m': 0.5, 'lambda_m': 30}],
        'source_results_untouched': True,
        'solver_started': False
    }
    plan['approved_wave_followup_20261101']['foil_only_scope_clarification'] = event
    plan['updated_at'] = now.isoformat()
    state['scope_clarified_at'] = now.isoformat()
    state['standalone_wave_only_mesh_tests_authorized'] = False
    state['standalone_wave_only_validation_prerequisite'] = False
    state['validation_scope'] = event['validation_scope']
    text = (A/'HANDOFF.md').read_text(encoding='utf-8-sig')
    addition = '\n## Latest user scope clarification: foil-only, ' + now.isoformat() + '\n\nStandalone wave-only mesh/propagation trials are DISCONTINUED, not a prerequisite to any further M13 work. Preserve their historical evidence. All further audits and approved dt/BC sensitivity tests concern the actual M13 FOIL case and its matched calm reference. The overnight H=0.5 m, lambda=20 m condition already ran and saved through R2/R3V/R4V to t=13.9792 s; do not restart it as an unrun W01. This condition is separate from the held legacy F: W01 queue. Preserve the current forcing/comparability gate and exploratory scientific status. After those checks, next conditions remain H=0.25 m/lambda=20 m, then H=0.5 m/lambda=30 m. No solver, active macro, source simulation, raw history, receipt or retry budget is changed by this clarification.\n'
    header, rest = text.split('\n', 1)
    revised = header + '\n' + addition + '\n' + rest
    backup = A/'backup'/('foil_only_scope_' + now.strftime('%Y%m%d_%H%M%S') + '_' + token[:6])
    backup.mkdir(parents=True, exist_ok=False)
    payloads = {R/'plan.json': json.dumps(plan, ensure_ascii=False, indent=2) + '\n', A/'stage_state.json': json.dumps(state, ensure_ascii=False, indent=2) + '\n', A/'HANDOFF.md': revised}
    for p, data in payloads.items():
        assert sha(p) == expected[p], 'Concurrent modification before commit: ' + str(p)
        (backup/p.name).write_bytes(p.read_bytes())
        tmp = p.with_name(p.name + '.' + token + '.tmp')
        with tmp.open('x', encoding='utf-8') as fh:
            fh.write(data)
        assert sha(p) == expected[p], 'Concurrent modification during staging: ' + str(p)
        os.replace(tmp, p)
        changed.append(str(p))
    (backup/'scope_decision.json').write_text(json.dumps(event, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    with (R/'decisions.jsonl').open('a', encoding='utf-8') as fh:
        fh.write(json.dumps(dict(event, event='user_discontinues_standalone_wave_only_trials', changed_metadata=changed, backup=str(backup)), ensure_ascii=False) + '\n')
    print(json.dumps({'scope_update': 'verified', 'changed_metadata': changed, 'wave_only_trials': 'discontinued', 'original_forcing_gate_unchanged': read(A/'stage_state.json')['forcing_review_ready_for_matched_sensitivity'] is False, 'solver_started': False, 'backup': str(backup)}, ensure_ascii=False))
finally:
    if lock.exists() and read(lock).get('token') == token:
        lock.unlink()
