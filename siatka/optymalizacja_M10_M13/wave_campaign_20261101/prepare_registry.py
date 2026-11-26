"""Campaign aliases and sourced wave scenarios; never rename original CFD data."""
from pathlib import Path
from datetime import datetime
import json,math
R=Path(r'E:\ntnu_mesh_optimization_20261030');D=Path(__file__).parent;P=R/'M13_wave_direct_20261031'
assert not (D/'campaign.json').exists(),'Preserve existing campaign registry'
def dispersion(T=None,L=None):
 g=9.81;depth=24.;U=18.
 if L is None:
  omega=2*math.pi/T;lo=1e-8;hi=10.
  for _ in range(100):
   k=(lo+hi)/2
   if g*k*math.tanh(k*depth)>omega**2:hi=k
   else:lo=k
  L=2*math.pi/((lo+hi)/2)
 k=2*math.pi/L;omega=math.sqrt(g*k*math.tanh(k*depth))
 return {'lambda_linear_m':L,'T_intrinsic_linear_s':2*math.pi/omega,'T_encounter_linear_s':2*math.pi/(omega+k*U),'linear_depth_m':depth,'U_m_s':U,'domain_lengths_per_wave':80/L,'forcing_lengths_per_wave':20/L,'dispersion_is_planning_estimate':True}
sources={
 'godo2024':{'title':'Godø, Steen, Barrett & Triantafyllou (2024), Active wave energy extraction by hydrofoil vessels through deep reinforcement learning-based flight control','doi':'10.1016/j.oceaneng.2024.119236','url':'https://www.sciencedirect.com/science/article/pii/S0029801824025745','verified':'Regular head waves H=1.5m, period5s; published abstract. A controlled hydrofoil vessel, not our fixed quasi-2D foil.','scope':'Use sourced wave condition, not a claim to reproduce full vessel/control results.'},
 'baltic2018':{'title':'Björkqvist et al. (2018), Comparing a 41-year model hindcast with decades of wave measurements from the Baltic Sea','doi':'10.1016/j.oceaneng.2018.01.048','url':'https://www.hereon.de/imperia/md/content/hzg/zentrale_einrichtungen/bibliothek/journals/2018/bjorkqvist_38712.pdf','verified':'Section4.1, printed page10: mean spectral peak periods5–6s in Baltic Proper,3–4s in Gulf of Riga. PDF page visually checked.','scope':'Chosen monochromatic scenarios informed by period ranges, not observations of particular H/T pairs and not an irregular Baltic sea state.'},
 'northsea2021':{'title':'Magnusson, Jensen & Swail (2021), Spectral shapes and parameters from three different wave sensors','doi':'10.1007/s10236-021-01468-7','url':'https://link.springer.com/article/10.1007/s10236-021-01468-7','verified':'Ekofisk primary measurements; energetic period bands include8–5s and10–8s, among others.','scope':'T=8s is a selected regular-wave screening condition. H=1m is a project choice, not a measured H/T pair.'}
}
def wave(i,title,H,L=None,T=None,group='Projekt',source=None,note='',extra=None):
 o={'id':i,'kind':'wave','title':title,'group':group,'H_regular_m':H,'Hs_m':None,'wave_type':'regular','direction':'head','reference_id':'C01','mesh':'M13','cells':309441,'planned_dt_s':.0004,'production_dt_requires_review':True,'source_key':source,'note':note,'priority':int(i[1:]),'scientific_status':'planned','source_runs':[],'future_folder':str(P/(f'M13_GPU_{i}_wave_20261101')),'launch_ready':False,'preconditions':['matched_calm_wave_review','chosen_dt_review','single_GPU_free','case_specific_mesh_forcing_damping_check','source_hash_and_no_STOP'],**dispersion(T,L)}
 if T is not None:o['target_intrinsic_period_s']=T;o['requires_native_period_match']=True
 if extra:o.update(extra)
 return o
