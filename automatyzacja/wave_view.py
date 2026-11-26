"""Read-only interactive wave views. Uses the report's measured phase and lineage."""
from common import *
from analysis import analyze, cycles, numeric_rows, exact_segment
from cycle_policy import accepted_cycles, POLICY_ID
from history_view import run_chain, envelope_indices
from phase_alignment import align_to_position
from calm_reference import force_reference_for
from report_selection import active_entries
import numpy as np
import statistics

_CACHE = {}
_LOCK = threading.RLock()


def first_cycle_progress(data, gauge, phase, L, origin, distance, timing=None):
    """Display estimate only. Completion comes exclusively from measured cycles()."""
    T = period(L); current = float(data['time_s'][-1]); eligible = origin+2*T+distance*T/L
    out = dict(percent=0., state='waiting_start', current_time_s=current, eligible_time_s=eligible,
               period_s=T, cycle_start_s=None, target_time_s=None, remaining_physical_s=None,
               eta_wall_s=None, eta_range_wall_s=None, estimated=True, complete=False)
    if phase.get('count', 0):
        first = phase['cycles'][0]
        return dict(out, percent=100., state='complete', complete=True, estimated=False,
                    cycle_start_s=first['start'], target_time_s=first['end'], remaining_physical_s=0.)
    if phase.get('error'):
        return dict(out, state='unavailable', reason=phase['error'])
    valid = gauge[(gauge[:, 0]>=eligible)&np.isfinite(gauge).all(axis=1)]
    level = phase.get('phase_level'); crossings = []
    if level is not None:
        for a, b in zip(valid[:-1], valid[1:]):
            if a[1] <= level < b[1]:
                t = float(a[0]+(level-a[1])*(b[0]-a[0])/(b[1]-a[1]))
                if not crossings or t-crossings[-1] > .5*T:
                    crossings.append(t)
    if crossings:
        start = crossings[-1]; target = start+T
        out.update(cycle_start_s=start, target_time_s=target, percent=min(99., max(0.,100*(current-start)/T)),
                   state='recording' if current<target else 'awaiting_crossing')
        if current < target:
            out['remaining_physical_s'] = target-current
    else:
        out.update(state='startup' if current<eligible else 'waiting_start',
                   target_time_s=max(current,eligible)+1.5*T,
                   remaining_physical_s=max(0.,eligible-current)+1.5*T)
    timing = timing or {}
    out['timing_available'] = timing.get('available', False)
    if timing.get('available') and out['remaining_physical_s'] is not None:
        remaining=out['remaining_physical_s']
        out['eta_wall_s']=remaining*timing['wall_s_per_physical_s']
        out['eta_range_wall_s']=[remaining*x for x in timing['rate_range']]
    return out


def next_cycle_progress(data, gauge, phase, L, origin, distance, timing=None, active=True):
    """Rolling display target; the measured acceptance counter is never changed."""
    count = phase.get('count', 0)
    if count>=5:
        last=phase['cycles'][4]
        return dict(first_cycle_progress(data,gauge,phase,L,origin,distance),
                    state='saving' if active else 'saved',cycle_number=5,completed_cycles=count,
                    cycle_start_s=last['start'],target_time_s=last['end'])
    if not active and count:
        last = phase['cycles'][-1]
        return dict(first_cycle_progress(data, gauge, phase, L, origin, distance),
                    state='saved', cycle_number=count, completed_cycles=count,
                    cycle_start_s=last['start'], target_time_s=last['end'])
    # Reuse the same eligible probe crossings as the first-cycle display.
    out = first_cycle_progress(data, gauge, dict(phase, count=0), L, origin, distance, timing)
    out.update(cycle_number=count+1, completed_cycles=count)
    measured = phase.get('period_measured_s')
    estimated_period = float(measured) if measured and math.isfinite(measured) and measured>0 else period(L)
    out.update(period_s=estimated_period, period_basis='measured_cycles' if measured else 'configured_wave')
    start = out['cycle_start_s']
    if start is not None:
        target = start+estimated_period; current = out['current_time_s']
        out.update(target_time_s=target, percent=min(99., max(0.,100*(current-start)/estimated_period)),
                   state='recording' if current<target else 'awaiting_crossing',
                   remaining_physical_s=target-current if current<target else None,
                   eta_wall_s=None, eta_range_wall_s=None)
        if (timing or {}).get('available') and current<target:
            out['eta_wall_s']=(target-current)*timing['wall_s_per_physical_s']
            out['eta_range_wall_s']=[(target-current)*rate for rate in timing['rate_range']]
    return out


