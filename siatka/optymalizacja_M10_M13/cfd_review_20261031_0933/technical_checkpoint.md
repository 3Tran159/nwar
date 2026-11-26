# CFD checkpoint: 31.10.2026 09:35 Europe/Oslo

## M12 hydrofoil, 1,154,199 cells
**PROJECT PRIMARY CL/CD SETTLED / LEGACY FOUR-COMPONENT TEST NOT PASSED**.
Gentle stop and save verified at t=3.3314 s, 24414 steps. STAR exit=0; saved final.sim 1.561 GB with matching completed/export receipts.
Two formal checks at 3.0013s and 3.2013s reproduced from complete raw records. At second: CL shift 0.197%; total CD shift 0.441%; last RMS CL 0.054%; CD 0.122%. Pressure change normalized to CD 0.431%, viscous 0.010%, sum abs 0.441% (no opposite-sign compensation).
Fluid/VOF check: volume range over last 0.45s 0.00490%, max bulk CFL 8.891, max interface CFL 0.954.
These are PROJECT criteria, not general ITTC rules, iterative uncertainty estimates or GCI. M10/M11 still require comparable settled windows; no light mesh selected yet.

## Wave mesh only
The 53,200-cell λ20m, H0.5m baseline has an independently saved **flat calm** t=0.4s at 18m/s, 400 steps of 0.001s; max bulk CFL 0.090; water-volume range 1.99e-13m3, max absolute free surface η 5.12e-13m. Interface CFL unavailable for empty alpha-threshold, not equal to zero.
No incident wave, no wave propagation or reflection validation yet. Next safe step: audited upstream-inlet wave from preserved calm .sim on a disposable copy; reject transient and diagnose historical outlet backflow. Original C01/HF untouched.
