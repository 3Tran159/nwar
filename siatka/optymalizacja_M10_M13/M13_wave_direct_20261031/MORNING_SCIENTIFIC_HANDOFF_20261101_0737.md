# M13 foil + wave, factual handoff for 08:00 (1 Nov 2026, Europe/Oslo)

## Verified completion and resources
R4V ended **06:34:18** with exit code 0, 12,000 steps, physical t=13.9792 s, full 544,280,864-byte saved .sim SHA256 `64a8be30fc7fe53aabafd8e5b3ec6cb88b7cae57b4199c8396047a722edf4672`. Its source checkpoint was preserved. No STAR solver remained alive at 07:30. STOP_ALL absent on E and F, legacy campaign_hold on F remains active; no owned GPU/wave locks; SHA256 runbook matches plan. Available approximately 33.72 GiB RAM, C 53.52 GiB, E 188.01 GiB, GPU 11321 MiB. Local dashboard root 127.0.0.1:8771 HTTP 200. Hash #m13, not an HTTP /api/m13 endpoint.

## Measured complete cycles (diagnostic, not validation)
7 complete local probe x=-0.5 m wave-surface upward-crossing cycles after the model's *estimated* arrival/ramp exclusion. The last four (4–7) have:
- Cycle 4: T=0.846795s, CL_hydro mean 0.31813589, CD_total mean 0.006667234
- Cycle 5: T=0.847206s, CL 0.31819703, CD 0.006663927
- Cycle 6: T=0.847384s, CL 0.31823377, CD 0.006661996
- Cycle 7: T=0.847388s, CL 0.31827285, CD 0.006659446

Between cycles 6→7, delta mean CL +0.000039079 and CD -0.000002550; phase-overlay absolute RMS differences 0.00003906 CL and 0.00000237 CD. All are calculated from actual force series using gauge-defined phase, not fitted force alignment. Local period source is a measured interface gauge; incident wave arrival has **not** been independently established and full 20-cycle criterion is unmet. M13 independent saved calm reference last 0.2s: CL=0.31435150, CD=0.007071966; cycle7 CD is about 5.83% lower, a **provisional exploratory observation**, not yet validated negative added resistance.

## Additional physically measured wave-gauge audit
Harmonic fundamental of actual saved R4V gauge eta, fixed T=0.84727s on physical window 9.929–13.317s: H at x=-34: 0.49931m; -25: 0.50201m; -15: 0.50064m; -10: 0.49646m; -6: 0.49489m; -0.5: 0.49199m; 5: 0.50414m; 10: 0.46096m; 20: 0.42992m. Compared with reference x=-25, observed phase deviations from k dx (lambda20m) are below ~0.024 radians up to x=-0.5, ~-0.085 at x=10, and +0.083 at x=20. This is evidence of **plausible upstream wave propagation**, but possible downstream attenuation/interference/VOF and reflections require review. Do not interpret x40 in damping zone as clean mesh accuracy. This is not comparison to the exact STAR FifthOrder theoretical field.

Latest native STAR VOF+foil+instantaneous streamlines frame verified SHA, t=13.9392s, interface CFL=1.9006. Final CFL bulk=17.328; VOF bounds 0–1 and finite pressure, speed, forces. The frame is real saved output, not animated synthetic streamlines.

## Status/decision
R2, R3V and R4V were bounded separate stages, each saved; historical R1 zero-step error is NOT the latest run. R4V stopped by planned step budget, not failure. No third unreviewed continuation launched; current overnight budget/caps and remaining time do not permit demonstrating 20 periods by 09:00. An additional 13 complete periods require ~11s more physical time, which at measured cost is multiple hours. Report cycle deficit honestly. Existing F campaign C01/W01–W08 hold and HF unchanged. No new M14/M15.

Sources:
- `E:\ntnu_mesh_optimization_20261030\M13_wave_direct_20261031\WATCH_R4V_20261101_0732.json`
- `E:\ntnu_mesh_optimization_20261030\M13_wave_direct_20261031\WAVE_PROPAGATION_AUDIT_20261101_0735.json`
- `E:\ntnu_mesh_optimization_20261030\M13_wave_direct_20261031\M13_GPU_W20_H050_continuation_R4V_20261101\stage_result.json`
