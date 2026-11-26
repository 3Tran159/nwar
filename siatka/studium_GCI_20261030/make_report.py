from pathlib import Path
import sys,json,hashlib,csv
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'.deps'))
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.pagesizes import A4
D=json.loads((HERE/'evidence.json').read_text(encoding='utf-8'))
FONT=HERE/'.deps/matplotlib/mpl-data/fonts/ttf'
for n,f in [('DV','DejaVuSans.ttf'),('DVB','DejaVuSans-Bold.ttf'),('DVI','DejaVuSans-Oblique.ttf')]:pdfmetrics.registerFont(TTFont(n,str(FONT/f)))
pdfmetrics.registerFontFamily('DV',normal='DV',bold='DVB',italic='DVI',boldItalic='DVB')
navy=colors.HexColor('#173443');teal=colors.HexColor('#007e83');muted=colors.HexColor('#526773');light=colors.HexColor('#eff5f6');amber=colors.HexColor('#8b5b15')
ss=getSampleStyleSheet()
ss.add(ParagraphStyle('BodyPL',fontName='DV',fontSize=9.3,leading=14,textColor=navy,spaceAfter=8))
ss.add(ParagraphStyle('SmallPL',parent=ss['BodyPL'],fontSize=8,leading=11.5,spaceAfter=6))
ss.add(ParagraphStyle('TitlePL',parent=ss['BodyPL'],fontName='DVB',fontSize=23,leading=28,spaceAfter=14))
ss.add(ParagraphStyle('H1PL',parent=ss['BodyPL'],fontName='DVB',fontSize=17,leading=22,spaceAfter=12))
ss.add(ParagraphStyle('H2PL',parent=ss['BodyPL'],fontName='DVB',fontSize=11.2,leading=16,spaceBefore=7,spaceAfter=6))
ss.add(ParagraphStyle('Kicker',parent=ss['SmallPL'],fontName='DVB',textColor=teal,fontSize=8.2,spaceAfter=10))
ss.add(ParagraphStyle('QuotePL',parent=ss['BodyPL'],fontSize=10,leading=15,backColor=light,borderPadding=10,spaceBefore=8,spaceAfter=14))
W,H=A4; usable=W-84;story=[]
def clean(s):return s.replace('–','-').replace('—','-').replace('‑','-')
def p(t,style='BodyPL'):return Paragraph(clean(t),ss[style])
def add(t,style='BodyPL'):story.append(p(t,style))
def h(t):add(t,'H2PL')
def tab(rows,widths,small=True):
 header_style=ParagraphStyle('HeaderPL',parent=ss['SmallPL'],textColor=colors.white,fontName='DVB')
 data=[[Paragraph(clean(str(c)),header_style if i==0 else ss['SmallPL' if small else 'BodyPL']) for c in row] for i,row in enumerate(rows)]
 t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT');t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),navy),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,light]),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),6),('LINEBELOW',(0,0),(-1,0),.5,navy),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#cbdadd'))]))
 story.append(t);story.append(Spacer(1,8))
def page(k,title):story.append(PageBreak());add(k,'Kicker');add(title,'H1PL')
def fig(name,width=usable):
 from PIL import Image as PILImage
 with PILImage.open(HERE/name) as im:ww,hh=im.size
 story.append(Image(str(HERE/name),width=width,height=width*hh/ww));story.append(Spacer(1,7))
def footer(c,doc):
 c.setStrokeColor(colors.HexColor('#d4e1e4'));c.line(42,37,W-42,37);c.setFont('DV',7);c.setFillColor(muted);c.drawString(42,24,'NTNU | Studium wrażliwości na siatkę | 30.10.2026');c.drawRightString(W-42,24,f'{doc.page}')
