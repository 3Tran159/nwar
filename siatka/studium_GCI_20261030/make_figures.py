from pathlib import Path
import sys,os,json,csv
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'.deps'));os.environ['MPLCONFIGDIR']=str(HERE/'.mplconfig')
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
D=json.loads((HERE/'evidence.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':12,'axes.labelsize':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.19,'axes.axisbelow':True,'savefig.facecolor':'white','pdf.fonttype':42,'svg.fonttype':'none'})
COL={'M09':'#007e83','M08':'#d18720','M07':'#6548a3'}
meshes=['M09','M08','M07']; matched={r['mesh']:r for r in D['matched']['results']}
fig,ax=plt.subplots(2,2,figsize=(14,9.6));fig.subplots_adjust(top=.85,bottom=.15,left=.078,right=.97,hspace=.42,wspace=.31)
fig.suptitle('M09: różnice Cᴅ i Cʟ względem M07 poniżej 0,5%',x=.078,y=.965,ha='left',fontsize=22,fontweight='bold',color='#173443')
fig.text(.078,.916,'Spokojna woda · quasi-2D · U = 18 m/s · SST k-ω · II rząd w czasie · Δt = 1 ms · 10 iteracji/krok',fontsize=11,color='#425866')
fig.text(.078,.886,'Wniosek dotyczy badanego okna i wariantów siatki. Formalna niepewność siatkowa GCI pozostaje nieokreślona.',fontsize=11,color='#8c5c16')
for a,k,title in [(ax[0,0],'CD','A  Przebieg współczynnika oporu'),(ax[0,1],'CL_total','B  Przebieg całkowitej siły nośnej')]:
 a.axvspan(1.84,2.04,color='#e4eff2',alpha=.75,label='okno porównania')
 for m in meshes:
  c=D['cases'][m]['curve'];a.plot([x['physical_time_s'] for x in c],[x[k] for x in c],color=COL[m],label=m,lw=2,ls={'M09':'-','M08':'--','M07':'-.'}[m])
 a.set(xlabel='Czas fizyczny t [s]',ylabel='$C_D$ [-]' if k=='CD' else '$C_{L,total}$ [-]',xlim=(1.64,2.04));a.set_title(title,loc='left',fontweight='bold',pad=12)
 a.ticklabel_format(axis='y',style='plain',useOffset=False);a.legend(loc='best',ncol=2,fontsize=9,framealpha=.9)
 a.text(.98,.02,'Średnie: 1,84 < t ≤ 2,04 s',transform=a.transAxes,ha='right',fontsize=9,color='#425866')
a=ax[1,0];a.axhspan(-1,1,color='#e5f2ec');a.axhline(0,color='#5e7380',lw=.8)
for k,marker,shift in [('CD','o',-.025),('CL_total','s',.025)]:
 x=np.array([matched[m]['cells']/1000 for m in meshes]);y=np.array([100*(D['cases'][m]['mean'][k]/D['cases']['M07']['mean'][k]-1) for m in meshes])
 for i,m in enumerate(meshes):a.scatter(x[i],y[i],marker=marker,s=75,color=COL[m],edgecolor='white',zorder=4)
 a.plot([],[],marker=marker,color='#344e5b',ls='',label='$C_D$' if k=='CD' else '$C_{L,total}$')
for m in meshes:a.text(matched[m]['cells']/1000,.8,f'{m}\n{matched[m]["cells"]:,}'.replace(',',' '),ha='center',fontsize=9,color=COL[m],fontweight='bold')
a.set(xlabel='Liczba komórek [tys.]',ylabel='Różnica średniej względem M07 [%]',ylim=(-1.15,1.2),xlim=(185,515));a.set_title('C  Zgodność średnich a liczba komórek',loc='left',fontweight='bold',pad=12)
a.legend(loc='lower right',fontsize=9);a.text(.03,.05,'Zielone pole: projektowy próg ±1%\nPunkty nie tworzą jednorodnej rodziny GCI.',transform=a.transAxes,fontsize=9,color='#425866')
a=ax[1,1];keys=['CD','CL_total','pressure_drag_N','viscous_drag_N'];labels=['$C_D$','$C_{L,total}$','Opór ciśnieniowy','Opór lepki'];y=np.arange(4)
for candidate,reference,offset,col,marker in [('M09','M07',-.17,COL['M09'],'o'),('M08','M07',0,COL['M08'],'s'),('M09','M08',.17,'#394e5a','D')]:
 v=[100*(D['cases'][candidate]['mean'][k]-D['cases'][reference]['mean'][k])/abs(D['cases'][reference]['mean'][k]) for k in keys]
 a.scatter(v,y+offset,color=col,marker=marker,s=50,label=f'{candidate} / {reference}',zorder=4)
 if candidate=='M09' and reference=='M07':
  for yy,vv in zip(y+offset,v):a.annotate(f'{vv:+.3f}%',(vv,yy),xytext=(7,9),textcoords='offset points',fontsize=8,color=col)
