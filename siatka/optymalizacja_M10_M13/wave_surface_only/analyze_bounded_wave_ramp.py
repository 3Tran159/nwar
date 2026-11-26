"""Read-only bounded no-foil wave-ramp evidence audit.

Reads actual STAR history and water-volume gauges. This is not a propagation
accuracy / reflection / mesh convergence certification. Writes only a new
small review JSON beside the disposable pilot run on E:.
"""
from pathlib import Path
import csv,json,datetime,math,statistics,sys,os,uuid
ROOT=Path(r"E:\ntnu_mesh_optimization_20261030")
WAVE=ROOT/"wave_surface_only"
STAGE=sys.argv[1] if len(sys.argv)>1 else "WS_L20_H050_baseline_inlet_wave_CPU2_20261031_100620_c8139b"
DIR=WAVE/STAGE
def rows(path):
 try:
  with path.open(newline="",encoding="utf-8-sig") as f:
   return [r for r in csv.DictReader(f) if isinstance(r,dict) and None not in r]
 except (OSError,ValueError,csv.Error):return []
def valid(x):
 try:
  v=float(x)
  return v if math.isfinite(v) else None
 except (TypeError,ValueError):return None
def number(v):
 a=[x for x in v if isinstance(x,(float,int)) and math.isfinite(x)]
 return {"n":len(a),"min":min(a) if a else None,"max":max(a) if a else None,
         "mean":statistics.mean(a) if a else None}
def filejson(path):
 try:return json.loads(path.read_text(encoding="utf-8-sig"))
 except (OSError,ValueError):return {}
def audit():
 h=rows(DIR/"history.csv");g=rows(DIR/"gauges.csv")
 done=filejson(DIR/"completed.json")
 setup=filejson(DIR/"wave_setup_audit.json")
 result=filejson(DIR/"pilot_result.json")
 st=datetime.datetime.now().astimezone().isoformat()
 hh=[r for r in h if valid(r.get("time_s")) is not None and valid(r.get("step")) is not None]
 fromstep=[int(float(r["step"])) for r in hh]
 t=[float(r["time_s"]) for r in hh]
 max_speed=number([valid(r.get("max_speed_m_s")) for r in hh])
 max_cfl=number([valid(r.get("max_CFL")) for r in hh])
 interface=number([valid(r.get("interface_CFL")) for r in hh])
 water=number([valid(r.get("water_volume_m3")) for r in hh])
 nominal=number([valid(r.get("target_height_m")) for r in hh])
 physical=number([valid(r.get("actual_wave_height_m")) for r in hh])
 period=number([valid(r.get("period_s")) for r in hh if valid(r.get("step")) is not None and float(r["step"])>0])
 delta=[abs(valid(r.get("actual_wave_height_m"))-valid(r.get("target_height_m"))) for r in hh if valid(r.get("actual_wave_height_m")) is not None and valid(r.get("target_height_m")) is not None]
 byx={}
 for row in g:
  x=valid(row.get("x_m"));eta=valid(row.get("eta_actual_m"))
  if x is not None and eta is not None:
   byx.setdefault(str(round(x,3)),[]).append((valid(row.get("time_s")),eta))
 probes={}
 for x, vals in sorted(byx.items(),key=lambda z:float(z[0])):
  vv=[v for _,v in vals]
  above=[{"time_s":tt,"eta_m":v} for tt,v in vals if tt is not None and abs(v)>=.005]
  probes[x]={"samples":len(vv),"min_eta_m":min(vv),"max_eta_m":max(vv),
   "max_abs_eta_m":max(map(abs,vv)),"first_abs_eta_over_5mm":above[0] if above else None}
 stop=str(done.get("status","not_yet_completed"))
 samples=len(hh)
 r={
  "schema":"read_only_wave_ramp_quality_v1","sampled_at":st,
  "run_path":str(DIR),"phase":"inlet_wave_ramp_from_computed_flat_calm",
  "source_time_s":.4,"target_dt_s":.001,
  "n_history_samples":samples,"n_gauge_samples":len(g),
  "last_step":max(fromstep) if fromstep else None,
  "last_physical_time_s":t[-1] if t else None,
  "completed_status":stop,"exit_code":result.get("exit_code"),
  "max_speed_m_s":max_speed,"bulk_CFL":max_cfl,
  "interface_CFL_valid":interface,"interface_CFL_unavailable_samples":samples-interface["n"],
  "water_volume_m3":water,
  "water_volume_range_pct":(water["max"]-water["min"])/water["mean"]*100 if water["n"]>1 and water["mean"] else None,
  "nominal_H_m":nominal,"evaluated_H_m":physical,
  "max_abs_evaluated_height_difference_m":max(delta) if delta else None,
  "wave_period_s_after_first_step":period,
  "raw_surface_probe_statistics":probes,
  "measured_probe_wave_disturbance":any(p["first_abs_eta_over_5mm"] for p in probes.values()),
  "wave_height_envelope_complete":bool(t and t[-1]>=.4+1.6945346413782258),
  "propagation_accuracy_accepted":False,
  "mesh_convergence_accepted":False,
  "reflection_evaluated":False,
  "phase_speed_evaluated":False,
  "ramp_startup_must_be_excluded_from_amplitude_or_phase_accuracy":True,
  "disclaimer":"Source is raw solver history and probes only; no guessed phase, reflection, damping or full-height wave. Empty interface threshold yields unavailable CFL, not zero. Station arrival needs actual full-height time-series evidence.",
 }
 return r
if __name__=="__main__":
 r=audit()
 p=DIR/"read_only_wave_ramp_review.json"
 tmp=DIR/("read_only_wave_ramp_review."+uuid.uuid4().hex+".tmp")
 tmp.write_text(json.dumps(r,indent=2,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
 os.replace(tmp,p)
 print(json.dumps({k:r[k] for k in
 ["sampled_at","n_history_samples","n_gauge_samples","last_step","last_physical_time_s","completed_status",
 "water_volume_range_pct","measured_probe_wave_disturbance","wave_height_envelope_complete","propagation_accuracy_accepted"]},
  ensure_ascii=False,allow_nan=False))