add('NTNU / HYDROFOIL / OCENA NUMERYCZNA','Kicker')
add('Studium wpływu siatki<br/>na jakość wyników CFD','TitlePL')
add('Wniosek: M09 spełnia projektowy test zgodności średnich C<sub>D</sub> i C<sub>L,total</sub> z dwiema gęstszymi siatkami w spokojnej wodzie. Dane nie wystarczają jeszcze do podania formalnej niepewności siatkowej ani do deklaracji walidacji fizycznej.','QuotePL')
fig('mesh_comparison.png')
add('<b>Zakres:</b> wycinek quasi-2D, 20 mm; cięciwa 1,19 m; U = 18 m/s; ρ = 1000 kg/m³; pole odniesienia 0,0238 m²; SST k-ω, All y+ Wall Treatment, VOF. Porównanie końcowe: II rząd w czasie, Δt = 1 ms, 10 iteracji na krok. Średnie z 200 próbek na siatkę w przedziale 1,84 &lt; t ≤ 2,04 s.','SmallPL')
add('<b>Najważniejsze liczby M09 / M07:</b> C<sub>D</sub> +0,4667%; C<sub>L,total</sub> -0,1643%; opór ciśnieniowy +1,5552%. M09 ma 214 908 komórek, czyli o 55,38% mniej niż M07. Oszczędności liczby komórek nie utożsamiamy ze zmierzonym przyspieszeniem obliczeń.','SmallPL')
page('01 / KRYTERIA I LITERATURA','Kiedy podobne wyniki można uznać za dobre?')
add('W przejrzanych wytycznych nie ma uniwersalnej reguły „krzywe nakładają się w 99%, więc mesh jest zwalidowany”. Tolerancja musi odpowiadać celowi obliczeń. W tej kampanii zapisano próg 1% dla różnic średnich C<sub>D</sub> i C<sub>L,total</sub>; traktujemy go jako kryterium projektowe, nie limit ustanowiony przez ITTC lub AIAA.')
tab([['Źródło','Co wnosi do oceny'],['ITTC 7.5-03-01-01, rev. 05 (2024), sekcje 2-4 [1]','Rozróżnia weryfikację rozwiązania i walidację względem eksperymentu. Wymaga systematycznej relacji między siatkami; omawia wpływ funkcji ściennych i oddzielne źródła niepewności.'],['NASA/NPARC, materiały oparte m.in. na AIAA G-077-1998 [2,3]','Zaleca badanie serii zagęszczeń, oszacowanie rzędu i GCI oraz sprawdzenie zakresu asymptotycznego. Mała różnica dwóch siatek sama nie określa błędu względem rozwiązania granicznego.'],['Roache, AIAA Journal 36(5), 696-702 (1998) [4]','Pokazuje różnicę między zbieżnością iteracyjną i siatkową. GCI służy do porównywalnego raportowania niepewności numerycznej; dobra jakość komórek nie zastępuje tego oszacowania.'],['Eça i Hoekstra, J. Comput. Phys. 262, 104-130 (2014) [5]','Dopasowanie metodą najmniejszych kwadratów uwzględnia rozrzut wyników. Wymaga systematycznie zagęszczanych siatek; nie uzasadnia dowolnego łączenia wariantów o innych ustawieniach.'],['ITTC 7.5-03-02-01, rev. 02 (2024) [6]','Przykład badania oporu i profilu fali na czterech siatkach. Ocena wielkości całkowej i lokalnej jest osobna: zgodny opór nie dowodzi zgodności całego pola.']],[165,usable-165])
h('Miara zgodności zastosowana tutaj')
add('δ<sub>ij</sub>(φ) = 100 · (φ̄<sub>i</sub> - φ̄<sub>j</sub>) / |φ̄<sub>j</sub>|. Wartość odniesienia i okno czasu muszą być jawne. Dla wartości bliskich zeru stosujemy skalę odniesienia lub różnicę bezwzględną. Nie używamy procentu wizualnego nakładania się linii.')
h('Formalne oszacowanie, gdy seria spełnia założenia')
add('Dla trzech siatek: 1 = najdrobniejsza, 3 = najgrubsza; przy równym r = h₂/h₁ = h₃/h₂ i monotonicznej zbieżności:<br/>p = ln |(φ₃ - φ₂)/(φ₂ - φ₁)| / ln r<br/>φ<sub>ext</sub> = (r<sup>p</sup> φ₁ - φ₂)/(r<sup>p</sup> - 1)<br/>GCI<sub>fine</sub> = F<sub>s</sub> · |(φ₁ - φ₂)/φ₁| / (r<sup>p</sup> - 1) · 100%.<br/>F<sub>s</sub> = 1,25 dotyczy poprawnie przeprowadzonego badania z co najmniej trzema siatkami; nie jest automatyczną gwarancją. Sprawdzamy też zgodność z zachowaniem asymptotycznym [3,4].','SmallPL')
add('Pasmo ±1% na wykresie jest tolerancją porównania, nie GCI, błędem modelu ani 95-procentowym przedziałem ufności. Walidacja fizyczna dodatkowo potrzebuje danych pomiarowych oraz ich niepewności [1].','SmallPL')
page('02 / WARIANTY SIATKI','Co rzeczywiście porównaliśmy')
add('Dostępna kampania zmienia rozdzielczość zewnętrzną, rozdzielczość profilu i warstwę przyścienną. Są to warianty siatki quasi-2D, a nie udokumentowany test niezależnych rodzin tetrahedral / polyhedral / hexahedral. Nie deklarujemy uniwersalnej niezależności od typu elementu.')
fig('mesh_variants_history.png')
rows=[['ID','Komórki','1. warstwa<br/>[μm] / warstwy','Baza / profil / FS<br/>[mm]','Rola']]
roles={'M02':'Gruby wariant wall-function','M03':'Pośredni wall-function','M04':'Zmiana reżimu przyściennego','M05':'Gęstszy wall-function','M06':'Rozwinięcie low-y+','M07':'Gęsta referencja','M08':'Kontrola rozdzielczości','M09':'Oszczędny wariant zewnętrzny'}
for m in ['M02','M03','M04','M05','M06','M07','M08','M09']:
 z=D['mesh_definition_evidence'].get(m)
 if m=='M09':z={'first_layer_um':1.5306122449,'layers':48,'base_m':.25,'foil_target_m':.002857142857,'free_surface_m':.02857142857}
 rows.append([m,f'{D["quality"][m]["cell_count"]:,}'.replace(',',' '),f'{z["first_layer_um"]:.3f} / {z["layers"]}',f'{1000*z["base_m"]:.1f} / {1000*z["foil_target_m"]:.2f} / {1000*z["free_surface_m"]:.2f}',roles[m]])
