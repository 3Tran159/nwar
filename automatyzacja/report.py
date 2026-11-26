"""Standalone scientific HTML/PNG/SVG/CSV/MAT report, generated from preserved solver files."""
from common import *
from analysis import *
import html,zipfile,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import savemat
from project_results import COEFFICIENT_DENOMINATOR,policy,q_result,c01_force_reference
from response_plots import save_response,q_figures,lift_figures
from comparison_plots import save_comparison
from phase_alignment import align_to_position,REFERENCE_X
from history_view import history_view,run_chain
from report_selection import report_entries,display_id,final_report_root
from calm_reference import reference_for,local_reference_enabled,REFERENCE_ID
COLORS=['#087f8c','#e49527','#5b64a5','#cf6262']
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'axes.grid':True,'grid.alpha':.18,'figure.facecolor':'white','axes.facecolor':'white','savefig.dpi':180})
def e(v):return html.escape(str(v))
def f(v,n=6):return '—' if v is None else format(v,'.'+str(n)+'f')
def external_runs():
 result=[]
 for p in NIGHT.glob('W0*_resume*'):
  pre=read(p/'resume_preflight.json');setup=read(p/'continuation_setup.json')
  if not pre:continue
  case=pre.get('case') or setup.get('case')
  if case not in EXISTING:continue
  done=read(p/'completed.json');stage=read(p/'stage_result.json');proc=read(p/'process.json')
  status='failed' if read(p/'macro_error.json') or stage.get('exit_code',0)!=0 else 'completed' if done and stage.get('exit_code')==0 else 'running' if birth(proc.get('controller_pid')) else 'interrupted'
  result.append(dict(id=p.name,case_id=case,folder=str(p),status=status,external=True,spec=dict(parent_folder=str(EXISTING[case]),source_sha=pre.get('source_sha256'))))
 return result
def verified_hash(p,cache):
 p=Path(p)
 if not p.exists():return None
 stat=p.stat();key=str(p);signature=[stat.st_size,stat.st_mtime_ns]
 if cache.get(key,{}).get('signature')==signature:return cache[key]['sha256']
 value=sha(p);cache[key]=dict(signature=signature,sha256=value);return value