a.axvline(0,color='#627782',lw=.8);a.axvline(1,color='#b07d28',ls='--',lw=1.2)
a.set(yticks=y,yticklabels=labels,xlabel='100 × (wariant − odniesienie) / |odniesienie| [%]',xlim=(-.42,2.12),ylim=(3.6,-.62));a.set_title('D  Składowe oporu ujawniają większą różnicę',loc='left',fontweight='bold',pad=12);a.legend(loc='upper right',fontsize=8,framealpha=.9)
fig.text(.078,.074,'Próg 1% pochodzi z kampanii; nie jest uniwersalnym kryterium ITTC/AIAA ani przedziałem niepewności.',fontsize=10,color='#425866')
fig.text(.078,.047,'M09 → M07: +0,467% Cᴅ, −0,164% Cʟ; opór ciśnieniowy +1,555%.  Δt 1 → 0,5 ms na M09: −0,00242% Cᴅ.',fontsize=10,color='#425866')
fig.text(.078,.023,'Źródło: historie obliczeń M07/M08/M09, ponownie przeliczone 30.10.2026. Siły i współczynniki dotyczą wycinka quasi-2D.',fontsize=9,color='#6c7d86')
fig.savefig(HERE/'mesh_comparison.png',dpi=190);fig.savefig(HERE/'mesh_comparison.svg');plt.close(fig)
old=D['mesh_convergence']['settled_results'];fig,axes=plt.subplots(1,2,figsize=(13,5.5));fig.subplots_adjust(top=.73,bottom=.24,left=.08,right=.97,wspace=.28)
fig.suptitle('Warianty przyścienne dają różne wyniki oporu',x=.08,y=.96,ha='left',fontsize=20,fontweight='bold',color='#173443')
fig.text(.08,.875,'Historyczny screening M02–M08: różne okna czasu. Punkty pokazują wrażliwość konfiguracji, nie formalną zbieżność.',fontsize=10,color='#8c5c16')
for a,k,label in zip(axes,['CD','CL_total'],['$C_D$ [-]','$C_{L,total}$ [-]']):
 for fam,col,marker,lab in [('wall_function','#b66a25','^','Reżim wall-function'),('low_yplus','#16858a','o','Reżim low-y⁺')]:
  rr=[r for r in old if r['family']==fam];a.scatter([r['cells']/1000 for r in rr],[r[k] for r in rr],color=col,marker=marker,s=65,label=lab,zorder=4)
  for r in rr:a.annotate(r['id'],(r['cells']/1000,r[k]),xytext=(4,6 if r['id']!='M08' else -15),textcoords='offset points',fontsize=9)
 a.set(xlabel='Liczba komórek [tys.]',ylabel=label);a.ticklabel_format(axis='y',useOffset=False);a.legend(fontsize=9)
fig.text(.08,.12,'M02/M03/M05 mają pierwszą warstwę 179,9 μm; M04: 3 μm; M06: 2,14 μm; M07/M08: 1,53 μm.',fontsize=10,color='#425866')
fig.text(.08,.075,'Wspólny model All y+ Wall Treatment pracuje tu w różnych reżimach. Nie wolno łączyć tych punktów w jeden fit GCI.',fontsize=10,color='#425866')
fig.text(.08,.035,'Źródło: historyczne mesh_convergence.json i mesh_definition_evidence.json. Końcowa ocena M09 używa osobnego, dopasowanego zestawu.',fontsize=9,color='#6c7d86')
fig.savefig(HERE/'mesh_variants_history.png',dpi=180);fig.savefig(HERE/'mesh_variants_history.svg');plt.close(fig)
with (HERE/'mesh_comparison_values.csv').open('w',encoding='utf-8-sig',newline='') as f:
 w=csv.writer(f);w.writerow(['mesh','cells','window_start_exclusive_s','window_end_inclusive_s','CD','CL_total','pressure_drag_slice_N','viscous_drag_slice_N','CD_vs_M07_pct','CL_vs_M07_pct','CD_adjacent_window_drift_pct'])
 for m in meshes:
  s=D['cases'][m];w.writerow([m,matched[m]['cells'],1.84,2.04,*[s['mean'][k] for k in keys],100*(s['mean']['CD']/D['cases']['M07']['mean']['CD']-1),100*(s['mean']['CL_total']/D['cases']['M07']['mean']['CL_total']-1),s['drift_pct']['CD']])
print('Created main and historical figures, SVG copies and numerical table.')
