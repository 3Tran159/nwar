# Wave-only mesh-screen compact briefing

Geometry verified by independent CGNS topology/volume/face audit. Wave CFD not yet computed for these candidates.

| Lambda [m] | Coarse cells (dz50mm) | Baseline cells (dz25mm) | Fine cells (dz12.5mm) | dx [m] | lambda/dx |
|---:|---:|---:|---:|---:|---:|
| 10 | 41,200 | 53,200 | 77,200 | 0.1 | 100 |
| 20 | 41,200 | 53,200 | 77,200 | 0.2 | 100 |
| 30 | 61,800 | 79,800 | 115,800 | 0.2 | 150 |

## Wave-height resolution in the vertical
| H [m] | H/dz coarse | H/dz baseline | H/dz fine |
|---:|---:|---:|---:|
| 0.25 | 5 | 10 | 20 |
| 0.50 | 10 | 20 | 40 |
| 0.75 | 15 | 30 | 60 |

## Do not confuse geometry with CFD evidence
- All 9 variants: topology and analytic volume checks pass. No accepted wave propagation run was performed on these variants.
- Horizontal lambda/dx: 100 at 10m, 100 at 20m, 150 at 30m. Only a design parameter.
- Wavelengths 20m and 30m each consider H = .25,.5,.75 m; 10m considers H=.5m. H does not require remeshing, so there are 9 geometries rather than 21.
- Prefer wave dt=0.001s if stable; test 0.0005s on one selected variant separately. Current M12 dt=0.0001s is not the production wave default.
- Calm baseline must stabilize; incoming wave is generated at upstream domain origin with initially flat water elsewhere. Waiting for wave arrival and discarding startup is required.
- Historical 1ms propagation encountered a boundary backflow/stability guard near t=.704s, so no unverified result can be admitted.
- Before combining with foil mesh: verify near-foil prism controls, local resolution, free-surface interface, transition, mass balance, CFL and whether wave has correct amplitude, period and phase.

Plots: comparison_chart.png / comparison_chart.svg. Raw data: morning_summary.json / morning_table.csv.
