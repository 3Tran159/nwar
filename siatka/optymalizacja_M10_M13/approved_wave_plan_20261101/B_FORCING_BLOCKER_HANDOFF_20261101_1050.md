# M13 audit B: verified recovery and unresolved scientific gate

## Technical incident, 1 Nov 2026
At 10:44–10:46 Europe/Oslo, the 09:59 isolated CPU1 audit remained hung after its 900 s budget. STOP file creation was **10:14:19**; at two observations 57 seconds apart, STAR frontend PID **34760** (started 09:59:08) and native rank0 PID **12440** (started 10:00:59) had no meaningful CPU progress, while STAR log and the 77 MB CSV had not changed since 10:08. Existing R4V final.sim is a healthy saved, exploratory (not wave-validated) source. The audit's R4V source remained unchanged.

A precisely identified audit-owned native rank0 PID12440 was terminated after >30 minutes of ineffective STOP, without task-tree killing. Frontend and Python controller PID8196 then exited themselves and released the **owned** forcing_audit.lock, m13_wave_gpu.lock and wave_inlet.lock. The audit recorded exit 4294967295 and controller_reason=wall_budget. This is a **failed controller completion**, not a physically divergent CFD simulation. No CFD steps were executed by the audit.

## Grounded audit facts
- forcing_audit/wave_R4V/audit.json recorded a 309441-cell wave configuration at t=13.9792 s before the process hung.
- R4V region uses FORCING_DAMPING with boundary-based forcing/damping lengths 20 m. Inlet has wave velocity/volume-fraction functions; outlet has wave damping. wave_inlet_only:true does not prove volumetric forcing is absent near the foil.
- Saved cell-centre domain x extent: -34.9004 to +44.9010 m. If the boundary-distance definitions behave as expected, forcing would be geometrically near -35..-15 m and damping +25..+45 m. **These intervals are conditional estimates, NOT actual measured forcing strengths.**
- All five wave-zone scalar fields from forcing_and_fields.csv are the 1.7976931348623157e308 sentinel in **309441 / 309441 cells**. Valid physical values: zero. Raw pressure/VOF/velocity/coordinates export; this neither proves source zero nor proves source active near foil.
- Wave FifthOrder object's heavy/light densities: 997.561 / 1.18415 kg/m³; inherited Calm model: 1000 / 1.2 kg/m³. Calm setup lists rho=1000. Top and outlet use Hydrostatic Pressure of Heavy Fluid of Calm. The pressure function's GetFieldFunctionValue raised errors during reflection. This does not prove pressure fields are corrupted.
- Native wave period ~0.84726732 s. Separate from analytic startup/ramp estimate.
- Corrected exploratory Q_CD = -0.0004087994476 (about -5.78056%) **is NOT yet accepted**.

## Scientific next action
forcing_review.json intentionally has ready_for_matched_sensitivity:false and forcing_at_foil_excluded_or_quantified:false. Preserve the gate.

1. Do **not** rerun the same 77 MB whole-domain reflection/table audit. Develop a separately reviewed **small** zero-step or analytical boundary-zone audit on a copy, no massive internal-table dump, resolving actual spatial source/strength, material density and calm/wave pressure/VOF boundary comparison.
2. Because reference wave-function densities/pressure differ, a matched **H≈0 control** is scientifically justified if direct equivalence cannot be demonstrated. Prepare a guarded new GPU case, uniquely copied from accepted M13 calm, with identical wave-zone/BC setup but negligibly small incident amplitude. Require preflight, compilation, exclusive locks, source hash and bounded steps before launch. Do not map an earlier incident-wave solution to this H0 control.
3. Only after forcing/BC effects are bounded and documented, set positive forcing_review.json gates and run matched dt0.2 sensitivity calm then wave. A prepared macro alone is not a successful trial.
4. After sensitivity, launch H0.25/λ20 then H0.5/λ30 individually. No M14/M15, no F: hold changes, no silent acceptance.

## Artifacts
- forcing_audit/RECOVERY_INTENT_20261101_1044.json
- forcing_audit/RECOVERY_RESULT_20261101_1046.json
- forcing_audit/derived_spatial_summary.json
- forcing_review.json
- Updated stage_state.json, appended decisions.jsonl / attempts.jsonl

No new CFD solver was launched in the recovery. Do not claim a pass for the zero-step audit merely because its JSON and CSV exist.
