NWAR portable Windows dashboard — STAR-CCM+ 2602 / 2606

Extract the entire ZIP to writable local storage. Run Start NWAR.cmd and
select an installed STAR executable, output directory and local licensing.
Configure NWAR.cmd changes setup; Close dashboard.cmd closes an idle service.
Opening the dashboard does not launch a solver. Selecting a wave and adding
it to the queue authorizes calculation. Only one process with one GPU is used.

Supported installation families: 21.02.x (2602), 21.04.x (2606).
Macro compilation was checked against 21.02.007-R8 and 21.04.009-R8.
Native solver execution of this portable build has NOT been tested: the
source machine's existing W04 was kept running without interruption.
Compile compatibility is not a numerical equivalence claim. Review the first
target-machine run, particularly on 2606, before accepting production results.

Requirements: Windows x64; licensed local Siemens STAR with NVIDIA GPU
support and a compatible driver. Python and scientific dependencies are
included. STAR, its libraries, drivers and license credentials are not.
Preflight requires 8 GiB free RAM, 4000 MiB free GPU memory, GPU utilization
below 45%, temperature below 85 C and 25 GiB free workspace storage.
Long runs need additional storage for preserved simulation checkpoints.

The original C01 and accepted PRE at t=5.8 s are immutable package assets.
The complete PRE source/checkpoint chain is shipped to preserve hash-based
provenance verification. New runs use disposable copies, preserve 30 scenes
and record full force history and resume markers. Original C01 remains the
Q reference. H is crest-to-trough height, not amplitude. Supported custom
input range: H=0.25–1.50 m, wavelength=20–40 m. Existing numerical guards and
four-repeatable-cycle acceptance remain unchanged. The authorized +/-1.5 m
surface guard applies only to W04; all other waves retain +/-1.0 m.

Each release has an independent workspace, queue, reports and saved runs.
Never open 2606-written checkpoints with 2602. Fresh starts use the accepted
source PRE supplied in this package. Do not move a populated workspace:
queued jobs contain absolute source paths. For a different computer, copy
the clean distribution and initialize a new workspace. Keep prior results
as a separate archive. Never copy a live queue to another machine.

All other STAR/MPI processes block launch. No external solver is terminated,
adopted or attached to. There is no automatic restart after physics failures.
Use Pause and save, wait for the saved checkpoint and solver exit, then shut
down the computer. Closing the browser tab alone leaves the service running.
The dashboard binds only to localhost and protects mutations with a per-run
request token. It automatically selects an unused local port starting at 8782.
Report and UI assets are local and do not require internet connectivity.

The cycle progress bar counts down to each next measured complete cycle.
The current cycle is drawn progressively as a dashed trace from recorded
samples. Its phase and remaining time are estimates until the closing probe
crossing is measured. Then it becomes a completed trace and the countdown
advances. Partial display cycles do not count toward scientific acceptance.
This layout and automatic updates are preserved when selecting another wave.
For an existing installation, extract NWAR_patch_v2 inside the portable
folder and run its Apply patch.cmd while that installation is idle. The
patch updates the distribution and its configured 2602/2606 workspaces,
preserving simulation files and results. It refuses active workspaces.
For a fresh installation, Start NWAR.cmd initializes a new workspace.

Power-on-Demand keys are session-only environment input, never persisted in
settings. Logs redact the configured key. A local license-server address may
be stored in the target workspace settings. The distributed package contains
no original-machine license configuration or active controller state.

Verify package.cmd checks immutable distribution files using SHA-256.
package_manifest.json inventories the package; asset_provenance.json records
unchanged scientific source hashes; app/compile_receipt.json records compiler
compatibility. setup and results are generated outside these immutable assets.
Python and dependency licenses remain in runtime/LICENSE.txt and lib package
LICENSE/COPYING/dist-info directories. Siemens software must be installed and
licensed independently. See CZYTAJ_NAJPIERW.txt for the Polish start guide.
