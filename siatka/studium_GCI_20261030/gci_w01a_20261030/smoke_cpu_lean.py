from pathlib import Path
import cpu_study as s
s.state=lambda status,**kw:print(status,kw,flush=True)
source=Path(r'E:\ntnu\quasi2d_waves_20261029\W01a_W20L4_M10_inlet_fullheight_restart_r3\checkpoint_startup_t0.020.sim')
out,diag=s.flow('smoke_cpu8_lean_monitors',source,.02,.0203,.0001,10,317277,.8472673206891129,True)
old=s.rawrows(s.O/'force_stabilization_20261029/smoke_cpu8_W01a/history.csv')
new=s.rawrows(out/'history.csv')
errors={k:max(abs(x[k]-y[k])/max(abs(x[k]),1e-12) for x,y in zip(old,new)) for k in ['CD','CL_total','pressure_drag_N','viscous_drag_N']}
timing={'old_last_step_s':old[-1]['wall_seconds']-old[-2]['wall_seconds'],'new_last_step_s':new[-1]['wall_seconds']-new[-2]['wall_seconds']}
s.write(s.O/'monitor_cleanup_check.json',{'relative_force_differences':errors,'timing':timing,'physics_unchanged_within_1e-7':max(errors.values())<1e-7,'steps':len(new),'gpu':False})
print(errors,timing,flush=True)
assert max(errors.values())<1e-7
