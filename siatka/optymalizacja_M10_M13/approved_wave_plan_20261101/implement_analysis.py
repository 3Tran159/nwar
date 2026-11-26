"""Verify exact-cycle diagnostics against raw data; deploy only derived UI corrections."""
from pathlib import Path
from datetime import datetime
import importlib.util,sys,json,hashlib,math,statistics,subprocess,os
D=Path(__file__).resolve().parent;R=D.parent;UI=R/'foil_live_dashboard_20261031';P=R/'M13_wave_direct_20261031';RUN=P/'M13_GPU_W20_H050_continuation_R4V_20261101'
sys.path.insert(0,str(D));import cycle_analysis as ca
spec=importlib.util.spec_from_file_location('original_foil_ui',UI/'foil_live.py');old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert not (D/'analysis_corrected.json').exists(),'Do not overwrite this analysis receipt'
# Pure numerical unit test, never presented as measured CFD data.
series=[[i*.007,1+2*(i*.007),5-3*(i*.007)] for i in range(1000)]
seg=ca.segment(series,.123,2.789,[1,2],max_gap=.01)
assert abs(ca.time_mean(seg,1)-(1+.123+2.789))<1e-12
assert ca.interpolate(series,.123,1,max_gap=.01) is not None
forces={};gauges={}
for folder in old.chain(RUN):
 for row in old.curve(folder):forces[round(row[0],9)]=row
 for row in old.csvrows(folder/'gauges.csv'):
  t,x,y=old.num(row.get('time_s')),old.num(row.get('x_m')),old.num(row.get('eta_actual_m'))
  if None not in (t,x,y):gauges.setdefault(str(x),{})[round(t,9)]=[t,y]
full=sorted(forces.values());g={x:sorted(a.values()) for x,a in gauges.items()};cfg=old.read(RUN/'wave_setup_audit.json')
cyc=ca.analyze_cycles(full,g,cfg);assert len(cyc['overlays'])==4
assert all(len(c['points'])==121 and c['points'][0][0]==0 and c['points'][-1][0]==1 for c in cyc['overlays'])
block=cyc['four_cycle_time_mean'];a,b=block['start_s'],block['end_s'];T=cyc['period_measured_s'];bounds=[(c['start'],c['end']) for c in cyc['overlays']]
wave={}
for x,s in sorted(g.items(),key=lambda v:float(v[0])):
 h=ca.harmonic_metrics(s,a,b,T,bounds)
 if h:
  own=ca.crossings([row for row in s if a<=row[0]<=b],T)
  ps=[end-start for start,end in zip(own,own[1:]) if .65*T<end-start<1.35*T]
  h['T_measured_local_s']=statistics.fmean(ps) if ps else None
  wave[x]=h