tab(rows,[38,65,90,135,usable-328])
add('FS = zadany rozmiar w strefie powierzchni swobodnej; „profil” = target powierzchniowy. W M09 baza 250 mm dotyczy dalekiej części domeny; środkowy obszar jest chroniony rozmiarem 142,86 mm. M07/M08/M09 mają tę samą pierwszą warstwę, 48 warstw i 15,46 mm łącznej grubości warstwy pryzmatycznej.','SmallPL')
add('Dane historyczne służą do screeningu. Mają różne końce okien i nie stanowią wspólnego badania końcowego. W M02/M03/M05 audyt wykazał także niezerowe przesunięcie przekrojów przy ekstrudowaniu. Końcowy zestaw M07/M08/M09 ma potwierdzoną jedną warstwę w rozpiętości i zerowe przesunięcie x-z.','SmallPL')
page('03 / WYNIKI','Ponowne obliczenie ze źródłowych przebiegów')
add('Średnie i różnice przeliczono z historii CSV, nie tylko z istniejącego werdyktu kampanii. Dla M07/M08/M09 potwierdzono po 200 próbek w oknie (1,84; 2,04] s. Kontrolny przebieg M09 przy 0,5 ms zawiera 400 próbek w tym samym oknie. Wartości zgadzają się z zapisanymi podsumowaniami do 10⁻¹² w sprawdzonych wielkościach.')
rows=[['ID','C<sub>D</sub>','C<sub>L,total</sub>','F<sub>D,p</sub> [N]','F<sub>D,v</sub> [N]']]
for m in ['M09','M08','M07']:
 v=D['cases'][m]['mean'];rows.append([m,f'{v["CD"]:.9f}',f'{v["CL_total"]:.9f}',f'{v["pressure_drag_N"]:.6f}',f'{v["viscous_drag_N"]:.6f}'])
