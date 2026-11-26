"""Read-only actual CFD progress dashboard: no synthetic wave amplitude, phase, CFL or wall cost."""
from pathlib import Path
import csv,json,math,html,datetime
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
R=W/"wave_mesh_triplet_20261031"
CASES=(("coarse",41200,.05),("baseline",53200,.025),("fine",77200,.0125))
def get(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except (OSError,ValueError):return {}
def rows(p):
 try:
  with Path(p).open(newline="",encoding="utf8-sig") as f:return list(csv.DictReader(f))
 except OSError:return []
def show(x,d=3):
 if x is None:return "—"
 if isinstance(x,float):return format(x,f".{d}f")
 return str(x)
report=[]
plot_series=[]
for tag,n,dz in CASES:
 mapd=R/("map_"+tag);calmd=R/("calm_"+tag);waved=R/("wave_"+tag)
 calmdone=get(calmd/"completed.json");wavedone=get(waved/"completed.json")
 cm=rows(calmd/"history.csv"); wh=rows(waved/"history.csv"); gauges=rows(waved/"gauges.csv")
 m=get(mapd/"mapping_audit.json"); 
 measured_steps=int(float(wh[-1].get("step",0))) if wh else 0
 max_ci=None;max_cfl=None;duration=None;eta_peak=None;volrange=None
 if wh:
  a=[float(z["interface_CFL"]) for z in wh if z.get("interface_CFL") and math.isfinite(float(z["interface_CFL"]))]
  max_ci=max(a) if a else None
  c=[float(z["max_CFL"]) for z in wh if z.get("max_CFL") and math.isfinite(float(z["max_CFL"]))]
  max_cfl=max(c) if c else None
  duration=float(wh[-1].get("wall_s",0))
  mass=[float(z["water_volume_m3"]) for z in wh if z.get("water_volume_m3")]
  volrange=max(mass)-min(mass) if mass else None
 if gauges:
  eta_peak=max(abs(float(g["eta_actual_m"])) for g in gauges)
  sg=[(float(g["time_s"])-.6,1000*float(g["eta_actual_m"])) for g in gauges if abs(float(g["x_m"])+34)<1e-5]
  if sg:plot_series.append((tag,sg))
 stage=("wave completed" if wavedone.get("status")=="target_reached" else
  "wave running" if wh else "calm ready" if calmdone.get("status")=="target_reached" else
  "calm running" if cm else "mesh mapping verified" if m.get("pass") else
  "mapping running" if mapd.is_dir() else "queued")
 report.append(dict(mesh=tag,cells=n,dz_mm=1000*dz,spatial_cells_per_0p5m=int(round(.5/dz)),map_pass=m.get("pass") if tag!="baseline" else "direct same mesh",calm_steps=int(float(cm[-1]["step"])) if cm else None,calm_complete=calmdone.get("status")=="target_reached",wave_steps=measured_steps,physical_time_s=float(wh[-1]["time_s"]) if wh else None,max_interface_CFL=max_ci,max_bulk_CFL=max_cfl,max_abs_eta_mm=1000*eta_peak if eta_peak is not None else None,water_volume_range_m3=volrange,wave_solver_wall_s=duration,status=stage,full_propagation_validated=False))
colors={"coarse":"#db7e20","baseline":"#3078c0","fine":"#7f49bb"}
width,height=860,300
chart='<p>Nie ma jeszcze danych z sondy x = −34 m dla porównania trzech siatek.</p>'
if plot_series:
 points=[xy for _,series in plot_series for xy in series]
 lo=min(y for x,y in points);hi=max(y for x,y in points)
 yr=max(1,hi-lo);lo-=.1*yr;hi+=.1*yr
 xmax=max(max(x for x,y in s) for _,s in plot_series)
 xmax=max(.1,xmax)
 paths=[]
 for tag,s in plot_series:
  seg=" ".join(("M" if i==0 else "L")+format(50+760*x/xmax,".1f")+","+format(235-195*(y-lo)/(hi-lo),".1f") for i,(x,y) in enumerate(s))
  paths.append(f'<path d="{seg}" stroke="{colors[tag]}" stroke-width="2.2" fill="none"/>')
 chart=f'''<svg viewBox="0 0 {width} {height}" role="img" aria-label="Zmierzona elewacja powierzchni x minus 34 m względem czasu od rozpoczęcia fali"><rect x="0" y="0" width="{width}" height="{height}" fill="#fff"/><line x1="50" x2="810" y1="235" y2="235" stroke="#7b8692"/><line x1="50" x2="50" y1="40" y2="235" stroke="#7b8692"/>{"".join(paths)}<text x="430" y="280" font-size="13" fill="#526273" text-anchor="middle">Czas po włączeniu fali [s]</text><text x="48" y="25" font-size="13" fill="#526273">η [mm], sonda x = −34 m</text></svg>''' + '<div class="legend">'+''.join(f'<span><i style="background:{colors[tag]}"></i>{tag}</span>' for tag,_ in plot_series)+'</div>'
heads=[("mesh","Siatka"),("cells","Komórki"),("dz_mm","Δz [mm]"),("wave_steps","Kroki fali"),("max_interface_CFL","Max interface CFL"),("max_abs_eta_mm","Max |η| [mm]"),("status","Etap")]
def td(row,k):return html.escape(show(row.get(k)))
table='<table><thead><tr>'+''.join('<th>'+label+'</th>' for k,label in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+td(a,k)+'</td>' for k,_ in heads)+'</tr>' for a in report)+'</tbody></table>'
at=datetime.datetime.now().astimezone().isoformat()
page=f'''<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CFD: badanie rozdzielczości fal</title><style>
:root{{--ink:#243244;--muted:#5e7184;--border:#d6dfe8}}body{{font-family:system-ui,-apple-system,sans-serif;max-width:1170px;margin:28px auto;padding:0 20px;color:var(--ink);background:#f7f9fb;line-height:1.45}}
h1{{font-size:1.6rem}}.table{{overflow-x:auto}}table{{width:100%;border-collapse:collapse;background:white;font-variant-numeric:tabular-nums}}td,th{{padding:12px;border-bottom:1px solid var(--border);text-align:left;white-space:nowrap}}th{{background:#e9f0f7}}.legend{{display:flex;gap:15px}}.legend i{{display:inline-block;width:10px;height:10px;border-radius:3px;margin-right:6px}}.sub{{color:var(--muted)}}.chart{{background:white;border-radius:10px;padding:8px}}svg{{width:100%;height:auto}}.table,.chart{{margin:18px 0}}</style>
<h1>Rozdzielczość pionowa siatki a propagacja fali</h1><p class="sub">Aktualizacja {html.escape(at)}. Trzy siatki tej samej domeny, H docelowe = 0,5 m, λ = 20 m, Δx = 0,2 m, Δt = 0,001 s. Spokojna woda: 18 m/s, bez płata.</p>
<div class="table">{table}</div><div class="chart">{chart}</div>
<p><b>Granica wnioskowania:</b> obecne przebiegi obejmują rozruch fali od wlotu. Tabela nie potwierdza jeszcze pełnej amplitudy, fazy, odbić ani niezależności od siatki. Dane nieobecnych prób pozostają puste, nie są interpolowane.</p>
<p class="sub">Źródło: wyłącznie history.csv, gauges.csv, mapping_audit.json i completed.json w bieżących folderach CPU2.</p></html>'''
R.mkdir(exist_ok=True)
(R/"live_comparison.html").write_text(page,encoding="utf8")
(R/"live_comparison.json").write_text(json.dumps(dict(updated_at=at,records=report,full_validation=False),ensure_ascii=False,indent=2,allow_nan=False),encoding="utf8")
print(json.dumps({"html":str(R/"live_comparison.html"),"records":[{"mesh":a["mesh"],"stage":a["status"],"wave_steps":a["wave_steps"]} for a in report]},ensure_ascii=False))
