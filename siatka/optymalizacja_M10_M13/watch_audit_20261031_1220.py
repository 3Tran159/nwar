# Read-only diagnostic for independently owned CFD files. Writes ONLY a new E: report.
from pathlib import Path
from datetime import datetime
from collections import deque
import csv, json, hashlib, statistics, math, re, shutil, html, os

R=Path("E:/ntnu_mesh_optimization_20261030")
OUT=R/"watch_review_20261031_1220"
plan=json.loads((R/"plan.json").read_text(encoding="utf-8-sig"))
sha=hashlib.sha256((R/"AUTONOMOUS_RECOVERY_PROMPT.md").read_bytes()).hexdigest()
if sha!=plan["recovery_policy"]["runbook_sha256"]:
    raise SystemExit("RUNBOOK HASH MISMATCH: no report written")
M=R/"M11_G10_M_GPU_queue_20261031_105607_91db08"
W=R/"wave_surface_only"
COARSE=W/"wave_mesh_triplet_20261031_r2"
def readj(p, fallback=None):
    try: return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception: return fallback
def csvrows(p):
    with p.open(newline="", encoding="utf-8-sig") as f: return list(csv.DictReader(f))
def numerical_tail(p):
    out=[]
    if not p.exists(): return out
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        m=re.match(r"^\s*(\d+)\s+([+\-]?\d+(?:\.\d+)?e[+\-]?\d+)\s",line,re.I)
        if m and int(m.group(1))%10==0:
            try: out.append((int(m.group(1))/10, float(m.group(2))))
            except ValueError: pass
    return out
def log_info(p):
    if not p.exists(): return {}
    s=p.read_text(encoding="utf-8",errors="replace")
    residual=numerical_tail(p)
    return {"legacy_monitor_nonfinite_notifications":s.lower().count("non-finite value detected"),
            "last_continuity_residual":residual[-1][1] if residual else None,
            "max_continuity_residual":max((a[1] for a in residual),default=None),
            "sampled_end_step_residuals":residual[-6:]}
hist=csvrows(M/"history.csv")
last=hist[-1]
def f(x): return float(x)
n=min(120,len(hist)-1)
dur=[f(hist[i]["wall_seconds"])-f(hist[i-1]["wall_seconds"]) for i in range(len(hist)-n,len(hist))]
dur=[v for v in dur if math.isfinite(v) and v>0]
main = {"last_step":int(last["step"]),"last_time_s":f(last["physical_time_s"]),
        "last_CL_hydro":f(last["CL"]),"last_CD_total":f(last["CD"]),
        "dt_s":f(last["dt_s"]),"median_wall_s_per_step_last120":statistics.median(dur) if dur else None,
        "max_CFL_last":f(last["max_CFL"]),"max_interface_CFL_last":f(last["interface_max_CFL"]),
        "latest_controller_settling":readj(M/"settling_check.json"),"source":str(M/"history.csv")}
