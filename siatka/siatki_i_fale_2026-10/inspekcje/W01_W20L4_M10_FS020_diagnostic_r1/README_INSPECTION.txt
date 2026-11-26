W01 H0.5m L20m H24m, M10 FS020, 317277 cells.
Open inspection_setup.sim for zero-time setup, or the newest completed checkpoint/final.sim for flow fields.
Scenes W01 01-12: whole tank alpha; alpha0.5 free surface; foil pressure/speed/instantaneous streamlines; outlet alpha/mesh, water+air residual, pressure/speed/streamlines; free-surface close-up.
Monitors/plots contain independent slice forces, native phase error (kg/step) and outlet-column imbalance (kg/s). Divide native kg/step by current dt for comparison. Do not multiply per-cell kg/s by cell volume.
Outlet cell/face CSVs sample evolving fields. Full local_balance snapshots calibrate cell sums against native phase reports.
This is an exploratory first wave run. User accepts previous~0.0143% mass deviation; original0.01% is still flagged and recorded. No final wave-force accuracy/reflection/grid/time convergence claim.
Never continue guard_or_error_preserved.sim after physical instability.
