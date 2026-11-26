# NWAR — ujemny przyrost oporu na fali nieruchomego płata podwodnego

**NWAR** = *Negative Wave-Added Resistance*: zjawisko, w którym na fali opór płata jest **mniejszy** niż na spokojnej wodzie.
Projekt badawczy NTNU (staż, Trondheim, X–XI 2026), prowadzący: prof. Sverre Steen. Autor: Julian Serkieza.

Pytanie: czy sztywny, nieruchomy płat NACA 66-012 mod (cięciwa 1,19 m, zanurzenie 2 m, prędkość 18 m/s) dostaje z fali regularnej ciąg do przodu — ile, dlaczego i jak pewny jest wynik?

## Wynik w jednym zdaniu

W 14 zaakceptowanych falach regularnych średnia siła pozioma spadła o **0,77–10,1 N** względem spokojnej wody (C01, Fx = 27,0 N), czyli do **−0,83 % siły nośnej**. Mechanizm: fala obraca napływ, a siła nośna (prostopadła do napływu) ma przez część cyklu składową do przodu. Klasyczna teoria niestacjonarna (Sears) tłumaczy trend z błędem RMSE 0,82 N bez dopasowywania. Model podatnej krawędzi spływu **nie** dał zysku większego niż swój błąd (< 0,1 N).

## Wyniki — 14 fal regularnych

| Przypadek | H [m] | λ [m] | Hloc [m] | ΔFx [N] | ± t* [N] | ΔFz [N] | ΔFx/Fz₀ [%] |
|---|---|---|---|---|---|---|---|
| W01 | 0,50 | 20 | 0,494 | −1,31 | 0,006 | 9,88 | −0,108 |
| W02 | 0,25 | 20 | 0,251 | −0,768 | 0,03 | 10,5 | −0,063 |
| W03 | 0,50 | 30 | 0,494 | −1,56 | 0,003 | 10,3 | −0,128 |
| W04 | 1,50 | 39 | 1,49 | **−10,1** | 0,03 | 15,9 | −0,827 |
| W04c | 1,50 | 20 | 1,47 | −7,17 | 0,1 | 15,5 | −0,589 |
| W04e | 1,50 | 15 | 1,47 | −5,02 | 0,2 | 12,1 | −0,412 |
| W04f | 1,50 | 30 | 1,48 | −9,36 | 0,009 | 16,1 | −0,769 |
| W04g | 1,50 | 25 | 1,47 | −8,54 | 0,1 | 16,4 | −0,702 |
| W04h | 0,75 | 15 | 0,723 | −2,25 | 0,1 | 15,4 | −0,185 |
| W04i | 1,00 | 15 | 0,958 | −3,03 | 0,04 | 14,9 | −0,249 |
| W04j | 0,50 | 15 | 0,490 | −1,67 | 0,1 | 15,8 | −0,137 |
| W05 | 1,00 | 20 | 0,971 | −4,03 | 0,03 | 17,2 | −0,331 |
| W06 | 1,00 | 30 | 0,988 | −5,06 | 0,09 | 18,3 | −0,415 |
| W07 | 1,00 | 40 | 1,00 | −5,41 | 0,08 | 19,2 | −0,445 |

Opis kolumn:
- **H** — zadana wysokość fali (dolina–grzbiet). **λ** — długość fali (odległość grzbietów).
- **Hloc** — wysokość fali zmierzona w symulacji tuż przed płatem (x = −0,5 m; W01: −6 m). Hloc < H = fala osłabiona numerycznie po drodze.
- **ΔFx** — zmiana średniej siły poziomej względem spokojnej wody C01. **Ujemna = mniejszy opór** (ciąg z fali).
- **± t\*** — 95 % przedział Studenta z rozrzutu cykli 2–5. Pokazuje powtarzalność cykli, **nie** błąd numeryczny.
- **ΔFz** — zmiana średniej siły pionowej (po odjęciu wyporu 22,7 N); fala dokłada nośności.
- **ΔFx/Fz₀** — ΔFx jako procent siły nośnej na spokojnej wodzie (Fz₀ = 1220 N); miara „ile zyskuje statek”.

Średnie z cykli 2–5 (pierwszy pełny cykl pominięty). Cykl = między kolejnymi przejściami powierzchni wody w górę. Dane: `wyniki/fale/case_results.csv`, `cycle_statistics.csv`.

Dodatkowo **W08bi** (dwie fale nałożone, 0,5 m/20 m + 1,0 m/30 m): ΔFx = −5,67 N — diagnostyka, poza dopasowaniami.

## Wnioski

