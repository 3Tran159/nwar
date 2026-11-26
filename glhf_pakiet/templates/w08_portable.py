"""Pinned W08bi transfer and saved-pause lineage checks for GLHF."""
from pathlib import Path

from common import DATA, HERE, job, read, sha

SEED_ID = '28cb7c64d2f04420'
SHA = '3b28035594c92910122ac30c30e8bea9fd6649ddb42cf5ae0df0824ad1c18010'
TIME = 10.600000000004671
ORIGIN = 5.8
END = ORIGIN + 19.8798073563431
REQUEST = 'glhf_w08bi_resume_' + SHA[:16]
SEED = DATA/'glhf_seed'/SEED_ID
BUDGET = 129600


def seed_spec():
    from analysis import analyze, numeric_rows
    from bichromatic import case

    proof = read(SEED/'seed.json')
    source = SEED/'checkpoint.sim'
    names = ('history.csv', 'gauges.csv', 'wave_setup_audit.json', 'bichromatic_setup.json',
             'native_C01_rho_readback.json', 'source_identity.json')
    if (proof.get('job_id') != SEED_ID or proof.get('sha256') != SHA
            or proof.get('time_s') != TIME or proof.get('step') != 12000 or sha(source) != SHA
            or any(sha(SEED/name) != proof['history_sha256'].get(name) for name in names)):
        raise ValueError('W08bi checkpoint or archived history differs from its transfer receipt.')
    result, data, _ = analyze(case(), [SEED])
    gauges = numeric_rows(SEED/'gauges.csv')
    if (not result['health']['ok'] or abs(result['time_s']-TIME) > 1e-7
            or data['step'][-1] != 12000 or abs(float(gauges['time_s'][-1])-TIME) > 1e-7):
        raise ValueError('W08bi history and checkpoint do not share a healthy endpoint.')
    return dict(source=str(source), source_sha=SHA, source_time=TIME,
                parent_segments=[str(SEED)], w08_seed=True)


def resume_policy(spec):
    profile = spec.get('mesh_profile', {})
    proof = read(SEED/'seed.json')
    if (abs(profile.get('wave_origin_s', 0)-ORIGIN) > 1e-7
            or profile.get('source_sha') != proof.get('pre_sha256')):
        raise ValueError('GLHF must use the same approved PRE wave origin as the W08bi source.')
    spec.update(stop_kind='diagnostic', extra_steps=0, budget_s=BUDGET,
                mpi_processes=1, target_complete_cycles=None,
                discard_first_cycles=0, analysis_cycle_numbers=[])


def verify_job(current):
    from analysis import analyze, segment_chain
    from bichromatic import case
    from portable_config import RELEASE

    proof = read(HERE/'bichromatic_w08.json')
    if RELEASE != '2606' or not proof.get('compiled') or sha(HERE/'NwarBichromatic.java') != proof.get('macro_sha256'):
        raise ValueError('Verified portable W08bi macro for STAR-CCM+ 2606 is required.')
    seed = seed_spec()
    seen = set()
    while True:
        spec = current['spec']
        if (current['id'] in seen or current['case_id'] != 'W08' or spec.get('mode') != 'resume'
                or spec.get('components') != case()['components'] or spec.get('stop_kind') != 'diagnostic'
                or spec.get('extra_steps') != 0 or spec.get('smoke') or spec.get('mpi_processes') != 1
                or not TIME-1e-7 <= spec['source_time'] < END):
            raise ValueError('W08bi request differs from the verified diagnostic continuation.')
        seen.add(current['id'])
        if spec.get('w08_seed'):
            if (current['request_key'] != REQUEST or spec.get('parent_id') or spec.get('parent_folder')
                    or any(spec.get(k) != v for k, v in seed.items())):
                raise ValueError('W08bi request differs from the pinned transfer checkpoint.')
            return
        parent = job(spec['parent_id'])
        folder = Path(parent['folder'])
        done, ck, integrity, stage = (read(folder/name) for name in
            ('completed.json', 'latest_checkpoint.json', 'final_integrity.json', 'stage_result.json'))
        source = folder/'wave_pilot_final.sim'
        result, _, _ = analyze(case(), segment_chain(parent))
        if (parent['status'] != 'paused' or done.get('status') != 'paused_saved'
                or stage.get('exit_code') != 0 or stage.get('source_unchanged') is not True
                or any((folder/name).exists() for name in ('macro_error.json', 'macro_error.txt'))
                or ck.get('healthy') is not True or ck.get('file') != source.name
                or not result['health']['ok'] or abs(result['time_s']-spec['source_time']) > 1e-7
                or any(item.get('time_s') != spec['source_time'] for item in (done, ck, integrity))
                or Path(spec['source']).resolve() != source.resolve()
                or integrity.get('sha256') != spec['source_sha'] or sha(source) != spec['source_sha']):
            raise ValueError('W08bi saved pause requires checkpoint review.')
        current = parent
