# Mesh CFD → wave campaign: bramki projektu
Decyzja użytkownika: 2026-10-31 11:21 Europe/Oslo.
Ten dokument zapisuje kolejność prac; nie jest pozwoleniem na bezwarunkowy start solvera ani zdjęcie istniejącego hold.

## 1. Wybór siatki płata, calm water [NIE POTWIERDZONO JESZCZE]
- Porównać M12/G10_F (zapisany, t=3.3314 s, CL/CD stabilne w dwóch oknach) z M11/G10_M i innymi porównywalnymi siatkami, kiedy mają wiarygodne wyniki.
- Dla każdej: poprawny hydrodynamiczny CL, total CD, dwa okna 0.2 s i 0.5% dla średniej i RMS, wpływ liczby komórek i czasu kroku; pressure/viscous CD jako diagnostyka.
- Potwierdzić zbieżność między siatkami i wybrać najlżejszą wiarygodną. Sam zapis M12 nie oznacza jeszcze wyboru siatki płata.

## 2. Wybór siatki swobodnej powierzchni, WAVE-ONLY bez płata [NIE POTWIERDZONO JESZCZE]
- Źródło: wave_surface_only/wave_case_matrix.json, pliki WS_*, sondy, historia, logi i receipt.
- 21 możliwych kombinacji = 7 warunków falowych × 3 rozdzielczości; 8 priorytetowych, 13 opcjonalnych; nie trzeba liczyć wszystkich 21.
- Weryfikować rzeczywisty 18 m/s throughflow i spokojną powierzchnię początkową. Dopiero potem wzbudzać falę na upstream inlet.
- Porównywać na wspólnych warunkach różne dz, dx i dt (cel 0.001 s; kontrola 0.0005 s), gdy fala przejdzie od wlotu do sond i minie transient.
- Kryteria: stabilność CFL/VOF, zachowanie masy, amplituda H, faza i okres, propagacja między sondami, odbicia, koszt s/krok. Krótki ramp to tylko rozruch, nie zaliczona propagacja.
- Stan odniesienia 31.10 ok. 11:14: 9/9 geometrii audytowanych, 0/8 priorytetowych i 0/21 możliwych pełnych propagacji; jeden wariant lambda=20 m, H=0.5 m, FS_baseline 53200 komórek ma dwa ukończone krótkie testy rozruchowe (dt 0.001 i 0.0005 s), nie full pass. Aktualizować wyłącznie na podstawie świeżych dowodów.

## 3. Połączenie siatek i JEDEN testowy przebieg [ZABLOKOWANE DO 1 i 2]
- Złożyć zaakceptowaną siatkę płata (w tym prism/near-field) z zaakceptowaną rozdzielczością swobodnej powierzchni i poprawnymi przejściami, zweryfikować komórki i jakość siatki.
- Test na jednym reprezentatywnym warunku: najpierw spokojna woda, zapis stabilnego pola, następnie wymuszenie fali od upstream inlet, nie fale w całej domenie od t=0.
- Porównać dt=0.001 s i 0.0005 s, jeśli wymagają tego stability/accuracy, oraz wydajność GPU, CFL/VOF, zachowanie masy, sondy, odbicia, CL/CD i propagację do płata. 0.0001 s tylko jeśli uzasadnia diagnostyka.
- Test ma dać decyzję, czy połączona siatka nadaje się do kampanii W01-W08; nie zaliczać samego startu ani końca procesu.

## 4. Kampania fal z płatem W01-W08 [HOLD]
- Wolno rozważyć dopiero po pozytywnej weryfikacji etapu 3 oraz wymaganym świadomym zwolnieniu istniejącej blokady przez użytkownika.
- NIGDY nie zwalniać automatycznie campaign_hold.json tylko dlatego, że wybrano M11/M12 albo zaliczono wave-only. Nie uruchamiać W01-W08 w tym etapie.
- Niezależny monitoring M11 pozostaje osobny; monitoring fal ma raportować wyłącznie etap 2 i gotowość przekazania siatki do 3.

## Bezpieczeństwo
Przestrzegać STOP_ALL, pauz, blokad, runbooka, limitów wznowień i zasobów, harmonogramu, licencji i pierwszeństwa zdrowego solvera. Nie modyfikować uruchomionych symulacji M11, HF ani istniejących artefaktów M12; nie zdejmować hold. Ten dokument nie zmienia istniejących skryptów ani parametrów solverów.
