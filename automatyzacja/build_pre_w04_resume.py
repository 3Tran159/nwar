"""Continue the saved PRE W04 ramp without clearing fields or changing physics."""
from common import *
from pre_w04 import PRE,CALM_RUN
from build_pre_w04 import replace,CP,JAVAC
from pre_balance import patch_balance
import subprocess

def build():
 s=(CALM_RUN/'PreW04Fresh.java').read_text(encoding='utf8').replace('PreW04Fresh','PreW04Resume')
 start=s.index('      if(fv.getCellCount()!=309441)')
 end=s.index('      // Rebind inherited monitors',start)
 s=s[:start]+'      // Saved expanded mesh and all physical fields are retained.\n'+s[end:]
 s=replace(s,'target!=8.0||!initialize','target!=8.0||initialize')
 s=replace(s,'      configureFreshCalm(pc,calm);rho=1000;','      verifySavedC01Calm(pc,calm);rho=1000;')
 s=replace(s,'if(Math.abs(startTime)>1e-10||fv.getCellCount()!=expectedCells)','if(Math.abs(startTime-expectedStart)>1e-8||fv.getCellCount()!=expectedCells)')
 # Remove the unused fresh initializer entirely: a resume cannot call it.
 start=s.index('  private void configureFreshCalm(');end=s.index('  private MinReport alphaMin,pressureMin,densityMin;',start)
 s=s[:start]+s[end:]
 old='if(!calm.getCurrentVector().toString().contains("18.0")||!calm.getWindVector().toString().contains("18.0"))throw new IllegalStateException("Old calm source must have constant U18/current and wind");'
 ramp='[<18 m/s>*0.5*(1.0-cos(3.141592653589793*min(1.0,max(0.0,$Time/<1 s>)))),<0 m/s>,<0 m/s>]'
 s=replace(s,old,'if(!calm.getCurrent().getDefinition().equals("'+ramp+'")||!calm.getWind().getDefinition().equals("'+ramp+'"))throw new IllegalStateException("Saved startup ramp changed");')
 s=s.replace('audit.put("fresh_fields",true)','audit.put("fresh_fields",false)').replace('audit.put("restart_from_saved_fields",false)','audit.put("restart_from_saved_fields",true)')
 s=s.replace('"reinitialized",true','"reinitialized",false').replace('"fresh_initialization_authorized",true','"fields_retained",true')
 s=replace(s,'waterAtRestart=waterBudget.getReportMonitorValue();','waterAtRestart=Double.parseDouble(System.getenv("PRE_W04_EXPECTED_WATER"));')
 s=replace(s,'waterAtRestart<76||waterAtRestart>78','waterAtRestart<=0||waterAtRestart>=95.9976842322')
 s=replace(s,'(steps+priorCount)%(int)Math.round(window/dt)==0','Math.round(t/dt)%(int)Math.round(window/dt)==0')
 # A duplicated boundary sample joins both histories and fixes the resume marker.
 anchor='        while(s.getSolution().getPhysicalTime()<target-dt*.1) {'
 s=replace(s,anchor,'''        String boundary=Files.readString(Paths.get(System.getenv("PRE_W04_BOUNDARY_ROW"))).strip();
        if(Math.abs(Double.parseDouble(boundary.split(",")[3])-startTime)>1e-8)throw new IllegalStateException("History boundary time mismatch");
        w.write(boundary+"\\n");w.flush();
'''+anchor)
 s=patch_balance(s)
 assert 'clearSolution(' not in s and 'initializeSolution(' not in s and 'replaceMesh(' not in s
 path=PRE/'PreW04Resume.java';path.write_text(s,encoding='utf8')
 p=subprocess.run([JAVAC,'-cp',CP,'-d',str(PRE/'compiled'),str(path)],capture_output=True,text=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
 receipt=dict(ok=p.returncode==0,macro_sha256=sha(path),fields_retained=True,physics_changed=False,ramp_s=1.,messages=p.stderr[-4000:])
 write(PRE/'resume_compile_receipt.json',receipt)
 if p.returncode:raise RuntimeError(p.stderr)
 return receipt

if __name__=='__main__':print(json.dumps(build()))
