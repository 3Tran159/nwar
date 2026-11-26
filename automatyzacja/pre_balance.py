"""Inventory guard for an open, fixed-volume two-phase domain during startup."""
from common import *
from analysis import numeric_rows
import numpy as np

def balance_seed(folders):
 rows=[]
 for folder in folders:
  data=numeric_rows(Path(folder)/'conservation.csv')
  cutoff=read(Path(folder)/'history_cutoff.json').get('time_s')
  if data and cutoff is not None:
   keep=data['time_s']<=float(cutoff)+1e-9;data={k:v[keep] for k,v in data.items()}
  if data:rows.append(np.column_stack([data[k] for k in ('time_s','mass_kg','water_volume_m3','net_outward_mass_kg_s')]))
 values=np.concatenate(rows)
 values=values[np.r_[True,np.diff(values[:,0])>1e-9]]
 assert np.isfinite(values).all() and np.all(np.abs(np.diff(values[:,0])-.0004)<.00004),'Incomplete conservation history'
 integral=float(np.sum((values[1:,3]+values[:-1,3])*.5*np.diff(values[:,0])))
 initial_water,initial_mass=float(values[0,2]),float(values[0,1])
 error=float(values[-1,1]-initial_mass+integral)
 return dict(initial_water_m3=initial_water,initial_mass_kg=initial_mass,last_time_s=float(values[-1,0]),
             last_net_flux_kg_s=float(values[-1,3]),integrated_net_outflow_kg=integral,
             last_water_m3=float(values[-1,2]),mass_closure_error_kg=error,
             water_closure_error_m3=float(values[-1,2]-initial_water+integral/(1000-1.2)),
             seed_csv=','.join(map(str,[initial_water,initial_mass,values[-1,0],values[-1,3],integral])))

def patch_balance(s):
 from build_pre_w04 import replace
 s=replace(s,'  private double waterAtRestart=Double.NaN;', '''  private double waterAtRestart=Double.NaN;
  private double balanceWater,balanceMass,balanceTime=Double.NaN,balanceFlux,balanceIntegral=0,expectedWater=Double.NaN;
  private double calmWaveLevelMax=Double.NaN;''')
 s=replace(s,'      prepareHealthAndGauges(vf);','''      prepareHealthAndGauges(vf);
      String seed=System.getenv("PRE_W04_BALANCE_SEED");
      if(seed!=null){String[] b=seed.split(",");if(b.length!=5)throw new IllegalStateException("Invalid conservation seed");
        balanceWater=Double.parseDouble(b[0]);balanceMass=Double.parseDouble(b[1]);balanceTime=Double.parseDouble(b[2]);balanceFlux=Double.parseDouble(b[3]);balanceIntegral=Double.parseDouble(b[4]);
        if(Math.abs(balanceTime-startTime)>1e-8)throw new IllegalStateException("Conservation seed time mismatch");}
      Files.writeString(out.resolve("mass_balance.csv"),"time_s,water_m3,expected_water_from_flux_m3,water_closure_error_m3,mass_closure_error_kg,integrated_net_outflow_kg\\n");''')
 s=replace(s,'    if(!Double.isFinite(nowWater)||Math.abs(nowWater-waterAtRestart)>.25)return false;', '''    if(!Double.isFinite(nowWater)||!Double.isFinite(expectedWater)||Math.abs(nowWater-expectedWater)>.25){
      save("field_guard.json",Map.of("reason","water_balance_closure","time_s",t,"water_m3",nowWater,"expected_from_flux_m3",expectedWater,"error_limit_m3",.25));return false;}''')
 s=replace(s,'    for(int i=0;i<gx.length;i++){','    calmWaveLevelMax=0;\n    for(int i=0;i<gx.length;i++){')
 s=replace(s,'      if(!Double.isFinite(eta)||Math.abs(eta)>.75)return false;', '''      if(!Double.isFinite(eta))return false;
      calmWaveLevelMax=Math.max(calmWaveLevelMax,Math.abs(eta));''')
 s=replace(s,'    double nowWater=waterBudget.getReportMonitorValue();','''    double nowWater=waterBudget.getReportMonitorValue();
    save("water_readiness.json",Map.of("time_s",t,"ramp_complete",t>=1.0-1e-9,"water_m3",nowWater,
      "initial_water_m3",balanceWater,"water_difference_m3",nowWater-balanceWater,"max_abs_eta_m",calmWaveLevelMax,
      "ready_for_wave",t>=1.0-1e-9&&Math.abs(nowWater-balanceWater)<=.25&&calmWaveLevelMax<=.75,
      "startup_level_changes_stop_solver",false));''')
 s=replace(s,'    boolean eligible=s.getSolution().getPhysicalTime()>=1.6-1e-9;', '''    boolean eligible=s.getSolution().getPhysicalTime()>=1.6-1e-9;
    double inventory=waterBudget.getReportMonitorValue();
    boolean waterReady=eligible&&Double.isFinite(inventory)&&Math.abs(inventory-balanceWater)<=.25&&Double.isFinite(calmWaveLevelMax)&&calmWaveLevelMax<=.75;
    check.put("water_inventory_m3",inventory);check.put("water_difference_m3",inventory-balanceWater);
    check.put("max_abs_eta_m",calmWaveLevelMax);check.put("water_ready_for_wave",waterReady);
    pass &= waterReady;''')
 anchor='    Files.writeString(out.resolve("conservation.csv"),s.getSolution().getPhysicalTime()+","+mass+","+water+","+net+","+inward+"\\n",StandardOpenOption.APPEND);'
 s=replace(s,anchor,anchor+'''
    double bt=s.getSolution().getPhysicalTime();
    if(Double.isNaN(balanceTime)){balanceWater=water;balanceMass=mass;}
    else{double gap=bt-balanceTime;if(Math.abs(gap-dt)>dt*.1)throw new IllegalStateException("Conservation time gap");balanceIntegral+=(net+balanceFlux)*.5*gap;}
    balanceTime=bt;balanceFlux=net;expectedWater=balanceWater-balanceIntegral/(1000.0-1.2);
    Files.writeString(out.resolve("mass_balance.csv"),bt+","+water+","+expectedWater+","+(water-expectedWater)+","+(mass-balanceMass+balanceIntegral)+","+balanceIntegral+"\\n",StandardOpenOption.APPEND);''')
 return s

def water_readiness(folders,balance):
 data=numeric_rows(Path(folders[-1])/'gauges.csv')
 if not data:return dict(ready=False,reason='Waiting for full probe record')
 latest=data['time_s'][-1];eta=data['eta_actual_m'][data['time_s']==latest]
 level=float(np.max(np.abs(eta)));difference=balance['last_water_m3']-balance['initial_water_m3']
 ready=bool(balance['last_time_s']>=1.6-1e-9 and abs(latest-balance['last_time_s'])<.0041
            and len(eta)==8 and np.isfinite(eta).all() and abs(difference)<=.25 and level<=.75)
 return dict(ready=ready,time_s=balance['last_time_s'],water_difference_m3=difference,max_abs_eta_m=level)
