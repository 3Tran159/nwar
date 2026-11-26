from pathlib import Path
import json,base64
ROOT=Path('E:/NWAR_portable_20261103');PATCH=ROOT/'NWAR_GLHF_UI_hotfix_v2'
manifest=json.loads((PATCH/'frontend_manifest.json').read_text(encoding='utf8'))
for entry in manifest['files']:entry['data']=base64.b64encode((PATCH/'payload'/entry['name']).read_bytes()).decode()
encoded=base64.b64encode(json.dumps(manifest).encode()).decode()
template=r'''param([string]$PackageRoot='', [string]$WorkspaceRoot='', [switch]$DiagnoseOnly)
$ErrorActionPreference='Stop'
$uiSpec='__PAYLOAD__'
$spec=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($uiSpec)) | ConvertFrom-Json
$allowed=@('index.html','style.css','app.js','wave_view.js','history_chart.js','convergence_chart.js')
function Read-Json([string]$Path){if(Test-Path -LiteralPath $Path){return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json};return $null}
function File-Hash([string]$Path){$h=[Security.Cryptography.SHA256]::Create();try{return ([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($Path)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
function Atomic-Replace([string]$Temp,[string]$Target){
 for($attempt=0;$attempt -lt 10;$attempt++){
  try{[IO.File]::Replace($Temp,$Target,[NullString]::Value);return}catch{if($attempt -eq 9){throw};Start-Sleep -Milliseconds (50*($attempt+1))}
 }
}
if(-not $PackageRoot){
 if(Test-Path -LiteralPath (Join-Path (Get-Location) 'package_manifest.json')){$PackageRoot=(Get-Location).Path}
 elseif(Test-Path -LiteralPath (Join-Path $PSScriptRoot 'package_manifest.json')){$PackageRoot=$PSScriptRoot}
 else{$PackageRoot=Read-Host 'Folder NWAR containing app, assets and runtime'}
}
$PackageRoot=(Resolve-Path -LiteralPath $PackageRoot).Path
$inventory=Join-Path $PackageRoot 'package_manifest.json';$package=Read-Json $inventory
if($package.package -ne 'NWAR Windows 2602/2606'){throw 'Unsupported NWAR package. No files changed.'}
$roots=@((Join-Path $PackageRoot 'workspaces'))
$launcher=Read-Json (Join-Path $PackageRoot 'launcher.json')
if($launcher.workspace_root){$roots+=([string]$launcher.workspace_root)}
if($WorkspaceRoot){$roots+=$WorkspaceRoot}
$apps=@((Join-Path $PackageRoot 'app'));$servers=@()
foreach($root in ($roots | Select-Object -Unique)){
 foreach($release in @('2602','2606')){
  $work=Join-Path $root $release;$app=Join-Path $work 'app'
  if(Test-Path -LiteralPath $app){
   $settings=Read-Json (Join-Path $work 'settings.json')
   if($settings.release -ne $release){throw ('Cannot verify workspace: '+$work)}
   $apps+=(Resolve-Path -LiteralPath $app).Path
   $server=Read-Json (Join-Path $work 'data/server.json')
   if($server.url){
    $uri=[Uri]$server.url
    if($uri.Scheme -eq 'http' -and $uri.Host -in @('127.0.0.1','localhost')){$servers+=[pscustomobject]@{url=[string]$server.url;work=$work;pid=$server.pid}}
   }
  }
 }
}
$apps=@($apps | Select-Object -Unique)
if($DiagnoseOnly){
 $report=@()
 foreach($server in $servers){
  try{
   $state=Invoke-RestMethod -Uri ($server.url+'/api/status') -TimeoutSec 5
   $rows=@()
   foreach($job in $state.jobs){
    $failure=Read-Json (Join-Path $job.folder 'controller_failure.json');$errorText=[string]$failure.error
    if($errorText -match '(?i)podkey|password|license|token|commandline|command_line'){$errorText='Sensitive error text omitted'}
    $rows+=[pscustomobject]@{id=$job.id;case=$job.case_id;status=$job.status;observed_status=$job.observed_status;controller_pid=$job.controller_pid;controller_birth=$job.controller_birth;time_s=$job.live.time_s;step=$job.live.step;age_s=$job.live.age_s;controller_error=$errorText}
   }
   $served=Invoke-WebRequest -UseBasicParsing -Uri ($server.url+'/wave_view.js?ui=diagnostic') -TimeoutSec 5
   $report+=[pscustomobject]@{url=$server.url;work=$server.work;worker_alive=$state.worker_alive;paused=$state.paused;current_run=$state.current_run;ui2_served=([string]$served.Content -match '20261103-ui2');jobs=$rows}
  }catch{$report+=[pscustomobject]@{url=$server.url;error=$_.Exception.Message}}
 }
 $destination=Join-Path $PSScriptRoot 'NWAR-dashboard-diagnostic.json'
 [IO.File]::WriteAllText($destination,(ConvertTo-Json -InputObject @($report) -Depth 15),(New-Object Text.UTF8Encoding($false)))
 Write-Host ('Read-only diagnostic: '+$destination);exit 0
}
$pending=@()
foreach($entry in $spec.files){
 if($entry.name -notin $allowed){throw 'Only static UI files are permitted'}
 $bytes=[Convert]::FromBase64String($entry.data);$hasher=[Security.Cryptography.SHA256]::Create()
 try{$payloadHash=([BitConverter]::ToString($hasher.ComputeHash($bytes))).Replace('-','').ToLowerInvariant()}finally{$hasher.Dispose()}
 if($payloadHash -ne $entry.sha256){throw 'Embedded payload checksum failed'}
 foreach($app in $apps){
  $target=Join-Path $app $entry.name
  if(-not (Test-Path -LiteralPath $target)){throw ('Missing UI file: '+$target)}
  if((Get-Item -LiteralPath $target).Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked UI file preserved'}
  $old=File-Hash $target
  if($old -eq $entry.sha256){continue}
  if($old -notin $entry.allowed_before_sha256){throw ('Unknown local UI revision preserved: '+$target)}
  $pending+=[pscustomobject]@{target=$target;data=$bytes;old=$old;hash=$entry.sha256;backup=''}
 }
}
if($pending.Count){
 $backupRoot=Join-Path $PackageRoot ('.nwar_frontend_backups/'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'_'+[guid]::NewGuid().ToString('N'))
 [IO.Directory]::CreateDirectory($backupRoot) | Out-Null
 $count=0;$written=@()
 try{
  foreach($item in $pending){
   $item.backup=Join-Path $backupRoot ($count.ToString()+'_'+[IO.Path]::GetFileName($item.target));$count++
   Copy-Item -LiteralPath $item.target -Destination $item.backup
   if((File-Hash $item.backup) -ne $item.old){throw 'UI changed during backup'}
  }
  Copy-Item -LiteralPath $inventory -Destination (Join-Path $backupRoot 'package_manifest.json')
  foreach($item in $pending){
   if((File-Hash $item.target) -ne $item.old){throw 'UI changed during update'}
   $temp=$item.target+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
   try{[IO.File]::WriteAllBytes($temp,$item.data);Atomic-Replace $temp $item.target;$written+=,$item}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp}}
  }
  foreach($name in $allowed){
   $target=Join-Path (Join-Path $PackageRoot 'app') $name;$record=@($package.files | Where-Object {$_.path -eq ('app/'+$name)})
   if($record.Count -ne 1){throw 'Package UI inventory is invalid'}
   $record[0].sha256=File-Hash $target;$record[0].bytes=(Get-Item -LiteralPath $target).Length
  }
  $package.total_bytes=[long](($package.files | Measure-Object -Property bytes -Sum).Sum)
  $temp=$inventory+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
  try{[IO.File]::WriteAllText($temp,($package | ConvertTo-Json -Depth 30),(New-Object Text.UTF8Encoding($false)));Atomic-Replace $temp $inventory}finally{if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp}}
  foreach($item in $pending){if((File-Hash $item.target) -ne $item.hash){throw 'Installed checksum failed'}}
 }catch{
  foreach($item in $written){$temp=$item.target+'.rollback.'+[guid]::NewGuid().ToString('N');Copy-Item -LiteralPath $item.backup -Destination $temp;Atomic-Replace $temp $item.target}
  $oldInventory=Join-Path $backupRoot 'package_manifest.json';if(Test-Path -LiteralPath $oldInventory){Copy-Item -LiteralPath $oldInventory -Destination $inventory -Force}
  throw
 }
 Write-Host ('UI files updated: '+$pending.Count+'; backups: '+$backupRoot)
}else{Write-Host 'This UI update is already installed.'}
foreach($server in $servers){
 try{
  $response=Invoke-WebRequest -UseBasicParsing -Uri ($server.url+'/wave_view.js?ui=20261103.2') -TimeoutSec 4
  if([string]$response.Content -match '20261103-ui2'){Write-Host ('LIVE UI 20261103.2 verified: '+$server.url)}
  else{Write-Warning ('This URL serves another UI folder: '+$server.url+'. Use -WorkspaceRoot to select its results directory.')}
 }catch{Write-Host ('Service was not available for the optional UI check: '+$server.url)}
}
Write-Host 'Done. Press Ctrl+F5 in the browser. Wait 8-16 seconds for advancing-history detection.'
Write-Host 'Solver, controller, backend and calculation settings were not restarted or edited.'
Write-Host 'If controller attention persists, run this same script with -DiagnoseOnly.'
'''
output=ROOT/'Update-NWAR-Dashboard-UI2.ps1';assert not output.exists(),'Existing script preserved'
output.write_text(template.replace('__PAYLOAD__',encoded),encoding='utf-8-sig')
print(json.dumps(dict(script=str(output),bytes=output.stat().st_size)))
