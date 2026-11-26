# NWAR — przebieg prac (28.10–16.11.2026)

Chronologia odtworzona z nazw i dat folderów, raportów przekazania (HANDOFF) i raportu v5. Liczby — z plików w `wyniki/`.

| Data | Etap | Co wyszło | Gdzie |
|---|---|---|---|
| 28.10 | Noc CFD: pierwsze przebiegi płata, sondy | Wizualizacje stanu, kolejka nocna | `siatka/noc_CFD_20261028/` |
| 29.10 | Fale quasi-2D na siatce M10, stabilizacja siatki, zachowanie w czasie | Próby startu fali na wlocie (kilka restartów, notatki `README_INSPECTION`) | `siatka/siatki_i_fale_2026-10/` |
| 30.10 | Studium GCI (rodziny G09/G10, M/F) | Wyniki i wnioski: `mesh_study_PL.pdf` | `siatka/studium_GCI_20261030/` |
| 30–31.10 | Optymalizacja siatek M10–M13, piloty kroku czasu Δt 0,2/0,4 ms na GPU i CPU | **M13** wybrana: 3,09·10⁵ komórek, ΔCL +1,15 %, ΔCD −3,10 % vs M12, ~12× taniej | `siatka/optymalizacja_M10_M13/`, `wyniki/siatka_M13/` |
| 31.10 | Fala na M13 („wave_surface_only”), awarie przełączania warunku brzegowego, triage nocny | Analiza przyczyny przełączania warunku brzegowego fali (notatka 31.10 22:46) | `…/wave_surface_only/` |
| 01.11 | Czysta kampania C01 (spokojna woda), polityka odniesienia, zatwierdzony plan fal | C01: Fx = 27,0 N, Fz = 1220 N; plan W01–W07 | `…/wave_campaign_20261101/`, `…/approved_wave_plan_20261101/` |
| 02–04.11 | Automatyzacja NWAR: kolejka fal, wznowienia z zapisów, polityka 5 cykli; W01–W07 | Pierwsze ΔFx < 0; W04 −10,1 N | `automatyzacja/`, `star/makra/NwarWave.java` |
| 03.11 | Paczka przenośna na GLHF (STAR 2606, bez instalacji) | Paczki v2, v3, transfer v4, poprawki panelu | `glhf_pakiet/` |
| 05–09.11 | Fale krótkie i warianty H: W04c, e, f, g, h, i, j; fala dwuskładnikowa W08bi (GLHF) | 14 przypadków zaakceptowanych 09.11 | `wyniki/pakiet_final_20261109/` |
| 09–10.11 | Analiza mechanizmu: Sears, fala biegnąca, model napływu z opóźnieniem, podatna krawędź | Sears RMSE 0,818 N; napływ z opóźnieniem R² 0,967; krawędź podatna — brak zysku | `automatyzacja/w04e_aoa.py`, `mechanism_followup.py` |
| 10.11 | Raport v5 (EN) + streszczenie PL | Wersja końcowa | `raporty/` |
| 11–16.11 | Jednostronicowe podsumowania dla Sverrego (v1–v4) | Onepage 11.11 i v4 16.11 w repo; v2/v3 tylko w archiwum H: | `raporty/onepage_v4_20261116/` |

## Decyzje

- Siatka M13 zamiast M12: koszt 34,7 vs 409 min na 1 s symulacji przy różnicach sił < 5 %. Świadomie **bez** formalnej niezależności od siatki.
- Analiza zawsze z cykli 2–5; pierwszy cykl odrzucony (rozbieg).
- Ciężkie fale (domena rozszerzona) liczone na GLHF; laptop dla krótkich i kontroli.
- Raport tylko o sztywnym płacie (bez podatnych krawędzi w tytule); NWAR rozwinięty przy pierwszym użyciu.
- Kąt −0,11° odczytany z siatki to artefakt; kąt geometryczny = 0°.

## Błędy i lekcje

- **Za dużo wersji tego samego**: paczki GLHF w 6+ wariantach (`_v2`, `_v3`, `GPU_Fix_v1–3`, `Startup_Fix_v4–5`) i duplikaty zip (4× 818 MB W08bi). Lekcja: jedna paczka + changelog.
- **Punkty zapisu bez sprzątania**: 722 pliki `.sim` (323 GB) na F: i H: — większość to pośrednie zapisy. Lekcja: zostawiać SETUP + FINAL.
- **Courant na powierzchni > próg HRIC** we wszystkich falach (1,90–2,00 vs 1,00) — wyszło w audycie po kampanii. Lekcja: sprawdzić CFLi przed kampanią.
- **Porównanie siatek miesza efekty** (inna siatka, inny Δt, inny stan ustalenia) → 1,14 N rozbieżności na spokojnej wodzie. Lekcja: zmieniać jedno naraz.
- **Tabele bez opisu kolumn** w pierwszych wersjach raportu (kolumny „tilt”/„rest”) — czytelnik nie wiedział, co czyta. Lekcja: każda kolumna opisana.

## Co dalej (nie zrobione)

1. W05 przy Δt/2 i Δt/4 (17,6 h i 35,3 h GPU) — błąd czasowy.
2. Siatka równoważna M12 (32,9 h) i pusty kanał (8,8 h) — błąd siatki i odbicia.
3. Mini-VOF z poruszaną klapą (zawias x/c = 0,80), skan fazy klapy przy równym średnim Fz.

Projekt potem przeszedł w sterowanie płatem (Godø, MPC, „wzór sufitu komfortu”) — to osobny wątek, poza tym repo.
