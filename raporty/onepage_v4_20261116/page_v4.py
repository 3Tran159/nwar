import pandas as pd, weasyprint
o=pd.read_csv('mech.csv')
m=lambda s: s.replace('-','−')
FX0=0.007002316911710474*3855.6
rows=''.join(m(f"<tr><td>{q.case}</td><td>{q.H:g}</td><td>{q.lam:.0f}</td><td>{q.th_deg:.2f}</td><td>{q.sig:.2f}</td><td>{q.Lamp:.0f}</td><td>{q.dFz:+.1f}</td><td>{FX0+q.dFx:.1f}</td><td><b>{q.dFx:.2f}</b></td><td>{q.tilt:.2f}</td><td>{q.rest:+.2f}</td></tr>") for q in o.itertuples())
def th(name,sym): return f"<th><span class='hn'>{name}</span><br>{sym}</th>"
head=("<th>Case</th>"+th("Wave<br>height","H [m]")+th("Wave<br>length","λ [m]")+th("Inflow-angle<br>amplitude","θ<sub>a</sub> [°]")
 +th("Reduced<br>frequency","σ [–]")+th("Lift swing<br>(amplitude)","F̂<sub>z</sub> [N]")
 +th("Mean lift<br>change","ΔF<sub>z</sub> [N]")+th("Mean F<sub>x</sub><br>(calm: 27.0)","F<sub>x</sub> [N]")+th("Mean F<sub>x</sub><br>change","ΔF<sub>x</sub> [N]")+th("Lift-tilt<br>thrust gain","F<sub>tilt</sub> [N]")+th("Change of drag<br>along inflow","F<sub>rest</sub> [N]"))
