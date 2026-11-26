package macro;

import java.nio.file.Files;
import java.nio.file.Path;
import star.base.report.Monitor;
import star.base.report.MonitorData;
import star.base.report.PlotableMonitor;
import star.common.StarMacro;

/** Read saved native monitor samples without executing any simulation steps. */
public class NwarNativeExport extends StarMacro {
  @Override public void execute() {
    Path out=Path.of(System.getenv("NWAR_NATIVE_EXPORT"));
    try {
      Files.createDirectory(out);
      for (Monitor monitor:getActiveSimulation().getMonitorManager().getObjects()) {
        String name=monitor.getPresentationName();
        if (!(monitor instanceof PlotableMonitor) || !name.startsWith("NWAR native ")) continue;
        String key=name.substring("NWAR native ".length());
        if (!key.matches("[A-Za-z0-9_]+")) throw new IllegalStateException("Unexpected native monitor name");
        PlotableMonitor plot=(PlotableMonitor)monitor;
        MonitorData data=plot.getAllSamples();
        double[] x=data.getXValues(),y=data.getYValues();
        if(x.length!=y.length)throw new IllegalStateException("Monitor axes differ: "+key);
        try(var f=Files.newBufferedWriter(out.resolve(key+".csv"))){
          f.write("sample_x,value\n");
          for(int i=0;i<x.length;i++)f.write(x[i]+","+y[i]+"\n");
        }
        Files.writeString(out.resolve(key+".axis"),plot.getXAxisName());
      }
      Files.writeString(out.resolve("final_time.txt"),Double.toString(getActiveSimulation().getSolution().getPhysicalTime()));
    } catch (java.io.IOException e) {
      throw new RuntimeException(e);
    }
  }
}