def partial_force_cycle(data, gauge, progress):
    """Recorded forces only; the open cycle's phase denominator is provisional."""
    start=progress.get('cycle_start_s');T=progress.get('period_s')
    if progress.get('complete') or progress.get('state') not in ('recording','awaiting_crossing') or start is None or not T or not len(gauge):
        return None
    end=min(float(data['time_s'][-1]),float(gauge[-1,0]))
    if end<=start+1e-9:return None
    lift=exact_segment(data['time_s'],data['CL_hydrodynamic'],start,end,.0013)
    drag=exact_segment(data['time_s'],data['CD_total'],start,end,.0013)
    surface=exact_segment(gauge[:,0],gauge[:,1],start,end,.012)
    if lift is None or drag is None or surface is None:return None
    values=np.column_stack((lift[0],lift[1],drag[1]))
    indices=envelope_indices(values,budget=500)
    sample=values[indices]
    return dict(number=progress['cycle_number'],start=start,end=end,estimated_end=start+T,T=T,
                complete=False,provisional=True,phase_estimated=True,
                phase=((sample[:,0]-start)/T).tolist(),time_s=sample[:,0].tolist(),
                CL=sample[:,1].tolist(),CD=sample[:,2].tolist())


def recent_timing(entry, folder, healthy):
    path=Path(folder)/'history.csv'; history=tail(path)[-300:]; rates=[]
    for a,b in zip(history[:-1],history[1:]):
        ta,tb,wa,wb=[number(v) for v in (a.get('time_s'),b.get('time_s'),a.get('wall_s'),b.get('wall_s'))]
        if None not in (ta,tb,wa,wb) and tb>ta and wb>wa:
            rates.append((wb-wa)/(tb-ta))
    fresh=path.exists() and time.time()-path.stat().st_mtime<180
    alive=bool(entry.get('controller_pid') and birth(entry['controller_pid'])==entry.get('controller_birth'))
    available=entry['status']=='running' and fresh and alive and healthy and len(rates)>=20
    return dict(available=available,wall_s_per_physical_s=statistics.median(rates) if rates else None,
                rate_range=np.percentile(rates,[25,75]).tolist() if rates else None)


def first_wave_arrival(current, gauge, components, origin, distance, timing):
    """Estimate inlet-to-foil travel, then look for a sustained local signal."""
    wavelengths = [float(c['lambda_m']) for c in components]
    fastest = min(wavelengths, key=lambda length: period(length)/length)
    travel = distance*period(fastest)/fastest
    target = origin+travel
    remaining = max(0., target-current)
    detected = None
    gauge = gauge[np.isfinite(gauge).all(axis=1)]
    shortest_period = min(map(period, wavelengths))
    baseline = gauge[(gauge[:, 0]>=origin-1e-8) & (gauge[:, 0]<=origin+.25*shortest_period), 1]
    if len(baseline)>=12:
        level = np.median(baseline)
        threshold = max(.05, 6*np.median(np.abs(baseline-level)))
        start = previous = None
        for t, eta in gauge[gauge[:, 0]>=target-.25*shortest_period]:
            if previous is not None and t-previous>.012:
                start = None
            previous = t
            if abs(eta-level)<threshold:
                start = None
                continue
            if start is None:
                start = t
            if t-start>=.08:
                detected = float(start)
                break
    return dict(current_time_s=current, target_time_s=target, detected_time_s=detected,
                percent=100. if detected is not None else min(99., max(0., 100*(current-origin)/travel)),
                eta_wall_s=remaining*timing['wall_s_per_physical_s']
                if timing['available'] and remaining>0 and detected is None else None)


