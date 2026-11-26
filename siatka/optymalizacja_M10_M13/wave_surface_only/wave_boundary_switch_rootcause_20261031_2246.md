# Diagnostic: discontinuity at calm → FifthOrder inlet-wave binding, 31 October 22:46 Oslo

Read-only log comparison, NOT acceptance or verified root cause.

- Same verified baseline calm source at t=0.400 s, 53,200 cells, 18 m/s, 38.4 m3.
- Calm t=0.400 last inner-iteration normalized residuals from STAR: continuity 4.330309e-01, X-momentum 9.744546e-01, Z-momentum 3.402263e+00.
- First 1ms step t=0.401, morning 2-CPU full-H=0.5: continuity 8.920168e+05, X-momentum 7.795274e+05, Z-momentum 5.273918e+06.
- First 1ms step t=0.401, evening 1-CPU full-H=0.5: continuity 8.910887e+05, X-momentum 7.835927e+05, Z-momentum 5.290708e+06.
- First 1ms step t=0.401, 1-CPU near-flat target-H=0.0001: continuity 6.232539e+05, X-momentum 5.480546e+05, Z-momentum 3.700395e+06.
- At t=0.401 the ramped incident height is near 0.000001 m in both full-H and near-flat runs. Thus strong residual shock occurs already at boundary/wave-model activation, despite near-flat physical height; it cannot be attributed only to nominal H=0.5 m or only to dt=1 ms.
- Full-H CPU1 failed after ~18 steps at dt1ms and ~19 steps at dt0.5ms; near-flat CPU1 saved 200 steps through t0.600. Morning full-H CPU2 saved 500 steps through t0.900, but also had very large residuals and legacy NaN reports. Neither continuation establishes credible propagation. Nonnumeric monitors Fx/Fz/Maximum Velocity are present even during flat calm and should be separated from physical-field divergence, not simply suppressed without audit.
- Priority: read-only comparison of inlet velocity, heavy-fluid fraction, pressure/hydrostatic BC and wave forcing before and immediately after binding; identify physical discontinuity; then isolate one controlled solver/setup fix on a copied E: .sim only if start budget and scientific/resource gates authorize. Confirm finite pressure/VOF and residual reduction on actual STAR steps before long run.
- No new solver launched by this note, no change to old results, hold on foil-wave C01/W01-W08 and HF preserved pending combined pilot and validated release.
