"""English presentation for the current qualitative NWAR results."""
import html,json
from project_results import force_difference_rows

def page(audit,blocks):
 e=lambda v:html.escape(str(v))
 f=lambda v,n=6:'—' if v is None else format(v,'.'+str(n)+'f')
 def table(headers,rows):
  return '<div class="table-wrap"><table><tr>'+''.join('<th>'+e(h)+'</th>' for h in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+e(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</table></div>'
 def picture(name,alt):return '<a href="'+name+'.svg"><img src="'+name+'.png" alt="'+e(alt)+'"></a>'
 result='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>NWAR quasi-2D · calculation report</title><style>
 body{font:16px/1.6 system-ui,sans-serif;color:#20333d;background:#eef3f4;margin:0}main{max-width:1080px;margin:auto;padding:34px}section,header{background:white;padding:30px;margin-bottom:22px;border-radius:12px}h1{font-size:36px;line-height:1.15}h2{font-size:25px}.eyebrow{color:#087f8c;font-size:12px;font-weight:bold;letter-spacing:2px}img{width:100%;height:auto;margin:12px 0}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:14px}td,th{padding:10px;text-align:left;border-bottom:1px solid #dfe8eb}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}a{color:#08727c}li{margin:9px 0}details{margin:12px 0}summary{cursor:pointer}@media print{body{background:white}main{padding:0}section{break-inside:avoid;padding:15px}img{max-height:235mm;object-fit:contain}}@media(max-width:650px){main{padding:12px}section,header{padding:18px}h1{font-size:28px}}</style><main>'''
 result+='<header><p class="eyebrow">NTNU · QUASI-2D · M13</p><h1>NWAR · trends, forces and waves</h1><p>'+e(audit['generated_at'])+'</p><p>Original C01: 309,441 cells · expanded W04 mesh: 572,176 cells. U = 18 m/s · Δt = 0.4 ms · 10 inner iterations · ρ = 1000 / 1.2 kg/m³.</p><p>Each campaign uses one recorded C01 reference. Preserve the physics and M13 cell-size controls, then record five measured wave cycles and verify repeatability of cycles 2–5; cycle 1 is excluded. The reference acceptance receipt records the PRE stability and compatibility policy. Legacy export labels CL, CD, L and D refer to fixed-axis Cz, Cx, Fz and Fx in CFD results. The polar lift and drag used by the quasi-steady model are defined relative to its incident flow.</p><p><a href="Q_summary.csv">Q data · CSV</a> · <a href="summary.csv">Current results · CSV</a> · <a href="report_data.mat">MATLAB data</a> · <a href="plot_in_matlab.m">MATLAB plots</a> · <a href="audit.json">Audit and provenance</a></p></header>'
 drag,lift=force_difference_rows(audit)
 calm=audit['C01'];labels={r['case']:r.get('display_id',r['case']) for r in audit['results'] if 'case' in r}
 averaging=lambda r:r.get('averaging','Accepted · cycles 2–5')
 result+='<section><h2>Q · horizontal force difference relative to C01</h2><p><b>C01 calm-water reference: '+f(calm['CD']*3855.6,2)+' N.</b></p><p>Q = ⟨Cx wave⟩ − ⟨Cx C01⟩. ΔFx = Q × 3855.6 N. Negative values indicate a reduction in horizontal force. Fx and Fz are measured in the fixed domain axes. Cx = Fx / 3855.6 N and Cz = Fz / 3855.6 N, with buoyancy subtracted from the vertical force. Each accepted wave contributes the mean of its complete measured cycles 2–5, excluding cycle 1.</p>'
 result+=table(['Wave','Mean Fx [N]','ΔCx','ΔFx [N]','Change vs C01','Averaging'],[[r.get('display_id',r['case']),f(r['D_wave_N'],2),f(r['Q_CD'],7),f(r['delta_D_N'],2),f(r['relative_change_pct'],1)+'%',averaging(r)] for r in drag])
 result+=(picture('Q_trend','Coefficient, force and percentage horizontal force differences from C01') if audit['Q_data'] else '<p>Waiting for an accepted run.</p>')+'</section>'
 if lift:
  result+='<section id="lift-trend"><h2>Vertical force relative to C01</h2><p><b>C01 calm-water reference: '+f(calm['CL']*3855.6,2)+' N.</b> Accepted regular waves use measured cycles 2–5. Fz excludes buoyancy.</p>'
  result+=table(['Wave','Mean Fz [N]','ΔCz','ΔFz [N]','Change vs C01','Averaging'],[[r['display_id'],f(r['L_wave_N'],2),f(r['delta_CL'],7),f(r['delta_L_N'],2),f(r['relative_change_pct'],2)+'%',averaging(r)] for r in lift])
  result+=(picture('lift_trend','Coefficient, force and percentage vertical force differences from C01') if audit.get('lift_trend') else '')+'</section>'
 diagnostic=audit.get('w08bi_snapshot')
 if diagnostic:
  start,end=diagnostic['mean_window_s']
  heading='final GLHF diagnostic' if diagnostic.get('final') else 'provisional GLHF snapshot'
  result+='<section id="w08bi-snapshot"><h2>W08bi · '+heading+'</h2><p>W01 (H = 0.50 m, λ = 20 m) + W06 (H = 1.00 m, λ = 30 m). Free surface measured directly at the foil (x = 0 m). The W08bi bars show the diagnostic time mean from '+f(start,4)+' to '+f(end,4)+' s, spanning three nominal beat periods after startup and propagation.</p>'
  result+=table(['Mean Fz [N]','Mean Fx [N]','ΔFz vs C01 [N]','ΔFx vs C01 [N]','Diagnostic ΔCx'],[[f(diagnostic['L_wave_N'],2),f(diagnostic['D_wave_N'],2),f(diagnostic['delta_L_N'],2),f(diagnostic['delta_D_N'],2),f(diagnostic['delta_CD'],7)]])
  result+=picture('W08bi_time_history','W08bi foil wave elevation, vertical and horizontal force over physical time')+'<p><a href="W08bi_snapshot.json">Diagnostic means and provenance · JSON</a></p>'
  model=diagnostic.get('quasi_steady')
  if model:
   result+='<h3>Quasi-steady model comparison</h3><p>The model uses the NACA66 XFOIL polar at Re = 20 million, 18 m/s current and 2 m foil depth. Calm lift sets the trim angle. The two wave phases come from the foil probe. The model projects the polar lift and drag onto the fixed domain axes before comparison. Both predictions use the same three-beat time window as CFD.</p>'
   result+=table(['Source','ΔFz [N]','ΔFx [N]'],[[label,f(model[key]['delta_L_N'],2),f(model[key]['delta_D_N'],2)] for label,key in [('CFD','cfd'),('Quasi-steady, nominal wave heights','nominal'),('Quasi-steady, measured wave heights','probe')]])
   result+=picture('W08bi_quasi_steady','CFD and quasi-steady changes in vertical and horizontal force')+'<p><a href="W08bi_quasi_steady.json">Model inputs, force decomposition and residuals · JSON</a></p>'
  result+='</section>'
 comparison=audit.get('force_wave_comparison',{})
 if comparison.get('case_count'):
  if comparison.get('files',{}).get('interactive'):
   result+='<p><a href="'+e(comparison['files']['interactive'])+'">Open interactive comparison · select cases</a></p>'
  result+='<section id="force-wave-comparison"><h2>Force–wave comparison relative to C01</h2><p>Means of cycles 2–5 at x = 0; cycle 1 excluded. The force curves show ΔFz and ΔFx in the fixed domain axes, with C01 as zero. Wave-cycle mean offsets are retained. Colours and line styles identify wave conditions consistently across all four panels.</p>'+picture('force_wave_comparison','Overlaid vertical and horizontal force differences from C01 and force–wave loops')
  result+='<p>'+ ' · '.join('<a href="'+e(comparison['files'][k])+'">'+label+'</a>' for k,label in [('pdf','PDF · vector'),('svg','SVG · editable vector'),('png','PNG · 600 dpi'),('csv','Curve data · CSV'),('caption','Figure caption')])+'</p>'
  result+='<details><summary>Figure caption and phase reconstruction</summary><p>'+e(comparison['caption'])+'</p><p><a href="'+e(comparison['files']['evidence'])+'">Curve provenance and propagation data · JSON</a></p></details></section>'
 result+='<section><h2>Current campaign</h2><p>C01: '+('checkpoint and history integrity confirmed' if calm['accepted'] else 'integrity requires review')+'. Cz = '+f(calm['CL'])+', Cx = '+f(calm['CD'])+'.</p>'
 result+=table(['Mesh','Cells','Δt [ms]','CL','CD','CL vs M12 [%]','CD vs M12 [%]'],[[m['mesh'],m['cells'],f(m['dt_s']*1000,1),f((m.get('settled') or {}).get('CL')),f((m.get('settled') or {}).get('CD')),f(m.get('delta_CL_pct'),2),f(m.get('delta_CD_pct'),2)] for m in audit['mesh']])
 result+='<p>The prior mesh comparison supports the selected M13 configuration. Mixed time steps and end times mean this is not a formal GCI estimate.</p>'
 result+=table(['Wave','Wave conditions','Availability'],[[labels.get(c['id'],c.get('display_id',c['id'])),c.get('condition_label') or ('H = '+f(c['H'],2)+' m, λ = '+f(c['L'],3)+' m'),('Bichromatic diagnostic · subject to the campaign time window' if c.get('diagnostic_only') else 'Saved result; available for continuation' if c['existing'] else 'New wave available from C01') if c['ready'] else c['blocker']] for c in audit['waves']])
 result+='<details><summary>Stage criteria and future work</summary><ol>'+''.join('<li>'+e(v)+'</li>' for v in audit['missing'])+'</ol></details><p>One current saved result per wave. W03 combines the original history and its continuation in a single result. Source files and previous reports remain preserved.</p></section>'
 pre=audit.get('PRE_W04',{})
 if pre.get('receipt'):
  r=pre['receipt']
  result+='<section><h2>PRE W04 · calm preparation on the expanded mesh</h2><p>'+('Calm gate passed.' if r.get('passed') else 'Wave remains blocked; inspect the calm evidence.')+' Original C01 remains the reference for all Q values. PRE W04 is not a wave result and contributes no Q.</p><p>CL/CD stability below 0.5% in adjacent 0.2 s windows; both means within 0.5% of original C01; two consecutive eligible checks.</p>'
  if r.get('initialization')=='whole_domain_momentum_ramp':
   result+='<p>Fresh whole-domain startup: flat water from rest; synchronized 0–18 m/s ramp over 1 s at the inlet and throughout the fluid region. The temporary momentum source is removed after the ramp. This PRE history starts at zero; the previous attempt remains archived.</p>'
  if pre.get('stop_reason'):result+='<p><strong>Preparation stopped:</strong> '+e(pre['stop_reason'])+'</p>'
  for name in pre.get('files',[]):
   if name.endswith('.png'):result+='<a href="'+e(name)+'"><img src="'+e(name)+'" alt="'+e(name)+'"></a>'
   else:result+='<p><a href="'+e(name)+'">'+e(name)+'</a></p>'
  result+='</section>'
 result+='<section><h2>Run validation checklists</h2><p>Accepted means the requirements of the current qualitative stage are met. Future studies do not block Q.</p>'
 states={'passed':'PASSED','failed':'FAILED','pending':'WAITING FOR DATA','future':'FUTURE WORK · NONBLOCKING'}
 for r in audit['results']:
  v=r.get('validation',{});key=r.get('display_id',r['id'])
  if not v:continue
  result+='<details><summary>'+e(key)+' — '+states.get(v.get('run_verification'),'REVIEW REQUIRED')+'</summary><p>'+e(v.get('generated_at'))+' · <a href="'+e(key)+'_validation.json">Full evidence · JSON</a></p>'
  if v.get('verification_kind')=='glhf_saved_state':
   result+='<p>Accepted for qualitative comparison from the native SIM state and the transferred histories. The GLHF controller exit was not independently verified.</p>'
  if v.get('error'):result+='<p>'+e(v['error'])+'</p>'
  for group in ('run','future'):
   if group=='future':result+='<details><summary>Future work · outside current acceptance</summary>'
   for c in v.get('checks',[]):
    if c.get('group','run')!=group:continue
    result+='<details><summary>'+states[c['status']]+' · '+e(c['title'])+'</summary><p>'+e(c['criterion'])+'</p><pre>'+e(json.dumps(dict(values=c['values'],evidence_files=c['evidence_files']),ensure_ascii=False,indent=2))+'</pre></details>'
   if group=='future':result+='</details>'
  result+='</details>'
 result+='</section>'+''.join(blocks)
 test=audit['automation_selftest']
 result+='<section><details><summary>Automation verification</summary><p>'+('PASSED: actual solver start from C01, pause/save and continuous resume; 10 + 20 steps. C01 unchanged.' if test.get('status')=='passed' else 'Status: '+e(test.get('status','pending')))+' This technical test is excluded from campaign results.</p><p><a href="automation_selftest.json">Test evidence</a> · <a href="cycle_counter_verification.json">Measured-cycle counter replay</a></p></details></section>'
 result+='<section><h2>C01 reference and mesh review</h2>'+picture('C01_forces','C01 coefficient history')+picture('mesh_comparison','M10–M13 comparison')+'</section>'
 result+='<section><h2>Method and scope</h2><p>Standard CL/CD histories show the current coefficients, with C01 drawn as a reference line. CL is hydrodynamic: the constant buoyancy contribution of 22.718189111947265 N is removed before division by 3855.6 N. C01 uses the same convention. Force-difference plots use L − L_C01 and D − D_C01; their zero lines denote C01. Wave-cycle mean force offsets remain visible.</p><p>Continuation histories are joined at verified time boundaries without changing the source CSV files. Dashed vertical lines mark every resume point in full-history plots and MATLAB exports.</p><p>All existing and future force–wave plots share the foil reference x = 0 m. A recorded measurement at this position is used directly. Otherwise the closest recorded upstream reference signal is extrapolated by its measured travel time to x = 0. W01 uses x = -6 m; W02 and W03 use x = -0.5 m. Propagation speed is measured from two upstream wave probes over their common settled history. The measured waveform and amplitude are retained. The reconstruction method and travel time are recorded in the evidence; local wave distortion is not reconstructed. If paired data are unavailable, a wavelength/period estimate is identified explicitly. Original raw samples are preserved.</p><p>The time shift and calibration evidence are saved in each force-wave JSON and CSV/MAT exports. Force data never determine the wave shift, and force timing is unchanged: the physical phase lead or lag remains visible. Each plot shows complete phase cycles 2–5 (cycle 1 excluded) with sufficient force data, with partial results labelled explicitly. Phase zero is the upward crossing of the wave reference level at x = 0 m. The acceptance counter and Q retain their independently recorded probe and averaging windows. Loop arrows indicate time direction.</p><p>New runs also record a direct probe at x = 0; the surface calculation accounts for the submerged foil section. Q describes trends relative to the accepted campaign C01. Cycle spread is not a formal uncertainty estimate. Partial runs and technical tests do not contribute to Q.</p></section></main></html>'
 result=result.replace('</html>', '''<script>
if(location.protocol==='http:'||location.protocol==='https:'){
 let follow=null;
 async function refreshLatest(){
  if(document.hidden)return;
  try{
   const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)return;
   const s=await r.json(),target='/'+s.report.relative+'/report.html';
   if(follow===null)follow=location.pathname===target;
   if(follow&&s.live_report_refresh?.enabled&&location.pathname!==target)location.replace(target+location.hash);
  }catch(e){}
 }
 refreshLatest();setInterval(refreshLatest,15000);
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshLatest()});
}
</script></html>''')
 if audit['C01'].get('reference_id')=='C01_PRE_W04_20261102':
  result=result.replace('Original C01 remains the reference for all Q values.', 'Stable PRE W04 is the accepted C01 for this series; original C01 and old wave results remain archived.').replace('CL/CD stability below 0.5% in adjacent 0.2 s windows; both means within 0.5% of original C01; two consecutive eligible checks.', 'CL/CD stability below 0.5% in adjacent 0.2 s windows; two consecutive eligible checks. Difference from original C01 is retained as a diagnostic.').replace('W03 combines the original history and its continuation in a single result.', 'This fresh W01–W07 series uses C01 from PRE W04. Earlier wave results are preserved in their archived reports.').replace('C01 calm-water reference:', 'C01 (PRE W04) calm-water reference:')
 return result
