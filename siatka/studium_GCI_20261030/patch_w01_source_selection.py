from pathlib import Path
H=Path(__file__).resolve().parent;O=H/'gci_w01a_20261030';p=O/'cpu_study.py'
t=p.read_text()
anchor="def select_source():\n state('waiting_for_completed_full_height_W01a_checkpoint',GPU_run_untouched=True)"
replace="""def select_source():
 global W
 state('waiting_for_completed_full_height_W01a_checkpoint',GPU_run_untouched=True)"""
assert anchor in t;t=t.replace(anchor,replace)
anchor="  if (W/'completed.json').exists():"
extra="""  runtime=read(R/'wave_foil_run_state.json') if (R/'wave_foil_run_state.json').exists() else {}
  candidate=Path(runtime.get('directory',str(W)))
  allowed=Path(r'E:\\ntnu\\quasi2d_waves_20261029').resolve()
  if candidate.resolve().parent!=allowed or not candidate.name.startswith('W01a_'):raise RuntimeError('Current wave runtime is outside the requested W01a scope')
  W=candidate
"""
# Use a raw replacement string so Windows path backslashes remain literal Python code.
extra=extra.replace("Path(r'E:\n", "Path(r'E:\\n")
assert t.count(anchor)==1
t=t.replace(anchor,extra+anchor)
t=t.replace("cp.get('time_s',0)>=act['ramp_end_time_s']+.2*act['planning_full_height_period_s']","cp.get('time_s',0)>=max(act['ramp_end_time_s']+.2*act['planning_full_height_period_s'],act['activation_time_s']+act['planning_full_height_period_s'])")
p.write_text(t,encoding='utf-8')
print('Controller will freeze one completed checkpoint from the current W01a runtime, including its exact startup definition.')
