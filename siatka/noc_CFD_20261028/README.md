# NTNU CFD visualization gallery
Created from real STAR-CCM+ 2602 solution checkpoints, 29 October 2026.

## Input sources (preserved)
- D001/checkpoint.sim
- D002/checkpoint_visualisation.sim (user's manually prepared scene)
- D003/checkpoint.sim
- D004/checkpoint.sim

## New model outputs (created separately)
- D001/checkpoint_visualisation_5mm.sim
- D002/checkpoint_visualisation_5mm.sim: user's existing "streamlines" scene enhanced to 11 Z levels
- D002/checkpoint_visualisation_gallery.sim: five extra NTNU_5mm_* scenes
- D003/checkpoint_visualisation_5mm.sim
- D004/checkpoint_visualisation_5mm.sim

## Seed grid
- Direction of the freestream: +X
- Line 1 endpoint: X=-1.5 m, Y=5.5 m, Z=z
- Line 2 endpoint: X=-1.5 m, Y=0.0 m, Z=z
- 60 seeds per line
- z=0.000,0.005,0.010,0.015,0.020,0.025,0.030,0.035,0.040,0.045,0.050 m
- Total 11 layers x 60=660 seeds, 5 mm vertical spacing
- Colored by Velocity Magnitude, 2 mm tube diameter

## Scenes to look for under Scenes
- NTNU_5mm_Streamlines
- NTNU_5mm_Water_Surface
- NTNU_5mm_Foil_Pressure
- NTNU_5mm_Vortices_Q
- NTNU_5mm_Velocity_Section

PNG images of the five scenes are stored here with the case ID prefix.
Open gallery.html in a web browser to compare them.

## Scientific caveat
These checkpoints were saved during early initialization (physical time around 0.0002 s). Streamlines are instantaneous, not fluid-particle trajectories; these snapshots are not a validated converged flow. If Q-criterion has no visible iso, that can mean no region matches the chosen threshold, rather than an export failure.

No CFD iteration or meshing was performed by these visualization macros. Original checkpoints are untouched.