waves = {
 "coarse_map":readj(COARSE/"map_coarse"/"mapping_audit.json"),
 "coarse_calm":readj(COARSE/"calm_coarse"/"completed.json"),
 "coarse_calm_audit":readj(COARSE/"calm_coarse"/"calm_acceptance_diagnostic.json"),
 "coarse_calm_log":log_info(COARSE/"calm_coarse"/"star.log"),
 "coarse_wave_error":readj(COARSE/"wave_coarse"/"macro_error.json"),
 "coarse_wave_attempt":readj(COARSE/"wave_coarse"/"stage_result.json"),
 "baseline_calm_log":log_info(W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"star.log"),
 "baseline_wave_1ms":readj(W/"WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0"/"completed.json"),
 "baseline_wave_05ms":readj(W/"WS_L20_H050_baseline_halfdt_CPU2_20261031_110308_37ca39"/"completed.json"),
}
res={
 "free_C_GiB":round(shutil.disk_usage("C:/").free/2**30,2),
 "free_E_GiB":round(shutil.disk_usage("E:/").free/2**30,2),
}
try:
    import ctypes
    class Mem(ctypes.Structure):
        _fields_=[("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),
                  ("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),
                  ("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),
                  ("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),
                  ("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
    mem=Mem(); mem.dwLength=ctypes.sizeof(Mem)
    if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
        res["free_RAM_GiB"]=round(mem.ullAvailPhys/2**30,2)
except Exception:
    res["free_RAM_GiB"]=None
holds={str(p):p.exists() for p in [R/"STOP_ALL",Path("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/STOP_ALL"),
                                        Path("F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/campaign_hold.json")]}
m12=readj(R/"project_primary_readiness_latest.json",{})
audit={"at":datetime.now().astimezone().isoformat(),"source":"direct THINKPAD-LUCJAN read-only raw history and STAR logs",
       "runbook_hash_verified":True,"M12":{"saved_result_reported":True,"time_s":3.3314,"project_primary_two_pass":m12.get("project_primary_acceptance"),
       "legacy_four_way":m12.get("legacy_4component_acceptance"),"GCI_certified":False},
       "M11":main,"wave_only":waves,"resources":res,"safety_markers":holds,
       "interpretation":{"M11":"Active queue continuation at exploratory dt=0.0002; not settled based on latest formal check; not comparable to M12 until matched temporal check.",
       "FS_coarse":"Map conservation passed but calm coarse STAR continuity residuals anomalously high compared with 53.2k base; old legacy monitor NaNs occur in BOTH, alone inconclusive. Post-calm wave validation failed at step 0 due baseline initial volume/velocity guard. The 200-step calm receipt is NOT physical acceptance.",
       "FS_baseline":"Two short inlet-wave ramp pilots have solver steps, not complete propagation or wave mesh acceptance.",
       "FS_fine":"Geometry audited; propagation not measured.",
       "action":"Do not auto-restart coarse wave from questionable mapped calm, do not launch joined foil-wave or lift campaign hold. Keep healthy M11 unchanged. Diagnose coarse mapped calm source and reports before a distinct bounded pilot."}}
def svg(series,title,width=720,height=176):
    top=27;left=52;right=12;bottom=30
    allpts=[(x,y) for _,points in series for x,y in points if math.isfinite(x) and math.isfinite(y)]
    if not allpts: return ""
    xs=[x for x,y in allpts];ys=[y for x,y in allpts]
    lo,hi=min(xs),max(xs); yl,yh=min(ys),max(ys)
    if hi==lo:hi+=1
    if yh==yl:yh+=1
    pad=(yh-yl)*.10; yl-=pad;yh+=pad
    X=lambda a:left+(a-lo)/(hi-lo)*(width-left-right)
    Y=lambda b:height-bottom-(b-yl)/(yh-yl)*(height-top-bottom)
    colors=["#2563eb","#dc6b2f","#16a34a"]
    parts=[f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(title)}"><text x="14" y="17" fill="#25334c" font-size="12" font-weight="600">{html.escape(title)}</text>',
           f'<path d="M{left},{top} V{height-bottom} H{width-right}" stroke="#94a3b8" fill="none"/>']
    for i,(name,points) in enumerate(series):
        valid=[(x,y) for x,y in points if math.isfinite(x) and math.isfinite(y)]
        if not valid:continue
        if len(valid)>180:valid=valid[::max(1,len(valid)//180)]
        q=" ".join(f"{X(x):.1f},{Y(y):.1f}" for x,y in valid)
        parts.append(f'<polyline fill="none" stroke="{colors[i%len(colors)]}" stroke-width="1.7" points="{q}"/>')
        parts.append(f'<text x="{left+12+175*i}" y="{height-7}" font-size="11" fill="{colors[i%len(colors)]}">{html.escape(name)}</text>')
    parts.append(f'<text x="{left+3}" y="{top+11}" font-size="10" fill="#556274">{yh:.4g}</text>')
    parts.append(f'<text x="{left+3}" y="{height-bottom-3}" font-size="10" fill="#556274">{yl:.4g}</text></svg>')
    return "".join(parts)
curve=[(f(x["physical_time_s"]),f(x["CL"])) for x in hist]
drag=[(f(x["physical_time_s"]),f(x["CD"])) for x in hist]
coarse_res=numerical_tail(COARSE/"calm_coarse"/"star.log")
base_res=numerical_tail(W/"WS_L20_H050_baseline_flatCalm_CPU2_20261031_075518_43108c"/"star.log")
cr=[(x,math.log10(y)) for x,y in coarse_res if y>0 and math.isfinite(y)]
br=[(x,math.log10(y)) for x,y in base_res if y>0 and math.isfinite(y)]
style="""<style>body{font:14px system-ui,Arial;background:#f8fafc;color:#243244;margin:28px;max-width:1060px}h1{font-size:23px}h2{font-size:17px;margin-top:30px}.small{color:#64748b}table{border-collapse:collapse;width:100%;background:white}td,th{padding:9px;border-bottom:1px solid #e2e8f0;text-align:left}th{background:#e8eef6}.bad{color:#a32920;font-weight:650}.ok{color:#146c3d;font-weight:650}.svg{display:grid;grid-template-columns:1fr 1fr;gap:9px}.svg svg{background:white;border:1px solid #d7dfea;border-radius:8px;max-width:100%}p{line-height:1.5}</style>"""
date=html.escape(audit["at"])
body=f"""<!doctype html><html lang="pl"><meta charset="utf-8"><title>CFD audyt bezpieczeństwa 31.10</title>{style}
<h1>CFD: odczyt techniczny i bramki, 31.10.2026</h1><p class="small">Odczyt {date}; zweryfikowany SHA-256 runbooka. Diagnostyka niezależna, nie modyfikuje aktywnych obliczeń.</p>
<h2>Stany</h2><table><tr><th>Obszar</th><th>Dowód</th><th>Wniosek</th></tr>
<tr><td>M12 / G10_F</td><td>1 154 199 kom., t=3,3314 s; CL/CD 2/2</td><td class="ok">Zapisany; brak GCI</td></tr>
<tr><td>M11 / G10_M</td><td>595 285 kom., t={main["last_time_s"]:.4f}s; CL={main["last_CL_hydro"]:.6f}, CD={main["last_CD_total"]:.6f}, {main["median_wall_s_per_step_last120"]:.3f}s/krok</td><td>Trwa dt=0,0002; CL/CD nieustalone</td></tr>
<tr><td>M10 / W01a</td><td>317 277 kom.; dotąd test zasobów 60 kroków</td><td>Nieustalony, bez wyboru</td></tr>
<tr><td>Wave-only coarse dz=50mm</td><td>41 200 kom.; map PASS, flat 200 kroków; residual continuity {waves["coarse_calm_log"]["last_continuity_residual"]:.2e}; wave 0 kroków</td><td class="bad">BLOKADA: weryfikacja spokojnego pola</td></tr>
<tr><td>Wave-only baseline dz=25mm</td><td>53 200 kom.; dwa krótkie rampy 1 ms i 0,5 ms</td><td>Brak pełnej propagacji/akceptacji</td></tr>
<tr><td>Wave-only fine dz=12,5mm</td><td>77 200 kom.; audyt geometrii</td><td>Bez prób transportu</td></tr>
</table>
<h2>Ostatnia kontynuacja M11</h2><div class="svg">{svg([("CL hydrodyn.",curve)],"CL hydrodynamiczne względem czasu fizycznego")}{svg([("CD total",drag)],"CD całkowite względem czasu fizycznego")}</div>
<h2>Wave-only coarse: diagnostyka residualu</h2>{svg([("53.2k flat",br),("41.2k mapped flat",cr)],"log10(continuity residual), odczyt z logu STAR")}
<p class="bad">Stop naukowy wave_coarse. Automatyczny flat receipt target_reached nie jest walidacją: baseline wave_coarse przerwał przed pierwszym krokiem. W coarse ciągłość ma residual około {waves["coarse_calm_log"]["last_continuity_residual"]:.2e} na końcu, wobec {waves["baseline_calm_log"]["last_continuity_residual"]:.3g} w bazowym flat. Stare monitory zgłaszają NaN również dla bazowego flat, więc sam komunikat NaN nie dowodzi destabilizacji pól. Sprzeczność między nowymi raportami wartości skończonych i starymi monitorami wymaga diagnostyki, bez automatycznych wznowień.</p>
<p>Zasoby wolne: RAM {res.get("free_RAM_GiB")} GiB, C: {res["free_C_GiB"]} GiB, E: {res["free_E_GiB"]} GiB. Brak nowego solve i ingerencji w M11/M12/HF. Wave hold W01-W08 bez zmian.</p>
<p class="small">Weryfikacje: pliki progress/history, raporty przeniesienia i calm, logi STAR, konfiguracja M11, aktualny runbook. Projektowe kryteria 0,5% / 1% nie są wymogami ITTC; dt M11 0,2 ms wymaga kontroli czasowej przed porównaniem z M12 0,1 ms.</p></html>"""
OUT.mkdir(exist_ok=False)
(OUT/"audit.json").write_text(json.dumps(audit,indent=2,ensure_ascii=False),encoding="utf-8")
(OUT/"index.html").write_text(body,encoding="utf-8")
print(json.dumps({"report_dir":str(OUT),"audit":str(OUT/"audit.json"),"dashboard":str(OUT/"index.html"),
                  "M11_step":main["last_step"],"M11_time_s":main["last_time_s"],
                  "coarse_calm_continuity_end":waves["coarse_calm_log"]["last_continuity_residual"],
                  "baseline_calm_continuity_end":waves["baseline_calm_log"]["last_continuity_residual"],
                  "wave_coarse_step_zero":waves["coarse_wave_attempt"].get("receipt_present") is False,
                  "resources":res},ensure_ascii=False))
