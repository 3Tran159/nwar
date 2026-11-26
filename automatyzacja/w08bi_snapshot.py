"""Read the GLHF W08bi export and produce a diagnostic overlay for the report."""
import csv
import hashlib
import io
import json
import zipfile

import matplotlib.pyplot as plt
import numpy as np

from analysis import health, mean_segment
from common import DATA, now, period, sha, write


SOURCE = DATA/'glhf_imports'/'w08bi_live_snapshot.zip'
FINAL_SOURCE = DATA/'glhf_imports'/'w08bi_final_snapshot.zip'


def numeric_table(bundle, name):
    with bundle.open(name) as stream:
        rows = csv.DictReader(io.TextIOWrapper(stream, encoding='utf8', newline=''))
        columns = np.array([[float(row[key]) for key in rows.fieldnames] for row in rows])
    if not len(columns) or not np.isfinite(columns).all():
        raise ValueError('W08bi export has missing or non-finite samples.')
    return dict(zip(rows.fieldnames, columns.T))


def render_snapshot(out, reference):
    source = FINAL_SOURCE if FINAL_SOURCE.is_file() else SOURCE
    if not source.is_file():
        return None
    if reference['reference_id'] != 'C01_original':
        raise ValueError('The imported W08bi comparison requires the original C01 reference.')
    with zipfile.ZipFile(source) as bundle:
        manifest = json.loads(bundle.read('manifest.json'))
        components = [(c['baseline'],c['H_m'],c['lambda_m'],c['phase_deg']) for c in manifest['components']]
        final = manifest.get('kind') == 'w08bi_final_diagnostic' and manifest.get('final') is True
        preview = manifest.get('kind') == 'w08bi_live_diagnostic_snapshot' and manifest.get('final') is False
        if (not (final or preview) or manifest.get('case_id') != 'W08' or manifest.get('dt_s') != .0004
                or components != [('W01',.5,20.,0), ('W06',1.,30.,0)]):
            raise ValueError('The file is not the expected W08bi diagnostic export.')
        if final:
            ck = manifest['checkpoint']
            record = manifest['files'][ck['path']]
            if (ck['path']!='checkpoint/W08bi_final.sim' or ck['time_s']!=manifest['time_s']
                    or ck['sha256']!=record['sha256'] or bundle.getinfo(ck['path']).file_size!=record['bytes']):
                raise ValueError('The W08bi final checkpoint inventory is inconsistent.')
            for name in ('history.csv', 'gauges.csv'):
                contents = bundle.read(name)
                if manifest['files'][name] != dict(bytes=len(contents),sha256=hashlib.sha256(contents).hexdigest()):
                    raise ValueError('W08bi exported history checksum mismatch: '+name)
        force = numeric_table(bundle, 'history.csv')
        gauges = numeric_table(bundle, 'gauges.csv')
    t = force['time_s']
    at_foil = gauges['x_m']==0
    gt, eta = gauges['time_s'][at_foil], gauges['eta_actual_m'][at_foil]
    probe_steps = np.diff(gt)
    probe_end = manifest['probe_end_s'] if final else manifest['time_s']
    gauge_cadence = np.isclose(probe_steps,.004,atol=1e-7,rtol=0)
    if final:
        for segment in manifest['segments'][1:]:
            begin = segment['begin_s']
            gauge_cadence |= ((gt[:-1]<begin-1e-7)&(gt[1:]>=begin-1e-7)&(probe_steps>0)&(probe_steps<=.004+1e-7))
    if (len(t)!=manifest['force_samples'] or len(gauges['time_s'])!=manifest['probe_samples']
            or not len(gt) or abs(t[-1]-manifest['time_s'])>1e-7 or abs(probe_end-gt[-1])>1e-7
            or not -1e-7<=t[-1]-gt[-1]<=.004+1e-7
            or not np.allclose(np.diff(t), .0004, atol=1e-7, rtol=0)
            or not gauge_cadence.all() or (final and int(force['step'][-1])!=int(ck['step']))
            or not health(force)['ok']):
        raise ValueError('W08bi endpoint, continuity, or numerical history requires review.')
    periods = [period(c[2]) for c in components]
    beat = 1/abs(1/periods[0]-1/periods[1])
    end = float(t[-1])
    start = end-3*beat
    warmup_end = t[0]+2*max(periods)+max(69.5*T/c[2] for T,c in zip(periods,components))
    if start < warmup_end:
        raise ValueError('The W08bi export needs three full beat periods after startup and propagation.')
    scale = reference['coefficient_denominator_N']
    cl = mean_segment(t, force['CL_hydrodynamic'], start, end, .0013)
    cd = mean_segment(t, force['CD_total'], start, end, .0013)
    if cl is None or cd is None:
        raise ValueError('The W08bi mean requires a continuous force history.')
    delta_cl, delta_cd = cl-reference['CL'], cd-reference['CD']
    result = dict(case='W08', display_id='W08bi', id=manifest['job_id'], time_s=end,
                  diagnostic_only=True, final=final, project_accepted=False, mean_window_s=[start,end],
                  beat_period_s=beat, beat_period_count=3, components=manifest['components'],
                  reference_id=reference['reference_id'], snapshot_sha256=sha(source),
                  captured_at=manifest['captured_at'], generated_at=now(),
                  CL_wave=cl, CD_wave=cd, L_wave_N=cl*scale, D_wave_N=cd*scale,
                  delta_CL=delta_cl, delta_CD=delta_cd, delta_L_N=delta_cl*scale, delta_D_N=delta_cd*scale,
                  lift_change_pct=100*delta_cl/reference['CL'], drag_change_pct=100*delta_cd/reference['CD'])
    fig, axes = plt.subplots(3, 1, sharex=True, figsize=(11, 7.6), layout='constrained')
    for ax, (tx, y, label, color, baseline) in zip(axes, (
        (gt, eta, 'Surface elevation at foil [m]', '#087f8c', None),
        (t, force['CL_hydrodynamic']*scale, 'Vertical force Fz [N]', '#315aa6', reference['L_N']),
        (t, force['Fx_N'], 'Horizontal force Fx [N]', '#a35e18', reference['D_N']),
    )):
        ax.axvspan(start, end, color='#eeb768', alpha=.19, label='Mean window · 3 beat periods')
        ax.plot(tx, y, color=color, lw=1.25)
        if baseline is not None:
            ax.axhline(baseline, color='#526674', ls=':', lw=1.1, label='C01')
        for segment in manifest['segments'][1:]:
            ax.axvline(segment['begin_s'], color='#526674', ls='--', lw=.9, label='Resume' if segment['index']==1 else None)
        ax.set_ylabel(label)
        ax.legend(loc='upper left', fontsize=8, ncols=3)
    axes[-1].set(xlabel='Physical time [s]', xlim=(t[0], end))
    dataset = 'final diagnostic' if final else 'snapshot'
    fig.suptitle(f'W08bi · GLHF {dataset} through {end:.3f} s\nW01 (0.50 m / 20 m) + W06 (1.00 m / 30 m)')
    for suffix in ('png','svg'):
        fig.savefig(out/f'W08bi_time_history.{suffix}')
    plt.close(fig)
    if final:
        from w08bi_qs import compare
        comparison = compare(out, reference, manifest, t, force, gt, eta, start, end)
        if comparison:
            result['quasi_steady'] = comparison
    write(out/'W08bi_snapshot.json', result)
    return result
