"""Measured force/wave phase plots and project Q, without force-based phase shifts."""
from analysis import cycles,gauge_series
from common import T0
from phase_alignment import align_to_position,REFERENCE_X
from project_results import COEFFICIENT_DENOMINATOR,c01_force_reference
import numpy as np
import matplotlib.pyplot as plt
import csv
FOIL_PROBE_X=REFERENCE_X

def response_gauge(folders,acceptance_x):
 local=gauge_series(folders,FOIL_PROBE_X)
 if len(local):return FOIL_PROBE_X,local,True
 return acceptance_x,gauge_series(folders,acceptance_x),False

def response_profile(data,gauge,H,L,x=-6.,origin=T0,probe_distance=34.5,force_reference=None):
 c=cycles(data,gauge,H,L,origin=origin,probe_distance=probe_distance)
 if c['analyzed_count']<1:return None
 last=c['analyzed_cycles'];phase=np.array(last[0]['phase'])*360
 eta=np.array([a['eta'] for a in last]);cl=np.array([a['CL'] for a in last]);cd=np.array([a['CD'] for a in last])
 # All force samples share the fixed original C01, retaining each cycle's mean offset.
 reference=force_reference if force_reference is not None else c01_force_reference()
 eta_prime=eta-np.array([a['eta_mean'] for a in last])[:,None]
 lift=(cl-reference['CL'])*COEFFICIENT_DENOMINATOR
 drag=(cd-reference['CD'])*COEFFICIENT_DENOMINATOR
 return dict(phase_deg=phase.tolist(),probe_x_m=x,cycle_count=len(last),cycle_policy_id=c['cycle_policy_id'],cycle_numbers=c['analyzed_cycle_numbers'],discarded_cycle_numbers=c['discarded_cycle_numbers'],
             phase_origin='Rising crossing of the fixed measured wave level at probe x='+str(x)+' m',
             windows_s=[[a['start'],a['end']] for a in last],
             eta_prime_cycles=eta_prime.tolist(),lift_minus_C01_cycles_N=lift.tolist(),drag_minus_C01_cycles_N=drag.tolist(),
             eta_prime_mean_m=eta_prime.mean(axis=0).tolist(),lift_minus_C01_mean_N=lift.mean(axis=0).tolist(),drag_minus_C01_mean_N=drag.mean(axis=0).tolist(),
             force_reference='C01',C01=reference,force_definition='L - L_C01 and D - D_C01; no cycle-mean force subtraction',
             cycle_mean_lift_minus_C01_N=[(a['CL_mean']-reference['CL'])*COEFFICIENT_DENOMINATOR for a in last],
             cycle_mean_drag_minus_C01_N=[(a['CD_mean']-reference['CD'])*COEFFICIENT_DENOMINATOR for a in last],
             crest_phase_deg=float(phase[np.argmax(eta_prime.mean(axis=0))]),trough_phase_deg=float(phase[np.argmin(eta_prime.mean(axis=0))]),
             spread_interpretation='Spread of the displayed cycles, not an uncertainty estimate.',force_phase_shift_applied=False)

