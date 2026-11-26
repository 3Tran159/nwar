from pathlib import Path
import json,html
R=Path(r"E:\ntnu_mesh_optimization_20261030")
a=json.loads((R/"watch_scientific_snapshot_20261031_1537.json").read_text(encoding="utf-8"))
w=json.loads((R/"full_status_raw_analysis_latest.json").read_text(encoding="utf-8"))
f=lambda x,n=3:f"{x:.{n}f}"
m=a["M11"];m12=a["M12"];r=a["R4"];p=r["progress"];wins=r["monitor"]["main_windows"]
x=['<!doctype html><html lang="pl"><head><meta charset="utf-8"><title>CFD monitoring 31.10</title><style>body{font:15px system-ui;margin:36px auto;max-width:1000px;padding:0 20px;background:#10151b;color:#edf2f6}h1,h2{font-weight:550}small,.muted{color:#a2afba}table{border-collapse:collapse;width:100%;margin:18px 0}td,th{padding:11px;border-bottom:1px solid #39424a;text-align:left}th{color:#acb9c4}section{margin:32px 0}.track{width:300px;max-width:100%;height:12px;background:#303b45;border-radius:6px;overflow:hidden;display:inline-block;vertical-align:middle}.fill{height:100%;background:#3eb6b0}.hbar{width:280px;max-width:100%;height:12px;background:#2b3540;position:relative;display:inline-block;border-radius:4px}.hbar span{display:block;height:100%;background:#5f9ea0;border-radius:4px}.hbar:after{content:"";position:absolute;left:83.33%;top:-3px;height:18px;border-left:2px dashed #f4bf65}.fine{font-size:12px;color:#a2afba}</style></head><body>']
x+=[f'<h1>CFD: nadzór i diagnostyka</h1><p class="muted">Odczyt z THINKPAD-LUCJAN: {html.escape(a["at"])}. Zapis z realnych CSV/JSON, bez interwencji w solvery.</p>']
x+=['<section><h2>Płat, spokojna woda</h2><table><tr><th>Wskaźnik</th><th>M11 medium</th><th>M12 fine (zapisany)</th></tr>']
for label,k in [("CL hydrodyn.","CL_instant"),("CD total","CD_instant")]:
 x+=[f'<tr><td>{label}</td><td>{f(m[k],7)}</td><td>{f(m12[k],7)}</td></tr>']
x+=[f'<tr><td>Czas fizyczny</td><td>{f(m["t_s"])} s</td><td>{f(m12["last_t_s"])} s</td></tr>',
f'<tr><td>Komórki</td><td>595 285</td><td>1 154 199</td></tr></table>',
f'<p>Zmiana średniej M11 między dwoma oknami 0,2 s: CL {f(m["mean_shift_pct"]["CL"])}%; CD {f(m["mean_shift_pct"]["CD"])}%. '+
f'RMS ostatniego okna: CL {f(m["latest_window"]["CL"]["rms_pct"])}%; CD {f(m["latest_window"]["CD"]["rms_pct"])}%.</p>',
f'<p class="fine">Diagnostyka |ΔCDp|/|CD|={f(m["component_delta_over_totalCD_pct"]["pressure"])}%; |ΔCDv|/|CD|={f(m["component_delta_over_totalCD_pct"]["viscous"])}%; suma modułów={f(m["component_delta_over_totalCD_pct"]["sum_moduli"])}%. '+
'Jedno pozytywne porównanie okien nie oznacza dwóch kolejnych formalnych zaliczeń ani walidacji GCI.</p></section>']
pct=100*p["steps"]/2000
x+=[f'<section><h2>Fala bez płata: λ20 m / H0,5 m, coarse 41 200 komórek</h2>',
f'<p>R4: {p["steps"]}/2000 kroków ({f(pct,1)}%). <span class="track"><span class="fill" style="display:block;width:{pct}%"></span></span></p>',
f'<p>t = {f(p["time_s"])} s; dt = 0,001 s; CFL max={f(p["max_CFL"])}; CFL interfejsu={f(p["interface_CFL"])}; woda={f(p["water_volume_m3"])} m³.</p>',
f'<p>Trzy ostatnie niezależne okna spowolnienia M11: {", ".join(f(z["slowdown_pct"],1)+"%" for z in wins)}; limit projektu 15%. Jedno CPU2, GPU bez zmian.</p>',
'<h2>R3: zmierzone H na sondach (2 końcowe okresy)</h2><table><tr><th>x</th><th>H szczyt–dolina</th><th>skala 0–0,6 m</th></tr>']
for z in w["wave"]["gauges_late"]:
 H=z["H_peak_to_peak_m"];xx=z["x_m"]
 x += [f'<tr><td>{f(xx,0)} m</td><td>{f(H,3)} m</td><td><div class="hbar"><span style="width:{min(100,max(0,H/0.6*100))}%"></span></div></td></tr>']
x+=['</table><p class="fine">Linia przerywana: zadane H=0,5 m. Sonda x=40 m leży w strefie tłumienia; brak jeszcze potwierdzonej diagnostyki odbić, fazy i niezależnej siatki baseline/fine. Fala nie została naukowo zaakceptowana.</p></section>']
x+=[f'<section><h2>Bezpieczeństwo</h2><p>RUNBOOK SHA: {"zgodny" if a["runbook_hash_ok"] else "NIEZGODNY"}. Blokada W01–W08: {"aktywna" if a["campaign_hold"] else "BRAK!"}. STOP_ALL: {a["STOP_ALL"]}. R4 właściciel/proces żyją: {r["owner_alive"]}/{r["star_alive"]}.</p>',
f'<p>Wolny RAM {a["ram_available_GiB"]} GiB; C: {a["C_free_GiB"]} GiB; E: {a["E_free_GiB"]} GiB. Tylko odczyt, bez zmian M11/M12/HF i blokad.</p></section></body></html>']
path=R/"watch_scientific_snapshot_20261031_1537.html"
path.write_text("".join(x),encoding="utf-8")
print("HTML_SAVED",path,"BYTES",path.stat().st_size)
