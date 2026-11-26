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
fig.suptitle('M09: mean drag and lift differ from M07 by less than 0.5%',x=.078,y=.965,ha='left',fontsize=20,fontweight='bold',color='#173443')
fig.text(.078,.916,'Calm water · quasi-2D · U = 18 m/s · SST k-ω · second-order time scheme · Δt = 1 ms · 10 iterations/step',fontsize=11,color='#425866')
fig.text(.078,.886,'Scope: the tested meshes and averaging window. Formal grid uncertainty (GCI) has not yet been established.',fontsize=11,color='#8c5c16')
for a,k,title in [(ax[0,0],'CD','A  Drag coefficient history'),(ax[0,1],'CL_total','B  Total lift coefficient history')]:
 a.axvspan(1.84,2.04,color='#e4eff2',alpha=.75,label='comparison window')
 for m in meshes:
  c=D['cases'][m]['curve'];a.plot([x['physical_time_s'] for x in c],[x[k] for x in c],color=COL[m],label=m,lw=2,ls={'M09':'-','M08':'--','M07':'-.'}[m])
 a.set(xlabel='Physical time t [s]',ylabel='$C_D$ [-]' if k=='CD' else '$C_{L,total}$ [-]',xlim=(1.64,2.04));a.set_title(title,loc='left',fontweight='bold',pad=12)
 a.ticklabel_format(axis='y',style='plain',useOffset=False);a.legend(loc='best',ncol=2,fontsize=9,framealpha=.9)
 a.text(.98,.02,'Averages: 1.84 < t ≤ 2.04 s',transform=a.transAxes,ha='right',fontsize=9,color='#425866')
a=ax[1,0];a.axhspan(-1,1,color='#e5f2ec');a.axhline(0,color='#5e7380',lw=.8)
for k,marker,shift in [('CD','o',-.025),('CL_total','s',.025)]:
 x=np.array([matched[m]['cells']/1000 for m in meshes]);y=np.array([100*(D['cases'][m]['mean'][k]/D['cases']['M07']['mean'][k]-1) for m in meshes])
 for i,m in enumerate(meshes):a.scatter(x[i],y[i],marker=marker,s=75,color=COL[m],edgecolor='white',zorder=4)
 a.plot([],[],marker=marker,color='#344e5b',ls='',label='$C_D$' if k=='CD' else '$C_{L,total}$')
for m in meshes:a.text(matched[m]['cells']/1000,.8,f'{m}\n{matched[m]["cells"]:,}'.replace(',',' '),ha='center',fontsize=9,color=COL[m],fontweight='bold')
a.set(xlabel='Cell count [thousands]',ylabel='Mean difference relative to M07 [%]',ylim=(-1.15,1.2),xlim=(185,515));a.set_title('C  Mean agreement versus cell count',loc='left',fontweight='bold',pad=12)
a.legend(loc='lower right',fontsize=9);a.text(.03,.05,'Green band: project tolerance of ±1%\nThese meshes do not form a systematic GCI family.',transform=a.transAxes,fontsize=9,color='#425866')
a=ax[1,1];keys=['CD','CL_total','pressure_drag_N','viscous_drag_N'];labels=['$C_D$','$C_{L,total}$','Pressure drag','Viscous drag'];y=np.arange(4)
for candidate,reference,offset,col,marker in [('M09','M07',-.17,COL['M09'],'o'),('M08','M07',0,COL['M08'],'s'),('M09','M08',.17,'#394e5a','D')]:
 v=[100*(D['cases'][candidate]['mean'][k]-D['cases'][reference]['mean'][k])/abs(D['cases'][reference]['mean'][k]) for k in keys]
 a.scatter(v,y+offset,color=col,marker=marker,s=50,label=f'{candidate} / {reference}',zorder=4)
 if candidate=='M09' and reference=='M07':
  for yy,vv in zip(y+offset,v):a.annotate(f'{vv:+.3f}%',(vv,yy),xytext=(7,9),textcoords='offset points',fontsize=8,color=col)
a.axvline(0,color='#627782',lw=.8);a.axvline(1,color='#b07d28',ls='--',lw=1.2)
a.set(yticks=y,yticklabels=labels,xlabel='100 × (candidate − reference) / |reference| [%]',xlim=(-.42,2.12),ylim=(3.6,-.62));a.set_title('D  Drag components reveal a larger difference',loc='left',fontweight='bold',pad=12);a.legend(loc='upper right',fontsize=8,framealpha=.9)
fig.text(.078,.074,'The 1% tolerance is a project criterion, not a universal ITTC/AIAA limit or an uncertainty interval.',fontsize=10,color='#425866')
fig.text(.078,.047,'M09 relative to M07: +0.467% Cᴅ, −0.164% Cʟ; pressure drag +1.555%.  M09, Δt 1 → 0.5 ms: −0.00242% Cᴅ.',fontsize=10,color='#425866')
fig.text(.078,.023,'Source: M07/M08/M09 simulation histories, recomputed on 30 Oct 2026. Forces and coefficients refer to the quasi-2D slice.',fontsize=9,color='#6c7d86')
fig.savefig(HERE/'mesh_comparison_EN.png',dpi=190);fig.savefig(HERE/'mesh_comparison_EN.svg');plt.close(fig)
