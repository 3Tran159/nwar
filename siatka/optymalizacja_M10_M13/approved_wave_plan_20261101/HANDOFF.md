
## NAJNOWSZE: CZYSTE C01 NAJPIERW, 2026-11-01T11:50:18.563093+01:00
Użytkownik anulował T01 i polecił nową spokojnowodną bazę ze spójnymi gęstościami1000/1.2. Patrz E:\ntnu_mesh_optimization_20261030\clean_c01_campaign_20261101\HANDOFF.md. T01 STOP requested jest świadomym anulowaniem, NIE awarią do restartowania. Nowe C01: E:\ntnu_mesh_optimization_20261030\clean_c01_campaign_20261101\C01_rho1000_air1p2_fresh. Następne fale TYLKO jako kontynuacje zapisanego ustabilizowanego final.sim TEGO C01, bez reinitialize i bez starego nocnego pola. Nocny W01 to archiwum. Bieżąca akceptacja C01 i porównania pozostają fail-closed. To zastępuje wcześniejszą kolejność T01/audit/dt/W01.


## NADRZĘDNA KOREKTA C01, 2026-11-01T11:16:21.005451+01:00
Przeczytaj E:\ntnu_mesh_optimization_20261030\wave_campaign_20261101\C01_REFERENCE_POLICY_20261101.md. Historyczny M13 calm z badań siatki NIE jest teraz referencją C01 do W01. C01=pending_compatibility; Q/ΔCD/ΔCL/procenty i linie baseline wyłączone do jawnej weryfikacji zgodności gęstości, normalizacji i BC. T01 jest kandydatem/kontrolą, nie automatycznym C01. Własne wyniki W01 zachowane. To zastępuje wcześniejsze, sprzeczne opisy C01 poniżej.

# Approved M13 follow-up, 1–2 November 2026

## Latest user scope clarification: foil-only, 2026-11-01T11:00:34.462722+01:00

Standalone wave-only mesh/propagation trials are DISCONTINUED, not a prerequisite to any further M13 work. Preserve their historical evidence. All further audits and approved dt/BC sensitivity tests concern the actual M13 FOIL case and its matched calm reference. The overnight H=0.5 m, lambda=20 m condition already ran and saved through R2/R3V/R4V to t=13.9792 s; do not restart it as an unrun W01. This condition is separate from the held legacy F: W01 queue. Preserve the current forcing/comparability gate and exploratory scientific status. After those checks, next conditions remain H=0.25 m/lambda=20 m, then H=0.5 m/lambda=30 m. No solver, active macro, source simulation, raw history, receipt or retry budget is changed by this clarification.


## Authority and priority
User explicitly approved the attached 154-line research plan and extended work until **2 November 2026 09:00 Europe/Oslo**. Source: `authorization.json` here and root `plan.json.approved_wave_followup_20261101`. Runbook hash remains unchanged and must continue to match root plan. This overrides old night cutoffs and the old interpretation that 20 wave periods were mandatory. It does not authorize unrestricted retries, cleanup, system changes, removal of others' locks, legacy F: queue release or source overwriting.

Preserve healthy M13 (309441 cells), its calm final.sim and R2/R3V/R4V original histories. No M14/M15 and no full wave-only campaign. R4V finished 12000 steps at t13.9792; it is a saved exploratory result, not a validated NAR claim.

## A. Implemented postprocessing
`cycle_analysis.py` is now called by `E:\ntnu_mesh_optimization_20261030\foil_live_dashboard_20261031\foil_live.py`.
- Phase gauge is FIXED x=-0.5m; no automatic alternate probe and no force-phase fitting.
- Interpolate from full unsliced histories, including exactly phase0 and phase1 (121 points per overlay).
- Integrate mean forces using raw time samples and interpolated exact cycle endpoints.
- Four complete cycles are required for comparison. 20 is only a diagnostic ceiling for unresolved repeatability, never a mandatory minimum or automatic acceptance.
- `analysis_corrected.json` separates H1 (twice fundamental amplitude), Hpp (cycle crest-to-trough), mean eta, first five harmonic amplitudes, fixed-probe measured period and upstream-probe phase differences. Native STAR period is explicitly unknown pending audit; ramp planning estimate is separate.
- Analysis onset is STILL labeled estimated. Do not certify settled incident forcing from four apparently repeating force curves alone.
- Browser QA passed desktop/mobile (`browser_qa.json`), 7 diagnostic cycles, exactly121 phase points and endpoints0/1. Result after correction: Q_CD=-0.0004087994476, deltaCD=-5.78056%, deltaCL=+1.22733%. This is still exploratory. Source raw data unchanged.
- Backups before edits are under `backup/`. Original legacy wave-gauge audit and raw receipts are unchanged.