tab(rows,[45,115,115,118,usable-393])
add('F<sub>D,p</sub> i F<sub>D,v</sub> to składowe oporu wycinka o szerokości 20 mm. Współczynnik C<sub>L,total</sub> zachowuje definicję z kampanii; nie zastąpiono go składową dynamiczną.','SmallPL')
rows=[['Porównanie','δ C<sub>D</sub> [%]','δ C<sub>L</sub> [%]','δ F<sub>D,p</sub> [%]','δ F<sub>D,v</sub> [%]']]
for a,b in [('M09','M07'),('M09','M08'),('M08','M07')]:
 v=[100*(D['cases'][a]['mean'][k]-D['cases'][b]['mean'][k])/abs(D['cases'][b]['mean'][k]) for k in ['CD','CL_total','pressure_drag_N','viscous_drag_N']];rows.append([a+' / '+b,*[f'{x:+.4f}' for x in v]])
tab(rows,[103,102,102,102,usable-409])
h('Co z tego wynika')
add('Przy zadanym progu 1% oba współczynniki przechodzą porównanie M09 z M08 i M07. Największa różnica C<sub>D</sub> w całym dopasowanym zestawie to 0,4924% (M08/M07), a C<sub>L,total</sub> 0,1810%. To wspiera wybór M09 dla średnich sił w badanych warunkach.')
add('Różnica oporu ciśnieniowego M09/M07 wynosi 1,5552%, a M08/M07 1,6522%. Zatem twierdzenie „wszystkie składowe siły są zgodne do 1%” byłoby nieprawdziwe. Różnica całkowitego oporu M09/M07 to około 0,1337 N, z czego około 0,1230 N pochodzi ze składowej ciśnieniowej.')
h('Dryf i krok czasowy')
tab([['Sprawdzenie','C<sub>D</sub>','C<sub>L,total</sub>','Interpretacja'],['Zmiana okna na M09:<br/>(1,64;1,84] → (1,84;2,04] s','-0,2259%','+0,1107%','Pozostała ewolucja w czasie; nie jest przedziałem niepewności.'],['M09, Δt: 1 → 0,5 ms','-0,002423%','+0,001453%','Mała wrażliwość w tej gałęzi i tym oknie; tylko dwa kroki czasu.']],[188,76,76,usable-340])
add('Dryf oporu w trzech siatkach wynosi 0,189-0,245%, a samej części ciśnieniowej 0,658-0,864%. Jest większy od różnicy M09/M08 dla C<sub>D</sub> (0,0256%). Nie uzasadnia to podania dokładności rozwiązania na poziomie 0,026%. Próba 0,5 ms startuje z tego samego zapisanego stanu w t ≈ 1,64 s i trwa 0,40 s; nie mierzy błędu wcześniejszej historii.','SmallPL')
page('04 / OCENA','Co jest potwierdzone, a co pozostaje otwarte')
tab([['Obszar','Ocena','Uzasadnienie'],['Zgodność średnich sił','Warunkowo potwierdzona','M09 mieści się w projektowym 1% względem M08 i M07 dla C_D i C_L,total; wspólne ustawienia i okno.'],['Formalne GCI / U_grid','Nie wyznaczono','Zagęszczanie lokalne, stała warstwa przyścienna; brak jednej uzasadnionej skali h i potwierdzonego trendu asymptotycznego.'],['Niezależność lokalnego pola','Nie wykazano ilościowo','Zgodne siły nie dowodzą zgodności C_p(x/c), naprężeń, śladu i interfejsu.'],['Walidacja fizyczna','Nie wykazano w tym studium','Zestaw nie zawiera dopasowanego eksperymentu z budżetem niepewności.'],['Przeniesienie na fale / klapę','Nieuprawnione na tym etapie','Wymaga osobnej oceny amplitudy, fazy, średnich i obciążeń szczytowych dla nowych warunków.']],[116,110,usable-226])
h('Jakość komórek i reżim przyścienny')
rows=[['ID','Min. CellQuality','Maks. skewness','y+ p95*','Powierzchnia y+ &lt; 1*','Maks. y+*']]
yplus={x['mesh']:x for x in D['configured_wall_yplus_audit']['cases']}
for m in ['M09','M08','M07']:
 q=D['quality'][m];y=yplus[m];rows.append([m,f'{q["min_cell_quality"]:.4f}',f'{q["max_skewness_angle_deg"]:.2f}°',f'{y["area_weighted_yplus_p95"]:.3f}',f'{y["wall_area_yplus_below_1_pct"]:.3f}%',f'{y["max_yplus"]:.1f}'])