phase_ref=wave['-0.5']['fundamental_phase_rad'];wrap=lambda x:(x+math.pi)%(2*math.pi)-math.pi
for x,h in wave.items():h['phase_error_vs_fixed_probe_and_lambda20_rad']=wrap(h['fundamental_phase_rad']-phase_ref+2*math.pi*(float(x)+.5)/20)
calm=old.csvrows(old.CALM/'history.csv');calm_series=[[float(r['physical_time_s']),float(r['CL']),float(r['CD'])] for r in calm]
end=calm_series[-1][0];calm_sub=ca.segment(calm_series,end-.2,end,[1,2],max_gap=.005)
ref={'CL':ca.time_mean(calm_sub,1),'CD':ca.time_mean(calm_sub,2),'window_s':[end-.2,end],'method':'exact endpoints, time-integrated saved M13 calm, same dt0.4ms'}
result={'at':datetime.now().astimezone().isoformat(),'source':str(RUN),'source_history_sha256':sha(RUN/'history.csv'),'source_gauges_sha256':sha(RUN/'gauges.csv'),'physical_window_s':[a,b],'period_ramp_estimate_s':float(cfg['wave_period_s']),'period_STAR_s':None,'period_measured_s':T,'phase_ref_x_m':-.5,'gauges':wave,'force_block':block,'calm_reference_exact':ref,'Q_CD':block['CD']-ref['CD'],'delta_CD_percent':100*(block['CD']/ref['CD']-1),'delta_CL_percent':100*(block['CL']/ref['CL']-1),'cycles':cyc,'no_new_solver_steps':True,'scientific_accepted':False,'limitations':['analysis start still based on estimated arrival, not certification','native STAR period and forcing audit pending','H1 and Hpp are distinct measured quantities','no downstream energy extraction claim','20 cycles is a diagnostic ceiling, not an acceptance minimum']}
(D/'analysis_corrected.json').write_text(json.dumps(result,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf8')
# Surgical UI changes, original code backed up before any replacement.
py=UI/'foil_live.py';js=UI/'foil_live.js';rawpy=py.read_bytes();rawjs=js.read_bytes();pys=rawpy.decode('utf8');jss=rawjs.decode('utf8')
(D/'backup'/'foil_live_before.py').write_bytes(rawpy);(D/'backup'/'foil_live_before.js').write_bytes(rawjs)
lo=pys.index('def cycles(force,gauges,config):');hi=pys.index('\ndef frame(p):',lo)
pys=pys[:lo]+"def cycles(force,gauges,config):\n import sys\n source=str(ROOT/'approved_wave_plan_20261101')\n if source not in sys.path:sys.path.insert(0,source)\n from cycle_analysis import analyze_cycles\n return analyze_cycles(force,gauges,config)\n"+pys[hi:]
anchor=' wave_audit=read(audits[0]) if audits else {}';assert pys.count(anchor)==1
pys=pys.replace(anchor," wave_audit=read(ROOT/'approved_wave_plan_20261101'/'analysis_corrected.json') or (read(audits[0]) if audits else {})",1)
# Preserve old reference means to avoid silently rewriting prior values; expose exact means separately.
old_label="+' / 20 cykli diagnostycznych</b>";assert jss.count(old_label)==1
jss=jss.replace(old_label,"+' pełnych okresów; porównanie ostatnich 4</b>",1)
lo=jss.index(' const waveAudit=d.wave_diagnostics||{};');hi=jss.index(" html+='<article class=\"m13-card\"><h3>Płat względem",lo)
new_js=""" const waveAudit=d.wave_diagnostics||{};
 if((r.lineage||[]).some(x=>x.includes('R4V'))&&waveAudit.gauges){
  const xids=['-34.0','-25.0','-15.0','-10.0','-6.0','-0.5','5.0','10.0','20.0'];
  html+='<article class="m13-card"><h3>Fala: H₁, grzbiet–dolina i okresy</h3><p>Okno '+fmt(waveAudit.physical_window_s?.[0],6)+'–'+fmt(waveAudit.physical_window_s?.[1],6)+' s. H₁ to podwojona amplituda pierwszej harmonicznej; Hpp to średnia wysokość grzbiet–dolina z czterech okresów. Średnie sił są całkowane po dokładnych granicach, z fazami 0 i 1.</p><p><b>Okres do planowania rampy:</b> '+fmt(waveAudit.period_ramp_estimate_s,6)+' s; <b>okres natywny STAR:</b> '+fmt(waveAudit.period_STAR_s,6)+'; <b>okres zmierzony na stałej sondzie −0,5 m:</b> '+fmt(waveAudit.period_measured_s,6)+' s.</p><div class="m13-scroll"><table><thead><tr><th>x [m]</th><th>H₁ [m]</th><th>Hpp [m]</th><th>Średnie η [m]</th><th>Amplituda 2. harmonicznej [m]</th><th>T lokalny [s]</th><th>Różnica fazy względem sondy i kΔx [rad]</th></tr></thead><tbody>'+xids.map(x=>{const q=waveAudit.gauges[x]||{};return '<tr><td>'+x+'</td><td>'+fmt(q.H1_m,5)+'</td><td>'+fmt(q.Hpp_m,5)+'</td><td>'+fmt(q.mean_eta_m,5)+'</td><td>'+fmt(q.harmonic_amplitudes_1_to_5_m?.[1],6)+'</td><td>'+fmt(q.T_measured_local_s,6)+'</td><td>'+fmt(q.phase_error_vs_fixed_probe_and_lambda20_rad,5)+'</td></tr>'}).join('')+'</tbody></table></div><p><b>20 okresów nie jest minimum:</b> brak powtarzalności do tego momentu uruchamia diagnozę. Nie dopasowujemy fazy sił. Rozruch i zasięg forcingu wymagają odrębnej oceny; spadek wysokości za płatem nie dowodzi przejęcia energii.</p><p><b>Q = średnie CDwave − CDcalm:</b> '+fmt(waveAudit.Q_CD,8)+'; zmiana CD '+fmt(waveAudit.delta_CD_percent,3)+'%. Wynik eksploracyjny, jeszcze bez oszacowanej niepewności.</p></article>';
 }
"""
jss=jss[:lo]+new_js+jss[hi:]
compile(pys,str(py),'exec');testjs=D/'foil_live_candidate.js';testjs.write_text(jss,encoding='utf8')
check=subprocess.run([r'F:\Program Files\nodejs\node.exe','--check',str(testjs)],capture_output=True,text=True,timeout=30);assert check.returncode==0,check.stderr
assert py.read_bytes()==rawpy and js.read_bytes()==rawjs,'Concurrent dashboard update, refuse overwrite'
for path,text in ((py,pys),(js,jss)):
 tmp=path.with_suffix(path.suffix+'.stage.tmp');tmp.write_text(text,encoding='utf8');os.replace(tmp,path)
receipt={'at':datetime.now().astimezone().isoformat(),'cycles':cyc['count'],'phase_points_each':121,'endpoints':[0,1],'Q_CD':result['Q_CD'],'delta_CD_percent':result['delta_CD_percent'],'delta_CL_percent':result['delta_CL_percent'],'phase_fixed_x':-.5,'runbook_unchanged':True,'no_raw_changes':True,'installed':True,'native_period_still_pending':True}
(D/'analysis_install_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8');print(json.dumps(receipt))