## B. Active zero-step forcing audit
`run_forcing_audit.py --run` was started at 01.11 09:59. It opens separate COPIES of wave_R4V then calm_M13, CPU1 BELOW_NORMAL, zero time steps and no .sim save. Reads config, forcing/damping lengths and fields, source pressure/VOF/U; exports `forcing_and_fields.csv` and `audit.json`. Outputs in `forcing_audit/wave_R4V` and `forcing_audit/calm_M13`. Locks: own forcing_audit.lock, root m13_wave_gpu.lock, wave_surface_only/wave_inlet.lock and parallel_cpu auxiliary.lock. DO NOT duplicate or start CFD while audit owns locks. Runtime has a900s per-source budget; loading/evaluation alone is not numerical CFD failure. If audit does not complete, inspect CPU/log/receipts and use existing stop/ownership policy; never treat exit0 without audit receipt as success.
The wave audit log has reported `Cannot evaluate field function Hydrostatic Pressure of Heavy Fluid of Calm` while traversing inherited properties. This is NOT itself proof of bad current wave fields; do not hide it or declare the audit passed. Review its exact scope and whether all needed settings/spatial fields were obtained. Preserve failed audit evidence if a narrower read-only audit is needed.

Before sensitivity, create `forcing_review.json` ONLY after reviewing actual results, with `ready_for_matched_sensitivity:true`, `sources_unchanged:true`, `forcing_at_foil_excluded_or_quantified:true`, paths/hashes, actual lengths and spatial forcing values in foil vicinity, and pressure/BC comparison. False or absent review MUST block new CFD. Check wave_inlet_only against real volumetric forcing and damping, particularly x=20/40m. A saved .sim marked inlet-only is not proof. Check U=18, waterline z2, densities, gravity, pressure reference, top/outlet, SST, normalization. H=0 same-BC control only if a difference may change resistance even at zero incident wave and cannot be excluded directly.

## C. Explicitly approved paired dt sensitivity
Prepared and compiled separately: `M13CalmDt02.java`, `M13WaveDt02.java`, `sensitivity_compile_receipt.json`; original macros are intact. `run_sensitivity.py` must compile and pass its preflight before use. GPU1, dt=.0002, second-order,10inner and same M13 physics/BC.
1. Run `python run_sensitivity.py --case calm --preflight-only`, then `--case calm --run` only after PASS, audit review and no ownership conflict. Source is original accepted M13 calm. Output `M13_wave_direct_20261031/M13_GPU_sensitivity_calm_dt0002_20261101`. No mixed-dt prior history; minimum two full primary CL/CD 0.2s-window passes. Pressure and viscous are diagnostics only. Bounded1.0s physical target, max6000s wall. Controller independently recomputes raw settling and writes `calm_dt02_result.json` only when genuinely passed. No automatic retry if incomplete.
2. Only after matched calm has passed, run `--case wave --preflight-only`, then `--case wave --run` after PASS. Source is saved R4V wave_pilot_final.sim, NOT calm and NOT reset wave. Output `M13_GPU_W20_H050_sensitivity_dt0002_20261101`. Bound26000 steps/27000s wall, preserve existing wave field and start time. Exclude at least the documented setting-change adaptation interval, then inspect real settled cycles; do not automatically certify one period is sufficient. Compare four full periods.
3. Compute Q=meanCDwave-CDcalm with matched settings; also amplitude/phase/CL/component changes. Working project screen |Q_dt02-Q_dt04|<=4e-5 AND same sign; not ITTC/GCI uncertainty. Write `sensitivity_review.json` with actual evidence and decision. Do not silently substitute unequal calm references.
4. 20inner at same dt only if residual/iterative evidence warrants; local free-surface refinement only if necessary and with matching calm. No indiscriminate restarts or multiple concurrent parameter changes.

## D. Next wave conditions (authorized, NOT already running)
After basic controls, use a separate reviewed copy and guarded launcher, same validated base mesh and chosen production dt:
- First H=0.25m, lambda20m.
- Next H=0.5m, lambda30m, after reviewing propagation region, forcing/damping and period for lambda30.
For each NEW H/lambda start from its appropriate healthy calm field, inject wave ONLY from upstream without global initialization, record arrival/ramp, preserve original results. Do not relabel old wave fields as calm. Do not run all21 combinations. Expected ~H force amplitudes/~H² mean effect is a hypothesis, NOT a validation rule. Active flap remains outside this stage. Choose economical production dt from sensitivity evidence; do not assume dt02 necessary for all cases if dt04 passes.

## Diagnostics and UI
Maintain live CLhydro/CDtotal, fixed-probe four overlays, native VOF/instantaneous streamlines, clear source timestamps and real source case. Instantaneous streamlines are not particle paths; crossing a moving free surface is not itself water-to-air conversion. Do not fake trajectories or alter healthy solver to improve a picture. Add u,w,p ahead of foil and phase-resolved Cp to a new inactive reporting-only macro when feasible. Interpret water inventory with boundary phase fluxes/sources, not as a closed-volume mass error.

## Ownership and schedule
Hourly automation `6ae4f80e310c81918478423ec09bc316` is extended through 02.11 09:00. Keep healthy work untouched, enforce STOP_ALL/user pauses and source hashes, oneGPU, RAM16GiB/C15GiB/E25GiB/VRAM4000MiB before launch. No secrets in outputs. Existing F: C01/W01-W08 hold and HF remain untouched. Writes/new scripts/results on E:. After horizon, no new starts; do not kill healthy runs merely for reaching a date. Audit/analysis are not CFD steps. Final report must distinguish completed, running, prepared, blocked and scientifically accepted.
