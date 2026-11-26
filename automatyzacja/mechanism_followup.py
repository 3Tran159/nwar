"""CPU-only phase diagnostics and an empirical local-inflow test on saved CFD."""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1');os.environ.setdefault('OMP_NUM_THREADS','1')
from common import *
from analysis import numeric_rows
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT=Path('H:/NTNU_RESEARCH_ARCHIVE/NWAR_research_summary_20261109/mechanism_followup')
AOA=DATA/'analyses/W04e_aoa_20261107'
DEN=3855.6;BUOYANCY=22.718189111947265

def save_csv(name,records):
 with(OUT/name).open('w',encoding='utf-8-sig',newline='')as f:
  w=csv.DictWriter(f,fieldnames=list(records[0]));w.writeheader();w.writerows(records)
def harmonic(phi,y):
 p=np.radians(phi[:-1]);v=y[:-1]
 X=np.column_stack([np.ones(len(p)),*[f(n*p)for n in(1,2,3)for f in(np.cos,np.sin)]])
 b=np.linalg.lstsq(X,v,rcond=None)[0];amp=np.hypot(b[1::2],b[2::2])
 return dict(mean=float(b[0]),A1=float(amp[0]),A2=float(amp[1]),A3=float(amp[2]),A2_A1=float(amp[1]/amp[0]))
def sector(phi,y,a,b):
 points=np.r_[a,phi[(phi>a)&(phi<b)],b]
 return float(np.trapezoid(np.interp(points,phi,y),points)/(b-a))
def metrics(actual,pred):
 return dict(RMSE_N=float(np.sqrt(np.mean((actual-pred)**2))),R2=float(1-np.sum((actual-pred)**2)/np.sum((actual-actual.mean())**2)),
             actual_phase_mean_N=float(actual.mean()),predicted_phase_mean_N=float(pred.mean()))