1. **Efekt jest i rośnie z (wysokością fali)²**: dopasowanie ΔFx = s·θa² przez zero, R² = 0,850 (θa — amplituda kąta napływu z ruchu orbitalnego fali na głębokości 2 m).
2. **Krótkie fale dają mniej**, bo przepływ nie nadąża (opóźnienie Searsa). Model QS×|Sears|²: RMSE 0,818 N, R² 0,926, bez parametrów dopasowanych.
3. **Kąt napływu z sondy 0,9 m przed płatem + opóźnienie 0,05 s** odtwarza przebieg siły w W04e z R² = 0,967.
4. **Podatna krawędź spływu**: odciążanie (κ = 0,3/0,5/0,7) zjada 11/24/41 % zysku; usztywnianie daje maks. ~0,1 N przy +18 % amplitudy Fz → kierunek zamknięty.
5. **Ograniczenie**: różnica dwóch siatek na spokojnej wodzie (M12 vs M13) = 1,14 N — większa niż zysk W02. Pewność dla małych fal jest ograniczona.

## Ustawienia obliczeń

| Parametr | Wartość |
|---|---|
| Program | STAR-CCM+ 2602 (21.02.007) i 2606 (21.04.009); GLHF: 2606 |
| Model | URANS, SST k–ω (Menter), all-y+; VOF z HRIC (Courant 0,5/1,0); quasi-2D (szerokość 0,02 m, ścianki symetrii) |
| Przepływ | woda słodka ρ = 1000 kg/m³, U = 18 m/s, Re = 2,14·10⁷ |
| Płat | NACA 66-012 mod, c = 1,19 m, kąt geometryczny 0° (−0,11° z siatki to artefakt), zanurzenie h = 2 m (h/c = 1,68) |
| Fale | regularne Stokes 5. rzędu, czołowe; głębokość 24 m; strefa wymuszania 40 m, tłumienia 40 m |
| Siatka | M13: 3,09·10⁵ komórek (W01–W03), domena rozszerzona 5,72·10⁵ (reszta); 48 warstw, 1. warstwa 1,53 µm, y+ < 1 na 99,88 % pow. |
| Czas | Δt = 0,4 ms, 2. rząd, 10 iteracji wewnętrznych; 5 pełnych cykli fali na przypadek |

Wybór siatki M13 (z M10–M13): różnice względem najgęstszej M12: CL +1,15 %, CD −3,10 % (limit projektowy 5 %), koszt 34,7 min czasu rzeczywistego na 1 s symulacji vs 409 min dla M12. To wybór praktyczny, **nie** dowód niezależności od siatki. Szczegóły: `wyniki/siatka_M13/`.

## Struktura repo

| Folder | Co zawiera |
|---|---|
| `raporty/` | Raport końcowy v5 (EN, PDF+DOCX), streszczenie PL, onepage 11.11 i v4 16.11; `zrodla_v5/` — skrypty budujące raport |
| `wyniki/fale/` | Tabele wyników 14 fal, statystyki cykli, porównanie siły z falą (wykres główny), `results.json` |
| `wyniki/siatka_M13/` | Porównanie siatek M10–M13, y+ wzdłuż płata, uzasadnienie wyboru |
| `wyniki/pakiet_final_20261109/` | Pakiet danych raportu: historie sił per przypadek, wykresy, `lineage.json`, `checks.json` |
| `wyniki/przeglady_kampanii/` | Przeglądy W04, W07, walidacja CFL |
| `star/makra/` | Makra Java STAR-CCM+ (`NwarWave.java` — ustawienie fali i przebieg, `NwarBichromatic.java`, `PreW04GlobalRamp.java`, eksport, wznawianie); `diagnostyka/` — makra audytowe |
| `automatyzacja/` | Kontroler kampanii fal (kolejka, wznawianie z punktów zapisu, polityka cykli, analiza, panel w przeglądarce `server.py` + `index.html`) i testy |
| `glhf_pakiet/` | Budowanie przenośnych paczek do zdalnej maszyny GLHF (STAR 2606, bez instalacji); `templates/` — skrypty uruchamiane na GLHF; `wydania/` — README kolejnych paczek |
| `siatka/` | Studium GCI (30.10), optymalizacja siatek M10–M13 (skrypty kolejki GPU/CPU, plany, decyzje, raporty przekazania), noc CFD 28.10 |
| `docs/` | `RAPORT.md` — przebieg prac i lekcje; notatka o przeniesieniu sterowania Godø (NDLL) do URANS |
| `skrypty/` | `zbuduj_repo.py` (odtwarza to repo z dysków), `pochodzenie_plikow.csv` (skąd każdy plik), skrypty git |
| `ARCHIWUM_DANYCH_inwentarz.csv` | Każdy ciężki plik (.sim, .simh, .zip, CGNS, …) z pełną ścieżką, rozmiarem, datą i przypadkiem |

## Nazewnictwo przypadków

