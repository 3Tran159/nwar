$studyRoot='C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030'
$state=Get-Content -LiteralPath (Join-Path $studyRoot 'cpu_study_state.json') -Raw | ConvertFrom-Json
if ($state.status -ne 'CPU_job_running') { $state | ConvertTo-Json -Compress; exit 0 }
$inventory=Get-CimInstance Win32_Process
$jobRoot=$inventory | Where-Object ProcessId -eq $state.star_pid
if (-not $jobRoot -or $jobRoot.CommandLine -notlike '*gci_w01a_20261030*') { throw 'Owned STAR root not verified' }
$ownedIds=@([int]$state.star_pid)
for ($level=0; $level -lt 30; $level++) {
 $newIds=@($ownedIds+@($inventory | Where-Object {$ownedIds -contains $_.ParentProcessId} | ForEach-Object {[int]$_.ProcessId}) | Select-Object -Unique)
 if ($newIds.Count -eq $ownedIds.Count) {break}
 $ownedIds=$newIds
}
$owned=@(Get-Process -Id $ownedIds -ErrorAction SilentlyContinue)
$native=@($owned | Where-Object ProcessName -eq 'star-ccm+')
$before=@{}
foreach ($procItem in $owned) { $before[$procItem.Id]=$procItem.CPU }
$start=Get-Date
Start-Sleep -Seconds 8
$duration=((Get-Date)-$start).TotalSeconds
$after=@(Get-Process -Id $ownedIds -ErrorAction SilentlyContinue)
$rows=@($after | ForEach-Object { [pscustomobject]@{pid=$_.Id;name=$_.ProcessName;affinity=$_.ProcessorAffinity.ToInt64();cores=if($before.ContainsKey($_.Id)){[math]::Round(($_.CPU-$before[$_.Id])/$duration,3)}else{0}} })
$result=[pscustomobject]@{at=(Get-Date).ToString('o');job=$state.job;configured_workers=$state.workers;native_solver_processes=$native.Count;owned_average_busy_cores=[math]::Round(($rows | Measure-Object cores -Sum).Sum,2);all_owned_exclude_C01_cores=@($rows | Where-Object {($_.affinity -band 3) -ne 0}).Count -eq 0;all_owned_full_22_mask=@($rows | Where-Object {$_.affinity -ne 16777212}).Count -eq 0;processes=$rows}
[System.IO.File]::WriteAllText((Join-Path $studyRoot 'live_CPU_allocation_audit.json'),($result | ConvertTo-Json -Depth 5))
$result | Select-Object at,job,configured_workers,native_solver_processes,owned_average_busy_cores,all_owned_exclude_C01_cores,all_owned_full_22_mask | ConvertTo-Json -Compress