def save_response(out,key,data,folders,result):
 gauge,alignment=align_to_position(folders,result['cycles']['phase_probe_x_m'],result,require_full_history=True)
 x=REFERENCE_X;direct=alignment['method']=='direct_measurement'
 distance=result.get('probe_distance_m',34.5)+x+.5
 profile=response_profile(data,gauge,result['H'],result['L'],x=x,origin=result.get('wave_origin_s',T0),probe_distance=distance,force_reference=result.get('force_reference'))
 if result.get('diagnostic_only'):profile=None
 if profile is None:
  fig,ax=plt.subplots(figsize=(10.5,3.5));ax.axis('off')
  ax.text(.5,.6,result.get('display_id',result['case'])+' · force–wave response'+('\n'+result['condition_label'] if result.get('condition_label') else ''),ha='center',fontsize=16)
  message='Bichromatic diagnostic: inspect full force and probe histories.\nNo single-period repeatability or regular-wave Q.' if result.get('diagnostic_only') else 'Waiting for cycle 2; cycle 1 is excluded as startup.\nFull force history is available above.'
  ax.text(.5,.38,message,ha='center',fontsize=11)
  base=key+'_force_wave';fig.savefig(out/(base+'.png'),bbox_inches='tight');fig.savefig(out/(base+'.svg'),bbox_inches='tight');plt.close(fig)
  return None,[base+'.png']
 position='Foil reference x = 0, measured directly' if direct else 'Foil reference x = 0, reconstructed from upstream wave measurements'
 profile.update(at_foil_position=True,direct_measurement_at_foil=direct,direct_measurement_at_reference=direct,
                reference_x_m=x,probe_position=position,
                phase_origin='Upward crossing of the wave reference level at x = '+str(x)+' m',
                spatial_phase_shift_applied=not direct,alignment=alignment)
 phase=np.array(profile['phase_deg']);eta=np.array(profile['eta_prime_cycles']);em=eta.mean(axis=0)
 fig,axes=plt.subplots(2,2,figsize=(13.3,7.8),gridspec_kw={'width_ratios':[1.65,1]})
 for row,(field,label,color) in enumerate([('lift_minus_C01_cycles_N',r'$F_z-F_{z,\mathrm{C01}}$ [N]','#6557a3'),('drag_minus_C01_cycles_N',r'$F_x-F_{x,\mathrm{C01}}$ [N]','#c17a19')]):
  values=np.array(profile[field]);mean=values.mean(axis=0);ax=axes[row,0];right=axes[row,1]
  for panel in (ax,right):panel.axhline(0,color='#526674',lw=.9,ls='--',label='C01')
  for curve in values:ax.plot(phase,curve,color=color,alpha=.18,lw=.8)
  ax.fill_between(phase,values.min(axis=0),values.max(axis=0),color=color,alpha=.12)
  force_line,=ax.plot(phase,mean,color=color,lw=2.1,label='Mean force response · '+str(profile['cycle_count'])+' cycles')
  ax.set(xlim=(0,360),xticks=[0,90,180,270,360],ylabel=label)
  ax.tick_params(axis='y',labelcolor=color)
  wave=ax.twinx();wave.spines['right'].set_visible(True);wave.grid(False)
  wave_line,=wave.plot(phase,em,color='#087f8c',ls='--',lw=1.8,label='Wave at x = '+str(x)+' m − mean')
  wave.set_ylabel('η − mean [m]',color='#087f8c');wave.tick_params(axis='y',labelcolor='#087f8c')
  for angle in (profile['crest_phase_deg'],profile['trough_phase_deg']):ax.axvline(angle,color='#8797a0',lw=.8,ls=':')
  if row==0:ax.legend(handles=[force_line,wave_line],fontsize=8,loc='upper right',framealpha=.94)
  for e,y in zip(eta,values):right.plot(e,y,color=color,alpha=.18,lw=.8)
  right.plot(em,mean,color=color,lw=2)
  for i in (12,42,72,102):right.annotate('',xy=(em[i+3],mean[i+3]),xytext=(em[i],mean[i]),arrowprops=dict(arrowstyle='->',color=color,lw=1.3))
  for angle,name,marker in [(profile['crest_phase_deg'],'crest','o'),(profile['trough_phase_deg'],'trough','s')]:
   i=int(np.argmin(abs(phase-angle)));right.scatter(em[i],mean[i],color=color,s=35,marker=marker,label=name)
  right.set(xlabel='η − mean [m]',ylabel=label)
  if row==0:right.legend(fontsize=8,loc='best')
 axes[0,0].set_title('Common wave reference · x = '+str(x)+' m',fontsize=11)
 axes[0,1].set_title('Force–wave loop · arrows: time direction',fontsize=11)
 axes[1,0].set_xlabel('Wave phase at x = '+str(x)+' m [°] · 0° = upward crossing of reference level')
 fig.suptitle(result.get('display_id',result['case'])+' · foil response to waves | H='+str(result['H'])+' m, λ='+str(result['L'])+' m'+(' · partial run' if profile['cycle_count']<4 else ''),fontsize=15)
 note='Measured directly at the common reference x = '+str(x)+' m.' if direct else 'Probe x = '+str(alignment['source_probe_x_m'])+' m → reference x = '+str(x)+' m; wave delay = '+format(alignment['time_shift_s'],'.4f')+' s ('+format(alignment['phase_shift_deg'],'.1f')+'°).'
 fig.text(.5,.015,note+' Zero force difference = C01. Thin lines: '+str(profile['cycle_count'])+' cycles.',ha='center',fontsize=9,color='#526674')
 fig.tight_layout(rect=(0,.035,1,.95),w_pad=3)
 base=key+'_force_wave'
 fig.savefig(out/(base+'.png'),bbox_inches='tight');fig.savefig(out/(base+'.svg'),bbox_inches='tight');plt.close(fig)
 with (out/(key+'_force_wave_phase.csv')).open('w',newline='',encoding='utf8') as f:
  w=csv.writer(f);w.writerow(['phase_deg','eta_at_reference_prime_mean_m','lift_minus_C01_mean_N','drag_minus_C01_mean_N','target_x_m','source_probe_x_m','wave_time_shift_s','L_C01_N','D_C01_N'])
  w.writerows(zip(phase,em,profile['lift_minus_C01_mean_N'],profile['drag_minus_C01_mean_N'],[x]*len(phase),[alignment['source_probe_x_m']]*len(phase),[alignment['time_shift_s']]*len(phase),[profile['C01']['L_N']]*len(phase),[profile['C01']['D_N']]*len(phase)))
 return profile,[base+'.png']

