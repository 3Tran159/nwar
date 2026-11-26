package macro;

import java.nio.file.Files;
import java.nio.file.Path;
import star.base.report.Report;
import star.base.report.ReportMonitor;
import star.common.*;

/** Prepare a short, isolated native batch test from an already configured wave save. */
public class NwarNativePilot extends StarMacro {
  private ReportMonitor monitor(Simulation sim, String reportName) {
    Report report = sim.getReportManager().getReport(reportName);
    if (report == null) throw new IllegalStateException("Missing saved report " + reportName);
    ReportMonitor monitor = report.createMonitor();
    monitor.setPresentationName("NWAR native " + reportName);
    monitor.getTriggerOption().setSelected(MonitorTriggerOption.TIME_STEP);
    monitor.getStarUpdate().getTimeStepUpdateFrequency().setTimeSteps(1);
    monitor.setEnabled(true);
    return monitor;
  }

  private void bound(SolverStoppingCriterionManager criteria, ReportMonitor monitor,
                     boolean maximum, double limit) {
    MonitorIterationStoppingCriterion rule = criteria.createIterationStoppingCriterion(monitor);
    rule.getCriterionOption().setSelected(maximum
        ? MonitorIterationStoppingCriterionOption.MAXIMUM : MonitorIterationStoppingCriterionOption.MINIMUM);
    ((MonitorIterationStoppingCriterionLimitType)rule.getCriterionType()).getLimit().setValue(limit);
    rule.setInnerIterationCriterion(false);
    rule.setOuterIterationCriterion(true);
    rule.getLogicalOption().setSelected(SolverStoppingCriterionLogicalOption.OR);
    rule.setIsUsed(true);
  }

  @Override public void execute() {
    Simulation sim = getActiveSimulation();
    Path output = Path.of(System.getenv("NWAR_NATIVE_PILOT_OUT"));
    if (!output.isAbsolute() || Files.exists(output))
      throw new IllegalArgumentException("Expected a new absolute pilot output path.");
    double start = sim.getSolution().getPhysicalTime();
    if (Math.abs(start - 5.8) > 1e-7)
      throw new IllegalStateException("Pilot source does not match the prepared wave start.");

    SolverStoppingCriterionManager criteria = sim.getSolverStoppingCriterionManager();
    PhysicalTimeStoppingCriterion end = null;
    for (SolverStoppingCriterion criterion : criteria.getObjects()) {
      if (criterion instanceof PhysicalTimeStoppingCriterion) {
        end = (PhysicalTimeStoppingCriterion)criterion;
      } else if (criterion instanceof StepStoppingCriterion) {
        criterion.setIsUsed(false);
      }
    }
    if (end==null) throw new IllegalStateException("Missing native physical-time stop.");
    double endTime = start + 20 * .0004;
    end.setMaximumTime(endTime);
    if (Math.abs(end.getMaximumTime().getSIValue() - endTime) > 1e-9)
      throw new IllegalStateException("Unexpected native physical time unit.");
    end.getLogicalOption().setSelected(SolverStoppingCriterionLogicalOption.OR);
    end.setIsUsed(true);

    monitor(sim, "Wave_M13_Fx");
    monitor(sim, "Wave_M13_Fz");
    bound(criteria, monitor(sim, "W01_interface_CFL"), true, 2.2);
    bound(criteria, monitor(sim, "Wave_M13_CFL"), true, 25.0);
    bound(criteria, monitor(sim, "Wave_M13_MaxVelocity"), true, 50.0);
    bound(criteria, monitor(sim, "Wave_M13_MinAlpha"), false, -.00001);
    bound(criteria, monitor(sim, "Wave_M13_MaxAlpha"), true, 1.00001);

    AutoSave save = sim.getSimulationIterator().getAutoSave();
    save.getTriggerOption().setSelected(AutoSaveTriggerOption.TIME_STEP);
    save.getTimeStepUpdateFrequency().setTimeSteps(10);
    save.setMaxAutosavedFiles(2);
    save.setEnabled(true);
    save.setAutoSaveBatch(true);
    if (!save.getEnabled() || save.getTimeStepUpdateFrequency().getTimeSteps()!=10)
      throw new IllegalStateException("Native autosave settings did not persist.");
    sim.saveState(output.toString());
  }
}
