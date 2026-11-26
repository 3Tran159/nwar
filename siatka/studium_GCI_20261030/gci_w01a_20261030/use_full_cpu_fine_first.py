from pathlib import Path
import json,datetime,py_compile,shutil
O=Path(__file__).resolve().parent;H=O.parent
def update(p,edits,backup):
 if not (p.parent/backup).exists():shutil.copy2(p,p.parent/backup)
 t=p.read_text()
 for before,after in edits:
  if t.count(before)!=1:raise RuntimeError('Expected one occurrence in '+p.name+': '+before[:100])
  t=t.replace(before,after)
 p.write_text(t,encoding='utf-8');py_compile.compile(str(p),doraise=True)
update(O/'cpu_study.py',[
 ('WORKERS=8;AFFINITY=1020 # CPUs 2-9; W01a\'s existing GPU driver uses CPUs 0-1.','WORKERS=22;AFFINITY=16777212 # CPUs 2-23 for this study; CPUs 0-1 reserved for C01.'),
 ('Every mesh level and numerical control uses CPU8.','Every mesh level and numerical control uses CPU22.'),
 ('subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS','subprocess.CREATE_NO_WINDOW|subprocess.NORMAL_PRIORITY_CLASS')
],'cpu_study_before_cpu22.py.txt')
update(O/'cpu_calm_study.py',[
 ("LEVELS=['W01a','G10_M','G10_F']","LEVELS=['W01a','G10_M','G10_F']\nRUN_ORDER=['G10_F','G10_M','W01a'] # Fine reference first; keep mathematical GCI ordering coarse/medium/fine."),
 ("  for m in LEVELS:\n   out,d=flow('calm_pilot_","  for m in RUN_ORDER:\n   out,d=flow('calm_pilot_"),
 (" for m in LEVELS:\n  p=pilots[m]"," for m in RUN_ORDER:\n  p=pilots[m]"),
 ("  for m in LEVELS:\n   t=summaries[m]","  for m in RUN_ORDER:\n   t=summaries[m]")
],'cpu_calm_before_fine_first.py.txt')
update(H/'build_w01_gci.py',[
 ('*saved_options(2)','*saved_options(22)'),
 ("{'pid':p.pid,'CPU_workers':2}","{'pid':p.pid,'CPU_workers':22,'CPU_affinity_mask':16777212}"),
 ("def run_star(source,macro,log,timeout=7200):","""def run_star(source,macro,log,timeout=7200):
 import ctypes
 kernel=ctypes.windll.kernel32;kernel.GetCurrentProcess.restype=ctypes.c_void_p;kernel.SetProcessAffinityMask.argtypes=[ctypes.c_void_p,ctypes.c_size_t]
 if not kernel.SetProcessAffinityMask(kernel.GetCurrentProcess(),16777212):raise RuntimeError('CPU allocation failed: C01 cores must remain excluded')""")
],'build_w01_gci_before_cpu22.py.txt')
update(H/'postbuild_w01_gci.py',[('k.GetCurrentProcess(),1020','k.GetCurrentProcess(),16777212')],'postbuild_w01_gci_before_cpu22.py.txt')
plan=json.loads((O/'study_plan.json').read_text())
plan.update(CPU_workers=22,CPU_logical_processors=list(range(2,24)),reserved_for_C01=[0,1],execution_order=['G10_F','G10_M','W01a'],target_production_cell_count=300000,current_light_candidate_cells=317277,fine_reference_cells=1154199,resource_change_at=datetime.datetime.now().astimezone().isoformat())
plan.pop('initial_CPU_workers',None)
(O/'study_plan.json').write_text(json.dumps(plan,indent=2))
import cpu_calm_study as c
assert c.WORKERS==22 and c.runner.AFFINITY==16777212 and c.RUN_ORDER[0]=='G10_F'
print('CPU22 on cores 2-23, C01 cores 0-1 excluded. Fine-reference-first order verified. Existing mapping process allowed to complete without losing its work.')