def accepted_trend_records(results):
 latest={}
 for r in results:
  if r.get('Q') and (r['case'] not in latest or r['time_s']>latest[r['case']]['time_s']):latest[r['case']]=r
 return [latest[k] for k in sorted(latest)]

def q_figures(out,results,diagnostic=None):
 records=accepted_trend_records(results)
 fields=['case','display_id','run','H_m','lambda_m','CD_wave','CD_C01','D_wave_N','D_C01_N','Q_CD','delta_D_N','relative_change_pct','window_start_s','window_end_s','phase_probe_x_m','project_accepted','scope']
 rows=[]
 for r in records:
  q=r['Q'];rows.append(dict(case=r['case'],display_id=r.get('display_id',r['case']),run=r['id'],H_m=r['H'],lambda_m=r['L'],**{k:q[k] for k in ('CD_wave','CD_C01','D_wave_N','D_C01_N','Q_CD','delta_D_N','relative_change_pct','scope')},window_start_s=q['wave_window_s'][0],window_end_s=q['wave_window_s'][1],phase_probe_x_m=r['cycles']['phase_probe_x_m'],project_accepted=True))
 with (out/'Q_summary.csv').open('w',newline='',encoding='utf8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 if records:
  trend_figure(out,'Q_trend',records,[r['Q'] for r in records],
   (('Q_CD','Q = ⟨Cx wave⟩ − ⟨Cx C01⟩'),('delta_D_N','Horizontal force difference ΔFx [N]')),
   'horizontal force',records[0]['Q']['D_C01_N'],'Negative values indicate lower horizontal force.',
   diagnostic and dict(final=diagnostic.get('final',False),Q_CD=diagnostic['delta_CD'],delta_D_N=diagnostic['delta_D_N'],
                       relative_change_pct=diagnostic['drag_change_pct']))
 return rows

def lift_figures(out,results,diagnostic=None):
 records=accepted_trend_records(results)
 rows=[]
 for r in records:
  reference=r['force_reference'];calm=reference['CL'];wave=r['cycles']['CL_mean']
  scale=reference['coefficient_denominator_N'];delta=wave-calm
  rows.append(dict(case=r['case'],display_id=r.get('display_id',r['case']),run=r['id'],
   CL_wave=wave,CL_C01=calm,L_wave_N=wave*scale,L_C01_N=calm*scale,
   delta_CL=delta,delta_L_N=delta*scale,relative_change_pct=100*delta/calm))
 if rows:
  trend_figure(out,'lift_trend',records,rows,
   (('delta_CL','ΔCz = ⟨Cz wave⟩ − ⟨Cz C01⟩'),('delta_L_N','Vertical force difference ΔFz [N]')),
   'vertical force',rows[0]['L_C01_N'],'The vertical force excludes buoyancy.',
   diagnostic and dict(final=diagnostic.get('final',False),delta_CL=diagnostic['delta_CL'],delta_L_N=diagnostic['delta_L_N'],
                       relative_change_pct=diagnostic['lift_change_pct']))
 return rows

def trend_figure(out,stem,records,rows,panels,quantity,baseline,convention,diagnostic=None):
 fig,axes=plt.subplots(1,3,figsize=(max(15.5,2.35*(len(records)+bool(diagnostic))),5.1))
 colors=['#087f8c' if row[panels[0][0]]<0 else '#c17a19' for row in rows]
 labels=[f"{r.get('display_id',r['case'])}\nH={r['H']:g} m\nλ={round(r['L'],2):g} m" for r in records]
 short_labels=[r.get('display_id',r['case']) for r in records]
 if diagnostic:
  rows=[*rows,diagnostic]
  colors.append('#526fab' if diagnostic['final'] else '#fff5e2')
  labels.append('W08bi*\nW01 + W06')
  short_labels.append('W08bi*')
 def bars(ax,values,palette):
  patches=ax.bar(range(len(values)),values,color=palette,width=.56)
  if diagnostic and not diagnostic['final']:
   patches[-1].set(edgecolor='#875815',hatch='///',linewidth=1.3)
 for i_panel,(ax,(key,title)) in enumerate(zip(axes,panels)):
  values=[row[key] for row in rows];bars(ax,values,colors)
  ax.axhline(0,color='#334b55',lw=1);ax.set_xticks(range(len(labels)),labels,fontsize=9);ax.set_title(title,fontsize=11)
  pad=max(abs(v) for v in values)*.13 or 1e-6;ax.set_ylim(min(0,min(values))-pad*2,max(0,max(values))+pad)
  for i,value in enumerate(values):ax.text(i,value+(-pad*.55 if value<0 else pad*.3),format(value,'.2e' if i_panel==0 else '.2f'),ha='center',fontsize=10)
 absolute=[0.]+[row['relative_change_pct'] for row in rows]
 bars(axes[2],absolute,['#81949c']+colors)
 axes[2].set_xticks(range(len(absolute)),['C01']+short_labels);axes[2].set_title(f'Mean {quantity} change vs C01 [%]',fontsize=11)
 pad=max(max(abs(v) for v in absolute)*.13,.1);axes[2].set_ylim(min(absolute)-pad*2,max(absolute)+pad);axes[2].axhline(0,color='#334b55',lw=1)
 for i,value in enumerate(absolute):axes[2].text(i,value+(-pad*.55 if value<0 else pad*.3),format(value,'.2f')+'%',ha='center',fontsize=10)
 fig.suptitle(f'NWAR · {quantity} trend in the selected M13 configuration',fontsize=14)
 note=f'C01 {quantity} = {baseline:.2f} N. {convention} Means use cycles 2–5 of each accepted run.'
 if diagnostic:
  dataset='final diagnostic' if diagnostic['final'] else 'provisional diagnostic'
  note+=f'\n* W08bi: {dataset} mean over three beat periods.'
 fig.text(.5,.015,note,ha='center',fontsize=9,color='#526674')
 fig.tight_layout(rect=(0,.11 if diagnostic else .07,1,.94));fig.savefig(out/(stem+'.png'),bbox_inches='tight');fig.savefig(out/(stem+'.svg'),bbox_inches='tight');plt.close(fig)
