$ErrorActionPreference = 'Continue'
$root = 'E:\ntnu_mesh_optimization_20261030'
$main = 'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mesh_study_20261030\gci_w01a_20261030'
Write-Output ('LOCAL_TIME=' + (Get-Date).ToString('o'))
$plan = Get-Content -LiteralPath ($root+'\plan.json') -Raw | ConvertFrom-Json
$hash = (Get-FileHash -LiteralPath ($root+'\AUTONOMOUS_RECOVERY_PROMPT.md') -Algorithm SHA256).Hash.ToLower()
Write-Output ('RUNBOOK_MATCH=' + ($hash -eq $plan.recovery_policy.runbook_sha256) + ' ACTUAL=' + $hash + ' EXPECTED=' + $plan.recovery_policy.runbook_sha256)
Write-Output ('PARALLEL_POLICY=' + ($plan.parallel_execution | ConvertTo-Json -Depth 6 -Compress))
$os = Get-CimInstance Win32_OperatingSystem
Write-Output ('FREE_RAM_GIB=' + [math]::Round($os.FreePhysicalMemory/1MB,2))
foreach($drive in @('C:','E:')) {
 $v = Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DeviceID -eq $drive }
 if($v){Write-Output ('FREE_'+$drive+' GIB='+[math]::Round($v.FreeSpace/1GB,2))}
}
foreach($f in @($main+'\STOP',$main+'\STOP_ALL',$root+'\STOP_ALL',$root+'\recovery.lock',$root+'\parallel_cpu_20261031\auxiliary.lock',$main+'\gpu_study.lock',$main+'\cpu_study.lock')){
 if(Test-Path -LiteralPath $f){$o=Get-Item -LiteralPath $f;Write-Output ('PRESENT_CONTROL='+$f+' SIZE='+$o.Length+' MTIME='+$o.LastWriteTime.ToString('o'))}
}
Write-Output 'PROCESS_TREE_BEGIN'
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '(?i)java|python|star|mpi|orted|powershell' } |
  Select-Object ProcessId,ParentProcessId,Name,CreationDate,ExecutablePath |
  ConvertTo-Json -Depth 3 -Compress | Write-Output
Write-Output 'PROCESS_TREE_END'
try {
 $a = Invoke-RestMethod -Uri 'http://127.0.0.1:8771/api/mesh-study' -TimeoutSec 5
 Write-Output ('API_KEYS='+(($a.PSObject.Properties.Name) -join ','))
 $a | ConvertTo-Json -Depth 7 -Compress | ForEach-Object {Write-Output ('API_RESPONSE='+($_.Substring(0,[Math]::Min(18000,$_.Length))))}
} catch { Write-Output ('API_ERROR='+$_.Exception.Message) }
