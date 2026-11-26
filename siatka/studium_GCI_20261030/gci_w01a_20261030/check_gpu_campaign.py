from pathlib import Path
import py_compile,json
O=Path(__file__).resolve().parent
py_compile.compile(str(O/'gpu_calm_study.py'),doraise=True)
import gpu_calm_study as g
old=O/'force_stabilization_20261029/calm_settle_G10_F'
cpu=g.runner.rawrows(old/'history.csv')[:20]
gpu=[dict(r,wall_seconds=r['wall_seconds']/10) for r in cpu]
assert g.compare_hardware(cpu,gpu)['pass_check']
gpu[5]['CL_total']*=1.01
assert not g.compare_hardware(cpu,gpu)['pass_check']
gpu[5]['physical_time_s']+=.00001
try:g.compare_hardware(cpu,gpu)
except RuntimeError:pass
else:raise AssertionError('Unmatched times accepted')
print(json.dumps({'code_and_equivalence_checks':'passed','CPU_completed':g.read(old/'completed.json') if (old/'completed.json').exists() else None,'CPU_export_complete':(old/'EXPORT_OK.json').exists(),'CPU_controller_alive':g.alive(40380),'CPU_launcher_alive':g.alive(34872),'gpu_free_MiB':g.gpu_memory_free()}))
