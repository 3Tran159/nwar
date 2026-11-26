"""Read-only scientific comparison. Never launches or alters any solver."""
from pathlib import Path
import csv, json, statistics, datetime

root = Path(r"E:\ntnu_mesh_optimization_20261030")
paths = {
 "M10": root / "M10_W01a_GPU_queue_20261031_165802_aef11e" / "history.csv",
 "M11": root / "M11_G10_M_GPU_queue_20261031_105607_91db08" / "history.csv",
 "M12": Path(r"C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030\force_stabilization_20261029\calm_settle_G10_F_GPU_live_r2_resume_20261030_173420_4854e1\history.csv"),
 "M13": root / "M13_farfield15_20261031" / "M13_GPU_calm_dt0004" / "history.csv"
}
fields = ["CL", "CD", "pressure_drag_N", "viscous_drag_N"]
def load(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return [{k: float(v) for k,v in r.items()} for r in csv.DictReader(f)]
def window(rows, a, b):
    w = [r for r in rows if a - 2e-7 <= r["physical_time_s"] <= b + 2e-7]
    if not w: return {"n":0}
    return {"n":len(w), "first_t":w[0]["physical_time_s"],"last_t":w[-1]["physical_time_s"],
            **{k: statistics.fmean(r[k] for r in w) for k in fields}}
def cost(rows):
    r = rows[-601:]
    diffs = [(r[i]["wall_seconds"]-r[i-1]["wall_seconds"]) for i in range(1,len(r))
             if r[i]["wall_seconds"]>=r[i-1]["wall_seconds"]]
    return {"median_s_per_step_last600":statistics.median(diffs),"mean_s_per_step_last600":statistics.fmean(diffs),
            "mean_wall_per_physical_second_last600":(r[-1]["wall_seconds"]-r[0]["wall_seconds"])/(r[-1]["physical_time_s"]-r[0]["physical_time_s"])}
data={k:load(p) for k,p in paths.items()}
out={"time_local":datetime.datetime.now().astimezone().isoformat(),
     "scope":"Offline CSV only. No process or source files modified. CL column is ALREADY buoyancy-adjusted.",
     "rule":"abs relative difference <=5% separately CL and total CD, reference M12; matched-window requirement and unequal dt caveat",
     "samples":{}, "matched_M10_M11_M12_3p098_to_3p298":{}, "comparisons":{}}
for name, rows in data.items():
    t0,t1=rows[0]["physical_time_s"],rows[-1]["physical_time_s"]
    out["samples"][name]={"t_first":t0,"t_last":t1,"dt_last":rows[-1]["dt_s"],"rows":len(rows),
        "last_0p2":window(rows,t1-0.2,t1),"cost":cost(rows)}
for name in ["M10","M11","M12"]:
    out["matched_M10_M11_M12_3p098_to_3p298"][name]=window(data[name],3.098,3.298)
ref=out["matched_M10_M11_M12_3p098_to_3p298"]["M12"]
for name in ["M10","M11"]:
    vals=out["matched_M10_M11_M12_3p098_to_3p298"][name]
    out["comparisons"][name+"_M12_matched_window"]={k+"_pct":100*(vals[k]/ref[k]-1) for k in ("CL","CD")}
ref=out["samples"]["M12"]["last_0p2"]
for name in ["M10","M11","M13"]:
    vals=out["samples"][name]["last_0p2"]
    out["comparisons"][name+"_M12_distinct_last_windows_PROVISIONAL"]={k+"_pct":100*(vals[k]/ref[k]-1) for k in ("CL","CD")}
m13=data["M13"];m12=data["M12"];m10=data["M10"]
out["overlap_M13_M12_s"]=max(0,min(m13[-1]["physical_time_s"],m12[-1]["physical_time_s"])-max(m13[0]["physical_time_s"],m12[0]["physical_time_s"]))
out["overlap_M13_M10_s"]=max(0,min(m13[-1]["physical_time_s"],m10[-1]["physical_time_s"])-max(m13[0]["physical_time_s"],m10[0]["physical_time_s"]))
out["honesty"]="No 0.2 s common raw-data window exists between M13 and M12/M10; M13 vs M12 relative deviations remain provisional, not strict 5% matched-window certification. dt M10=.4ms, M11=.2ms, M12=.1ms."
out["M13_cells"]=309441
out["M10_cells"]=317277
out["M13_cell_reduction_vs_M10_pct"]=100*(1-309441/317277)
target=root/"watch_mesh_comparison_readonly_20261031_2140.json"
target.write_text(json.dumps(out,indent=2,ensure_ascii=False),encoding="utf-8")
print(json.dumps(out,indent=2,ensure_ascii=False))
