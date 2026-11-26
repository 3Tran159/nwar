from pathlib import Path
import cpu_study as s
s.state=lambda status,**kw:print(status,kw,flush=True)
source=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_inlet_fullheight_restart_r3\checkpoint_startup_t0.020.sim')
out,diag=s.flow('smoke_cpu8_W01a',source,.02,.0203,.0001,10,317277,.8472673206891129,True)
setup=s.read(out/'setup.json');assert setup['gpu_count']==0
s.write(s.O/'cpu_smoke_result.json',{'pass':True,'workers':8,'gpu_count':setup['gpu_count'],'steps':s.read(out/'completed.json')['steps'],'directory':str(out),'wave':s.read(out/'wave_audit.json'),'diagnostics':diag,'purpose':'Bounded execution check on an immutable copy; not a convergence result.'})
print('CPU-only wave continuation and export check passed',flush=True)
