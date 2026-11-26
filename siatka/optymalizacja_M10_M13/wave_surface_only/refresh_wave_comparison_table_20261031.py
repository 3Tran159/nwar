from pathlib import Path
import json,csv,html,datetime,os,math
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
BASE=W/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0"
HALF=W/"WS_L20_H050_baseline_halfdt_CPU2_20261031_110308_37ca39"
ROOT=W.parent
def read(p):
 try:return json.loads(Path(p).read_text(encoding="utf8-sig"))
 except (ValueError,OSError):return {}
def rows():
 out=[]
 for mesh,cells,dz in (("FS_coarse",41200,.05),("FS_baseline",53200,.025),("FS_fine",77200,.0125)):
  for dt in (.001,.0005):
   source=BASE if mesh=="FS_baseline" and dt==.001 else HALF if mesh=="FS_baseline" and dt==.0005 else None
   done=read(source/"completed.json") if source else {}
   progress=read(source/"progress.json") if source else {}
   history=source/"history.csv" if source else None
   actual_steps=0
   if history and history.is_file():
    with history.open(encoding="utf8-sig",newline="") as f:
     measured=list(csv.DictReader(f))
     actual_steps=int(float(measured[-1]["step"])) if measured else 0
   status="not_run_geometry_only" if not source else ("bounded_startup_completed_not_full_wave" if done.get("status")=="target_reached" else "active_unfinished" if actual_steps else "initializing_no_physical_steps_yet")
   out.append(dict(mesh=mesh,cells=cells,near_surface_dz_m=dz,dt_s=dt,geometry_topology_audited=True,actual_wave_steps=actual_steps,time_s=done.get("time_s",progress.get("time_s")),measured_interface_CFL=progress.get("interface_CFL"),measured_max_CFL=progress.get("max_CFL"),measured_max_abs_gauge_eta_m=progress.get("max_abs_gauge_eta_m"),status=status,full_wave_validated=False))
 return out
out=rows();csvp=W/"wave_mesh_dt_live_table_20261031.csv";jsonp=W/"wave_mesh_dt_live_table_20261031.json";htmlp=W/"wave_mesh_dt_live_table_20261031.html"
with csvp.open("w",encoding="utf8",newline="") as f:
 writer=csv.DictWriter(f,fieldnames=list(out[0]));writer.writeheader();writer.writerows(out)
jsonp.write_text(json.dumps(dict(at=datetime.datetime.now().astimezone().isoformat(),records=out,remarks="Measured only. Same physical windows/phase not yet validated; grid geometry audit is not CFD convergence."),ensure_ascii=False,indent=2),encoding="utf8")
heads=["Siatka","Komórki","dz [mm]","Δt [ms]","Kroki CFD","t [s]","Interface CFL","Status"]
def v(x):return "—" if x is None else f"{x:.3f}" if isinstance(x,float) else str(x)
tr=[]
for a in out:
 values=[a["mesh"],a["cells"],1000*a["near_surface_dz_m"],1000*a["dt_s"],a["actual_wave_steps"],a["time_s"],a["measured_interface_CFL"],a["status"]]
 tr.append("<tr>"+''.join("<td>"+html.escape(v(x))+"</td>" for x in values)+"</tr>")
page='''<!doctype html><html lang="pl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CFD • no-foil wave mesh/time-step matrix</title>
<style>body{font-family:system-ui,sans-serif;margin:2rem auto;padding:0 1rem;max-width:1150px;line-height:1.5;background:#f7f9fb;color:#122336}table{width:100%;border-collapse:collapse;background:#fff}th,td{padding:9px;border-bottom:1px solid #dbe3e9;text-align:left}th{background:#e9f0f4}section{overflow:auto}small{color:#586979}</style>
<h1>Siatki i kroki czasowe • fale bez płata</h1><p>Wyniki rzeczywiste i statusy uruchomień; brak propagacji i GCI nie jest zaliczeniem.</p><section><table><thead><tr>'''+''.join("<th>"+x+"</th>" for x in heads)+'</tr></thead><tbody>'+''.join(tr)+'''</tbody></table></section>
<p><small>Geometria 41.2k / 53.2k / 77.2k przeszła audyt CGNS; CFD zfalowane wykonano tylko tam, gdzie podano kroki fizyczne. Nie przypisano fikcyjnej amplitudy, fazy ani odbicia. Starszy pilot 1 ms obejmuje rampę 0,4–0,9 s, a kontrola 0,5 ms ma zakres 0,4–0,6 s.</small></p></html>'''
htmlp.write_text(page,encoding="utf8")
print("WAVE_TABLE_UPDATED",csvp,jsonp,htmlp,"rows",len(out), "measured",[(x["mesh"],x["dt_s"],x["actual_wave_steps"]) for x in out if x["actual_wave_steps"]])
