"""Single owned CPU1 resource pilot on a disposable, already-saved no-foil wave.
No scientific wave acceptance, no automatic extension or duplicate start.
Does not touch M11, M12, HF, held C01, the source .sim, or legacy macros.
"""
from pathlib import Path
import sys,os,json,hashlib,uuid,datetime,shutil,time,csv,statistics
W=Path(r"E:\ntnu_mesh_optimization_20261030\wave_surface_only")
R=W.parent
F=Path(r"F:\ntnu\mesh_screening_20261028\force_stabilization_20261029")
sys.path.insert(0,str(W))
import run_zero_start_cpu1_stage_20261031 as z
import launch_halfdt_wave_cpu2_with_M11_guard as perf
import bounded_cpu_pilot as guard
OLD=W/"zero_start_matrix_R2_coarse_continuation_20261031_4"/"waves"/"L20_H500_coarse"
SOURCE=OLD/"wave_pilot_final.sim"
NEW=W/"wave_cpu1_resource_pilot_20261031_1603"
MACRO=OLD/"ContinueWaveOnlySavedR4.java"
LOCKS=z.LOCKS
TOKEN=uuid.uuid4().hex
def now():return datetime.datetime.now().astimezone().isoformat()
def read(p):return z.read(p)
def write(p,obj):return z.write(p,obj)
def sha(p):return z.sha(p)
def preflight():
 assert datetime.datetime.now().astimezone().date()==datetime.date(2026,10,31)
 assert datetime.datetime.now().astimezone().hour<23
 plan=read(R/"plan.json")
 assert plan["parallel_execution"]["authorized"]
 assert plan["parallel_execution"]["maximum_auxiliary_solvers"]==1
 assert sha(R/"AUTONOMOUS_RECOVERY_PROMPT.md")==plan["recovery_policy"]["runbook_sha256"]
 assert not NEW.exists(), "Do not duplicate the CPU1 resource hypothesis"
 assert not any(p.exists() for p in LOCKS), "Other auxiliary is active"
 assert z.check_danger() is None
 assert read(F/"campaign_hold.json").get("active") is True
 done=read(OLD/"completed.json")
 result=read(OLD/"stage_result.json")
 assert done.get("status")=="stopped_by_marker" and done.get("steps")==996
 assert result.get("exit_code")==0 and result.get("source_unchanged") is True
 assert result.get("controller_reason")=="M11_slowdown_two_windows_over_15pct"
 assert abs(done.get("time_s",0)-5.503)<1e-8
 assert SOURCE.is_file() and SOURCE.stat().st_size>20_000_000
 hist=z.rows(OLD/"history.csv")
 assert len(hist)>=997 and int(hist[-1]["step"])==996
 assert abs(float(hist[-1]["time_s"])-done["time_s"])<1e-7
 assert float(hist[-1]["max_CFL"])<1 and float(hist[-1]["interface_CFL"])<1
 assert float(hist[-1]["max_speed_m_s"])<25 and 38.35<float(hist[-1]["water_volume_m3"])<38.45
 assert MACRO.is_file()
 assert sha(MACRO)==sha(W/"resume_coarse_r4_compilecheck_20261031"/"ContinueWaveOnlySavedR4.java")
 main=perf.main_state()
 assert main is not None and main.name.startswith("M11_G10_M_GPU_queue_")
 perf.only_owned_main_star(main)
 dur,baseline=perf.get_gpu_durations(main)
 assert len(dur)>=200 and .3<baseline<10
 assert time.time()-(main/"history.csv").stat().st_mtime<120
 return main,baseline,done["time_s"],hist
def run():
 main,baseline,t0,history=preflight()
 captured=[]
 try:
  for lk in LOCKS:
   with lk.open("x",encoding="utf8") as f:
    json.dump(dict(pid=os.getpid(),kind="wave_cpu1_resource_pilot_only",token=TOKEN,at=now()),f)
   captured.append(lk)
  NEW.mkdir(exist_ok=False)
  z.ROOT=NEW
  z.STATUS=W/"cpu1_resource_pilot_current.json"
  before=sha(SOURCE)
  write(NEW/"plan.json",dict(at=now(),scope="resource test CPU1 only",
   M11=str(main),M11_baseline_s_step=baseline,workers=1,priority="BELOW_NORMAL",
   gpu=False,source=str(SOURCE),source_sha256=before,start_t_s=t0,
   steps=120,dt_s=.001,inner=10,from_saved_wave_no_reinitialization=True,
   original_wave_hold_preserved=True,no_auto_extension=True,
   guard="two independent M11 windows above 15% stop only helper"))
  started=time.monotonic()
  save,folder=z.stage(main,baseline,"waves","L20_H500_coarse_CPU1",SOURCE,MACRO,
    dict(NTNU_NOFOIL_CELLS="41200",NTNU_NOFOIL_SOURCE_T=str(t0),
         NTNU_NOFOIL_WAVE_DT=".001",NTNU_NOFOIL_WAVE_STEPS="120"),
    max_wall_s=850)
  data=z.rows(folder/"history.csv")
  assert data and int(data[-1]["step"])==120
  pilot_s=float(data[-1]["wall_s"])/120
  prior_s=(float(history[-1]["wall_s"])-float(history[-121]["wall_s"]))/120
  monitor=read(folder/"monitor.json")
  slowdowns=[x["slowdown_pct"] for x in monitor.get("main_windows",[])]
  assert sha(SOURCE)==before
  outcome=dict(at=now(),status="completed_resource_measurement_not_wave_validation",
     source_preserved=True,source=before,after_t_s=float(data[-1]["time_s"]),
     cpu1_s_per_step=pilot_s,prior_cpu2_s_per_step=prior_s,
     cpu1_to_cpu2_time_ratio=pilot_s/prior_s,
     main_M11_slowdown_windows_pct=slowdowns,
     main_M11_slowdown_limit_pct=15,
     main_M11_changed=(perf.main_state()!=main),
     original_hold_active=read(F/"campaign_hold.json").get("active"),
     all_120_steps_finished=True,
     caution="Resource pilot only; scientifically unvalidated no-foil case; no second solver.")
  write(NEW/"pilot_result.json",outcome)
  write(z.STATUS,dict(status="cpu1_pilot_finished_readout_available",at=now(),
                            directory=str(NEW),pilot_result=str(NEW/"pilot_result.json")))
  print(json.dumps(outcome,ensure_ascii=False),flush=True)
 except BaseException as ex:
  if NEW.exists():
   data=read(NEW/"waves"/"L20_H500_coarse_CPU1"/"monitor.json")
   status=dict(at=now(),status="blocked_no_auto_retry",kind=type(ex).__name__,
     reason=str(ex)[:400],M11_monitor=data,folder=str(NEW))
   write(NEW/"pilot_result.json",status)
   write(W/"cpu1_resource_pilot_current.json",status)
  print("CPU1 PILOT NOT ACCEPTED",type(ex).__name__,str(ex)[:300],flush=True)
 finally:
  for lk in reversed(captured):
   if read(lk).get("token")==TOKEN:
    lk.unlink()
if __name__=="__main__":run()
