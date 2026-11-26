from pathlib import Path
import json
O=Path(__file__).resolve().parent
R=Path(r'F:\ntnu\mesh_screening_20261028\force_stabilization_20261029')
t=(R/'conservation_probe_20261029/ContinueUntilSettled.java').read_text()
t=t.replace('ContinueUntilSettled','ContinueGCI')
t=t.replace('if(steps%500==0)', 'if(steps%Math.max(1,(int)Math.round(.2/dt))==0)')
anchor='if(Math.abs(d-p-v)>Math.max(.01,Math.abs(d)*1e-4))'
assert t.count(anchor)==1
t=t.replace(anchor,'''if(co>Double.parseDouble(System.getenv().getOrDefault("NTNU_GCI_MAX_CFL","1e8"))||ci>Double.parseDouble(System.getenv().getOrDefault("NTNU_GCI_INTERFACE_CFL","1e8"))){state="CFL_guard";break;}
          '''+anchor)
# Only project-controlled directories are written by this copy.
(O/'ContinueGCI.java').write_text(t,encoding='utf-8')
plan={'objective':'Quantify mesh uncertainty for lightweight M09; refined grids are reference levels for future coarsening.',
'restarts':{'M09':str(R/'matched_endpoint_20261029/M09_SO_common_t2040_r1/final.sim'),'new_grids':'Higher-order stencil mapping of the same saved M09 solution at t=2.04 s, no cold initialization.'},
'mesh_family':['M09','G09_M','G09_F'],'spanwise_layers':1,'GCI_effective_dimension':2,
'common_initial_dt_s':.0001,'order':'SECOND_ORDER','inner_iterations':10,
'CFL_policy':{'flow_max':10,'interface_max':1,'VOF_effective_interface_max':.5,'interpretation':'Project accuracy screening limits for implicit URANS, not a universal explicit CFL stability bound or a quoted Fluid Mechanics 101 numeric limit. Verify dt/2 on the fine grid. Common dt may decrease after pilots.'},
'yplus_policy':{'target':1,'local_exceedances_allowed_by_user':True,'check':'Record maxima, spatial location and wall-length weighted distribution. Do not block solely because tiny local regions exceed y+=1; assess their impact through mesh convergence.'},
'pilot_duration_s':.01,'first_common_target_s':3.0,'averaging_windows_s':[[2.4,2.6],[2.6,2.8],[2.8,3.0]],'max_window_mean_shift_pct':.05,
'nuisance_fraction_of_smallest_mesh_difference':.1,'extend_common_target_s':.6,'max_common_target_s':5.4,
'controls':{'source':'Same fine-grid settled checkpoint','baseline':{'dt':'common','inner':10},'time_step':{'dt':'common/2','inner':10},'inner_iterations':{'dt':'common','inner':20},'duration_s':.8,'discard_s':.2,'compare_last_s':.6},
'quality_policy':'Audit actual CGNS geometry, all depth bands, in-plane resolution, topology, positive volumes and boundary/physics continuity before launching the flow family.',
'sources':['https://www.fluidmechanics101.com/pdf/calculators.pdf','https://www.youtube.com/watch?v=1gSHN99I7L4','https://www.youtube.com/watch?v=WBWY46ynRk0','https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html'],
'outputs':'Existing results reused; machine-readable logs, checks and GCI data only. No report.'}
(O/'study_plan.json').write_text(json.dumps(plan,indent=2),encoding='utf-8')
print('Prepared controlled flow macro and plan')
