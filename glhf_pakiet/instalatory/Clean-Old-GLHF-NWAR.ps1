[CmdletBinding(SupportsShouldProcess)]
param(
    [string] $OldRoot = 'D:\cfd\NWAR_Windows_2602_2606\NWAR_Windows_2602_2606'
)

$ErrorActionPreference = 'Stop'
$old = Get-Item -LiteralPath $OldRoot
if (!$old.PSIsContainer -or ($old.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
    $old.Name -ne 'NWAR_Windows_2602_2606') { throw 'Expected the original NWAR_Windows_2602_2606 package directory.' }
$root = $old.FullName
if (!(Test-Path -LiteralPath (Join-Path $root 'start_nwar.py') -PathType Leaf) -or
    !(Test-Path -LiteralPath (Join-Path $root 'runtime\python.exe') -PathType Leaf)) {
    throw 'Old NWAR package markers are missing. No changes made.'
}
if ($PSScriptRoot.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase) -or $PSScriptRoot -eq $root) {
    throw 'Run this script from outside the old package.'
}
$configFile = Join-Path $root 'launcher.json'
if (Test-Path -LiteralPath $configFile) {
    $config = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json
    if ($config.workspace_root -and ![IO.Path]::GetFullPath($config.workspace_root).StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The old workspace is outside the old package. Archive that location separately before cleaning.'
    }
}
$destination = Join-Path $old.Parent.FullName ('NWAR_GLHF_OLD_' + (Get-Date -Format yyyyMMdd_HHmmss))
if (Test-Path -LiteralPath $destination) { throw 'Archive destination already exists.' }
$oldReference = '(?i)' + [regex]::Escape($root) + '(?:[\\/"\s]|$)'
$tasks = @(Get-ScheduledTask | Where-Object {
    @($_.Actions | Where-Object {
        [Environment]::ExpandEnvironmentVariables("$($_.Execute) $($_.Arguments) $($_.WorkingDirectory)") -match $oldReference
    }).Count -gt 0
})

if (!$PSCmdlet.ShouldProcess($root, 'Disable its scheduled tasks, stop its processes, and move the old package to a backup')) { return }
Set-Location -LiteralPath $old.Parent.FullName
foreach ($task in $tasks) {
    Disable-ScheduledTask -InputObject $task | Out-Null
    if ($task.State -eq 'Running') { Stop-ScheduledTask -InputObject $task }
}

$processes = @(Get-CimInstance Win32_Process)
$ancestors = [Collections.Generic.HashSet[int]]::new()
$current = $PID
while ($current -and $ancestors.Add($current)) {
    $current = ($processes | Where-Object ProcessId -eq $current).ParentProcessId
}
$owned = [Collections.Generic.HashSet[int]]::new()
foreach ($proc in $processes) {
    if (!$ancestors.Contains($proc.ProcessId) -and (
        $proc.ExecutablePath -match $oldReference -or
        ($proc.Name -match '^(pythonw?|pwsh|powershell|cmd|starccm\+|star-ccm\+|mpiexec)\.exe$' -and $proc.CommandLine -match $oldReference)
    )) { [void]$owned.Add($proc.ProcessId) }
}
foreach ($release in '2602', '2606') {
    $workspaces = if ($config.workspace_root) { $config.workspace_root } else { Join-Path $root 'workspaces' }
    $runs = Join-Path $workspaces "$release\data\runs"
    if (!(Test-Path -LiteralPath $runs -PathType Container)) { continue }
    foreach ($run in Get-ChildItem -LiteralPath $runs -Directory) {
        $record = Join-Path $run.FullName 'process.json'
        if (!(Test-Path -LiteralPath $record -PathType Leaf)) { continue }
        try { $owner = Get-Content -LiteralPath $record -Raw | ConvertFrom-Json } catch { continue }
        foreach ($pair in @(@('pid','birth'), @('controller_pid','controller_birth'))) {
            if (!$owner.($pair[0]) -or !$owner.($pair[1])) { continue }
            $proc = Get-Process -Id $owner.($pair[0]) -ErrorAction SilentlyContinue
            if ($proc -and !$ancestors.Contains($proc.Id) -and
                $proc.StartTime.ToFileTimeUtc().ToString() -eq [string]$owner.($pair[1])) {
                [void]$owned.Add($proc.Id)
            }
        }
    }
}
# Include still-identifiable children even when their command lacks the package path.
do {
    $before = $owned.Count
    foreach ($proc in $processes) {
        if (!$ancestors.Contains($proc.ProcessId) -and $owned.Contains($proc.ParentProcessId)) {
            $parent = $processes | Where-Object ProcessId -eq $proc.ParentProcessId
            if ($parent.CreationDate -le $proc.CreationDate) { [void]$owned.Add($proc.ProcessId) }
        }
    }
} while ($owned.Count -gt $before)

foreach ($proc in ($processes | Where-Object { $owned.Contains($_.ProcessId) } | Sort-Object CreationDate -Descending)) {
    $running = Get-CimInstance Win32_Process -Filter "ProcessId=$($proc.ProcessId)"
    if ($running -and $running.CreationDate -eq $proc.CreationDate) {
        Stop-Process -Id $proc.ProcessId -Force
    }
}
Move-Item -LiteralPath $root -Destination $destination
[pscustomobject]@{
    ArchivedTo = $destination
    DisabledTasks = @($tasks | ForEach-Object { $_.TaskPath + $_.TaskName })
    MatchedProcesses = $owned.Count
} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $destination 'cleanup_receipt.json') -Encoding UTF8
Write-Host "OLD NWAR ARCHIVED: $destination"
Get-Process -Name 'starccm+*','star-ccm+*','mpiexec*' -ErrorAction SilentlyContinue |
    Select-Object Id, ProcessName, StartTime | Format-Table