def next_bichromatic_wave(current, gauge, detected, components, timing):
    """Display-only crest forecast from the composite signal at the foil."""
    if detected is None:
        return None
    from scipy.signal import find_peaks
    periods = [period(c['lambda_m']) for c in components]
    shortest, longest = min(periods), max(periods)
    samples = gauge[(gauge[:, 0]>=detected-.25*shortest) & np.isfinite(gauge).all(axis=1)]
    crests = []
    for segment in np.split(samples, np.flatnonzero(np.diff(samples[:, 0])>.012)+1):
        if len(segment)<3:
            continue
        spacing = np.median(np.diff(segment[:, 0]))
        peaks, _ = find_peaks(segment[:, 1], prominence=.03, distance=max(1, .4*shortest/spacing))
        crests.extend(float(t) for t in segment[peaks, 0])
    recent = [gap for gap in np.diff(crests[-4:]) if .5*shortest<=gap<=1.5*longest]
    interval = float(statistics.median(recent)) if recent else shortest
    start = crests[-1] if crests else detected
    target = start+interval
    remaining = max(0., target-current)
    return dict(target_time_s=target, last_crest_s=crests[-1] if crests else None,
                from_measured_spacing=bool(recent), awaiting_crest=not remaining,
                percent=min(99., max(0., 100*(current-start)/interval)),
                eta_wall_s=remaining*timing['wall_s_per_physical_s']
                if timing['available'] and remaining>0 else None)


def select_source(case_id, entries, results):
    candidates = [j for j in entries if j['case_id'] == case_id and not j.get('spec', {}).get('smoke')
                  and j['status'] not in ('queued', 'deferred', 'cancelled', 'preflight_blocked')]
    active = next((j for j in candidates if j['status'] in ('running', 'preflight', 'pausing')), None)
    if active:
        return active, run_chain(active), read(DATA/'validations'/(active['id']+'.json')).get('project_accepted', False)
    saved = [r for r in results if r.get('case') == case_id and r.get('source_segments') and 'error' not in r]
    options = []
    for r in saved:
        entry = next((j for j in candidates if j['id'] == r['id']), dict(id=r['id'], case_id=case_id, status='saved', spec={}))
        options.append((r.get('time_s') or 0, entry, [Path(s['path']).parent for s in r['source_segments']], r.get('project_accepted', False)))
    # An ancestor's abandoned failure tail must not replace its current continuation.
    histories = [(j, tail(Path(j['folder'])/'history.csv')) for j in candidates]
    parents = {j.get('spec', {}).get('parent_id') for j, history in histories if history}
    for j, history in histories:
        if j['id'] in parents:
            continue
        if history:
            validation = j.get('validation') if j.get('imported') else read(DATA/'validations'/(j['id']+'.json'))
            options.append((number(history[-1].get('time_s')) or 0, j, run_chain(j), (validation or {}).get('project_accepted', False)))
    if not options:
        return None, [], False
    _, entry, folders, accepted = max(options, key=lambda item: item[0])
    return entry, folders, accepted


def probe_points(values, budget=1400):
    """Keep extrema and visibly break every missing/invalid interval; never fill gaps."""
    if not len(values):
        return []
    pieces, start = [], 0
    for i in range(1, len(values)):
        if not np.isfinite(values[i-1:i+1]).all() or values[i, 0]-values[i-1, 0] > .012:
            pieces.append(values[start:i]); start = i
    pieces.append(values[start:])
    result = []
    for part in pieces:
        part = part[np.isfinite(part).all(axis=1)]
        if not len(part):
            continue
        # The shared sampler expects two signal columns; the duplicate preserves eta extrema.
        indices = envelope_indices(np.column_stack((part, part[:, 1])), budget=max(20, int(budget*len(part)/len(values))))
        if result:
            result.append(None)
        result.extend(part[indices].tolist())
    return result