def figures(out,key,data,g,result,reference_cycles,alignment):
 paths=[];cy=result['cycles'];t=data['time_s'];thin=max(1,len(t)//12000)
 force_reference=result.get('force_reference') or c01_force_reference()
 title=key+('\n'+result['condition_label'] if result.get('condition_label') else '')
 def save(fig,suffix):
  name=key+'_'+suffix
  fig.savefig(out/(name+'.png'),bbox_inches='tight');fig.savefig(out/(name+'.svg'),bbox_inches='tight')
  plt.close(fig);paths.append(name+'.png')
 fig,ax=plt.subplots(2,1,figsize=(10.5,6.2),sharex=True)
 for a,k,label in zip(ax,('CD_minus_C01','CL_minus_C01'),('ΔFx [N]','ΔFz [N]')):
  a.plot(t[::thin],data[k][::thin]*COEFFICIENT_DENOMINATOR,color=COLORS[0],lw=1)
  a.axhline(0,color='#526674',lw=.9,ls='--',label='C01')
  if cy.get('window'):a.axvspan(*cy['window'],color=COLORS[1],alpha=.16,label='Cycles 2–5; cycle 1 excluded')
  for marker in result.get('resume_markers',[]):
   a.axvline(marker['time_s'],color='#536670',lw=1.2,ls='--',label='Resume: '+f(marker['time_s'],4)+' s')
  if a.get_legend_handles_labels()[0]:a.legend(loc='upper right',fontsize=8)
  a.set_ylabel(label)
 ax[-1].set_xlabel('Physical time [s]');fig.suptitle(title+' | force history');fig.tight_layout();save(fig,'forces')
 fig,ax=plt.subplots(2,1,figsize=(10.5,6.2),sharex=True)
 for a,k,name in zip(ax,('CD_total','CL_hydrodynamic'),('CD','CL')):
  a.plot(t[::thin],data[k][::thin],color=COLORS[0],lw=1,label=key)
  a.axhline(force_reference[name],color='#526674',lw=.9,ls='--',label=force_reference['name'])
  for marker in result.get('resume_markers',[]):a.axvline(marker['time_s'],color='#536670',lw=1,ls=':',label='Resume '+f(marker['time_s'],4)+' s')
  a.set_ylabel('Cz' if name=='CL' else 'Cx');a.legend(loc='best',fontsize=8)
 ax[-1].set_xlabel('Physical time [s]');fig.suptitle(title+' | normalized domain force history')
 fig.text(.5,.015,'Cz is the normalized vertical force after buoyancy correction. C01 uses the same convention.',ha='center',fontsize=9)
 fig.tight_layout(rect=(0,.04,1,.96));save(fig,'coefficients');paths.insert(0,paths.pop())
 fig,ax=plt.subplots(3,1,figsize=(10.5,8),sharex=True)
 for c,col in zip(reference_cycles['analyzed_cycles'],COLORS):
  for a,k in zip(ax,('CD','CL','eta')):a.plot(c['phase'],np.asarray(c[k])-(force_reference[k] if k in ('CD','CL') else 0.),label='Cycle '+str(c['number']),color=col,lw=1.5)
 for a in ax[:2]:a.axhline(0,color='#526674',lw=.9,ls='--')
 for a,label in zip(ax,('Cx − Cx_C01','Cz − Cz_C01','eta at x = 0 [m]')):a.set_ylabel(label)
 if reference_cycles['analyzed_cycles']:ax[0].legend(ncol=4)
 else:ax[0].text(.5,.5,'Waiting for cycle 2; cycle 1 is excluded',transform=ax[0].transAxes,ha='center')
 ax[-1].set_xlabel('Wave phase / 2 pi | x = 0 m | upward crossing = 0')
 fig.suptitle(title+' | cycle comparison at x = 0');fig.tight_layout();save(fig,'cycles')
 fig,ax=plt.subplots(2,2,figsize=(10.5,6.5))
 for a,k,label in zip(ax.flat,('max_CFL','interface_CFL','max_speed_m_s','water_volume_m3'),('Bulk CFL','Interface CFL','Maximum speed [m/s]','Water inventory [m3]')):
  if k in data:a.plot(t[::thin],data[k][::thin]*COEFFICIENT_DENOMINATOR,color=COLORS[0],lw=1)
  a.set(xlabel='Physical time [s]',ylabel=label)
 fig.suptitle(title+' | numerical health (inventory is not mass-flux closure)');fig.tight_layout();save(fig,'health')
 fig,ax=plt.subplots(figsize=(10.5,3.5))
 if len(g):ax.plot(g[:,0],g[:,1],color=COLORS[0],lw=1)
 if reference_cycles.get('analysis_not_before_s'):ax.axvline(reference_cycles['analysis_not_before_s'],color=COLORS[1],ls='--',label='Estimated startup exclusion')
 ax.set(xlabel='Physical time [s]',ylabel='eta at x = 0 [m]',title=title+' | free surface at x = 0')
 if ax.get_legend_handles_labels()[0]:ax.legend()
 fig.tight_layout();save(fig,'gauge')
 return paths
def build_report():
 final_root=final_report_root()
 reports=final_root or HERE/'reports'
 if final_root and not final_root.parent.is_dir():raise ValueError('Final report archive is unavailable: '+str(final_root.parent))
 reports.mkdir(exist_ok=True)
 reports=reports.resolve()
 lock=HERE/'report.lock'
 try:
  with lock.open('x') as fd:json.dump(dict(pid=os.getpid(),birth=birth(os.getpid())),fd)
 except FileExistsError:
  old=read(lock)
  if old.get('birth')==birth(old.get('pid')):return read(HERE/'latest_report.json')
  lock.rename(HERE/('report.stale.'+uuid.uuid4().hex+'.json'))
  return build_report()
 out=None
 published=False
 try:
  name=datetime.now().strftime('%Y%m%d_%H%M%S_%f')
  target=reports/('final_'+name if final_root else name);target.mkdir()
  out=target
  cache=read(HERE/'hash_cache.json')
  active_entry=dict(spec=dict(reference_id=REFERENCE_ID)) if local_reference_enabled() else None
  accepted=reference_for(active_entry,verify=True)
  force_reference=c01_force_reference(active_entry)
  calm_source=Path(accepted['checkpoint']) if active_entry else SOURCE
  calm_hash=verified_hash(calm_source,cache)
  if active_entry:
   hist_hash={p:verified_hash(Path(p),cache) for p in accepted['history_sha256']}
   calm_ok=calm_hash==accepted['checkpoint_sha256'] and hist_hash==accepted['history_sha256'] and accepted.get('project_primary_settled') is True
  else:
   hist_hash=verified_hash(CALM/'history.csv',cache)
   calm_ok=calm_hash==SOURCE_SHA and hist_hash==accepted.get('history_sha256') and accepted.get('project_primary_settled') is True
  catalog_by={c['id']:c for c in catalog()}
  meshfile=ROOT/'results_catalog/mesh_comparison.json';meshes=[]
  for c in read(meshfile).get('runs',[]):
   if c.get('group')=='current':meshes.append({k:c.get(k) for k in ('mesh','cells','dt_s','accepted','settled','delta_CL_pct','delta_CD_pct','path','limitations')})
  historical_meshes=[{k:c.get(k) for k in ('mesh','group','cells','dt_s','accepted','status','path','limitations')} for c in read(meshfile).get('runs',[]) if c.get('group')!='current']
  fig,axes=plt.subplots(1,2,figsize=(10.5,4.2))
  for ax,key in zip(axes,('CL','CD')):
   for i,m in enumerate(meshes):
    value=(m.get('settled') or {}).get(key)
    if value is not None:
     ax.scatter(m['cells']/1000,value-force_reference[key],s=55,color=COLORS[i%len(COLORS)])
     ax.annotate(m['mesh']+' / dt='+f(m['dt_s']*1000,1)+' ms',(m['cells']/1000,value-force_reference[key]),xytext=(7,6 if i%2 else -14),textcoords='offset points',fontsize=8)
   ax.axhline(0,color='#526674',lw=.9,ls='--');ax.set(xlabel='Cells [thousands]',ylabel='ΔCz' if key=='CL' else 'ΔCx',xlim=(200,1450))
  fig.suptitle('Calm mesh comparison | mixed time steps, not a formal GCI');fig.tight_layout()
  fig.savefig(out/'mesh_comparison.png',bbox_inches='tight');fig.savefig(out/'mesh_comparison.svg',bbox_inches='tight');plt.close(fig)
  calm_data=numeric_rows(DATA/'PRE_W04_20261102/history.csv' if active_entry else CALM/'history.csv')
  fig,axes=plt.subplots(2,1,figsize=(10.5,5.5),sharex=True)
  for ax,key,label,refkey in zip(axes,('CD_total','CL_hydrodynamic'),('Cx − Cx_C01','Cz − Cz_C01'),('CD','CL')):
   if key in calm_data:ax.plot(calm_data['time_s'],calm_data[key]-force_reference[refkey],color=COLORS[0],lw=1)
   ax.axhline(0,color='#526674',lw=.9,ls='--')
   reference_time=accepted['physical_time_s'];ax.axvspan(reference_time-.2,reference_time,color=COLORS[1],alpha=.2);ax.set_ylabel(label)
  axes[-1].set_xlabel('Physical time [s]');fig.suptitle('C01 | saved calm reference, final averaging window');fig.tight_layout()
  fig.savefig(out/'C01_forces.png',bbox_inches='tight');fig.savefig(out/'C01_forces.svg',bbox_inches='tight');plt.close(fig)
  missing=[
   'This stage assesses trends and qualitative foil response. Acceptance requires the recorded C01 reference, a verified source, preserved physical settings, five complete cycles with repeatable cycles 2–5 and a healthy saved result.',
   'The M10–M13 review was completed before C01. Expanded domains preserve the M13 cell-size controls and foil layers. PRE W04 must pass two consecutive 0.5% stability checks. The accepted reference policy is recorded with every run.',
   'Q = mean wave Cx over cycles 2–5 (cycle 1 excluded) minus accepted C01 Cx. Negative Q indicates lower horizontal force. ΔFx is also reported in newtons.',
   'Force–wave plots use one common foil reference at x = 0 m for existing and future runs. Older signals are extrapolated from the recorded upstream probe using measured wave propagation, with reconstruction details saved in the evidence. A direct measurement at x = 0 is preferred when available. Force timing is unchanged; lag calibration uses wave probes only.',
   'Forcing and reflection quantification, time-step sensitivity, formal uncertainty and mass-flux closure are future studies; they do not block current acceptance or Q.'
  ]
  allresults=[];mat={};blocks=[];summary=[]
  entries=[dict(id=k,case_id=k,folder=str(p),status='completed',legacy=True) for k,p in EXISTING.items()]
  entries+=external_runs()
  entries+=[j for j in jobs()[::-1] if Path(j['folder']).joinpath('history.csv').exists()]
  from glhf_import import imported_entries
  entries += [j for j in imported_entries() if j['status']=='completed' or j.get('reviewed_partial')]
  for entry in report_entries(entries,final_only=bool(final_root)):
   case=catalog_by[entry['case_id']];key=case.get('display_id') or display_id(entry);folder=Path(entry['folder'])
   if case.get('diagnostic_only'):
    case=dict(case,**{k:entry['spec'][k] for k in ('components','condition_label') if k in entry.get('spec',{})})
   chain=run_chain(entry)
   if not (folder/'history.csv').exists():continue
   try:
    entry_reference=reference_for(entry,verify=True);force_reference=c01_force_reference(entry)
    result,data,g=analyze(case,chain);result.update(id=entry['id'],display_id=key,status=entry['status'],folder=str(folder),smoke=entry.get('spec',{}).get('smoke',0))
    result['force_reference']=force_reference;result['reference_id']=entry_reference['reference_id']
    result['condition_label']=case.get('condition_label')
    data.update(CD_minus_C01=data['CD_total']-force_reference['CD'],CL_minus_C01=data['CL_hydrodynamic']-force_reference['CL'])
    result['resume_markers']=history_view(chain)['resume_markers']
    expected=None
    if entry.get('imported'):
     verification=entry['validation']
     final=Path(verification['checkpoint'])
     if verified_hash(final,cache)!=verification['checkpoint_sha256'] or abs(verification['time_s']-result['time_s'])>1e-7:
      raise ValueError('Imported GLHF checkpoint changed after review.')
     result.update(saved_hash_verified=True,saved_hash_verification_basis=verification['scope'])
    elif entry.get('legacy'):
     receipt=read(NIGHT/'W01_four_cycle_review.json') if key=='W01' else read(folder/'four_cycle_independent_review.json')
     expected=receipt.get('final_sim_SHA256');final=folder/'wave_pilot_final.sim'
     result['legacy_four_cycle_repeatability']=receipt.get('four_cycles_repeated')
     result['historical_planning_period_means']={k:receipt.get('metrics',{}).get(k,{}).get('mean') for k in ('CL','CD')}
     result['historical_steps']=receipt.get('total_steps')
     result['saved_hash_verified']=verified_hash(final,cache)==expected and bool(expected)
     result['raw_hash_matches_receipt']=sha(folder/'history.csv')==receipt.get('raw_history_SHA256')
    else:
     final=folder/('wave_pilot_extended_final.sim' if entry.get('external') else 'wave_pilot_final.sim')
     expected=read(folder/'final_integrity.json').get('sha256')
     result['saved_hash_verified']=bool(expected and verified_hash(final,cache)==expected)
    if not entry.get('imported'):
     from validation import validate
     verification=validate(entry,result,data)
    if entry.get('status')=='completed' and not entry.get('legacy') and not entry.get('external'):
     previous=read(folder/'independent_cycle_review.json')
     if previous and previous.get('cycles',{}).get('cycle_policy_id')!=result['cycles']['cycle_policy_id']:
      archive=folder/'independent_cycle_review_before_first_cycle_exclusion.json'
      if not archive.exists():write(archive,previous)
     write(folder/'independent_cycle_review.json',result)
    result['validation']=verification
    result['project_accepted']=verification.get('project_accepted',False)
    result['Q']=q_result(result,verification,entry_reference) if calm_ok else None
    result['Q_delta_CD']=result['Q']['Q_CD'] if result['Q'] else None
    if entry.get('external') and not entry.get('imported'):
     checkpoint_check=next((c for c in verification.get('checks',[]) if c['id']=='checkpoint'),{})
     result['saved_hash_verified']=checkpoint_check.get('status')=='passed'
     result['saved_hash_verification_basis']='Post-save SHA-256 fingerprint recorded by the independent checklist; original source unchanged.'
    write(out/(key+'_validation.json'),verification)
    cy=result['cycles']
    reference_gauge,alignment=align_to_position(chain,cy['phase_probe_x_m'],result,require_full_history=True)
    if len(reference_gauge):reference_gauge=reference_gauge[(reference_gauge[:,0]>=data['time_s'][0])&(reference_gauge[:,0]<=data['time_s'][-1])]
    reference_cycles=cycles(data,reference_gauge,result['H'],result['L'],origin=result.get('wave_origin_s',T0),probe_distance=result.get('probe_distance_m',34.5)+REFERENCE_X+.5)
    imgs=figures(out,key,data,reference_gauge,result,reference_cycles,alignment)
    with (out/(key+'_wave_x0.csv')).open('w',newline='',encoding='utf8') as wf:
     writer=csv.writer(wf);writer.writerow(['time_s','eta_at_x0_m']);writer.writerows(reference_gauge)
    response,response_images=save_response(out,key,data,chain,result)
    result['force_wave_response']=response;result['force_wave_plot']=response_images[0] if response_images else None
    if response:write(out/(key+'_force_wave.json'),response)
    imgs=imgs[:1]+response_images+imgs[1:]
    allresults.append(result)
    historical=result.get('historical_planning_period_means',{})
    sumrow=dict(run=entry['id'],case=key,case_id=case['id'],H_m=case['H'],lambda_m=case['L'],time_s=result['time_s'],samples=result['samples'],complete_probe_cycles=cy['count'],CL_mean_4cycles=cy.get('CL_mean'),CD_mean_4cycles=cy.get('CD_mean'),repeatable=cy['repeatable'],health_ok=result['health']['ok'],historical_CL_planning_windows=historical.get('CL'),historical_CD_planning_windows=historical.get('CD'),phase_probe_x_m=cy['phase_probe_x_m'],project_accepted=result['project_accepted'],acceptance_scope='qualitative_M13',Q_delta_CD=result['Q_delta_CD'],delta_D_N=result['Q']['delta_D_N'] if result['Q'] else None)
    sumrow['wave_conditions']=case.get('condition_label')
    if case.get('diagnostic_only'):sumrow.update(H_m=None,lambda_m=None,acceptance_scope='bichromatic_diagnostic')
    summary.append(sumrow)
    safe='r_'+key.replace('-','_')
    mat[safe]=dict(**data,gauge_t=g[:,0],gauge_eta=g[:,1],H_m=case['H'],lambda_m=case['L'],source_paths=' | '.join(map(str,chain)),resume_times_s=[m['time_s'] for m in result['resume_markers']])
    if case.get('diagnostic_only'):
     del mat[safe]['H_m'],mat[safe]['lambda_m']
     mat[safe]['wave_conditions']=case['condition_label']
    mat[safe].update(reference_wave_t=reference_gauge[:,0],reference_wave_eta=reference_gauge[:,1],reference_wave_x_m=REFERENCE_X,CL_C01=force_reference['CL'],CD_C01=force_reference['CD'],L_C01_N=force_reference['L_N'],D_C01_N=force_reference['D_N'])
    if response:
     mat[safe].update(response_phase_deg=response['phase_deg'],response_eta_prime_m=response['eta_prime_mean_m'],response_dL_C01_N=response['lift_minus_C01_mean_N'],response_dD_C01_N=response['drag_minus_C01_mean_N'],response_probe_x_m=response['probe_x_m'],response_source_probe_x_m=response['alignment']['source_probe_x_m'],response_wave_time_shift_s=response['alignment']['time_shift_s'],response_wave_estimated=response['alignment']['estimated'])
    if result['Q']:mat[safe].update(Q_CD=result['Q']['Q_CD'],delta_D_N=result['Q']['delta_D_N'],CD_C01=result['Q']['CD_C01'],D_C01_N=result['Q']['D_C01_N'],D_wave_N=result['Q']['D_wave_N'])
    csvpath=out/(key+'_history.csv')
    fields=list(data)
    with csvpath.open('w',newline='',encoding='utf8') as cf:
     w=csv.writer(cf);w.writerow(fields);w.writerows(zip(*(data[k] for k in fields)))
    with (out/(key+'_cycles.csv')).open('w',newline='',encoding='utf8') as cf:
     w=csv.DictWriter(cf,fieldnames=['number','start','end','T','CL_mean','CD_mean','CL_amp','CD_amp','eta_mean','H_measured'],extrasaction='ignore');w.writeheader();w.writerows(cy['cycles'])
    label='ACCEPTED · QUALITATIVE STAGE' if result['project_accepted'] else 'PARTIAL RUN / REVIEW REQUIRED'
    qtext=('Q = '+f(result['Q']['Q_CD'],7)+' · ΔFx = '+f(result['Q']['delta_D_N'],3)+' N relative to C01.') if result['Q'] else 'Bichromatic diagnostic; no single-period Q.' if case.get('diagnostic_only') else 'Q is added after five complete cycles with repeatable cycles 2–5 and checkpoint verification.'
    response_note=(' Force–wave reference: x='+f(response['probe_x_m'],3)+' m; '+response['probe_position']+'.') if response else ' Force–wave plot awaits complete reference cycles.'
    blocks.append('<section><p class="eyebrow">'+label+'</p><h2>'+e(key)+' · '+e(case.get('condition_label') or ('H = '+f(case['H'],2)+' m · λ = '+f(case['L'],1)+' m'))+'</h2><p>State: '+e(entry['status'])+' · time '+f(result['time_s'],4)+' s · complete measured cycles: '+str(cy['count'])+' · cycles 2-5 repeatable: '+('YES' if cy['repeatable'] else 'NO / INSUFFICIENT DATA')+'.</p><p>Acceptance cycle probe: x='+f(cy['phase_probe_x_m'],1)+' m.'+e(response_note)+'</p><p>Means over exact cycle boundaries: Cz='+f(cy.get('CL_mean'))+', Cx='+f(cy.get('CD_mean'))+'. '+e(qtext)+'</p>'+''.join('<a href="'+im.replace('.png','.svg')+'"><img src="'+im+'" alt="'+e(im)+'"></a>' for im in imgs)+'<details><summary>Data provenance</summary><pre>'+e(json.dumps(result['source_segments'],indent=2))+'</pre></details></section>')
   except Exception as exc:
    allresults.append(dict(id=key,error=str(exc),folder=str(folder)))
    blocks.append('<section><h2>'+e(key)+'</h2><p>Analysis stopped: '+e(exc)+'</p></section>')
  # The solver controller may have imported an older display module before this
  # report revision. Refresh only the reporting module, never the solver.
  force_reference=c01_force_reference(active_entry)
  import importlib,pre_w04
  pre_w04=importlib.reload(pre_w04);pre_w04.export()
  from pre_w04 import PRE,stop_reason
  pre_receipt=read(PRE/'calm_receipt.json')
  if active_entry:pre_receipt=accepted
  pre_files=[]
  if pre_receipt:
   for name in ('PRE_W04_history.png','PRE_W04_settling.png','PRE_W04_convergence.png','PRE_W04_history.svg','PRE_W04_settling.svg','convergence.csv','history.csv','calm_receipt.json'):
    source=PRE/name
    if active_entry and name=='calm_receipt.json':source=PRE/'reference_acceptance.json'
    if source.is_file():
     target=name if name.startswith('PRE_W04') else 'PRE_W04_'+name
     shutil.copy2(source,out/target);pre_files.append(target)
   pre_data=numeric_rows(PRE/'history.csv')
   if pre_data:mat['r_PRE_W04']=dict(**pre_data,CD_C01=force_reference['CD'],CL_C01=force_reference['CL'],CD_minus_C01=pre_data['CD_total']-force_reference['CD'],CL_minus_C01=pre_data['CL_hydrodynamic']-force_reference['CL'])
  from w08bi_snapshot import render_snapshot
  w08bi=render_snapshot(out,force_reference)
  q_rows=q_figures(out,allresults,w08bi)
  lift_rows=lift_figures(out,allresults,w08bi)
  comparison=save_comparison(out,allresults)
  with (out/'summary.csv').open('w',newline='',encoding='utf8') as cf:
   if summary:
    w=csv.DictWriter(cf,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
  savemat(out/'report_data.mat',mat,do_compression=True)
  (out/'plot_in_matlab.m').write_text("""% Run from the extracted report directory. No solver or source modification.
D = load('report_data.mat');
names = fieldnames(D);
for i = 1:numel(names)
 r = D.(names{i});
 figure('Name',[names{i} ' normalized domain forces']); tiledlayout(2,1);
 nexttile; plot(r.time_s,r.CD_total); yline(r.CD_C01,'--','C01'); grid on; ylabel('C_x');
 if isfield(r,'resume_times_s'), for t = r.resume_times_s(:)', xline(t,'--',sprintf('Resume %.4f s',t)); end; end
 nexttile; plot(r.time_s,r.CL_hydrodynamic); yline(r.CL_C01,'--','C01'); grid on; ylabel('C_z (buoyancy removed)'); xlabel('t [s]');
 if isfield(r,'resume_times_s'), for t = r.resume_times_s(:)', xline(t,'--',sprintf('Resume %.4f s',t)); end; end
 figure('Name',names{i});
 tiledlayout(2,1);
 nexttile; plot(r.time_s,r.CD_minus_C01); yline(0,'--','C01'); grid on; ylabel('C_x - C_{x,C01}'); title(names{i},'Interpreter','none');
 if isfield(r,'resume_times_s'), for t = r.resume_times_s(:)', xline(t,'--',sprintf('Resume %.4f s',t)); end; end
 nexttile; plot(r.time_s,r.CL_minus_C01); yline(0,'--','C01'); grid on; ylabel('C_z - C_{z,C01}'); xlabel('t [s]');
 if isfield(r,'resume_times_s'), for t = r.resume_times_s(:)', xline(t,'--',sprintf('Resume %.4f s',t)); end; end
 if isfield(r,'response_phase_deg')
  figure('Name',[names{i} ' force-wave']); tiledlayout(2,1);
  nexttile; yyaxis left; plot(r.response_phase_deg,r.response_dL_C01_N); yline(0,'--','C01'); ylabel('L - L_{C01} [N]');
  yyaxis right; plot(r.response_phase_deg,r.response_eta_prime_m,'--'); ylabel('eta fluctuation [m]'); grid on;
  nexttile; yyaxis left; plot(r.response_phase_deg,r.response_dD_C01_N); yline(0,'--','C01'); ylabel('D - D_{C01} [N]');
  yyaxis right; plot(r.response_phase_deg,r.response_eta_prime_m,'--'); ylabel('eta fluctuation [m]'); xlabel(sprintf('Wave phase [deg], reference x=%.1f m',r.response_probe_x_m)); grid on;
 end
end
""",encoding='utf8')
  audit=dict(generated_at=now(),C01=dict(name=accepted['name'],reference_id=accepted['reference_id'],accepted=calm_ok,checkpoint_sha256=calm_hash,history_sha256=hist_hash,CL=accepted.get('normalized_CL_hydro'),CD=accepted.get('normalized_CD_total')),mesh=meshes,historical_meshes=historical_meshes,waves=catalog(),results=allresults,missing=missing,reference_policy=accepted,external=external_runs(),jobs=jobs(),automation_selftest=read(HERE/'selftest.json'),methodology_source='https://www.ittc.info/media/11954/75-03-02-01.pdf')
  write(HERE/'hash_cache.json',cache)
  audit.update(force_frame=dict(axes='fixed domain x and z',normalization_N=COEFFICIENT_DENOMINATOR,
                               legacy_CFD_columns=dict(CD_total='Cx',CL_hydrodynamic='Cz'),
                               vertical_force='Fz_N minus 22.718189111947265 N buoyancy'),
               project_policy=policy(),Q_data=q_rows,lift_trend=lift_rows,w08bi_snapshot=w08bi,force_wave_comparison=comparison,PRE_W04=dict(receipt=pre_receipt,files=pre_files,stop_reason=stop_reason()))
  write(out/'audit.json',audit);write(out/'project_policy.json',policy());write(out/'Q_data.json',q_rows)
  write(out/'automation_selftest.json',audit['automation_selftest'])
  write(out/'cycle_counter_verification.json',read(HERE/'qa/cycle_counter_result.json'))
  from report_page import page as render_report_page
  page=render_report_page(audit,blocks)
  (out/'report.html').write_text(page,encoding='utf8')
  zpath=out/'nwar_report.zip'
  with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
   for p in out.iterdir():
    if p!=zpath and p.is_file():z.write(p,p.name)
  errors=[r for r in allresults if 'error' in r]
  if final_root and errors:raise ValueError('Final report has case errors: '+', '.join(str(r.get('id') or r.get('case') or '?')+': '+str(r['error']) for r in errors))
  relative='reports/final/'+out.name if final_root else out.relative_to(HERE).as_posix()
  latest=dict(generated_at=now(),directory=str(out),relative=relative,report=str(out/'report.html'),zip=str(zpath),cases=len(allresults),force_wave_comparison=dict(case_count=comparison['case_count'],cases=[c['display_id'] for c in comparison['cases']],files=comparison['files']),errors=errors)
  if final_root:write(out/'report_generation.json',dict(kind='NWAR consolidated final report'))
  write(HERE/'latest_report.json',latest)
  published=True
  if final_root:
   for previous in reports.glob('final_*'):
    if (previous!=out and previous.resolve()==previous and previous.is_dir()
        and read(previous/'report_generation.json').get('kind')=='NWAR consolidated final report'):
     try:shutil.rmtree(previous)
     except OSError as ex:event('report_rotation_deferred',directory=str(previous),error=str(ex))
  (DATA/'report_error.json').unlink(missing_ok=True)
  event('report_generated',directory=str(out),cases=len(allresults))
  # Detached housekeeping reads the live queue again and skips active owners.
  # A separate hourly Windows task also covers completions by older workers.
  if read(HERE/'storage_cleanup.json').get('enabled'):
   import subprocess
   with (DATA/'storage_cleanup.service.log').open('a',encoding='utf8') as log:
    subprocess.Popen([str(PYTHON),str(HERE/'storage_cleanup.py'),'--apply'],cwd=HERE,
                     stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW|subprocess.BELOW_NORMAL_PRIORITY_CLASS)
  return latest
 finally:
  if final_root and out is not None and not published and out.resolve().parent==reports:
   shutil.rmtree(out,ignore_errors=True)
  lock.unlink(missing_ok=True)
if __name__=='__main__':
 try:print(json.dumps(build_report(),ensure_ascii=False))
 except Exception as exc:
  write(DATA/'report_error.json',dict(at=now(),error=str(exc)));raise