html=f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
@page{{size:A4;margin:7mm 9mm 6mm 9mm}}
body{{font-family:'DejaVu Sans',sans-serif;font-size:6.4pt;line-height:1.2;color:#111}}
h1{{font-size:13pt;margin:0 0 1mm 0}} h2{{font-size:7.8pt;margin:1.2mm 0 0.5mm 0;border-bottom:0.4pt solid #888}}
.sub{{font-size:7.3pt;color:#444;margin-bottom:1.5mm}}
.lead{{font-size:7.4pt;margin:0 0 1mm 0}}
.cols{{display:flex;gap:4mm}} .c{{flex:1}}
table{{border-collapse:collapse;width:100%}} td,th{{padding:0.25mm 1.1mm;border-bottom:0.3pt solid #ddd;text-align:right}}
th{{background:#eef1f4;font-weight:bold}} td:first-child,th:first-child{{text-align:left}}
.kv td{{text-align:left}} .kv td:first-child{{font-weight:bold;width:19%}}
img{{width:100%}} ul{{margin:0.5mm 0 0 3.5mm;padding:0}} li{{margin-bottom:0.35mm}}
.note{{font-size:6.2pt;color:#444}}
.cm td{{padding:0.1mm 0.8mm;line-height:1.08}} .cm th{{padding:0.3mm 0.35mm;line-height:1.1;vertical-align:bottom;white-space:nowrap}} .hn{{font-weight:normal;font-size:5.1pt;color:#333}}
.bt{{display:table;width:100%;table-layout:fixed;border-spacing:0}} .bt>div{{display:table-cell;vertical-align:top}} .bl{{width:59%;padding-right:3.5mm}} .lim{{margin:0.5mm 0 0 0}}
.fig{{width:80.5%;display:block;margin:0 auto}}
.def{{display:table;width:100%;margin-top:0.9mm}} .def>div{{display:table-cell;vertical-align:top;font-size:6.15pt;line-height:1.17}} .def .sk{{width:46mm;padding-right:2.2mm}} .def img{{width:46mm;border:0.3pt solid #ccc;display:block}} .def p{{margin:0 0 0.6mm 0}} .cap{{font-size:5.6pt;color:#444}}
.ms td,.ms th{{white-space:nowrap}} .take{{margin:0.8mm 0 0 0}}
</style></head><body>
<h1>Resistance reduction of a fixed submerged hydrofoil in head waves</h1>
<div class="sub">Julian Serkieza · NTNU · 16 Nov 2026 (rev. 4) · STAR-CCM+ 2602/2606 · URANS-VOF, 14 regular head-wave cases + calm reference C01</div>
<p class="lead"><b>Result:</b> in all 14 regular wave cases the rigid foil at 2 m depth has a lower mean horizontal force F<sub>x</sub> than in calm water: ΔF<sub>x</sub> = −0.77 to −10.1 N (calm: F<sub>x</sub> = 27.0 N, F<sub>z</sub> = 1217 N on the 0.02 m span; C<sub>D</sub> = 0.00700, C<sub>L</sub> = 0.316), i.e. ΔC<sub>D</sub> = −0.0002 to −0.0026. This is negative wave added resistance (NWAR). It comes from the forward tilt of the oscillating lift: the wave turns the inflow up and down by ±0.4–2.3°, lift follows the angle, and its forward component is larger when lift is high than its backward component when lift is low.</p>
<div class="cols"><div class="c">
<h2>Simulation set-up</h2>
<table class="kv">
<tr><td>Foil</td><td>NACA 66-012 mod, a = 0.8 (mod.) mean line, camber f/c = 0.025; chord c = 1.19 m; quasi-2D span 0.02 m (symmetry planes); incidence 0°, fixed</td></tr>
<tr><td>Flow</td><td>U = 18 m/s, fresh water ρ = 1000 kg/m³, μ = 1.0·10⁻³ Pa·s, Re = 2.14·10⁷; air ρ = 1.2 kg/m³; qS = ½ρU²·c·0.02 m = 3856 N; C<sub>x</sub>, C<sub>z</sub>, C<sub>D</sub>, C<sub>L</sub> = force/qS</td></tr>
<tr><td>Submergence</td><td>h = 2.0 m from still-water level to the chord line (h/c = 1.68); water depth 24 m</td></tr>
<tr><td>Waves</td><td>Head waves, 5th-order Stokes, height H = 0.25–1.5 m, length λ = 15–40 m (H/λ ≤ 0.10); encounter frequency f<sub>e</sub> = 0.65–1.52 Hz; reduced frequency σ = πf<sub>e</sub>c/U = 0.13–0.32 (π × chord / distance the water travels in one wave encounter)</td></tr>
<tr><td>Physics</td><td>URANS, SST k–ω, fully turbulent (no transition model), all-y+ wall treatment; VOF free surface. Domain x = −70…90 m, waves imposed in a 40 m inlet zone and absorbed in a 40 m outlet zone (W01–W03: shorter domain, −35…45 m)</td></tr>
<tr><td>Time</td><td>Δt = 0.4 ms, 2nd order, 10 inner iterations; 1 640–3 860 steps per encounter period</td></tr>
<tr><td>Averaging</td><td>5 wave cycles, cycle 1 discarded, mean of 2–5; accepted if cycles repeat: mean within 1%, amplitude 8%, shape 5% (RMS)</td></tr>
</table></div><div class="c">
<h2>Mesh, wall resolution and numerical checks</h2>
<table class="ms"><tr><th>Calm mesh</th><th>Cells</th><th>Δt [ms]</th><th>C<sub>x</sub></th><th>vs M12</th><th>C<sub>z</sub></th><th>vs M12</th></tr>
<tr><td>M10</td><td>317 277</td><td>0.4</td><td>0.007147</td><td>−2.1%</td><td>0.3130</td><td>+0.7%</td></tr>
<tr><td>M11</td><td>595 285</td><td>0.2</td><td>0.007248</td><td>−0.7%</td><td>0.3130</td><td>+0.7%</td></tr>
<tr><td>M12 (finest)</td><td>1 154 199</td><td>0.1</td><td>0.007298</td><td>0</td><td>0.3108</td><td>0</td></tr>
<tr><td><b>M13 (used)</b></td><td><b>309 441</b></td><td>0.4</td><td><b>0.007002</b></td><td><b>−4.1%</b></td><td><b>0.3157</b></td><td><b>+1.6%</b></td></tr></table>
<ul>
<li><b>Calm-water cross-check</b> (α = 0°, Re ≈ 2·10⁷): CFD C<sub>L</sub> = 0.3157, C<sub>D</sub> = 0.00700. XFOIL 6.99 (transition forced at x/c = 0.01, no free surface): 0.3255 / 0.00684 (+3.1% / −2.3%). Brockett (1966): c<sub>l</sub> = 0.290 (CFD +8.9%).</li>
<li><b>Wave mesh:</b> M13 foil mesh plus a band of 0.02 m cells around the free surface (still-water level z = 2 m): z = 1.6–2.4 m for W01–W03 (H ≤ 0.5 m), z = 1–3 m for W04–W07 (H ≤ 1.5 m, 572 176 cells). The W04–W07 mesh matches C01 in calm water within 0.37% (C<sub>x</sub>) and 0.22% (C<sub>z</sub>).</li>
<li><b>Wall:</b> 48 prism layers, first cell 1.53 μm. y+ area mean 0.94 (C01) / 0.95 (W04e), 0.12% of the foil area above y+ = 1.</li>
<li><b>Mesh sensitivity:</b> calm C<sub>x</sub> varies by 4.1% (1.1 N) between M13 and M12, C<sub>z</sub> by 1.6%. Mixed Δt → not a formal grid convergence index (GCI).</li>
<li><b>Courant:</b> the Courant number at the free surface reaches 1.90–2.00; above 1.0 the free-surface scheme becomes more diffusive and can damp the wave. Measured local wave height is 0.96–1.00 of target.</li>
</ul></div></div>
<h2>Phase-resolved forces (rigid foil, mean of cycles 2–5, relative to C01)</h2>
<img class="fig" src="fig.png">
<div class="note">φ = wave phase at x = 0; η = surface elevation. α<sub>eff</sub>(φ) = θ<sub>a</sub>·cos(φ − k·x<sub>c/4</sub>) = inflow angle from linear wave theory at quarter chord; θ<sub>a</sub> = (H/2)·ω₀·e<sup>−kh</sup>/U, k = 2π/λ, ω₀ = √(gk). (e) F̂<sub>z</sub> = first-harmonic amplitude of F<sub>z</sub>, divided by the quasi-steady value 2π·θ<sub>a</sub>·qS (lift swing if lift followed the angle instantly); Sears = classical thin-foil theory for an oscillating inflow: the faster the oscillation (higher σ), the smaller the lift swing. (f) −F<sub>tilt</sub> against −ΔF<sub>x</sub> from the table below; r = correlation coefficient.</div>
<div class="bt"><div class="bl">
<h2>Case matrix: wave, lift response and split of the mean F<sub>x</sub> change</h2>
<table class="cm"><tr>{head}</tr>{rows}</table>
<p class="take"><b>Reading the table:</b> wave (H, λ, θ<sub>a</sub>, σ) → lift response (F̂<sub>z</sub>, ΔF<sub>z</sub>) → mean F<sub>x</sub> and its change, ΔF<sub>x</sub> = F<sub>tilt</sub> + F<sub>rest</sub>. F<sub>tilt</sub> is a thrust (negative) in all 14 cases and tracks ΔF<sub>x</sub> (r = 0.98).</p>
<div class="def"><div class="sk"><img src="tilt4.svg"></div><div>
<p><b>ΔF<sub>z</sub>, ΔF<sub>x</sub></b> = mean on the wave minus calm water (1217 N, 27.0 N). F<sub>x</sub> &gt; 0 is resistance, &lt; 0 thrust.</p>
<p><b>F<sub>tilt</sub> (lift-tilt thrust gain):</b> lift is perpendicular to the inflow, so it leans with the inflow and gets a horizontal part (sketch; angles exaggerated, real ±0.4–2.3°). F<sub>tilt</sub> = cycle mean of that part = −mean(ΔF<sub>z</sub>·α<sub>eff</sub>).</p>
<p><b>F<sub>rest</sub></b> = ΔF<sub>x</sub> − F<sub>tilt</sub> = change of mean drag along inflow. <b>W04:</b> −10.06 = −12.21 + 2.15 N.</p>
</div></div>
</div><div>
<h2>What happens to the foil</h2>
<ul>
<li><b>Lift follows the inflow angle with a lag.</b> F<sub>z</sub> oscillates ±100–680 N; its peak comes 14–28° of wave phase after the peak of α<sub>eff</sub> at quarter chord (a). The lift swing is 0.50–0.75 of the quasi-steady value and shrinks with σ as Sears theory predicts, 4–21% below it (e).</li>
<li><b>F<sub>x</sub> is strongly asymmetric.</b> W04: −50 N at φ ≈ 12° (high α<sub>eff</sub>, high lift tilted forward) but only +14 N at φ ≈ 130–180° (c). The positive half is flattened, so the cycle mean is negative.</li>
<li><b>Lift tilt explains the mean.</b> F<sub>tilt</sub> predicts the CFD ΔF<sub>x</sub> with r = 0.98 (f). For H = 1.5 m the force along the inflow (F<sub>rest</sub>) rises by +2.1 to +3.2 N and takes back 18–36% of the tilt thrust; for H ≤ 1.0 m it is within ±0.8 N.</li>
<li><b>Trends.</b> Reduction grows with H (λ = 20 m: 0.77 → 7.17 N for H = 0.25 → 1.5 m) and with λ at fixed H (H = 1.5 m: 5.0 N at λ = 15 m → 10.1 N at 39 m), because σ is lower and the lift is less attenuated (θ<sub>a</sub> stays at 2.1–2.3°).</li>
<li><b>Mean lift also rises</b> by +9.9 to +19.3 N (0.8–1.6%), so the comparison is not at equal load.</li>
</ul>
<h2>Limits</h2>
<p class="lim">F<sub>rest</sub> for H ≤ 1.0 m (≤ 0.8 N) and ΔF<sub>x</sub> of W01–W03 (≤ 1.6 N) are of the order of the calm mesh difference (1.1 N); the sign of F<sub>rest</sub> is resolved only for H = 1.5 m. Free-surface Courant number > 1: measured wave height up to 4% low, i.e. F<sub>tilt</sub> up to ≈8% low (∝ H²). Cycle-to-cycle 95% range of ΔF<sub>x</sub> ≤ ±0.2 N.</p>
</div></div>
</body></html>"""
open('NWAR_onepage_v4.html','w').write(html)
weasyprint.HTML('NWAR_onepage_v4.html',base_url='.').write_pdf('NWAR_onepage_v4.pdf')
