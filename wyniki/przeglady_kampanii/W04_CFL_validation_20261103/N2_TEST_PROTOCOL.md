# W04 | Test niezależności numerycznej VOF: N=1 / N=2

Cel badania: weryfikować **efekty względne fal** (delta względem C01 i różnice pomiędzy falami), a nie wymagać arbitralnej absolutnej dokładności współczynników.

## Wyniki audytu wyjściowego (03.11.2026)

- Siatka M13_W04, 572176 komórek: istniejące testy geometrii i chronionych warstw przy płacie zaliczone.
- C01 po PRE W04 zgodny z przyjętym źródłem: CL=0.31565950495122014, CD=0.007002316911710474 (dane settling_check.json).
- Przepływ W04: dt=0.0004 s; H=1.5 m; lambda=38.99857691441418 m; encounter T=1.5115894239782313 s; 2. rząd.
- 1702 zapisów PRE W04 potwierdza N=1 podkrok VOF; obecny W04 dziedziczy PRE, ale bez bezpośredniego readbacku checkpointu nie zaznaczać N=1 jako niezależnie potwierdzonego.
- Do porównania N=1/N=2 W04 **NIE** wolno zmieniać ustawień trwającego procesu.

## Procedura A/B po zwolnieniu aktywnego solvera

1. Zachować całą historię, finalny stan i checksum W04 N=1; NIE wyłączać aktualnego procesu ani modyfikować wejściowego .sim.
2. Test wstępny: skopiować *ten sam* checkpoint W04, np. checkpoint_t13.0408.sim (zaświadczyć SHA256), do nowego, izolowanego katalogu W04_N2; jedyny parametr fizyczno-numeryczny do zmiany: przełączyć VOF na Implicit Multi-Step, fixed substeps=2. Potwierdzić readback solvera. Pozostawić dt=0.0004 s, M13_W04, H, lambda, SST, gęstości i BC bez zmian; NIE reinitializować pól.
3. Pozostawić co najmniej 1 encounter T na zanikanie różnicy stanów startowych po zmianie N. Następnie na wspólnym przedziale czasowym wyznaczyć 2+ zgodne cykle CL_hydro, CD_total, Fx, Fz, eta(x=-15,-0.5,0,+5) i ich fazę względem grzbietów fali. Porównać z uprzednio obliczoną gałęzią N=1 na dokładnie tym samym oknie czasu.
4. Obliczyć średnią cykliczną, zakres peak-to-peak, rozrzut cykl/cykl, różnicę A/B, przesunięcie fazy i CFL na podkrok; sprawdzić czy N=2 zmienia znak, trend lub względną skalę efektu fali.
5. Jeśli efekt N=2 jest mały na tle efektu fali i przyszłego rozdzielenia wariantów: można uzasadnić użycie N=1 wyłącznie dla porównania względnego. Jeśli istotny, N=2 stosować **we wszystkich** falach, a tam gdzie konieczne powtórzyć W04.
6. Jeżeli różnica A/B jest graniczna, wykonać test pełny: rozgałęzić N=2 już z tego samego *calm PRE* t=5.8 s przed wprowadzeniem fali, żeby uniknąć odziedziczenia błędów N=1 z fazy propagacji.

## Proponowane kryteria robocze (nie norma bezwarunkowa)

- Cztery powtarzalne cykle potwierdzone z lokalnej sondy fali; obcięcie rampy i faz przejściowych. 
- N=2: efektywny CFL transportu alfa ~max(CFL_interface / 2) <= 1 w badanej części falowej, ale dodatkowo zweryfikować lokalizację maksimów.
- Wstępnie przyjąć tolerancję 5% amplitudy **mierzonego efektu fali**, nie 5% bezwzględnego CL/CD. Wartość ta służy ekranowaniu; końcowy wniosek musi porównać błąd numeryczny z *różnicą* między wariantami falowymi.
- Jeśli różnica efektów między dwiema falami nie przekracza niepewności N=1 vs N=2, nie wprowadzać sztucznego rankingu. W razie zmiany znaku delta CD nie wystarcza tolerancja względna, konieczne też porównanie absolutne.
- Kontrola jakości fali: sprawdzić H oraz T na x=-15 m, następnie fazę/grzbiety przy płacie; kontrola bilansu masowego to strumienie + pochodna inventory, nie samo inventory.

## Ograniczenia i bezpieczeństwo

Aktualny W04 pracuje na GPU. Nie uruchamiać kolejnego solvera równolegle, nie ingerować w bieżący W04, innych agentów ani kolejkę W05-W07. Nie wprowadzać zmiany podkroków w połowie obecnej symulacji. Ten plik jest wyłącznie protokołem, nie uruchamia testu ani automatyzacji.

Pliki dowodowe: validation_snapshot.json, observed_periods.json, CFL_interface_W04.svg, CL_W04.svg, CD_W04.svg.