def build_view(case, entry, folders, accepted):
    result, data, _ = analyze(case, folders)
    display = case.get('display_id',case['id'])
    label = dict(display_id=display+' · GLHF' if entry.get('imported') else display,
                 condition_label=case.get('condition_label'), diagnostic_only=bool(case.get('diagnostic_only')))
    if not data:
        return dict(label,case_id=case['id'], run_id=entry['id'], status=entry['status'], empty=True, message='Waiting for recorded wave samples.')
    reference, alignment = align_to_position(folders, result['cycles']['phase_probe_x_m'], result, require_full_history=True)
    phase = cycles(data, reference, case['H'], case['L'], origin=result['wave_origin_s'], probe_distance=result['probe_distance_m']+.5)
    if case.get('wave_kind')=='bichromatic':phase=result['cycles']
    timing=recent_timing(entry,folders[-1],result['health']['ok'])
    progress=next_cycle_progress(data,reference,phase,case['L'],result['wave_origin_s'],result['probe_distance_m']+.5,
                                 timing,active=entry['status'] in ('running','preflight','pausing'))
    partial=partial_force_cycle(data,reference,progress)
    if partial is None and progress['cycle_start_s'] is not None and progress['state'] in ('recording','awaiting_crossing') and data['time_s'][-1]>progress['cycle_start_s']+.012:
        progress.update(state='unavailable',reason='Waiting for continuous force and probe samples in the open cycle.',eta_wall_s=None,eta_range_wall_s=None)
    probes = {}
    for folder in folders:
        samples = numeric_rows(Path(folder)/'gauges.csv')
        if not samples or not all(k in samples for k in ('x_m', 'time_s', 'eta_actual_m')):
            continue
        for x in np.unique(samples['x_m'][np.isfinite(samples['x_m'])]):
            mask = np.isclose(samples['x_m'], x)
            values = np.column_stack((samples['time_s'][mask], samples['eta_actual_m'][mask]))
            values = values[(values[:, 0] >= data['time_s'][0]-1e-8) & (values[:, 0] <= data['time_s'][-1]+1e-8)]
            prior = probes.get(float(x))
            if prior is not None and len(prior):
                values = values[values[:, 0] > prior[-1, 0]+1e-8]
                values = np.concatenate((prior, values))
            probes[float(x)] = values
    arrival = (first_wave_arrival(float(data['time_s'][-1]), probes.get(0., np.empty((0, 2))),
                                  case['components'], result['wave_origin_s'], result['probe_distance_m']+.5, timing)
               if case.get('wave_kind')=='bichromatic' else None)
    next_wave = (next_bichromatic_wave(arrival['current_time_s'], probes.get(0., np.empty((0, 2))),
                                       arrival['detected_time_s'], case['components'], timing)
                 if arrival else None)
    markers = []
    for folder in folders[1:]:
        first = numeric_rows(Path(folder)/'history.csv').get('time_s', [])
        if len(first):
            markers.append(float(first[0]))
    return dict(label,case_id=case['id'],
                verified_import_checkpoint_s=entry.get('import_checkpoint_time_s'),
                run_id=entry['id'], status=entry['status'], sampled_at=now(), time_s=result['time_s'], H_m=case['H'],
                wavelength_m=case['L'], period_s=period(case['L']), project_accepted=bool(accepted and accepted_cycles(result['cycles'])),
                force_reference=force_reference_for(entry), alignment=alignment, phase_reference_x_m=0.,
                cycle_count=phase['count'], cycles=phase['analyzed_cycles'], excluded_cycles=phase['cycles'][:1], analyzed_cycle_count=phase['analyzed_count'], cycle_policy_id=POLICY_ID, target_complete_cycles=5, analysis_not_before_s=phase.get('analysis_not_before_s'),
                cycle_error=phase.get('error'), health_ok=result['health']['ok'],
                cycle_progress=progress,in_progress_cycle=partial,
                first_wave_arrival=arrival,
                next_wave=next_wave,
                first_cycle_progress=first_cycle_progress(data,reference,phase,case['L'],result['wave_origin_s'],result['probe_distance_m']+.5,timing),
                probes=[dict(x_m=x, points=probe_points(values), samples=len(values)) for x, values in sorted(probes.items())],
                resume_markers=markers, source_folders=list(map(str, folders)))


def wave_view(case_id, external=()):
    case = next((c for c in catalog() if c['id'] == case_id), None)
    if case is None:
        raise ValueError('Unknown wave case')
    with _LOCK:
        cached = _CACHE.get(case_id)
        if cached and time.monotonic()-cached[0] < 8:
            return cached[1]
        latest = read(HERE/'latest_report.json')
        results = read(Path(latest['directory'])/'audit.json').get('results', []) if latest else []
        entry, folders, accepted = select_source(case_id, active_entries(jobs()+list(external)), results)
        if folders and case.get('diagnostic_only'):
            case=dict(case,**{k:entry['spec'][k] for k in ('components','condition_label') if k in entry.get('spec',{})})
        payload = build_view(case, entry, folders, accepted) if folders else dict(case_id=case_id,display_id=case.get('display_id',case_id),condition_label=case.get('condition_label'),diagnostic_only=bool(case.get('diagnostic_only')),empty=True,message='This wave has no recorded samples yet.')
        _CACHE[case_id] = (time.monotonic(), payload)
        return payload
