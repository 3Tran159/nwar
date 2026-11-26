# Nocna diagnostyka awarii CFD: rzeczywiste ustalenia 31.10.2026

Zakres tego audytu: odczyt oryginalnych logów/historii, kontrola procesów, bezpieczne zamknięcie jednego potwierdzonego pozostałego procesu nieudanej próby i przygotowanie diagnostyki bez kroków CFD. Nie uruchomiono nowego solvera numerycznego w ramach tego audytu. Nie zmieniono aktywnych makr, oryginalnych .sim, STOP, campaign_hold ani HF.

## 1. Potwierdzona luka kontroli procesów

WAVE_H050_pressure_aligned_CPU1_20261031_once: kontroler 11704 i frontend 31404 zakończyły się, stage_result ma exit_code=1, ale natywny serwer STAR PID 6932 (start 23:06:31.1989806 +01:00) nadal istniał i słuchał na porcie 47827. Tożsamość potwierdzona w star.log jako rank 0 tego właśnie przypadku, nie przez sam PID. CPU pozostawało dokładnie 25.921875 s w wielu odczytach między 23:20 a 23:27; historia stała od 23:09:27, STOP istniał od 23:10:45; nie było aktywnego zapisu .sim. Zachowany zdrowy checkpoint źródłowy zweryfikowany SHA-256.

Po ponad 15 minutach bez kroków i ponad 10 minutach od STOP zamknięto wyłącznie PID 6932, bez zbiorczego zabijania procesów ani drzewa HF. native_cleanup_intent.json i native_cleanup_result.json zawierają dowody. Odczyt po interwencji: PID nie istnieje, stary port nie słucha, HF i nowy kontroler M13 pozostają nietknięte.

Przyszłe kontrolery MUSZĄ sprawdzać zarówno frontend, jak i natywne ranki STAR z PID + czasem utworzenia + przypisaniem do przypadku. Nie zwalniać locków tylko na podstawie śmierci frontendu. Nie stosować stałych list dozwolonych starych PID bez czasu utworzenia. Nie edytować aktualnie działającego kontrolera; poprawka wyłącznie w nowej, przejrzanej wersji przed następnym dozwolonym startem.

## 2. Nieudane fale CPU1 nie dowodzą same w sobie wadliwej siatki

failure_comparison.json porównuje surowe history.csv/star.log: H0.5 CPU1 dt1ms i pressure-aligned kończą zapis na kroku 18 / t0.418; dt0.5ms na kroku 19 / t0.4095. Ostatnie zapisane prędkości i CFL są skończone; pressure-aligned Vmax=18.01635063 m/s, CFL=0.09009319. CPU2 ta sama rodzina H0.5 osiągnęła 500 kroków / t0.9. CPU1 H0.0001 osiągnęła 200 kroków / t0.6. To nie jest walidacja tych fal i nie wyklucza błędu pola po ostatnim zapisie.

Powtarzane non-finite mają m.in. nazwy Fx_half Monitor, Fz_half Monitor, Maximum Velocity Monitor. Wymagają inspekcji powiązań części/reprezentacji po usunięciu płata. Nie wolno uznać wszystkich komunikatów za nieszkodliwe ani wyciszać rzeczywistych problemów VOF/ciśnienia. Źródło wielkich residuali pozostaje nieustalone: należy odczytać rzeczywiste współczynniki normalizacji i próbki residuali, a nie utożsamiać wydruku z bezwzględnym bilansem masy.

## 3. Pilot płat + fala: osobny błąd przygotowania

M13_wave_direct_20261031/M13_GPU_W20_H050_pilot_20261031 zakończył się o 23:28:39, zero kroków CFD, brak history.csv, macro_error: Unexpected wave period. Błąd występuje przy pobraniu okresu nowo utworzonego obiektu FifthOrder przed podpięciem funkcji do wlotu. Nie jest dowodem niestabilności płata.

