"""Publication figure: phase-averaged responses at one spatial reference."""
from common import write
import csv,math
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

# Fixed case identities: adding a run never recolours an existing wave.
STYLES={
 'W01':('#0072B2','-'), 'W02':('#D55E00',(0,(5,2))),
 'W03':('#009E73',(0,(5,1.5,1,1.5))), 'W04':('#CC79A7',(0,(1.2,1.5))),
 'W05':('#E69F00',(0,(7,2,2,2))), 'W06':('#56B4E9',(0,(3,1.5))),
 'W07':('#555555',(0,(6,1.5,1,1.5,1,1.5))),
 'W04c':('#8C564B',(0,(4,1))), 'W04e':('#9467BD',(0,(5,1,1,1))),
 'W04f':('#D62728',(0,(3,1,1,1))), 'W04g':('#17A0A0',(0,(7,1))),
 'W04h':('#BC8D22',(0,(2,1))),
 'W04i':('#7B4173',(0,(6,1,2,1))),
 'W04j':('#4B6F38',(0,(2,1,1,1))),
 'W04k':('#6B6ECF',(0,(5,1,1,1,1,1))),
}

def comparison_records(results):
 latest={};excluded=[]
 for r in results:
  p=r.get('force_wave_response') or {};reason=None
  if not r.get('project_accepted') or r.get('smoke'):reason='Awaiting campaign acceptance'
  elif p.get('cycle_count')!=4:reason='Four complete response cycles required'
  elif p.get('reference_x_m')!=0.:reason='Common x = 0 reference required'
  elif p.get('force_reference')!='C01':reason='Accepted C01 force reference required'
  else:
   arrays=[np.asarray(p.get(k,[]),dtype=float) for k in ('phase_deg','eta_prime_mean_m','lift_minus_C01_mean_N','drag_minus_C01_mean_N')]
   if not len(arrays[0]) or any(v.shape!=arrays[0].shape or not np.isfinite(v).all() for v in arrays):reason='Incomplete response arrays'
   elif arrays[0][0]!=0 or abs(arrays[0][-1]-360)>1e-6 or np.any(np.diff(arrays[0])<=0):reason='Full monotonic phase cycle required'
  if reason:excluded.append(dict(run=r.get('id'),case=r.get('case'),reason=reason));continue
  key=r['case']
  if key not in latest or r['time_s']>latest[key]['time_s']:latest[key]=r
 return [latest[k] for k in sorted(latest)],excluded

