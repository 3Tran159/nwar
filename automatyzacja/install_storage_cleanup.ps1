$ErrorActionPreference = 'Stop'
$taskName = 'NWAR verified storage cleanup'
$pythonPath = 'C:\Users\ThinkPad\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$windowlessPython = Join-Path (Split-Path -Parent $pythonPath) 'pythonw.exe'
if (Test-Path -LiteralPath $windowlessPython) { $pythonPath = $windowlessPython }
$codeFolder = $PSScriptRoot
$scriptPath = Join-Path $codeFolder 'storage_cleanup.py'
if (-not (Test-Path -LiteralPath $pythonPath) -or -not (Test-Path -LiteralPath $scriptPath)) { throw 'Cleanup runtime is missing.' }
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument ('-X utf8 "' + $scriptPath + '" --apply') -WorkingDirectory $codeFolder
$hourly = New-ScheduledTaskTrigger -Once -At (Get-Date).AddHours(1) -RepetitionInterval (New-TimeSpan -Hours 1)
$logon = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2) -Hidden
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($hourly,$logon) -Settings $settings -Principal $principal -Description 'Verify completed NWAR results on H:, deduplicate backup files, replace closed run folders with archive junctions, remove obsolete local reports. Never touch active solver runs or their source checkpoints.' -Force | Out-Null
Get-ScheduledTask -TaskName $taskName | Select-Object TaskName,State
