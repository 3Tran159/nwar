# Doprecyzowanie: referencyjny CL/CD przed dotarciem fali

Nowe polecenie użytkownika, 31.10.2026 noc. Ten dokument dodaje odczytowe kryteria dla przyszłego nowego pilota *combined foil+wave*; nie stanowi sam w sobie zgody na ominięcie aktywnego campaign_hold ani na modyfikację źródłowych .sim.

## Sekwencja
1. Zbuduj odrębną połączoną siatkę na podstawie zaakceptowanego rozwiązania płata i niezależnie wiarygodnej siatki powierzchni. Kontroluj prism/wake/transition/VOF/masę i nienadpisane źródło.
2. Wczytaj własny fizycznie zdrowy checkpoint *płaskiej* wody z prędkością 18 m/s, prawidłowym poziomem, ciśnieniem i modelem turbulencji. Upewnij się, że nie ma starej fali w całej domenie.
3. Wprowadź na upstream inlet funkcję narastającej fali FifthOrder, bez globalnego reinitialize; czas włączenia zapisany. Fala ma propagować od wlotu do punktu płata.
4. W czasie propagacji mierz CLhydro, CDtotal i lokalne sondy wolnej powierzchni przed płatem oraz na wysokości płata. Odróżniaj wpływ natychmiastowego impulsu ciśnieniowego po zmianie warunku brzegowego od właściwego fizycznego dotarcia fali.
5. Przed dotarciem fali sprawdź dla CLhydro i total CD DWIE kolejne pełne oceny po 0.2s: w każdej dwa sąsiednie rozłączne okna 0.2s, zmiana średniej oraz wewnątrzokienny RMS każdego współczynnika <0.5%. Pressure/viscous są diagnostyką, nie własną bramką 0.5%. CLhydro oblicz z odpowiednią geometrią i odejmij wypór jednokrotnie. Konieczne są dowody z raw history i lokalnie płaska powierzchnia, zdrowe residual/CFL/VOF/masę i brak wpływu zmiany inlet na monitorowane siły.
6. Dopiero wtedy opisz **pre-arrival calm reference = accepted** wraz z fizycznym przedziałem czasu i checkpointem. Jeśli fala dociera za wcześnie, żaden z warunków nie jest spełniony lub wykryto BC shock, oznacz jako provisional/absent i pozyskaj osobną, porównywalną calm-only referencję na tej samej połączonej siatce i dt. Nie korzystaj automatycznie z wartości M10 po zmianie geometrii.
7. Po arrival i ramp odrzuć transient, a następnie segmentuj według lokalnej fazy fali; nałóż 4 pełne cykle CLhydro oraz CDtotal, pokaż wartość średnią, amplitudę, RMS, fazę i różnice cykl/cykl. Kryterium 20 pełnych *okresów* od właściwego fizycznego momentu oceny, nie 20 timestepów. Brak pokrycia po 20 okresach uruchamia diagnozę odbić, transientu, FSI/czasowej niestacjonarności, BC i zbieżności iteracyjnej, nie automatyczne stwierdzenie przyczyny błędu.
8. Dashboard musi pokazywać osobno Airy/first-order jako analityczny punkt odniesienia, narzuconą STAR FifthOrder na wlocie i rzeczywistą falę z sond. Nie zrównuj ich jako identycznych rozwiązań dla H=0.5m.

Wszystkie nowe wyniki na E:, pełna historia, brak modyfikowania istniejących makr i aktywnych zadań. Oryginalny C01/W01-W08 pozostaje na hold do pełnych bramek.