Osobny istniejący kontroler uruchomił wersję R2 o 23:29:57: M13_GPU_W20_H050_pilot_20261031_r2, controller PID2536 (zawsze ponownie sprawdzić PID/start). NIE dublować. Plik prepare_period_fallback_r2_20261031.py dokumentuje korektę: wartość 20/23.612 s służy tylko zaplanowaniu długości rampy. Nie jest to zwalidowany odczyt okresu STAR FifthOrder. W setup.wave_period_s R2 zapisuje tę wartość pomocniczą; dashboard nie może prezentować jej jako zmierzonego okresu modelu. Ustalić native period po aktualizacji obiektu oraz fazę z lokalnych sond.

Budżet R2 to 1200 kroków x0.0004 s = tylko 0.48 s dalszego czasu fizycznego. To test rozruchu, nie 20 okresów i nie dowód dotarcia fali. Nie wolno naliczać wcześniejszych sekund calm jako okresów falowych ani przyjmować pre-arrival baseline bez wymaganych pełnych okien i braku impulsu ciśnienia. M13 nie ma pełnego wspólnego okna0.2s z M12: końcowy status wyboru siatki nadal wymaga tego zastrzeżenia.

## 4. Przygotowany audyt bez kroków, bez zapisu .sim

AuditWaveSetupZeroStep.java skompilowany. Czyta normalizację i historię residuali oraz powiązania raportów na kopii spokojnowodnego .sim. Dodatkowo tworzy wyłącznie analityczny obiekt fali i raport do oceny jego pola, aby sprawdzić okres przed i po ewaluacji analitycznej. Nie podłącza fali do BC, nie inicjalizuje, nie zmienia czasu i nie wykonuje solvera. run_zero_step_audit.py ma jednorazowy katalog, SHA źródła, CPU1 BELOW_NORMAL, STOP/resource/hold/lock checks oraz nie zwalnia locków, dopóki pozostaje natywny STAR.

Próba startu audytu została PRAWIDŁOWO zatrzymana w preflight z powodu istniejącego m13_wave_gpu.lock dla R2. Audyt nie uruchomił STAR i nie ma jego wyników. Nie omijać locka, nie powtarzać podczas aktywnego pilota. Po zakończeniu właściciela można ponownie ocenić legalność jednego odczytowego audytu, w granicach horyzontu i zabezpieczeń platformy. Nie jest to przygotowany restart pressure-aligned ani sposób obejścia jego blokady.

Wcześniejsza próba odczytowego podłączenia do pozostałego serwera przez CLI nie udała się: lokalna wersja nie obsługuje -nbuserdir; kolejna forma -host/-port została odrzucona jako invalid port i utworzyła pusty serwer bez wczytania .sim, który zakończył się odmową licencji. Nie wykonano makra ani kroków CFD; procesy tej próby zakończyły się. Zachowano attach.log i attach_verified_cli.log. Nie powtarzać tych wariantów.

## 5. Dalsze decyzje i ograniczenia

Nie budować siatki od nowa bez wskazania konkretnego defektu. Najpierw usunąć błędy konfiguracji/monitorów/kontroli klient-serwer. Czysta konfiguracja CPU1 z własną spokojną wodą może być informacyjną alternatywą dla dziedziczonych monitorów i przejścia Np2->Np1, ale wymaga odrębnego uzasadnienia, poprawnego workflow i niewyczerpanego limitu; nie jest automatycznie autoryzowanym retry.

Nocny horyzont do01.11 09:00, raport08:00. Limity odzyskiwania, zakaz obchodzenia zabezpieczeń platformy, stare STOP i F:/campaign_hold pozostają w mocy. Zgoda na izolowany diagnostyczny test z płatem nie zwalnia całej kampanii W01-W08 ani nie zatwierdza wave-only. Nie zmieniać działającej wersji R2. W razie ponownej awarii opisać faktyczny etap: konfiguracja, licencja, klient/serwer lub kroki CFD; nie zakładać, że zawsze winne dt albo mesh.
