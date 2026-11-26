# Wypchniecie repo na GitHub (logowanie: okno Git Credential Manager w przegladarce).
$g = 'C:\Program Files\Git\cmd\git.exe'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $g remote remove origin 2>$null
& $g remote add origin https://github.com/3Tran159/nwar.git
& $g add -A
& $g commit -q -m "skrypty git" 2>$null
& $g push -u origin main 2>&1
& $g status -sb
