"""Fresh PRE W04 startup explicitly requested by the user; no field mapping."""
from common import *
from pre_w04 import PRE
from build_pre_w04 import replace,CP,JAVAC
import subprocess

def build():
 s=(PRE/'PreW04Calm.java').read_text(encoding='utf8').replace('PreW04Calm','PreW04Fresh')
 # Use the accepted C01 simulation as the physics/BC container. Fields are
 # explicitly cleared before installing the already-audited expanded mesh.
 s=replace(s,'      fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");','''      fv=(FvRepresentation)s.getRepresentationManager().getObject("Volume Mesh");
      if(fv.getCellCount()!=309441)throw new IllegalStateException("Original C01 mesh container required");
      s.getSolution().clearSolution(Solution.Clear.History,Solution.Clear.Fields,Solution.Clear.Trn);
      if(s.getSolution().isInitialized())throw new IllegalStateException("Fields were not cleared before mesh replacement");
      s.getImportManager().importMeshFiles(List.of(System.getenv("PRE_W04_MESH")));
      Region donor=s.getRegionManager().getRegion("fluid 2");
      s.getMeshManager().replaceMesh(fluid,donor,true);
      for(Region r:new ArrayList<Region>(s.getRegionManager().getRegions()))if(r.getPresentationName().equals("fluid 2"))s.getRegionManager().removeObjects(List.of(r));
      foil=fluid.getBoundaryManager().getBoundary("HF_012_wall");
      if(s.getSolution().isInitialized())throw new IllegalStateException("Unexpected field initialization during mesh replacement");
      save("C01_mesh_replacement.json",Map.of("original_cells",309441,"expanded_cells",fv.getCellCount(),"C01_physics_and_boundaries_preserved",true,"fields_cleared_before_replacement",true,"solution_interpolation_used",false));''')
 fresh=(CLEAN/'CleanC01R3.java').read_text(encoding='utf8')
 fn=fresh[fresh.index('  private void configureFreshCalm('):fresh.index('  private MinReport alphaMin,pressureMin,densityMin;')]
 fn=fn.replace('fv.getCellCount()!=309441','fv.getCellCount()!=572176')
 fn=fn.replace('a.put("forcing_lengths_unchanged",true);','a.put("forcing_length_m",40);a.put("damping_length_m",40);')
 fn=fn.replace('    fluid.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(calm);','''    fluid.getValues().get(ForcingVofWaveSpecification.class).setForcingVofWave(calm);
    inlet.getValues().get(VofWaveForcingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(40);
    fluid.getBoundaryManager().getBoundary("DOMAIN.outlet").getValues().get(VofWaveDampingLength.class).getMethod(ConstantScalarProfileMethod.class).getQuantity().setValue(40);''')
 s=replace(s,'  private MinReport alphaMin,pressureMin,densityMin;',fn+'  private MinReport alphaMin,pressureMin,densityMin;')
 s=replace(s,'Math.abs(target-(expectedStart+2.0))>1e-8||initialize','target!=8.0||!initialize')
 s=replace(s,'if(Math.abs(startTime-expectedStart)>dt*.1)throw new IllegalStateException("Unexpected restart time "+startTime);','// Fresh initialization below resets physical time on this disposable copy only.')
 s=replace(s,'if(Math.abs(rho-1000)>1e-6)throw new IllegalStateException("Unexpected reference density");','// Native material and wave densities are set to the original C01 contract below.')
 s=replace(s,'verifySavedC01Calm(pc,calm);','configureFreshCalm(pc,calm);rho=1000;')
 s=replace(s,'if(Math.abs(startTime-expectedStart)>1e-7||fv.getCellCount()!=expectedCells)','if(Math.abs(startTime)>1e-10||fv.getCellCount()!=expectedCells)')
 s=s.replace('PRE W04: original C01 mapped to expanded mesh; no wave, no reinitialization, no new Q reference; 0.2 s windows and 0.5% stability/C01 gates','PRE W04: fresh flat water from rest, 1 s cosine current/wind ramp to 18 m/s, original C01 remains the sole Q reference; 0.2 s stability and 0.5% C01 gates')
 s=s.replace('audit.put("fresh_fields",false)','audit.put("fresh_fields",true)').replace('audit.put("restart_from_saved_fields",true)','audit.put("restart_from_saved_fields",false)')
 s=s.replace('audit.put("C01_lineage",','audit.put("C01_reference",').replace('audit.put("startup_current_ramp_s",0.0)','audit.put("startup_current_ramp_s",1.0)').replace('audit.put("settling_eligible_after_s",.6)','audit.put("settling_eligible_after_s",1.6)')
 s=s.replace('"reinitialized",false','"reinitialized",true').replace('"no_reinitialize",true','"fresh_initialization_authorized",true')
 s=replace(s,'waterAtRestart=Double.parseDouble(System.getenv("PRE_W04_EXPECTED_WATER"));','waterAtRestart=waterBudget.getReportMonitorValue();\n      if(!Double.isFinite(waterAtRestart)||waterAtRestart<76||waterAtRestart>78)throw new IllegalStateException("Fresh water inventory mismatch");')
 s=replace(s,'if(!Double.isFinite(actual)||Math.abs(actual-18.0)>1e-5)throw new IllegalStateException("Actual post-step inlet speed not 18m/s: "+actual);','if(!Double.isFinite(actual)||Math.abs(actual-rampSpeed(t))>1e-5)throw new IllegalStateException("Actual inlet speed differs from startup ramp: "+actual);')
 s=replace(s,'"expected_m_s",18.0','"expected_m_s",rampSpeed(t)')
 s=replace(s,'if(!Double.isFinite(imposedU)||(t>=1.001&&Math.abs(imposedU-18)>.00001))return false;','if(!Double.isFinite(imposedU)||Math.abs(imposedU-rampSpeed(t))>.00001)return false;')
 s=replace(s,'boolean eligible=s.getSolution().getPhysicalTime()>=startTime+.6-1e-9;','boolean eligible=s.getSolution().getPhysicalTime()>=1.6-1e-9;')
 s=replace(s,'  private void save(String file,Map<String,?> info)', '  private double rampSpeed(double t){return 18*.5*(1-Math.cos(Math.PI*Math.min(1,Math.max(0,t))));}\n  private void save(String file,Map<String,?> info)')
 s=replace(s,'      s.saveState(out.resolve("final.sim").toString());','''      if(state.equals("calm_gate_passed")){calm.getCurrent().setComponents(18,0,0);calm.getWind().setComponents(18,0,0);}
      s.saveState(out.resolve("final.sim").toString());''')
 # An open-domain startup can accumulate water. Guard the flux-corrected
 # inventory error with the same 0.25 m3 tolerance, preserving all field limits.
 from pre_balance import patch_balance
 s=patch_balance(s)
 # Retain first-step and numerical health checks; all normalization stays at U=18.
 path=PRE/'PreW04Fresh.java';path.write_text(s,encoding='utf8')
 p=subprocess.run([JAVAC,'-cp',CP,'-d',str(PRE/'compiled'),str(path)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
 receipt=dict(ok=p.returncode==0,macro_sha256=sha(path),fresh_initialization=True,ramp_s=1.,messages=p.stderr[-4000:])
 write(PRE/'fresh_compile_receipt.json',receipt)
 if p.returncode:raise RuntimeError(p.stderr)
 print(json.dumps(receipt),flush=True)

if __name__=='__main__':build()
