"""Read-only comparison of original logs/histories. Does not run or control STAR."""
from pathlib import Path
from datetime import datetime
import csv,json,re,math,hashlib,statistics
R=Path(r'E:\ntnu_mesh_optimization_20261030');W=R/'wave_surface_only';D=Path(__file__).parent
CASES={
 'H05_CPU1_dt1':W/'zero_start_matrix_evening_20261031_182305_689cb9'/'waves'/'L20_H500_baseline',
 'H05_CPU1_dt05':W/'zero_start_matrix_evening_dt05_20261031'/'waves'/'L20_H500_baseline',
 'H0001_CPU1_dt1':W/'wave_nearflat_inlet_CPU1_20261031_once',
 'H05_CPU2_dt1':W/'WS_L20_H050_baseline_inlet_wave_CPU2_20261031_101019_5dd9f0',
 'H05_CPU1_pressure_aligned':W/'WAVE_H050_pressure_aligned_CPU1_20261031_once',
 'foil_M13_GPU_R1':R/'M13_wave_direct_20261031'/'M13_GPU_W20_H050_pilot_20261031',
 'foil_M13_GPU_R2':R/'M13_wave_direct_20261031'/'M13_GPU_W20_H050_pilot_20261031_r2',
}
def js(p):
 try:return json.loads(p.read_text(encoding='utf-8-sig'))
 except (OSError,ValueError):return {}
def num(x):
 try:v=float(x);return v if math.isfinite(v) else None
 except (TypeError,ValueError):return None
def readcsv(p):
 try:
  with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
 except OSError:return []
def sh(p):return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
report={'at':datetime.now().astimezone().isoformat(),'scope':'Read-only log/history comparison, not convergence or wave acceptance','cases':{}}
for name,p in CASES.items():
 h=readcsv(p/'history.csv');last=h[-1] if h else {};log=(p/'star.log').read_text(encoding='utf-8',errors='replace') if (p/'star.log').exists() else ''
 complete_rows=[]
 for line in log.splitlines():
  a=line.split()
  if len(a)>=8 and a[0].isdigit() and int(a[0])%10==0 and all(num(x) is not None for x in a[1:8]):complete_rows.append({'iteration':int(a[0]),'continuity_printed':num(a[1]),'water_printed':num(a[7])})
 warnings={}
 for monitor in re.findall(r'Non-finite value detected while computing values for Monitor (.*?)\.',log):warnings[monitor]=warnings.get(monitor,0)+1
 finite_interface=[r for r in h if num(r.get('interface_CFL')) is not None]
 timing=[]
 for a,b in zip(h[-101:],h[-101:][1:]):
  if num(a.get('step')) is not None and num(b.get('step')) is not None and float(b['step'])-float(a['step'])==1:
   ta,tb=num(a.get('wall_s')),num(b.get('wall_s'))
   if ta is not None and tb is not None and tb>ta:timing.append(tb-ta)
 report['cases'][name]={'directory':str(p),'raw_history_records':len(h),'completed_steps_from_history':num(last.get('step')),'last_time_s':num(last.get('time_s')),'last_speed_m_s':num(last.get('max_speed_m_s')),'last_CFL':num(last.get('max_CFL')),'last_water_m3':num(last.get('water_volume_m3')),'interface_CFL_first_finite_step':num(finite_interface[0].get('step')) if finite_interface else None,'legacy_nonfinite_by_monitor':warnings,'last_full_inner_block':complete_rows[-1] if complete_rows else None,'client_connection_reset':'Connection reset' in log,'macro_error':js(p/'macro_error.json'),'stage_receipt':js(p/'stage_result.json'),'completion':js(p/'completed.json'),'median_last_seconds_per_step':statistics.median(timing) if len(timing)>=30 else None,'timing_step_count':len(timing),'history_sha256_snapshot':sh(p/'history.csv'),'log_sha256_snapshot':sh(p/'star.log')}
report['findings']={
 'confirmed_software_setup_failure':'M13 R1 exits before any history/CFD step on Unexpected wave period. It does not test foil-wave numerical stability.',
 'confirmed_resource_guard_gap':'Old pressure-aligned frontend exited and locks were released while native PID6932 was alive/idle; identity-checked cleanup completed and preserved all data.',
 'not_proven':'Root cause of CPU1 communication loss or spatial mesh defect. Finite last recorded speed/CFL is not a field-wide convergence proof.',
 'residual_gate':'Read actual monitor normalization factors and unnormalized values before interpreting huge printed residuals. Audit compiled but its launch correctly refused due to concurrent M13 R2 GPU ownership.',
 'R2_scope':'Separate existing controller launched M13 R2. Do not duplicate, edit active macro, or label 1200 steps x .0004s as wave arrival or 20 periods.',
 'R2_period_caution':'R2 uses 20/23.612 only to plan inlet ramp. Its setup wave_period_s is not an independently verified STAR FifthOrder period; phase assessment must use local gauges/actual native period.',
 'rebuild_gate':'No measured mesh defect currently warrants wholesale rebuilding. A clean CPU1 configuration may later isolate legacy-report/repartition effects, but only within approved recovery budgets and platform authorization.',
 'preserve':'F campaign_hold, HF, original simulations, and STOP markers unchanged.'}
path=D/'failure_comparison.json';path.write_text(json.dumps(report,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
for n,v in report['cases'].items():print(n,'steps=',v['completed_steps_from_history'],'t=',v['last_time_s'],'CFL=',v['last_CFL'],'s/step=',v['median_last_seconds_per_step'])
print('SAVED',path)