tab(rows,[40,89,91,66,132,usable-418])
add('* Diagnostyka y+ pochodzi z różnych zapisów: M09 t = 1,64 s; M08 t = 2,00 s; M07 t = 2,04 s. p95 jest ważone polem powierzchni. Nie jest to wspólne okno statystyczne.','SmallPL')
add('Wszystkie trzy siatki mają zero komórek o ujemnej objętości, niezamkniętych i zdegenerowanych; min. FaceValidity = 1. M09 ma dwie komórki z VolumeChange &lt; 0,01 (minimum 0,00426). Jest to sygnał lokalnej kontroli przejścia rozmiarów, nie automatyczny dowód błędu ani uniwersalne kryterium odrzucenia.')
add('Prawie cała powierzchnia M09 pracuje przy y+ &lt; 1, ale maksimum przy krawędzi spływu wynosi około 254. Mały udział powierzchni nie dowodzi małego wpływu na opór ciśnieniowy. Celowy test krawędzi spływu pozostaje uzasadniony.')
h('Dlaczego nie dopasowujemy GCI do M09/M08/M07')
add('M09 → M08 zagęszcza głównie odległą część domeny. M08 → M07 dodatkowo zmienia powierzchnię profilu, okolice profilu i powierzchnię swobodną. Rozmiar pierwszej warstwy pozostaje stały. Ponadto C_D najpierw rośnie, potem maleje, a C_L zmienia trend odwrotnie. Samo uporządkowanie po liczbie komórek nie tworzy kontrolowanej rodziny. Podanie p i GCI z takiego dopasowania dawałoby pozorną precyzję.')
add('Kontrolny przebieg M09 przy 0,5 ms ma zapisany maksymalny resztowy budżet masy BDF2 4,90·10⁻⁵% strumienia wlotowego; zmiana sił w drugiej połowie iteracji kroku wynosi maks. 0,000309% w x i 0,000153% w z. To korzystne diagnostyki, ale nie pełne oszacowanie błędu iteracyjnego ani walidacja.','SmallPL')
page('05 / DOMKNIĘCIE I ŹRÓDŁA','Co dopisać do pracy i co jeszcze policzyć')
add('<b>Proponowane sformułowanie do pracy:</b> Przeprowadzono studium wrażliwości rozwiązania na wariant siatki dla spokojnej wody. Przy jednakowych ustawieniach numerycznych i wspólnym oknie uśredniania siatka M09 wykazała różnice średnich C_D i C_L,total względem M07 odpowiednio 0,467% i 0,164%, a względem M08 0,026% i 0,017%. Spełniono projektowe kryterium zgodności 1% dla tych wielkości. Wynik stanowi podstawę praktycznego wyboru siatki, przy nieoszacowanej formalnie niepewności dyskretyzacji.','QuotePL')
add('<b>Minimalne dalsze kroki:</b> (1) wydłużyć wspólne przebiegi do mniejszego dryfu i potwierdzić wynik w kilku oknach; (2) przygotować co najmniej trzy systematyczne poziomy tej samej rodziny, a przy rozrzucie cztery lub więcej i rozważyć metodę Eçy-Hoekstry; (3) osobno skontrolować krawędź spływu oraz C_p, naprężenia i ślad; (4) dla fal sprawdzić rozdzielczość powierzchni swobodnej, krok czasu, powtarzalność cykli, amplitudę i fazę. [1,3,5]')
add('Propozycja projektowa dla nowej serii: r około 1,4 przy kontrolowanym zagęszczaniu w płaszczyźnie. W quasi-2D z jedną warstwą w rozpiętości przybliżenie h ∝ N⁻¹/² ma sens dopiero dla podobnych siatek; automatyczne N⁻¹/³ nie odpowiada takiemu zagęszczaniu. Docelowy próg U_grid, np. 1% średnich sił, trzeba uzgodnić z dokładnością potrzebną do wykrycia efektu fal lub klapy. To proponowany cel, nie wymóg normy.','SmallPL')
h('Literatura - źródła pierwotne i oficjalne')
refs=[
('[1] ITTC (2024). 7.5-03-01-01, rev. 05. Uncertainty Analysis in CFD Verification and Validation Methodology and Procedures. Sekcje 2, 3.2-3.3, 4.','https://ittc.info/media/11950/75-03-01-01.pdf'),
('[2] NASA/NPARC. Tutorial on CFD Verification and Validation. Materiał odwołuje się do AIAA G-077-1998; korzystano z publicznego opracowania NASA, nie pełnego płatnego przewodnika AIAA.','https://www.grc.nasa.gov/www/wind/valid/tutorial/tutorial.html'),
('[3] NASA/NPARC. Examining Spatial (Grid) Convergence. Definicje h, r, ekstrapolacji Richardsona i GCI.','https://www.grc.nasa.gov/www/wind/valid/tutorial/spatconv.html'),
('[4] Roache, P. J. (1998). Verification of Codes and Calculations. AIAA Journal, 36(5), 696-702. DOI: 10.2514/2.457.','https://doi.org/10.2514/2.457'),
('[5] Eça, L., Hoekstra, M. (2014). A procedure for the estimation of the numerical uncertainty of CFD calculations based on grid refinement studies. J. Comput. Phys., 262, 104-130. DOI: 10.1016/j.jcp.2014.01.006.','https://www.marin.nl/en/publications/a-procedure-for-the-estimation-of-the-numerical-uncertainty-of-cfd-calculations-based-on-grid-refinement-studies'),
('[6] ITTC (2024). 7.5-03-02-01, rev. 02. Uncertainty Analysis in CFD, Examples for Resistance and Flow.','https://www.ittc.info/media/11954/75-03-02-01.pdf')]
for title,url in refs:add(title+' <link href="'+url+'" color="#007e83">Otwórz źródło</link>.','SmallPL')
h('Ślad danych i odtwarzalność')
add('Dane: F:/ntnu/mesh_screening_20261028/force_stabilization_20261029/. Główne źródła: matched_endpoint_results.json, źródłowe history.csv / matched_history.csv, selected_mesh_time_results.json, audyty geometrii komórek i y+. Pakiet zawiera evidence.json z odczytanymi wartościami, zakresami przebiegów i sumami SHA-256 źródeł oraz mesh_comparison_values.csv. Ocena dotyczy zapisanego zestawu z 29-30.10.2026; nie uruchamiano nowych symulacji.','SmallPL')
SimpleDocTemplate(str(HERE/'mesh_study_PL.pdf'),pagesize=A4,rightMargin=42,leftMargin=42,topMargin=38,bottomMargin=50,title='Studium wpływu siatki na jakość wyników CFD',author='NTNU - analiza danych kampanii',pageCompression=1).build(story,onFirstPage=footer,onLaterPages=footer)
print('Created mesh_study_PL.pdf')