def build():
 OUT.mkdir(parents=True,exist_ok=True)
 report=Path(read(HERE/'latest_report.json')['directory']);audit=read(report/'audit.json')
 q={v['case']:v for v in audit['Q_data']};phases=[];harmonics=[];sectors=[];windows=[]
 for result in audit['results']:
  if not result.get('project_accepted'):continue
  profile=result['force_wave_response'];phi=np.array(profile['phase_deg']);fx=np.array(profile['drag_minus_C01_mean_N']);fz=np.array(profile['lift_minus_C01_mean_N'])
  assert profile['cycle_numbers']==[2,3,4,5]
  for label,y in [('delta_Fx',fx),('delta_Fz',fz)]:
   harmonics.append(dict(case=result['case'],quantity=label,reference_x_m=0.,**harmonic(phi,y)))
  for a,b in[(0,100),(100,270),(270,360)]:
   value=sector(phi,fx,a,b)
   sectors.append(dict(case=result['case'],start_deg=a,end_deg=b,mean_delta_Fx_N=value,phase_mean_contribution_N=value*(b-a)/360,
                       phase_mean_delta_Fx_N=float(np.trapezoid(fx,phi)/360),reference_x_m=0.))
  windows.append(dict(case=result['case'],Q_window_start_s=q[result['case']]['window_start_s'],Q_window_end_s=q[result['case']]['window_end_s'],
     mechanism_window_start_s=profile['windows_s'][0][0],mechanism_window_end_s=profile['windows_s'][-1][1],
     Q_window_delta_Fx_N=q[result['case']]['delta_D_N'],foil_phase_mean_delta_Fx_N=float(np.trapezoid(fx,phi)/360),
     difference_N=float(np.trapezoid(fx,phi)/360)-q[result['case']]['delta_D_N'],
     x0_reconstructed=not profile.get('direct_measurement_at_reference',profile.get('direct_measurement_at_foil',False))))
 save_csv('accepted_phase_sectors.csv',sectors);save_csv('accepted_force_harmonics.csv',harmonics);save_csv('Q_and_mechanism_windows.csv',windows)
 evidence=read(AOA/'W04e_aoa_evidence.json');phase=evidence['phase'];phi=np.array(phase['phase_deg']);cycles=np.array(phase['cycle_numbers'])
 t=np.array([a+(b-a)*phi/360 for a,b in phase['windows_s']]);force=numeric_rows(Path(job('449524f35ca14e94')['folder'])/'history.csv')
 fields=rows(AOA/'W04e_upstream_velocity_aoa.csv');fields=[v for v in fields if v['probe']=='upstream']
 ft=np.array([float(v['time_s'])for v in fields])
 assert t.min()>=ft.min() and t.max()<=ft.max()
 ux=np.interp(t,ft,[float(v['ux_m_s'])for v in fields]);uz=np.interp(t,ft,[float(v['uz_m_s'])for v in fields])
 alpha=np.interp(t,ft,[float(v['aoa_deg'])for v in fields]);beta=np.arctan2(uz,ux);V=np.hypot(ux,uz);qS=DEN*(V/18)**2
 fx=np.interp(t,force['time_s'],force['Fx_N']);fz=np.interp(t,force['time_s'],force['Fz_N'])-BUOYANCY
 parallel=fx*np.cos(beta)+fz*np.sin(beta);normal=-fx*np.sin(beta)+fz*np.cos(beta)
 Cpar=parallel/qS;Cnorm=normal/qS
 assert np.max(abs(parallel*np.cos(beta)-normal*np.sin(beta)-fx))<1e-10
 detail=[]
 for i,cycle in enumerate(cycles):
  for j,p in enumerate(phi):
   detail.append(dict(cycle=int(cycle),phase_deg=p,time_s=t[i,j],alpha_probe_deg=alpha[i,j],beta_deg=float(np.degrees(beta[i,j])),
    ux_m_s=ux[i,j],uz_m_s=uz[i,j],V_m_s=V[i,j],qS_N=qS[i,j],Fx_N=fx[i,j],Fz_buoyancy_corrected_N=fz[i,j],
    F_parallel_N=parallel[i,j],F_normal_N=normal[i,j],C_parallel=Cpar[i,j],C_normal=Cnorm[i,j]))
 save_csv('W04e_local_inflow_and_projected_forces.csv',detail)
 # Both models are fitted to CFD. Leave one whole cycle out, never random rows.
 # This tests diagnostic compression, not an independent steady polar or causality.
 aa=alpha[:,:-1];B=beta[:,:-1];F=fx[:,:-1];P=parallel[:,:-1];N=normal[:,:-1];QS=qS[:,:-1]
 predictions={};scores={}
 for label,scale in [('constant_speed_scale',np.full_like(QS,DEN)),('measured_speed_scale',QS)]:
  pred=np.empty_like(F)
  for i in range(4):
   take=np.arange(4)!=i;x=aa[take].ravel();xp=np.column_stack([np.ones(len(x)),x,x*x]);xn=xp[:,:2]
   bp=np.linalg.lstsq(xp,(P[take]/scale[take]).ravel(),rcond=None)[0]
   bn=np.linalg.lstsq(xn,(N[take]/scale[take]).ravel(),rcond=None)[0]
   a=aa[i];cp=bp[0]+bp[1]*a+bp[2]*a*a;cn=bn[0]+bn[1]*a
   pred[i]=scale[i]*(cp*np.cos(B[i])-cn*np.sin(B[i]))
  predictions[label]=pred;scores[label]=metrics(F,pred)
 # Predefined spatial-transport sensitivity. Neither lag is fitted to forces.
 # Wave speed and material advection are distinct approximations.
 period_measured=np.mean([b-a for a,b in phase['windows_s']]);distance=.9+evidence['chord']['leading_edge_m'][0]
 delay_scores={};delay_predictions={}
 for label,lag in [('wave_phase_estimate',distance*period_measured/15),('current_advection_estimate',distance/18)]:
  shifted=t[:,:-1]-lag
  assert shifted.min()>=ft.min()
  dx=np.interp(shifted,ft,[float(v['ux_m_s'])for v in fields]);dz=np.interp(shifted,ft,[float(v['uz_m_s'])for v in fields])
  bb=np.arctan2(dz,dx);al=np.degrees(bb)-evidence['chord']['chord_angle_deg'];scale=DEN*(dx*dx+dz*dz)/324
  par=F*np.cos(bb)+fz[:,:-1]*np.sin(bb);norm=-F*np.sin(bb)+fz[:,:-1]*np.cos(bb);pred=np.empty_like(F)
  for i in range(4):
   take=np.arange(4)!=i;x=al[take].ravel();xp=np.column_stack([np.ones(len(x)),x,x*x])
   bp=np.linalg.lstsq(xp,(par[take]/scale[take]).ravel(),rcond=None)[0]
   bn=np.linalg.lstsq(xp[:,:2],(norm[take]/scale[take]).ravel(),rcond=None)[0]
   a=al[i];pred[i]=scale[i]*((bp[0]+bp[1]*a+bp[2]*a*a)*np.cos(bb[i])-(bn[0]+bn[1]*a)*np.sin(bb[i]))
  delay_scores[label]=dict(delay_s=float(lag),phase_shift_deg=float(lag/period_measured*360),lag_fitted_to_force=False,**metrics(F,pred))
  delay_predictions[label]=pred
 model_records=[]
 for i,cycle in enumerate(cycles):
  for j,p in enumerate(phi[:-1]):
   model_records.append(dict(cycle=int(cycle),phase_deg=p,Fx_CFD_N=F[i,j],
       **{name+'_N':pred[i,j]for name,pred in {**predictions,**delay_predictions}.items()}))
 save_csv('W04e_cycle_held_out_predictions.csv',model_records)
 mean=lambda v:v.mean(axis=0)
 am=mean(alpha);vm=mean(V);cpm=mean(Cpar);cnm=mean(Cnorm);fxm=mean(fx);qm=mean(qS)
 branch=np.sign(np.gradient(am,phi));angle=phi[:-1]
 dist=np.minimum(abs(angle[:,None]-angle[None,:]),360-abs(angle[:,None]-angle[None,:]))
 mask=(branch[:-1,None]*branch[None,:-1]<0)&(dist>=30)&(abs(am[:-1,None]-am[None,:-1])<=.05)&(abs(vm[:-1,None]-vm[None,:-1])<=.05)
 support=dict(alpha_tolerance_deg=.05,speed_tolerance_m_s=.05,min_phase_separation_deg=30,
              opposite_branch_phase_points_with_match=int(mask.any(axis=1).sum()),phase_points_tested=120)
 same=[]
 for target in(1.5,2.):
  for j in range(len(phi)-1):
   if (am[j]-target)*(am[j+1]-target)<0:
    f=(target-am[j])/(am[j+1]-am[j]);interp=lambda v:float(v[j]+f*(v[j+1]-v[j]))
    same.append(dict(alpha_probe_deg=target,phase_deg=interp(phi),V_m_s=interp(vm),qS_N=interp(qm),Fx_N=interp(fxm),
      delta_Fx_N=interp(fxm)-phase['C01']['D_N'],C_parallel=interp(cpm),C_normal=interp(cnm)))
 save_csv('W04e_same_angle_branches.csv',same)
 summary=dict(at=now(),accepted_case_count=len(windows),source_report=str(report),source_audit_sha256=sha(report/'audit.json'),
   W04e=dict(source_velocity_csv_sha256=sha(AOA/'W04e_upstream_velocity_aoa.csv'),coordinate_convention='beta=atan2(Uz,Ux), alpha_probe=beta minus mesh chord angle; upward normal=(-sin(beta),cos(beta))',
    local_coefficients='Projection of total buoyancy-corrected forces onto one probe frame; not validated steady profile lift/drag coefficients',
    empirical_leave_one_cycle_out=scores,predefined_spatial_delay_sensitivity=delay_scores,matching_support=support,same_angle_branches=same,
    mean_delta_Fx_N=float(F.mean()-phase['C01']['D_N']),
    mean_forward_projection_N=float(np.mean(-N*np.sin(B))),mean_parallel_projection_change_N=float(np.mean(P*np.cos(B))-phase['C01']['D_N']),
    reduced_frequency_k=float(math.pi*evidence['chord']['chord_m']/np.mean([b-a for a,b in phase['windows_s']])/18),
    limitations=['Probe x=-0.9 m includes foil-induced flow.','Models calibrated on the same CFD case; cycle-held-out success does not establish a quasi-steady mechanism.',
                 'Matching alpha and speed requires common support; q-normalization is not equivalent to matching Reynolds number and flow state.',
                 'Upstream spatial delay can mimic temporal memory. Wave-phase speed and current advection are different; two uncalibrated delay estimates are only a sensitivity test.',
                 'Force rotation is an algebraic identity. New flexible-foil performance cannot be inferred from this rigid dataset.']),
   GPU_solver_started=False)
 write(OUT/'mechanism_diagnostics.json',summary)
 plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
 fig,axes=plt.subplots(2,2,figsize=(11,8),layout='constrained')
 axes[0,0].plot(phi,fxm-phase['C01']['D_N'],label='Saved CFD',color='black',lw=2)
 for label,pred in {'no transport correction':predictions['measured_speed_scale'],'wave-phase delay estimate':delay_predictions['wave_phase_estimate'],'current-advection delay estimate':delay_predictions['current_advection_estimate']}.items():
  axes[0,0].plot(phi[:-1],pred.mean(0)-phase['C01']['D_N'],label=label)
 axes[0,0].set(xlabel='Wave phase at x = 0 [deg]',ylabel='Delta Fx from C01 [N]',title='CFD-calibrated fits with one cycle held out');axes[0,0].legend(fontsize=7.5)
 sc=axes[0,1].scatter(am[:-1],vm[:-1],c=angle,cmap='viridis',s=15);fig.colorbar(sc,ax=axes[0,1],label='Wave phase [deg]')
 axes[0,1].set(xlabel='Local alpha probe [deg]',ylabel='Local speed [m/s]',title='Same angle need not mean same inflow')
 axes[1,0].plot(am,cnm,color='#007789');axes[1,0].set(xlabel='Local alpha probe [deg]',ylabel='C normal',title='Buoyancy-corrected force in local probe frame')
 axes[1,1].plot(am,cpm,color='#a25919');axes[1,1].set(xlabel='Local alpha probe [deg]',ylabel='C parallel',title='Projected parallel force is not a steady polar')
 for ax in axes.flat:ax.grid(alpha=.2)
 fig.savefig(OUT/'W04e_matched_inflow_diagnostic.png',dpi=190);fig.savefig(OUT/'W04e_matched_inflow_diagnostic.svg');plt.close(fig)
 names=list(dict.fromkeys(s['case']for s in sectors));outer=[];middle=[];total=[]
 for name in names:
  ss=[s for s in sectors if s['case']==name];a=sum(s['phase_mean_contribution_N']for s in ss if s['start_deg']!=100);b=next(s['phase_mean_contribution_N']for s in ss if s['start_deg']==100)
  assert abs(a+b-ss[0]['phase_mean_delta_Fx_N'])<1e-10
  outer.append(a);middle.append(b);total.append(a+b)
 fig,ax=plt.subplots(figsize=(9,5.5),layout='constrained');yy=np.arange(len(names))
 ax.barh(yy,outer,color='#007789',label='0-100 and 270-360 deg');ax.barh(yy,middle,color='#d49548',label='100-270 deg')
 ax.scatter(total,yy,color='black',s=22,label='Net phase mean',zorder=3);ax.axvline(0,color='gray',lw=.7)
 all_positive=all(v>0 for v in middle)
 ax.set(yticks=yy,yticklabels=names,xlabel='Contribution to mean Delta Fx from C01 [N]',
        title=f'The broad middle sector adds force in all {len(names)} accepted cases' if all_positive else
              f'Phase-sector contributions across {len(names)} accepted cases')
 ax.invert_yaxis();ax.legend(loc='lower left',fontsize=8);ax.grid(axis='x',alpha=.2)
 fig.savefig(OUT/'accepted_phase_sector_contributions.png',dpi=190);fig.savefig(OUT/'accepted_phase_sector_contributions.svg');plt.close(fig)
 print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':build()
