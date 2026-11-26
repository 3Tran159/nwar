NWAR GLHF transfer v4 — Windows, STAR-CCM+ 2602 and 2606

1. Extract NWAR_GLHF_Transfer_v4 into the existing GLHF NWAR package,
   next to app, assets, runtime, and Start NWAR.cmd.
2. If GLHF has a separate supervisor, stop or disable its scheduling through
   its own controls after any active solver has saved and exited. Leave the
   dashboard open if desired. Wait for the queue to be idle.
3. Run "Export and finish W05.cmd". It copies the latest saved SIM and the
   complete available force/probe history of the selected chain to
   GLHF_exports/GLHF_W05_<run-id>. Then it verifies and queues a continuation
   with the v3 five-cycle solver. The first cycle is excluded from analysis.
   If there are five cycles at the saved endpoint, review the exported result.
4. After completion, run "Export W05.cmd" again. Copy the entire new export
   folder, including manifest.json and checkpoint/latest.sim, to ThinkPad.

For export only, run "Export W05.cmd". Optional CLI arguments:
  --case W07
  --workspace "D:\path\to\workspaces\2606"
  --output "D:\path\to\exports"

The last plotted time and last saved SIM time may differ. The original CSVs
stay intact. The continuation uses the exact force-history row at the saved
checkpoint. The export reports both times. A missing or unverifiable save,
solver error, manual pause/STOP or occupied solver slot blocks the launch.
If HOLD is shown, send the console message for diagnosis. Do not clear STOP
or delete locks to get past a refusal.

The patch runs its own verified portable v3 application files. It preserves
GLHF's installed app, UI, assets and license settings and uses the existing
workspace queue. The worker is limited to the requested job. In POD mode
enter the key at the hidden prompt. It is not included in the transfer.
