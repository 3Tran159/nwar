package macro;

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;
import star.common.*;

/** Apply the authorized surface rule to a copy of a saved native wave. */
public class NwarNativeSurfaceRule extends StarMacro {
  @Override public void execute() {
    Simulation sim = getActiveSimulation();
    Path out = Path.of(System.getenv("NWAR_SURFACE_RULE_OUT"));
    double expected = Double.parseDouble(System.getenv("NWAR_SURFACE_RULE_TIME"));
    double time = sim.getSolution().getPhysicalTime();
    int iteration = sim.getSimulationIterator().getCurrentIteration();
    if (Math.abs(time-expected)>1e-7 || Files.exists(out.resolve("native_ready.sim")))
      throw new IllegalStateException("Unexpected surface-rule source or existing output");
    Map<SolverStoppingCriterion,Boolean> others = new LinkedHashMap<>();
    int surfaceRules = 0;
    for (SolverStoppingCriterion rule : sim.getSolverStoppingCriterionManager().getObjects()) {
      if (rule instanceof MonitorIterationStoppingCriterion
          && ((MonitorIterationStoppingCriterion)rule).getMonitor().getPresentationName().matches("NWAR native eta_\\d+")) {
        rule.setIsUsed(false);
        if (rule.getIsUsed()) throw new IllegalStateException("Surface rule remains active");
        surfaceRules++;
      } else {
        others.put(rule,rule.getIsUsed());
      }
    }
    if (surfaceRules!=22) throw new IllegalStateException("Expected eleven native probes with two surface bounds each");
    for (var entry : others.entrySet())
      if (entry.getKey().getIsUsed()!=entry.getValue()) throw new IllegalStateException("Another stopping rule changed");
    if (Math.abs(time-sim.getSolution().getPhysicalTime())>1e-12
        || iteration!=sim.getSimulationIterator().getCurrentIteration())
      throw new IllegalStateException("The surface-rule preparation advanced the solver");
    try {
      sim.saveState(out.resolve("native_ready.sim").toString());
      Files.writeString(out.resolve("native_surface_rule_applied.json"),
          "{\"passed\":true,\"surface_magnitude_limit_enabled\":false,\"time_s\":"+time+
          ",\"iteration\":"+iteration+",\"steps_advanced\":0,\"surface_rules_disabled\":"+surfaceRules+
          ",\"other_stopping_rules_verified\":"+others.size()+"}\n");
    } catch (java.io.IOException e) {
      throw new RuntimeException(e);
    }
  }
}
