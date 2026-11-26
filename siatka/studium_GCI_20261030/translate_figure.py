from pathlib import Path
import runpy
P=Path(__file__).resolve().parent
s=(P/'make_figures.py').read_text(encoding='utf-8').split("old=D['mesh_convergence']")[0]
replacements={
'M09: różnice Cᴅ i Cʟ względem M07 poniżej 0,5%':'M09: mean drag and lift differ from M07 by less than 0.5%',
'Spokojna woda · quasi-2D · U = 18 m/s · SST k-ω · II rząd w czasie · Δt = 1 ms · 10 iteracji/krok':'Calm water · quasi-2D · U = 18 m/s · SST k-ω · second-order time scheme · Δt = 1 ms · 10 iterations/step',
'Wniosek dotyczy badanego okna i wariantów siatki. Formalna niepewność siatkowa GCI pozostaje nieokreślona.':'Scope: the tested meshes and averaging window. Formal grid uncertainty (GCI) has not yet been established.',
'A  Przebieg współczynnika oporu':'A  Drag coefficient history',
'B  Przebieg całkowitej siły nośnej':'B  Total lift coefficient history',
'okno porównania':'comparison window',
'Czas fizyczny t [s]':'Physical time t [s]',
'Średnie: 1,84 < t ≤ 2,04 s':'Averages: 1.84 < t ≤ 2.04 s',
'Liczba komórek [tys.]':'Cell count [thousands]',
'Różnica średniej względem M07 [%]':'Mean difference relative to M07 [%]',
'C  Zgodność średnich a liczba komórek':'C  Mean agreement versus cell count',
'Zielone pole: projektowy próg ±1%\\nPunkty nie tworzą jednorodnej rodziny GCI.':'Green band: project tolerance of ±1%\\nThese meshes do not form a systematic GCI family.',
'Opór ciśnieniowy':'Pressure drag',
'Opór lepki':'Viscous drag',
'100 × (wariant − odniesienie) / |odniesienie| [%]':'100 × (candidate − reference) / |reference| [%]',
'D  Składowe oporu ujawniają większą różnicę':'D  Drag components reveal a larger difference',
'Próg 1% pochodzi z kampanii; nie jest uniwersalnym kryterium ITTC/AIAA ani przedziałem niepewności.':'The 1% tolerance is a project criterion, not a universal ITTC/AIAA limit or an uncertainty interval.',
'M09 → M07: +0,467% Cᴅ, −0,164% Cʟ; opór ciśnieniowy +1,555%.  Δt 1 → 0,5 ms na M09: −0,00242% Cᴅ.':'M09 relative to M07: +0.467% Cᴅ, −0.164% Cʟ; pressure drag +1.555%.  M09, Δt 1 → 0.5 ms: −0.00242% Cᴅ.',
'Źródło: historie obliczeń M07/M08/M09, ponownie przeliczone 30.10.2026. Siły i współczynniki dotyczą wycinka quasi-2D.':'Source: M07/M08/M09 simulation histories, recomputed on 30 Oct 2026. Forces and coefficients refer to the quasi-2D slice.',
"'mesh_comparison.png'":"'mesh_comparison_EN.png'",
"'mesh_comparison.svg'":"'mesh_comparison_EN.svg'",
'fontsize=22,fontweight':'fontsize=20,fontweight'
}
for a,b in replacements.items():
 assert a in s,a
 s=s.replace(a,b)
(P/'make_figure_en.py').write_text(s,encoding='utf-8')
runpy.run_path(str(P/'make_figure_en.py'),run_name='__main__')
print('English PNG and SVG created.')