- **C01** — spokojna woda, odniesienie dla wszystkich ΔF. **PRE_W04** — stan po rozbiegu na domenie rozszerzonej (start dla W04*).
- **W01–W03** — fale na domenie podstawowej; **W04–W07, W04c…W04k** — domena rozszerzona; litera = wariant H/λ. **W08bi** — fala dwuskładnikowa.
- **M10–M13** — warianty siatki; **G09_M, G10_M, G10_F** — siatki studium GCI (M = średnia, F = gęsta).
- **CUSTOM00x** — fale zdefiniowane w panelu na GLHF (15 m).
- **W04k** — przerwany przy t = 14,264 s, niezaakceptowany (poza tabelą).

## Gdzie są ciężkie dane

Nic z poniższego nie jest w repo; pełna lista w `ARCHIWUM_DANYCH_inwentarz.csv` (1305 plików, ~436 GB).

| Miejsce | Zawartość |
|---|---|
| `H:\10_ARCHIWUM_PROJEKTOW\NTNU_RESEARCH_ARCHIVE\NWAR_SIM_FINALS` | Końcowe `.sim` każdego przypadku (`C01_final.sim`, `W01_final.sim` … `W08bi_final_t25.6800.sim`) + `.simh` — **od tego zaczynać** |
| `H:\…\NWAR_PORTABLE_ARCHIVE` | Archiwa paczek GLHF (14 GB) |
| `F:\20_DANE_OBLICZEN\NTNU_NWAR\ntnu_mesh_optimization_20261030` | Przebiegi siatek M10–M13 i kampania fal na laptopie (176 GB w `nwar_automation_20261102`) |
| `F:\…\ntnu_siatki_i_fale_2026-10` | Pierwsze próby fal quasi-2D, stabilizacja siatki (29.10) |
| `F:\…\NWAR_portable_20261103` | Paczki GLHF (zip), wyniki odebrane z GLHF, środowisko uruchomieniowe |

## Jak odtworzyć przypadek

1. Wziąć `<przypadek>_final.sim` z `NWAR_SIM_FINALS` (ścieżka w inwentarzu) i skopiować do folderu roboczego (np. `T:\`).
2. Otworzyć w STAR-CCM+ 2606. Fala, siatka, raporty i monitory są w pliku — można przeglądać i liczyć dalej natywnie w GUI.
3. Dokładanie cykli / nowa fala: makro `star/makra/NwarWave.java` (parametry fali w `automatyzacja/wave_plan.json` / `custom_waves.json`); kontroler `automatyzacja/worker.py` pilnuje cykli, zapisów i wznowień.
4. Analiza cykli 2–5 i tabela: `automatyzacja/analysis.py`, `report.py`; raport v5: `raporty/zrodla_v5/build_report_v5.py`.
5. Na GLHF: `glhf_pakiet/build_package.py` buduje paczkę; klucz licencji podaje się przy starcie (nie jest zapisany w plikach).

Uwaga: skrypty mają ścieżki bezwzględne do starych lokalizacji (`C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\…`, `E:\ntnu_mesh_optimization_…`). Przed ponownym użyciem trzeba je przestawić — skąd pochodzi każdy plik: `skrypty/pochodzenie_plikow.csv`.

## Wymagania

STAR-CCM+ 2602/2606 z licencją (Power-on-Demand na GLHF), Python 3.12+ (numpy, scipy, matplotlib), GPU opcjonalnie (część przebiegów M10/M11/M13 liczona na GPU). Laptop: ThinkPad, liczone lokalnie; ciężkie przypadki W04* na GLHF.

## Znane ograniczenia (otwarte)

- Brak formalnej oceny błędu numerycznego: planowane W05 przy Δt/2 i Δt/4 (17,6 h i 35,3 h GPU), siatka równoważna M12 (32,9 h), pusty kanał (8,8 h) — nie wykonane.
- Courant na granicy woda–powietrze 1,90–2,00 > górny próg HRIC 1,00 → możliwe osłabienie fali (Hloc/H = 0,96–0,99, do ~8 % mniej zysku).
- Quasi-2D: brak wirów krawędziowych; dla rozpiętości AR 4–8 ten sam zysk to 16–23 % oporu indukowanego (tab. 6 raportu).
- Brak rozbicia sił na ciśnieniowe i lepkie w funkcji fazy fali; brak biegunowej ustalonej przy równym obciążeniu.
- W04i, W04j importowane z GLHF bez historii pól (są siły, sondy i końcowe `.sim`).

## Literatura kluczowa

Theodorsen (NACA 496, 1935); Sears (1941) doi:10.2514/8.10655; Wu (1972) doi:10.5957/jsr.1972.16.1.66; Isshiki (1982) doi:10.2534/jjasnaoe1968.1982.54; Rehman & Floryan (2025) doi:10.1017/jfm.2025.10825; Godø i in. (2024) doi:10.1016/j.oceaneng.2024.119236. Pełna lista w raporcie v5, dodatek F.
