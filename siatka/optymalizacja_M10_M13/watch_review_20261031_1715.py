from pathlib import Path
from collections import defaultdict
import csv, json, math, statistics, hashlib, html
from datetime import datetime
R = Path(r'E:\ntnu_mesh_optimization_20261030')
W = R / 'wave_surface_only'
dest = R / 'watch_review_20261031_1715'
plan = json.loads((R/'plan.json').read_text(encoding='utf-8'))
runbook_sha = hashlib.sha256((R/'AUTONOMOUS_RECOVERY_PROMPT.md').read_bytes()).hexdigest()
assert runbook_sha == plan['recovery_policy']['runbook_sha256'], 'RUNBOOK HASH MISMATCH'
dest.mkdir(exist_ok=True)
srcs = [
W/'zero_start_matrix_R2_coarse_continuation_20261031_3/waves/L20_H500_coarse/gauges.csv',
W/'zero_start_matrix_R2_coarse_continuation_20261031_4/waves/L20_H500_coarse/gauges.csv',
W/'wave_cpu1_resource_pilot_20261031_1603/waves/L20_H500_coarse_CPU1/gauges.csv'
]
by_station = defaultdict(dict)
actual_sources = []
for p in srcs:
    if not p.is_file(): continue
    actual_sources.append(str(p))
    with p.open(encoding='utf-8-sig', newline='') as f:
        for a in csv.DictReader(f):
            try:
                t=float(a['time_s']); x=float(a['x_m']); eta=float(a['eta_actual_m'])
                if math.isfinite(t) and math.isfinite(x) and math.isfinite(eta):
                    by_station[x][round(t,6)] = eta
            except (ValueError, KeyError): pass
T = 0.8472673206891129
last = max((max(s) for s in by_station.values() if s), default=float('nan'))
cutoff = last - 2*T
stats=[]
for x,d in sorted(by_station.items()):
    pts=sorted(d.items())
    recent=[z for t,z in pts if t >= cutoff]
    if recent:
        stats.append({'x_m':x,'samples_total':len(pts),'samples_last_two_periods':len(recent),
        'time_first_s':pts[0][0],'time_last_s':pts[-1][0],
        'minimum_eta_m':min(recent),'maximum_eta_m':max(recent),
        'observed_peak_to_peak_m':max(recent)-min(recent),
        'observed_half_range_m':(max(recent)-min(recent))/2,
        'nominal_H_m':0.5,'is_downstream_damping_zone':x>=40})
m10dir=R/'M10_W01a_GPU_queue_20261031_165802_aef11e'
m10 = json.loads((m10dir/'progress.json').read_text()) if (m10dir/'progress.json').is_file() else None
settle = json.loads((m10dir/'settling_check.json').read_text()) if (m10dir/'settling_check.json').is_file() else None
r4dir = W/'zero_start_matrix_R2_coarse_continuation_20261031_4/waves/L20_H500_coarse'
r4 = json.loads((r4dir/'stage_result.json').read_text())
cpu1 = json.loads((W/'wave_cpu1_resource_pilot_20261031_1603/pilot_result.json').read_text())
summary={
 'at_local':datetime.now().astimezone().isoformat(), 'runbook_sha_verified':True,
 'wave_nofoil':{'case':'lambda20_H0.5_coarse','R4_result':r4,
 'CPU1_resource_pilot':cpu1,'wave_gauge_sources':actual_sources,
 'window_last_two_nominal_periods_s':[cutoff,last], 'nominal_T_s':T,
 'gauge_stats':stats,'scientific_gate':'NOT ACCEPTED: no matched baseline/fine, residual/monitor warning, limited downstream signal'},
 'foil_mesh':{'M10_exploratory':m10, 'M10_last_settling':settle,
 'M11':{'project_primary_two_passes_at_s':[3.190999999999714,3.390999999999692],
 'saved_t_s':3.3935999999996915, 'dt_s':0.0002,'not_final_cross_mesh_or_timestep_validation':True},
 'M12':{'saved_t_s':3.3314,'not_restarted_after_noon':True}},
 'action':'Read-only CFD inspection; no solver start, pause, stop, lock edit or source modification'
}
(dest/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False),encoding='utf-8')
with (dest/'gauge_stats.csv').open('w',encoding='utf-8',newline='') as f:
    if stats:
        w=csv.DictWriter(f,fieldnames=list(stats[0])); w.writeheader();w.writerows(stats)
# SVG: measured traces, only 4 representative non-damping gauges
shown=[x for x in (-34.0,0.0,10.0,20.0) if x in by_station]
xmin = max(min(t for d in by_station.values() for t in d),last - 2.2) if by_station else 0
xmax = last if by_station else 1
width,height=950,400
left,right,top,bottom=65,25,30,45
palette=['#177e89','#c94f50','#7555b2','#9b7728']
def xx(t):return left+(t-xmin)/(xmax-xmin)*(width-left-right)
def yy(y):return top+(0.35-y)/0.70*(height-top-bottom)
s=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
 '<rect width="100%" height="100%" fill="#ffffff"/>']
for y in (-.3,-.2,-.1,0,.1,.2,.3):
    py=yy(y)
    s += [f'<line x1="{left}" y1="{py:.1f}" x2="{width-right}" y2="{py:.1f}" stroke="#e5e9ed"/>',
          f'<text x="8" y="{py+4:.1f}" font-size="12" fill="#445">{y:.1f}</text>']
for j in range(6):
    t=xmin+j*(xmax-xmin)/5
    px=xx(t)
    s += [f'<line x1="{px:.1f}" y1="{top}" x2="{px:.1f}" y2="{height-bottom}" stroke="#edf0f2"/>',
          f'<text x="{px-16:.1f}" y="{height-18}" font-size="12" fill="#445">{t:.2f}</text>']