def save_comparison(out,results):
 records,excluded=comparison_records(results)
 base='force_wave_comparison'
 meta=dict(case_count=len(records),reference_x_m=0.,cycles_per_case=4,cases=[],excluded=excluded,
           phase_reference='sin(phi), a dimensionless harmonic phase guide; not a shared measured wave height',
           force_units='N',loop_wave_units='m',force_normalization='Fixed accepted C01 subtracted; wave-cycle mean offsets retained',force_reference='C01',
           force_phase_shift_applied=False,files={})
 if not records:
  write(out/(base+'.json'),meta);return meta
 meta['C01']=records[0]['force_wave_response']['C01']
 if any(r['force_wave_response']['C01']!=meta['C01'] for r in records):raise ValueError('Mixed calm force references in comparison')
 rows=[];handles=[]
 for r in records:
  p=r['force_wave_response'];color,style=STYLES.get(r['case'],('#333333','-'))
  label=r.get('display_id',r['case'])
  handles.append(Line2D([],[],color=color,ls=style,lw=1.5,label=label+'\n'+r'$H$ = '+format(r['H'],'.2f')+' m; '+r'$\lambda$ = '+format(r['L'],'.3g')+' m'))
  meta['cases'].append(dict(case=r['case'],display_id=label,run=r['id'],H_m=r['H'],lambda_m=r['L'],
                            color=color,line_style=style,alignment=p['alignment'],windows_s=p['windows_s']))
  for ph,eta,lift,drag in zip(p['phase_deg'],p['eta_prime_mean_m'],p['lift_minus_C01_mean_N'],p['drag_minus_C01_mean_N']):
   rows.append(dict(case=label,H_m=r['H'],lambda_m=r['L'],phase_deg=ph,eta_prime_m=eta,lift_minus_C01_N=lift,drag_minus_C01_N=drag,L_C01_N=p['C01']['L_N'],D_C01_N=p['C01']['D_N'],
                    reference_x_m=0.,cycles=4,source_probe_x_m=p['alignment']['source_probe_x_m'],wave_time_shift_s=p['alignment']['time_shift_s']))
 with (out/(base+'.csv')).open('w',newline='',encoding='utf8') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
 legend_rows=math.ceil(len(records)/3)
 height=6.35+.38*(legend_rows-1)
 rc={'font.family':'DejaVu Sans','font.size':8.5,'axes.titlesize':9,'axes.labelsize':9,
     'xtick.labelsize':8,'ytick.labelsize':8,'axes.linewidth':.7,'axes.grid':False,
     'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'ps.fonttype':42,'svg.fonttype':'none',
     'figure.facecolor':'white','axes.facecolor':'white','savefig.facecolor':'white'}
 with plt.rc_context(rc):
  fig,axes=plt.subplots(2,2,figsize=(180/25.4,height),gridspec_kw={'width_ratios':[1.35,1.]})
  fig.subplots_adjust(left=.11,right=.98,bottom=.095,top=1-(.92+.38*(legend_rows-1))/height,wspace=.63,hspace=.34)
  fig.legend(handles=handles,ncol=min(3,len(records)),loc='upper center',bbox_to_anchor=(.53,.995),frameon=False,
             handlelength=2.7,columnspacing=1.55,handletextpad=.7,fontsize=8.2)
  guide_y=1-(.49+.38*(legend_rows-1))/height
  symbols=[Line2D([],[],color='#666666',ls=(0,(4,3)),lw=.9,label=r'Phase reference: $\sin\varphi$'),
           Line2D([],[],color='#444444',marker='o',mfc='white',ls='None',ms=4,label='Wave crest'),
           Line2D([],[],color='#444444',marker='s',mfc='white',ls='None',ms=4,label='Wave trough')]
  fig.legend(handles=symbols,ncol=3,loc='upper center',bbox_to_anchor=(.53,guide_y),frameon=False,
             columnspacing=1.8,handlelength=2.7,fontsize=8)
  phase=np.linspace(0,360,361)
  eta_max=max(np.max(np.abs(r['force_wave_response']['eta_prime_mean_m'])) for r in records)*1.16
  for row,(field,ylabel,force_name) in enumerate([
    ('lift_minus_C01_mean_N',r'$F_z-F_{z,\mathrm{C01}}$ (N)','Vertical force'),('drag_minus_C01_mean_N',r'$F_x-F_{x,\mathrm{C01}}$ (N)','Horizontal force')]):
   left,right=axes[row]
   extent=max(np.max(np.abs(r['force_wave_response'][field])) for r in records)*1.17 or 1.
   for ax in (left,right):
    ax.set_ylim(-extent,extent);ax.set_ylabel(ylabel,labelpad=4)
    ax.axhline(0,color='#6b747a',lw=.85,zorder=1)
    ax.grid(True,color='#e5e8ea',lw=.45,alpha=.65);ax.tick_params(direction='out',length=3,width=.65)
   left.set(xlim=(0,360),xticks=[0,90,180,270,360]);right.set_xlim(-eta_max,eta_max)
   guide=left.twinx();guide.patch.set_visible(False);guide.spines['right'].set_visible(True)
   guide.plot(phase,np.sin(np.deg2rad(phase)),color='#666666',ls=(0,(4,3)),lw=.85,alpha=.60,zorder=0)
   guide.set(ylim=(-1.22,1.22),yticks=[-1,0,1]);guide.set_ylabel(r'$\sin\varphi$',color='#777777',labelpad=2)
   guide.tick_params(axis='y',colors='#777777',length=2,width=.6);guide.spines['right'].set_color('#bbbbbb');guide.grid(False)
   # Force curves remain in front of the neutral reference curve.
   left.set_zorder(guide.get_zorder()+1);left.patch.set_visible(False)
   for r in records:
    p=r['force_wave_response'];color,style=STYLES.get(r['case'],('#333333','-'))
    ph=np.asarray(p['phase_deg']);eta=np.asarray(p['eta_prime_mean_m']);force=np.asarray(p[field])
    left.plot(ph,force,color=color,ls=style,lw=1.45)
    right.plot(eta,force,color=color,ls=style,lw=1.45)
    for angle,marker in ((p['crest_phase_deg'],'o'),(p['trough_phase_deg'],'s')):
     i=int(np.argmin(abs(ph-angle)));right.plot(eta[i],force[i],marker=marker,ms=4,mfc='white',mec=color,mew=.9,ls='None',zorder=4)
    for angle in (135,315):
     i=int(np.argmin(abs(ph-angle)));j=min(i+3,len(ph)-1)
     right.annotate('',xy=(eta[j],force[j]),xytext=(eta[i],force[i]),arrowprops=dict(arrowstyle='->',color=color,lw=.9,mutation_scale=7))
   left.set_title('('+('a' if row==0 else 'c')+') '+force_name+'–phase response',loc='left',pad=9)
   right.set_title('('+('b' if row==0 else 'd')+') '+force_name+'–wave loop',loc='left',pad=9)
   if row==0:left.tick_params(labelbottom=False);right.tick_params(labelbottom=False)
   else:left.set_xlabel(r'Wave phase $\varphi$ at $x=0$ (°)');right.set_xlabel(r'$\eta-\langle\eta\rangle$ at $x=0$ (m)')
  for suffix,dpi in (('.png',220),('_600dpi.png',600),('.svg',None),('.pdf',None)):
   kwargs={'dpi':dpi} if dpi else {}
   fig.savefig(out/(base+suffix),**kwargs)
  plt.close(fig)
 labels=', '.join(r.get('display_id',r['case']) for r in records)
 caption=('Phase-averaged foil response relative to accepted C01 ('+labels+'). Panels (a,c) show vertical and horizontal force differences in fixed domain axes from C01 versus wave phase at x = 0; '
          'panels (b,d) show the corresponding force–surface-elevation loops. Each curve is the mean of the complete response cycles 2–5, excluding cycle 1, '
          'after subtracting the same fixed C01 force from every sample. Horizontal zero lines denote C01. Wave-cycle mean force offsets are retained. '
          'C01 buoyancy-corrected vertical force is '+format(meta['C01']['L_N'],'.4f')+' N and horizontal force is '+format(meta['C01']['D_N'],'.4f')+' N. '
          'Force differences are in newtons; surface elevations are measured from each cycle mean in metres, with no amplitude normalization. '
          'Phase zero is the upward crossing of the wave reference level at x = 0. The grey dashed sin(phi) curves are dimensionless phase guides; '
          'they do not represent one physical wave height shared by all cases. Loop coordinates use each case’s wave signal. '
          'Circles and squares mark the measured-wave crest and trough; arrows indicate increasing time. '
          'Where the direct x = 0 history is incomplete, the wave signal is propagated from upstream probes. '
          'Travel time is calibrated from a probe pair where available and otherwise estimated from wavelength and period. '
          'Forces are not shifted or fitted to the wave. These results describe trends in the selected quasi-2D M13 configuration.')
 (out/(base+'_caption.txt')).write_text(caption+'\n',encoding='utf8')
 meta.update(caption=caption,width_mm=180.,files=dict(preview=base+'.png',png=base+'_600dpi.png',svg=base+'.svg',pdf=base+'.pdf',csv=base+'.csv',caption=base+'_caption.txt',evidence=base+'.json'))
 write(out/(base+'.json'),meta)
 from interactive_comparison import save_interactive
 meta['files']['interactive']=save_interactive(out,records)
 write(out/(base+'.json'),meta)
 return meta
