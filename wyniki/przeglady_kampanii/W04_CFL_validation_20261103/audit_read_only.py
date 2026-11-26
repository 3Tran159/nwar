"""Non-intrusive W04 validation snapshot. Does not alter or advance the CFD solver."""
import csv, json, math, statistics, datetime
from pathlib import Path
from html import escape
ROOT = Path(r"E:\ntnu_mesh_optimization_20261030\nwar_automation_20261102")
RUN = ROOT / "runs" / "W04_20261103_084458_e67f66"
PRE = ROOT / "PRE_W04_20261102" / "calm_global_resume_20261102_232341"
OUT = Path(__file__).parent
def jread(p):
    try: return json.loads(Path(p).read_text(encoding="utf-8-sig"))
    except Exception: return {}
def csv_rows(path):
    with Path(path).open("r",encoding="utf-8-sig",newline="") as f:
        for row in csv.DictReader(f):
            try:
                if row and row.get("time_s") and row.get("time_s")!="time_s": yield row
            except ValueError: continue
rows = list(csv_rows(RUN/"history.csv"))
h=[]
for row in rows:
    try: h.append({k:float(row[k]) for k in ("time_s","CL_hydrodynamic","CD_total","interface_CFL","max_CFL","water_volume_m3","max_speed_m_s")})
    except (KeyError, ValueError, TypeError): pass
assert len(h)>10, "Missing W04 historical data"
monitor=jread(RUN/"monitor.json"); prog=jread(RUN/"progress.json")
wave=jread(RUN/"wave_setup_audit.json")
c01=jread(PRE/"settling_check.json")
geo=jread(OUT.parent/"W04_20261102"/"geometry_receipt.json")
prot=jread(OUT.parent/"W04_20261102"/"protected_receipt.json")
sub=[]
with (PRE/"vof_substeps.csv").open("r",encoding="utf-8-sig") as f:
    for r in csv.DictReader(f):
        try: sub.append(int(r["VOF_substeps"]))
        except Exception: pass
times=[r["time_s"] for r in h]
cfl=[r["interface_CFL"] for r in h]
num=len(h)
v0=h[0]["water_volume_m3"]
reference={"CL":c01.get("reference_CL"),"CD":c01.get("reference_CD")}
stages={"mesh_geometry_passed":geo.get("passed"),
        "protected_mesh_passed":prot.get("passed"),
        "C01_inherited_reference_compatible":c01.get("compatible_with_original_C01"),
        "four_cycles_complete":int(prog.get("complete_cycles",0))>=4,
        "wave_arrival_confirmed":prog.get("arrival")=="CONFIRMED",
        "N1_N2_comparison_complete":False}
gauge={}
for p in (RUN/"prior_gauges.csv",RUN/"gauges.csv"):
    for r in csv_rows(p):
        try:
            x=round(float(r["x_m"]),5); t=float(r["time_s"]);eta=float(r["eta_actual_m"])
            if math.isfinite(eta): gauge.setdefault(x,[]).append((t,eta))
        except (ValueError,KeyError): pass
period=float(wave.get("wave_period_s",1.5115894239782313))
if period<=0: period=1.5115894239782313
gauges={}
for x in (-15.0,-0.5,0.0,5.0):
    g=gauge.get(x,[])
    if not g: continue
    g=sorted(set(g),key=lambda a:a[0])
    last=[y for t,y in g if t>=times[-1]-period and t<=times[-1]]
    gauges[str(x)]={"samples_last_period":len(last),"peak_to_peak_last_period_m":max(last)-min(last) if len(last)>4 else None,
                    "eta_min_m":min(last) if last else None,"eta_max_m":max(last) if last else None}
