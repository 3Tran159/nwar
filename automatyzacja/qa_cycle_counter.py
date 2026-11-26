"""Replay immutable measured wave gauges through the exact compiled Java counter."""
from common import *
import subprocess
source=(HERE/'NwarWave.java').read_text()
counter=source[source.index(' static final class FullCycleCounter {'):source.index('\n void loadPriorCycles')]
out=HERE/'qa/cycle_counter';out.mkdir(parents=True,exist_ok=True)
program='import java.util.*;import java.nio.file.*;\npublic class CounterReplay {\n'+counter+'''
 public static void main(String[] args)throws Exception{
  double T=Double.parseDouble(args[0]),H=Double.parseDouble(args[1]),eligible=Double.parseDouble(args[2]);
  int expected=Integer.parseInt(args[3]);FullCycleCounter c=new FullCycleCounter(T,H,eligible,.004);double last=-1e99;
  for(int k=4;k<args.length;k++){
   var lines=Files.readAllLines(Path.of(args[k]));var header=Arrays.asList(lines.get(0).split(","));
   int ti=header.indexOf("time_s"),xi=header.indexOf("x_m"),yi=header.indexOf("eta_actual_m");
   for(int i=1;i<lines.size();i++){var v=lines.get(i).split(",");double t=Double.parseDouble(v[ti]);
    if(Math.abs(Double.parseDouble(v[xi])+.5)<1e-7&&t>last+1e-8){c.observe(t,Double.parseDouble(v[yi]));last=t;}
   }
  }
  if(c.complete!=expected||c.gaps!=0)throw new IllegalStateException("Expected "+expected+" cycles without gaps, got "+c.complete+" gaps="+c.gaps);
  System.out.println("PASS measured_cycles="+c.complete+" restored_boundaries="+c.boundaries.size()+" gaps="+c.gaps);
 }
}
'''
(out/'CounterReplay.java').write_text(program,encoding='utf8')
jdk=Path('C:/Program Files/Eclipse Adoptium/jdk-25.0.3.9-hotspot/bin')
subprocess.run([str(jdk/'javac.exe'),str(out/'CounterReplay.java')],check=True,capture_output=True)
cases=[]
for name,L,H,expected,folders in [
 ('W02_original',20,.25,3,[EXISTING['W02']]),
 ('W03_original',30,.5,3,[EXISTING['W03']]),
 ('W03_with_extension',30,.5,4,[EXISTING['W03'],NIGHT/'W03_resume_plus1_v2_20261102_0841'])]:
 T=period(L)
 p=subprocess.run([str(jdk/'java.exe'),'-cp',str(out),'CounterReplay',str(T),str(H),str(T0+2*T+34.5*T/L),str(expected),*[str(f/'gauges.csv') for f in folders]],capture_output=True,text=True,check=True)
 cases.append(dict(case=name,expected=expected,result=p.stdout.strip()))
receipt=dict(at=now(),passed=True,macro_sha256=sha(HERE/'NwarWave.java'),cases=cases,no_solver_started=True)
write(HERE/'qa/cycle_counter_result.json',receipt)
print(json.dumps(receipt))