cases=[{'id':'C01','kind':'calm','title':'M13 · spokojna woda','group':'Odniesienie','H_regular_m':0,'mesh':'M13','cells':309441,'planned_dt_s':.0004,'source_runs':[str(R/'M13_farfield15_20261031'/'M13_GPU_calm_dt0004')],'reference_id':None,'note':'Alias zapisanej referencji M13. Nie jest odblokowaniem starego C01 na F:.','scientific_status':'primary_settled'},
 wave('W01','Pierwsza fala · odniesienie kampanii',.5,L=20,extra={'source_runs':[str(P/n) for n in ['M13_GPU_W20_H050_pilot_20261031_r2','M13_GPU_W20_H050_continuation_R3V_20261101','M13_GPU_W20_H050_continuation_R4V_20261101']],'scientific_status':'exploratory','already_computed':True}),
 wave('W02','Mniejsza wysokość',.25,L=20,note='Test wpływu wysokości przy tej samej długości fali.'),
 wave('W03','Dłuższa fala',.5,L=30,note='Test częstotliwości spotkaniowej i penetracji ruchu falowego.'),
 wave('W04','Godø 2024 · H1,5 m / T0=5 s',1.5,T=5,group='Literatura · obowiązkowy',source='godo2024',note='Warunek falowy z pracy; nasz stały M13 i U18m/s nie odtwarzają całego sterowanego statku. Sprawdzić pas zagęszczenia dla pełnej grzbietowej elewacji oraz tłumienie.',extra={'mandatory_requested':True,'mesh_envelope_review_required':True}),
 wave('W05','Bałtyk · krótka fala zatokowa',.5,T=3.5,group='Bałtyk · scenariusz',source='baltic2018',note='Projektowa fala regularna z okresem w zakresie3–4s opisywanym dla Zatoki Ryskiej. H0,5m jest wyborem testowym, nie Hs z obserwacji.'),
 wave('W06','Bałtyk właściwy · dłuższa fala',1.,T=5.5,group='Bałtyk · scenariusz',source='baltic2018',note='Projektowa fala regularna z okresem w zakresie5–6s. H1m jest wyborem testowym. Nie reprezentuje pełnego widma ani konkretnego pomiaru.',extra={'mesh_envelope_review_required':True}),
 wave('W07','Morze Północne · długa fala',1.,T=8.,group='Morze Północne · etap późniejszy',source='northsea2021',note='Wybrana fala regularna. Długość przekracza obecną domenę80m; nie uruchamiać bez przeglądu domeny, stref i nowej zgodnej referencji calm.',extra={'domain_review_required':True,'launch_blocker':'wavelength_exceeds_current_domain','scientific_status':'requires_domain_review'})]
controls=[{'id':'T01','kind':'control','title':'H≈0 · zgodność ustawień calm/fala','H_regular_m':1e-6,'planned_dt_s':.0004,'source_runs':[str(P/'M13_GPU_Hnear0_matched_control_20261101')],'note':'Kontrola generatora/BC na płacie, nie W02 i nie kolejna siatka wave-only.'},
 {'id':'T02','kind':'control','title':'Calm · Δt0,2ms','planned_dt_s':.0002,'source_runs':[str(P/'M13_GPU_sensitivity_calm_dt0002_20261101')],'note':'Osobna dopasowana referencja, nie nadpisuje C01.'},
 {'id':'T03','kind':'control','title':'W01 · Δt0,2ms','planned_dt_s':.0002,'source_runs':[str(P/'M13_GPU_W20_H050_sensitivity_dt0002_20261101')],'note':'Wrażliwość W01 na krok, nie nowy warunek H/λ.'}]
manifest={'schema':1,'namespace':'M13_wave_campaign_20261101','created_at':datetime.now().astimezone().isoformat(),'deadline_local':'2026-11-02T09:00:00+01:00','cases':cases,'controls':controls,'sources':sources,'legacy_F_campaign_hold_unchanged':True,'original_paths_unchanged':True,'queue_order':['W02','W03','W04','W05','W06','W07'],'requested_scope':'M13 foil only; no standalone wave-only prerequisite','policy':'Four complete gauge-phase cycles for comparison;20 is a diagnostic ceiling, not a minimum. New wave runs start from compatible calm. Hreg != Hs; intrinsic T != encounter T. Planned rows do not imply a solver has launched.'}
(D/'campaign.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'created':True,'ids':[c['id'] for c in cases],'controls':[c['id'] for c in controls],'planned':[{k:c.get(k) for k in ['id','H_regular_m','lambda_linear_m','T_intrinsic_linear_s','T_encounter_linear_s']} for c in cases]},ensure_ascii=False))