for k,x in enumerate(shown):
    d=sorted((t,y) for t,y in by_station[x].items() if t>=xmin)
    if not d:continue
    pts=' '.join(f'{xx(t):.2f},{yy(y):.2f}' for t,y in d)
    s.append(f'<polyline points="{pts}" fill="none" stroke="{palette[k]}" stroke-width="1.3"/>')
    s.append(f'<text x="{left+180*k}" y="18" font-size="13" fill="{palette[k]}">x={x:g} m</text>')
s += ['<text x="5" y="18" font-size="12">eta [m]</text>',
      f'<text x="{width/2-22:.1f}" y="{height-5}" font-size="12">t [s]</text>', '</svg>']
(dest/'gauges.svg').write_text('\n'.join(s),encoding='utf-8')
def fmt(x,n=3):
    return 'brak' if x is None else f'{x:.{n}f}'
statrows=''.join(f"<tr><td>{z['x_m']:g}</td><td>{z['samples_last_two_periods']}</td><td>{fmt(z['observed_peak_to_peak_m'])}</td><td>{'Damping' if z['is_downstream_damping_zone'] else 'Pomiar'}</td></tr>" for z in stats)
m10s=settle or {}
md=m10 or {}
document=f"""<!doctype html><html lang="pl"><meta charset="utf-8"><title>CFD review 31.10 17:15</title>
<style>body{{font:15px/1.55 system-ui,sans-serif;max-width:1100px;margin:35px auto;color:#25313d;padding:0 18px}}
h1,h2{{margin-bottom:10px}}.muted{{color:#627185}}table{{border-collapse:collapse;width:100%;margin:12px 0 22px}}
td,th{{text-align:left;border-bottom:1px solid #d8dce2;padding:8px 11px}}
.warn{{border-left:4px solid #cc8e39;padding-left:14px}}
code{{background:#f1f3f5;padding:1px 4px}}img{{max-width:100%}}</style>
<h1>Kontrola CFD | 31.10.2026</h1>
<p class="muted">Stan odczytu: {html.escape(summary['at_local'])}. Potwierdzona suma SHA256 runbooka. Bez zmian konfiguracji aktywnych solverów.</p>
<h2>Hydrofoil, spokojna woda</h2>
<table><tr><th>Siatka</th><th>Potwierdzony stan</th><th>Ograniczenie</th></tr>
<tr><td>M12</td><td>Checkpoint t=3.3314 s, zapisany wcześniej</td><td>Nie wznawiano po 12:00</td></tr>
<tr><td>M11</td><td>2 formalne zaliczenia project-primary CL / CD, checkpoint t=3.3936 s, dt=0.0002 s</td><td>Nie jest to potwierdzenie GCI ani walidacja kroku</td></tr>
<tr><td>M10</td><td>t={fmt(md.get('time_s'),4)} s, {md.get('steps','?')} kroków kontynuacji, dt=0.0004 s; interface CFL={fmt(md.get('interface_CFL'))}</td>
<td>CL shift={fmt(m10s.get('CL',{}).get('mean_change_pct'))}%, CD shift={fmt(m10s.get('CD',{}).get('mean_change_pct'))}%, brak ustalenia</td></tr></table>
<h2>Fale bez płata: H=0.5 m, lambda=20 m, coarse</h2>
<p>R4: {r4['completed']['steps']} kroków, t={fmt(r4['completed']['time_s'])} s, kontrolowane zatrzymanie z zapisem po dwóch oknach spowolnienia M11 >15%
({fmt(r4['monitor']['main_windows'][-2]['slowdown_pct'],2)}%, {fmt(r4['monitor']['main_windows'][-1]['slowdown_pct'],2)}%).
Oddzielny CPU1: {fmt(cpu1['after_t_s'])} s, 120 realnych kroków; spowolnienie M11 9.08–10.69%, lecz CPU1 był {fmt(cpu1['cpu1_to_cpu2_time_ratio'],2)}× wolniejszy niż CPU2.</p>
<img src="gauges.svg" alt="Zmierzony przebieg wysokości zwierciadła w sondach"/>
<p class="muted">Krzywe łączą istniejące pomiary R3, R4 i CPU1. Sonda x=40 m leży w strefie tłumienia i nie nadaje się jako miara nietłumionej amplitudy.</p>
<table><tr><th>Sonda x [m]</th><th>Próbki, ostatnie 2T</th><th>Rozstęp eta [m]</th><th>Uwagi</th></tr>{statrows}</table>
<p class="warn"><b>Bramka naukowa niezaliczona.</b> Dane wave-only coarse nie stanowią walidacji propagacji: brak porównywalnych baseline/fine i rozdzielonej analizy odbić/fazy, a końcowy log R4 pokazuje bardzo wysoki continuity residual i niefinitywne monitorowane wartości. Na obecnym etapie nie przenosić tych wyników na model płat+fala. Brak nowego startu baseline/fine przy aktywnym M10.</p>
<p>Odnośniki lokalne: <code>summary.json</code>, <code>gauge_stats.csv</code>, <code>gauges.svg</code>. To raport diagnostyczny, nie receipt akceptacyjny.</p></html>"""
(dest/'index.html').write_text(document,encoding='utf-8')
print(json.dumps({'output':str(dest),'station_count':len(stats),'gauge_t_last_s':last,
                  'M10_time_s':md.get('time_s'),'M10_steps':md.get('steps'),
                  'R4_stop':r4.get('controller_reason'),
                  'CPU1_time_s':cpu1['after_t_s'],
                  'sha_verified':True},ensure_ascii=False))
