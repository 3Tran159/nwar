"""Compare recorded horizontal force with original and delayed local AoA."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
from common import *
from analysis import numeric_rows
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_research_summary_20261109/mechanism_followup')
SOURCE=DATA/'analyses/W04e_aoa_20261107';LAG=.050

def branch_metrics(alpha,force):
 a=alpha[:-1];f=force[:-1];n=600
 # Even-odd vertical sections handle small reversals and self intersections
 # without smoothing or forcing either measured branch to be monotonic.
 grid=a.min()+(np.arange(n)+.5)*np.ptp(a)/n
 a2=np.roll(a,-1);f2=np.roll(f,-1);gap=[];lower=[];upper=[]
 for value in grid:
  cross=((a<=value)&(a2>value))|((a2<=value)&(a>value))
  yy=np.sort(f[cross]+(value-a[cross])*(f2[cross]-f[cross])/(a2[cross]-a[cross]))
  if len(yy)%2:raise ValueError('Ambiguous closed-curve intersections.')
  gap.append(float(np.sum(yy[1::2]-yy[::2])));lower.append(float(yy.min()));upper.append(float(yy.max()))
 gap=np.array(gap);fu=np.array(upper);fd=np.array(lower)
 interior=(grid>=a.min()+.1*np.ptp(a))&(grid<=a.max()-.1*np.ptp(a))
 return dict(unsigned_branch_area_N_deg=float(np.sum(gap)*np.ptp(a)/n),
             branch_gap_RMS_N=float(np.sqrt(np.mean(gap[interior]**2))),
             maximum_branch_gap_N=float(np.max(abs(gap))),
             definition='Even-odd enclosed area of the closed phase-mean curve; vertical-thickness RMS excludes outer 10 percent of angle range. No smoothing.'),grid,fu,fd

def main():
 evidence=read(SOURCE/'W04e_aoa_evidence.json');p=evidence['phase'];phi=np.array(p['phase_deg'])
 times=np.array([a+(b-a)*phi/360 for a,b in p['windows_s']]);fields=[r for r in rows(SOURCE/'W04e_upstream_velocity_aoa.csv')if r['probe']=='upstream']
 t=np.array([float(r['time_s'])for r in fields]);a=np.array([float(r['aoa_deg'])for r in fields])
 if times.min()-LAG<t.min()or times.max()>t.max():raise ValueError('The phase window would extrapolate past saved fields.')
 alpha=np.interp(times,t,a);delayed=np.interp(times-LAG,t,a)
 force=numeric_rows(Path(job('449524f35ca14e94')['folder'])/'history.csv')
 fx=np.interp(times,force['time_s'],force['Fx_N'])-p['C01']['D_N']
 am=alpha.mean(0);dm=delayed.mean(0);fm=fx.mean(0)
 before,grid,fu,fd=branch_metrics(am,fm);after,g2,du,dd=branch_metrics(dm,fm)
 metrics=dict(case='W04e',H_m=1.5,lambda_m=15.,lag_s=LAG,lag_definition='Compare force at t with upstream angle at t - 0.050 s; original force and wave phase are unchanged.',
              cycles=[2,3,4,5],phase_windows_s=p['windows_s'],before=before,after=after,
              unsigned_branch_area_reduction_pct=100*(1-after['unsigned_branch_area_N_deg']/before['unsigned_branch_area_N_deg']),
              force_retimed=False,force_modified=False,lag_fitted_to_force=False,
              limitations=['Probe is 0.9 m upstream and includes foil-induced flow.','Fixed delay is a sensitivity test, not a measured transfer function.',
                           'A residual loop is not evidence for temporal memory without matched speed and incident-flow control.'])
 write(OUT/'W04e_0p05s_loop_metrics.json',metrics)
 records=[dict(cycle=cycle,phase_deg=float(ph),time_s=float(times[i,j]),alpha_original_deg=float(alpha[i,j]),
           alpha_delayed_deg=float(delayed[i,j]),delta_Fx_N=float(fx[i,j]))for i,cycle in enumerate([2,3,4,5])for j,ph in enumerate(phi)]
 with(OUT/'W04e_0p05s_AoA_Fx.csv').open('w',encoding='utf-8-sig',newline='')as f:w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
 plt.rcParams.update({'font.size':11,'axes.spines.top':False})
 fig,axs=plt.subplots(2,1,figsize=(10.4,8.2),layout='constrained')
 left=axs[0];right=left.twinx()
 left.axvspan(100,270,color='#d2dddd',alpha=.4,zorder=0)
 left.fill_between(phi,fx.min(0),fx.max(0),color='black',alpha=.10);left.plot(phi,fm,color='black',lw=2,label='Recorded horizontal force')
 right.plot(phi,am,color='#999999',ls='--',lw=1.6,label='AoA at t')
 right.plot(phi,dm,color='#007f85',lw=2,label='AoA at t - 0.050 s')
 left.set(xlabel='Wave phase at x = 0 [deg]',ylabel='Delta Fx from C01 [N]',xlim=(0,360),xticks=[0,90,180,270,360])
 left.set_title('(a) The force waveform is unchanged; only the angle is delayed',pad=35)
 right.set_ylabel('Local upstream AoA [deg]');left.axhline(0,color='#777777',lw=.7)
 lines=left.get_lines()[:1]+right.get_lines();left.legend(lines,[x.get_label()for x in lines],loc='lower left',bbox_to_anchor=(0,1.005),fontsize=9,ncol=3,frameon=False)
 ax=axs[1]
 for aa,ff in zip(delayed,fx):ax.plot(aa,ff,color='#007f85',alpha=.2,lw=.6)
 ax.plot(am,fm,color='#999999',ls='--',lw=1.8,label='Original simultaneous-time loop')
 ax.plot(dm,fm,color='#007f85',lw=2.1,label='After 0.050 s angle delay')
 for i in(10,35,70,100):
  ax.annotate('',xy=(dm[i+2],fm[i+2]),xytext=(dm[i],fm[i]),arrowprops=dict(arrowstyle='->',color='#007f85',lw=1.3))
 ax.axhline(0,color='#777777',lw=.7);ax.set(xlabel='Local upstream AoA [deg]',ylabel='Delta Fx from C01 [N]',title='(b) Force-angle loop before and after the predefined delay')
 ax.legend(loc='upper right',fontsize=9)
 for a in axs:a.grid(alpha=.2)
 fig.suptitle('W04e | H = 1.5 m, wavelength = 15 m | cycles 2-5',fontsize=14)
 for ext in('png','svg','pdf'):fig.savefig(OUT/('W04e_AoA_Fx_delay_0p05s.'+ext),dpi=190)
 plt.close(fig);print(json.dumps(metrics,indent=2))

if __name__=='__main__':main()
