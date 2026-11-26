# NWAR — adaptacja sterowania Godø do quasi-2D URANS–VOF

6 listopada 2026

**Pierwszy cel.** Sprawdzić, czy jedną klapką można obniżyć średnią siłę oporu przy zadanej nośności w tej samej fali. Osobno sprawdzić, ile daje dopuszczenie okresowej zmiany nośności w fazie korzystnej dla napędu falowego.

## Co można przenieść z pracy Godø

Godø i współautorzy (2024, sekcje 2.1–2.4) użyli przyspieszonego cppNDLL jako środowiska symulacyjnego i algorytmu TD3 jako regulatora. Symulowali główny płat o skończonej rozpiętości. Prędkość postępowa była stała, położenie pionowe mogło się zmieniać, a komendą był kąt obrotu całego płata. Ograniczenia wynosiły ±7,5° i 90°/s. Obserwacje obejmowały położenie i prędkość pionową, elewację fali, pionową prędkość wody na średnim poziomie powierzchni oraz poprzednią komendę. Zysk energetyczny uwzględniał siłę wzdłużną i dodatnie zapotrzebowanie mocy napędu aktuatora. Podane 61,8% dotyczyło modelu autora w jednej regularnej fali czołowej i porównania ze spokojną wodą. [Godø i in. (2024), sekcje 2–4](https://doi.org/10.1016/j.oceaneng.2024.119236) · [Rozprawa NTNU, §4.6](https://hdl.handle.net/11250/3172953)

| Godø | Odpowiednik NWAR |
|---|---|
| CppNDLL wykonuje interakcje treningowe. | Tani model dynamiczny zidentyfikowany z trajektorii CFD wykonuje interakcje. Quasi-2D URANS–VOF generuje dane i testuje gotowy regulator w zamkniętej pętli. |
| Obrót całego płata, swobodny heave. | Jedna komenda kąta klapki przy \(x/c=0{,}80\). Główny płat ma stałe położenie i zanurzenie nominalne. Kąt i prędkość klapki ograniczamy do zakresu sprawdzonego dla naszej siatki. |
| Stan jednostki i lokalna fala. | Historia błędu \(C_L\), zmierzony kąt klapki i jego prędkość, poprzednia komenda. Do wariantu wave-preview dodajemy wyłącznie sygnał sondy przed płatem i prognozę, którą da się wyznaczyć z danych dostępnych do bieżącego kroku. |
| Wysokość, komfort i moc całej uproszczonej jednostki. | Siły przekroju \(F_x,F_z\), błąd śledzenia \(C_L\), moment zawiasowy, koszt aktuacji i lokalne ciśnienie na klapce. |

### Mechanizm, który warto sprawdzić

Godø uzyskał korzystną średnią siłę wzdłużną przez odpowiednie fazowanie nośności względem pionowej prędkości wody. W quasi-2D przy małym kącie lokalnego napływu można w przybliżeniu rozdzielić siłę wzdłużną na opór wzdłuż lokalnego napływu i rzut nośności. Przy osi \(x\) zgodnej ze średnim napływem ten drugi składnik wynosi w przybliżeniu \(-L_\perp w_{\mathrm{rel}}/U\). Tu \(w_{\mathrm{rel}}=w\), bo płat jest zamocowany. Weryfikujemy ten mechanizm na rozkładzie fazowym \(F_x,F_z,w\) oraz kowariancji \(F_z\) i \(w\). Sonda prędkości powinna reprezentować falę padającą na głębokości płata. Sondujemy przed płatem i kalibrujemy przesunięcie fazowe na przypadku FIXED. [Godø i in. (2024), §3 i §4.1](https://doi.org/10.1016/j.oceaneng.2024.119236)

**Dwa osobne pytania.** Pasmo \(C_L\) ±1% ogranicza celową modulację nośności, która napędzała strategię Godø. W teście regulacyjnym utrzymujemy to pasmo i mierzymy zmianę oporu. W osobnym eksperymencie mechanizmu dopuszczamy ograniczone wahania \(C_L\) przy tej samej średniej nośności. Wtedy można porównać korzystną fazę z fazą przesuniętą o 180°, zachowując amplitudę i pozostałe warunki. Odtworzenie dynamiki heave wymagałoby później osobnego modelu ze swobodą pionową i zdefiniowaną masą.

## Kolejność implementacji

1. **WAVE/FIXED.** Kończymy narastanie Stokesa V dla sealed, \(U=18\) m/s, \(\lambda=10\) m, \(H=0{,}10\) m. Zachowujemy aktualny krok 0,5 ms, 12 iteracji i limit CFL interfejsu 0,9. Wybieramy trzy powtarzalne cykle po rozruchu. Zapisujemy \(\eta\) przed płatem i przy płacie, lokalne \(u,w\), siły, \(M_h\), \(p_{\min}\) klapki i parametry numeryczne. Crest sondy przed płatem wyznacza fazę 0°.
2. **WAVE/ACTIVE ±1° i mapa fazowa.** Z tego samego stanu falowego zadajemy łagodnie narastającą sinusoidę o okresie spotkaniowym około 0,456 s. Dopasowujemy zespolone amplitudy pierwszej harmonicznej do przebiegów przy wspólnej fazie. Lokalna odpowiedź klapka–nośność to \(G_L=(\hat C_{L,\mathrm{active}}-\hat C_{L,\mathrm{fixed}})/\hat\delta_\mathrm{meas}\). Pierwsza komenda kompensująca wahania wynosi \(\hat\delta_\mathrm{ff}=-\hat C_{L,\mathrm{fixed}}/G_L\). Osobno dobieramy średni kąt, jeśli trzeba skorygować średnie \(C_L\). Sprawdzamy mapę w nowym przebiegu CFD. Wynik identyfikacji przy jednej częstotliwości opisuje lokalną odpowiedź dla tej fali.
3. **Regulator odniesienia.** W STAR-CCM+ używamy istniejącego User Defined Vertex Motion i aktualizujemy zadaną klapkę z makra Java. Proponowany pierwszy takt sterowania to 5 ms, czyli 10 kroków CFD. Na początku każdego bloku bierzemy pomiary z ostatniego ukończonego kroku. Wyznaczamy komendę PI lub PI plus mapa fazowa, stosujemy ograniczenie kąta i szybkości oraz płynnie interpolujemy do kolejnej komendy. Logujemy osobno kąt zadany i zmierzony. Pierwsza próba integracyjna ma zweryfikować kierunek ruchu, opóźnienie, dodatnie objętości i odtwarzalność po wznowieniu.
4. **Surrogate i TD3.** Do danych z jednej sinusoidy dokładamy przynajmniej jedno ograniczone, płynne wymuszenie o zmiennej częstotliwości lub fazie. Dopasowujemy mały model wejście–wyjście z pamięcią, przewidujący \(C_L,C_D,M_h\) i sygnał ciśnienia na klapce. Dzielimy dane po całych trajektoriach i warunkach falowych. Wyniki oceniamy również w swobodnym przewidywaniu wielu kroków. Dopiero potem podpinamy TD3. Startujemy od danych z bezpiecznego PI i ograniczonych perturbacji. Gotową politykę zamrażamy i odtwarzamy w STAR na tych samych pomiarach, z którymi trenowała. [Referencyjna implementacja TD3 Fujimoto](https://github.com/sfujim/TD3) · [Publikacja TD3](https://proceedings.mlr.press/v80/fujimoto18a.html)

## Jak rozstrzygnąć wynik

- **Porównania.** FIXED 0°, PI, PI z podglądem i później TD3. Ta sama geometria, siatka, fala, krok i okno analizy. Jeżeli średni \(C_L\) różni się istotnie, dodajemy FIXED z kątem dobranym do porównywalnej średniej nośności. Spokojna woda jest osobnym punktem odniesienia do oporu dodanego w falach.
- **Cel TD3.** Minimalizujemy średnie \(C_D\) przy utrzymaniu zadanego \(C_L\). Raportujemy czas w paśmie ±1%, RMS i maksymalny błąd \(C_L\), średni \(C_D\), \(p_{\mathrm{ABS,min}}\) na klapce, wykorzystanie ograniczeń kąta oraz moment zawiasowy. Wdrożenie ogranicza komendy poza polityką uczoną.
- **Moc.** Przy stałej prędkości porównujemy \(U\overline{F_x}\). Jeżeli \(M_h\) oznacza moment płynu działający na klapkę w tej samej konwencji co \(\dot\delta\), idealne mechaniczne zapotrzebowanie aktuatora bez odzysku to \(\max(0,-M_h\dot\delta)\). Przed bilansem weryfikujemy znaki i jednostki na znanym ruchu. Raportujemy moc przekroju i aktuatora osobno.
- **Zakres.** Jeden regularny przypadek rozstrzyga, czy metoda działa lokalnie. Kolejna fala regularna lub bichromatyczna sprawdza przenoszenie. JONSWAP zostaje na odłożony test z rzeczywistym, przyczynowym sygnałem podglądu. Wynik przekroju quasi-2D dotyczy obciążeń i oporu przekroju. Osiągi całej jednostki wymagają dynamiki kadłuba i płatów o skończonej rozpiętości.

## Co jest publicznie dostępne

Na publicznym profilu Godø znalazłem **dane modelu oporu i narzędzia pomocnicze**. Repozytorium NTNU-IMT udostępnia generator kadłubów. W przejrzanych publicznych repozytoriach nie znalazłem cppNDLL z uruchamialnym środowiskiem i wagami polityki z artykułu 119236. Artykuł wskazuje publiczny kod Fujimoto jako punkt wyjścia do TD3. [Repozytorium danych oporu Godø](https://github.com/johnmartingodo/hydrofoil_fast_ferry_resistance_model) · [FASTSHIPS, NTNU](https://www.ntnu.edu/imt/software/fastships) · [Generator kadłubów NTNU](https://github.com/NTNU-IMT/fastships_hull_generator) · [Kod TD3](https://github.com/sfujim/TD3)
