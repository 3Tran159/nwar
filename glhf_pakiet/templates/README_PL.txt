NWAR — przenośna paczka Windows / STAR-CCM+ 2602 i 2606

URUCHOMIENIE
1. Rozpakuj CAŁE archiwum na lokalny dysk, np. D:\NWAR. Nie uruchamiaj z ZIP.
2. Na komputerze musi być zainstalowany Siemens Simcenter STAR-CCM+ 2602
   (21.02.x) albo 2606 (21.04.x), z działającą licencją i obsługą GPU.
3. Otwórz Start NWAR.cmd. Wybierz starccm+.exe z lokalnej instalacji,
   folder wyników i sposób licencjonowania. Typowe instalacje są wykrywane.
4. Wybierz falę W04–W07 lub dodaj własną H=0,25–1,50 m, lambda=20–40 m.
   Dashboard otwiera się lokalnie w przeglądarce. Samo otwarcie nie rozpoczyna
   obliczeń. Dopiero dodanie zadania do kolejki uruchamia kontrolowane liczenie.

WYMAGANIA
Windows x64, zainstalowany STAR i właściwa licencja GPU, karta NVIDIA oraz
sterownik wspierane przez wybraną wersję STAR. W praktyce przygotuj komputer
z co najmniej 32 GB RAM. Kontrola startu wymaga co najmniej 8 GiB WOLNEGO RAM,
4000 MiB wolnej VRAM, temperatury GPU poniżej 85 C i małego obciążenia GPU.
Zostaw co najmniej 25 GiB wolnego miejsca w folderze wyników; dłuższa seria
z checkpointami potrzebuje więcej. Python i biblioteki są dołączone.
STAR, sterowniki, licencje i klucze licencyjne nie są częścią tej paczki.

WERSJE
Configure NWAR.cmd pozwala wybrać inną instalację. 2602 i 2606 mają osobne
foldery app/data w folderze wyników. Plik zapisany przez 2606 pozostaje
w jej folderze; nie przenoś takiego wznowienia do 2602.
W obu wersjach nowa fala zaczyna się od tego samego dołączonego PRE.
Makro skompilowano z bibliotekami 21.02.007 i 21.04.009. Dashboard i dane
sprawdzono osobno. Natywnego testu solvera tej przenośnej paczki nie wykonano,
aby nie przerywać ani nie obciążać trwającego W04. Pierwszy przebieg na nowym
komputerze i szczególnie pod 2606 wymaga sprawdzenia logu, konfiguracji i pól.
Sama poprawna kompilacja nie potwierdza zgodności wyników numerycznych.

DANE I WYKRESY
C01: assets\root\clean_c01_campaign_20261101\
  C01_warm_M13_steady_rho1000_air1p2_20261101\final.sim
PRE: assets\root\nwar_automation_20261102\PRE_W04_20261102\
  calm_global_resume_20261102_232341\final.sim
PRE kończy się przy t=5,8 s. Oryginalny C01 pozostaje odniesieniem Q.
Dołączono pełny łańcuch zapisów PRE, historię, wykresy i dowody walidacji.
To wyjaśnia rozmiar paczki. Nie usuwaj pośrednich checkpointów — walidacja
sprawdza ich sumy kontrolne. Każda fala pracuje na osobnej kopii.
Wykresy cykli, sondy i ręczne przesunięcie fazy pozostają w dashboardzie.
Pasek odlicza do każdego kolejnego pełnego cyklu. Bieżący cykl dorysowuje
się przerywaną linią wyłącznie z zapisanych próbek; jego faza i pozostały
czas są szacowane. Po zmierzonym zamknięciu cyklu linia staje się ciągła,
a odliczanie przechodzi do następnego. Niepełny cykl nie zwiększa licznika
akceptacji. Układ i automatyczne odświeżanie działają także dla kolejnych fal.
Przesuwanie fazy dotyczy wyłącznie wyświetlania.

AKTUALIZACJA PACZKI
Rozpakuj folder NWAR_patch_v2 wewnątrz dotychczasowego folderu paczki,
obok app, assets i runtime, i uruchom w nim Apply patch.cmd. Poprawka
aktualizuje paczkę oraz skonfigurowane foldery 2602/2606, zachowując dane
i wyniki. Odmówi zmian w aktywnym środowisku. Bieżący W04 na komputerze
źródłowym pozostaje niezależny i nie jest celem tej poprawki.

ZAPIS I ZAMYKANIE
Obliczenia: jeden proces solvera + jeden GPU. Inne aktywne procesy STAR/MPI
wstrzymują start. Paczka nigdy nie zamyka cudzych solverów. Nie kopiuje też
aktywnej kolejki, zadań ani automatyzacji z komputera źródłowego.
Zamknięcie karty przeglądarki nie zatrzymuje obliczeń ani serwera.
Przed wyłączeniem komputera wybierz Pause and save i poczekaj na zapisany
checkpoint oraz zakończenie solvera. Wynik jest zachowany do wznowienia.
Close dashboard.cmd zamyka wyłącznie własny, bezczynny serwer tej paczki;
odmówi zamknięcia, gdy trwa zadanie lub są oczekujące zlecenia.
Nie przenoś używanego katalogu w trakcie obliczeń.
Przed zmianą licencji/instalacji zamknij bezczynny serwer i użyj Configure.
Klucz Power-on-Demand jest przekazywany tylko w bieżącej sesji i nie jest
zapisywany w konfiguracji. Ponownie podaj go przy następnym uruchomieniu.

KRYTERIA
Cztery pełne, powtarzalne cykle i komplet wymaganych kontroli są konieczne
do akceptacji. W04 zachowuje zatwierdzony limit wychylenia powierzchni
+/-1,5 m; inne fale, w tym własne konfiguracje, zachowują +/-1,0 m.
H oznacza wysokość grzbiet–dolina, nie amplitudę. Zabezpieczenia numeryczne,
siatka, fizyka i kryteria akceptacji pozostają bez zmian. Na zlecenie
użytkownika minimalny wolny RAM w paczce obniżono z 16 do 8 GiB.
Po błędzie nie ma automatycznego wznowienia. Wyniki pozostają diagnostyczne
do zaliczenia kontroli. Terminu zakończenia nie da się zagwarantować.

WERYFIKACJA I LICENCJE
Verify package.cmd sprawdza wszystkie dołączone pliki według SHA-256.
Przy dużej paczce może to potrwać kilka minut. Nie uruchamia solvera.
asset_provenance.json zawiera tożsamość C01, PRE i plików dowodowych.
app\compile_receipt.json opisuje sprawdzone wersje makra.
runtime\LICENSE.txt oraz pliki LICENSE/COPYING w lib i katalogach dist-info
zawierają licencje dołączonego oprogramowania. Nie udostępniaj wyników lub
modelu osobom, które nie mają do nich uprawnień.
