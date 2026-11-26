# Jednorazowe: inicjalizacja repo git i pierwszy commit (autor: globalny noreply GitHuba).
$g = 'C:\Program Files\Git\cmd\git.exe'
Set-Location (Split-Path $PSScriptRoot -Parent)
& $g init -b main
& $g config user.name 'Julek'
& $g config user.email '361491866+3Tran159@users.noreply.github.com'
& $g add -A
& $g commit -q -m "NWAR: nieruchomy plat na fali - makra STAR, automatyzacja kampanii, pakiet GLHF, siatka M13, wyniki 14 fal, raport v5 (stan 26.11.2026)"
& $g count-objects -vH
& $g log --format="%h %an <%ae> %s" -1
& $g status --short | Measure-Object | % { "niezacommitowane: $($_.Count)" }
