
$ErrorActionPreference = 'Continue'
$r='E:\ntnu_mesh_optimization_20261030'
$b='C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030'
"DEVICE_CLOCK " + (Get-Date -Format o)
$plan=Get-Content (Join-Path $r 'plan.json') -Raw | ConvertFrom-Json
$h=(Get-FileHash (Join-Path $r 'AUTONOMOUS_RECOVERY_PROMPT.md') -Algorithm SHA256).Hash.ToLower()
"SHA_MATCH=$($h -eq $plan.recovery_policy.runbook_sha256) HASH=$h"
Get-PSDrive C,E | ForEach-Object { "DRIVE $($_.Name) FREE_GIB=$([math]::Round($_.Free/1GB,2))" }
$os=Get-CimInstance Win32_OperatingSystem
"RAM_FREE_GIB=$([math]::Round($os.FreePhysicalMemory*1KB/1GB,2))"
function readShort($p,$max=1400) {
 if (Test-Path $p -PathType Leaf) {
  $i=Get-Item $p; "FILE $p $($i.LastWriteTime.ToString('o')) SIZE=$($i.Length)"
  $t=Get-Content $p -Raw
  if($null -ne $t){$t.Substring(0,[math]::Min($max,$t.Length))}
 } else {"MISSING $p"}
}
try {
 $api=Invoke-RestMethod -Uri 'http://127.0.0.1:8771/api/mesh-study' -TimeoutSec 3
 $j=$api | ConvertTo-Json -Depth 5 -Compress
 "LOCAL_API " + $j.Substring(0,[math]::Min(4500,$j.Length))
} catch { "LOCAL_API_ERROR $($_.Exception.Message)" }
foreach($f in @('cpu_study_state.json','gpu_study_state.json','calm_stabilization_progress.json','calm_mesh_screen.json','gci_results.json')){readShort (Join-Path $b $f) 1300}
foreach($f in @('STOP_ALL','recovery.lock','parallel_cpu_20261031\auxiliary.lock','wave_surface_only\wave_inlet.lock','wave_surface_only\wave_mesh_comparison.lock')){readShort (Join-Path $r $f) 500}
"RECENT_WAVE_FOLDERS"
Get-ChildItem (Join-Path $r 'wave_surface_only') -Directory | Sort-Object LastWriteTime -Descending | Select-Object -First 15 | ForEach-Object {"WAVE_FOLDER $($_.Name) $($_.LastWriteTime.ToString('o'))"}
foreach($f in @('wave_surface_only\zero_start_12_current.json','wave_surface_only\zero_start_12_report.json','parallel_cpu_20261031\current.json','project_primary_readiness_latest.json')){readShort (Join-Path $r $f) 2200}
foreach($rel in @('M10_W01a_GPU_queue_20261031_165802_aef11e','M11_G10_M_GPU_queue_20261031_105607_91db08','wave_surface_only\zero_start_matrix_R2_coarse_continuation_20261031_4')) {
 $p=Join-Path $r $rel; "CASE_ROOT $rel EXISTS=$(Test-Path $p)"
 if(Test-Path $p){
  Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue |
   Where-Object {$_.Name -in @('history.csv','progress.json','completed.json','pilot_result.json','monitor.json','exit.json','settling_check.json','latest_checkpoint.json','process.json','star.log')} |
   Select-Object -First 24 | ForEach-Object {
   "CASE_FILE $($_.FullName) MTIME=$($_.LastWriteTime.ToString('o')) BYTES=$($_.Length)"
   if($_.Name -eq 'history.csv'){Get-Content $_.FullName -Tail 3}
   elseif($_.Name -eq 'star.log'){Get-Content $_.FullName -Tail 6}
   else { $t=Get-Content $_.FullName -Raw; $t.Substring(0,[math]::Min(900,$t.Length)) }
  }
 }
}
"NEWEST_ATTEMPTS";Get-Content (Join-Path $r 'attempts.jsonl') -Tail 12
"PROCESSES"
Get-CimInstance Win32_Process | Where-Object {$_.Name -match 'starccm|python|java'} | Select-Object -First 25 | ForEach-Object {"PID=$($_.ProcessId) PPID=$($_.ParentProcessId) NAME=$($_.Name) START=$($_.CreationDate)"}