def chart(file,key,label,ref=None,limit=None):
    pts=h[::max(1,len(h)//900)]
    if pts[-1] is not h[-1]: pts.append(h[-1])
    vals=[p[key] for p in pts]
    a,b=times[0],times[-1];lo=min(vals+[x for x in (ref,limit) if x is not None]); hi=max(vals+[x for x in (ref,limit) if x is not None])
    span=hi-lo if hi>lo else 1
    lo-=span*.06;hi+=span*.06
    X=lambda t:65+1000*(t-a)/max(b-a,1.e-12)
    Y=lambda v:380-340*(v-lo)/(hi-lo)
    poly=" ".join(f"{X(p['time_s']):.2f},{Y(p[key]):.2f}" for p in pts)
    svg=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 440"><rect width="1100" height="440" fill="white"/>',
         f'<text x="65" y="25" font-family="Arial" font-size="21">{escape(label)}</text>']
    for i in range(6):
        v=lo+(hi-lo)*i/5; yy=Y(v)
        svg.append(f'<line x1="65" x2="1065" y1="{yy:.2f}" y2="{yy:.2f}" stroke="#ddd" stroke-width="1"/>')
        svg.append(f'<text x="55" y="{yy+4:.2f}" text-anchor="end" font-size="13" font-family="Arial">{v:.3f}</text>')
    for t in (a,(a+b)/2,b):
        svg.append(f'<text x="{X(t):.2f}" y="410" text-anchor="middle" font-size="13" font-family="Arial">{t:.3f} s</text>')
    if ref is not None: svg.append(f'<line x1="65" x2="1065" y1="{Y(ref):.2f}" y2="{Y(ref):.2f}" stroke="#d88125" stroke-width="2" stroke-dasharray="9 6"/>')
    if limit is not None: svg.append(f'<line x1="65" x2="1065" y1="{Y(limit):.2f}" y2="{Y(limit):.2f}" stroke="#b33939" stroke-width="2" stroke-dasharray="9 6"/>')
    svg.append(f'<polyline points="{poly}" stroke="#086fa1" fill="none" stroke-width="2"/>')
    svg.append('</svg>')
    (OUT/file).write_text("\n".join(svg),encoding="utf-8")
chart("CFL_interface_W04.svg","interface_CFL","W04: interface CFL vs physical time",limit=1.0)
chart("CL_W04.svg","CL_hydrodynamic","W04: CL hydrodynamic vs physical time",ref=reference["CL"])
chart("CD_W04.svg","CD_total","W04: CD total vs physical time",ref=reference["CD"])
stats={"n_samples":num,"range_s":[times[0],times[-1]],"dt_s":wave.get("dt_s"),
       "period_s":period,"steps_per_encounter_period":period/wave.get("dt_s",0.0004),
       "interface_CFL":{"min":min(cfl),"max":max(cfl),"mean":statistics.mean(cfl),"last":cfl[-1],
                        "fraction_over_1":sum(q>1 for q in cfl)/num,
                        "fraction_over_1p5":sum(q>1.5 for q in cfl)/num,
                        "fraction_over_2":sum(q>2 for q in cfl)/num},
       "global_CFL_max":max(r["max_CFL"] for r in h),
       "water_volume_initial_m3":v0,"water_volume_latest_m3":h[-1]["water_volume_m3"],
       "water_inventory_shift_m3":h[-1]["water_volume_m3"]-v0,
       "water_inventory_is_NOT_mass_balance":True,
       "last_CL":h[-1]["CL_hydrodynamic"],"last_CD":h[-1]["CD_total"],
       "C01_reference":reference,"last_delta_CL":h[-1]["CL_hydrodynamic"]-reference["CL"],
       "last_delta_CD":h[-1]["CD_total"]-reference["CD"],
       "PRE_substeps":sorted(set(sub)),"PRE_substep_samples":len(sub),
       "W04_substeps_native_readback":"NOT_YET_VERIFIED",
       "wave_probe_diagnostic":gauges}
result={"at":datetime.datetime.now().astimezone().isoformat(timespec="seconds"),"read_only":True,
        "run":str(RUN),"run_status":monitor.get("status"),
        "reported_complete_cycles":prog.get("complete_cycles"),"gates":stages,
        "scientific_validation_complete":all(stages.values()),"stats":stats,
        "limitations":["VOF substeps directly verified for PRE, not native-read from running W04.",
        "Global CFL and interface CFL are maxima; spatial origins unknown.",
        "W04 snapshot must reach four repeated, wave-arrival-confirmed cycles before means can be accepted.",
        "Water inventory in a wave-driven open domain cannot prove mass flux closure.",
        "N=2 sensitivity run must branch from identical source checkpoint; never switch mid-W04."]}
(OUT/"validation_snapshot.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
(OUT/"VALIDATION_README.md").write_text(
    "# W04 CFD validation (read-only snapshot)\n\n"
    f"Run status: {result['run_status']}; physical time {times[-1]:.4f} s; samples {num}; "
    f"reported completed cycles {result['reported_complete_cycles']}.\n\n"
    f"Interface CFL: min {min(cfl):.3f}, max {max(cfl):.3f}, "
    f"fraction >1 = {stats['interface_CFL']['fraction_over_1']*100:.1f}%; "
    f"PRE VOF substeps {stats['PRE_substeps']}.\n\n"
    f"Original C01 reference: CL={reference['CL']:.6f}, CD={reference['CD']:.6f}.\n\n"
    "Geometric audit is separately recorded. Scientific acceptance PENDING: "
    "need four repeatable force cycles, wave probe quality, native W04 substep readback "
    "and matched N=1/N=2 sensitivity test.\n\n"
    "Acceptance for relative wave comparison: same checkpoint, mesh and BCs; "
    "time-phase-aligned cycle mean CL, CD and peak-to-peak response; "
    "N sensitivity must not change directional conclusions or exceed a small "
    "fraction of the physical separation between wave cases. Treat small "
    "differences below numerical sensitivity as indistinguishable.\n\n"
    "NO solver run, STOP, checkpoint rewrite, mesh change or queue alteration performed.\n",
    encoding="utf-8")
print(json.dumps(result,indent=2,ensure_ascii=False))
