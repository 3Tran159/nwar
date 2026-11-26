(()=>{'use strict';
const $=s=>document.querySelector(s),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,n=3)=>v==null||!Number.isFinite(Number(v))?'—':Number(v).toLocaleString('en-GB',{maximumFractionDigits:n,minimumFractionDigits:n});
const duration=s=>s==null?'—':s>=3600?fmt(s/3600,1)+' h':fmt(s/60,0)+' min';
const names={deferred:'After local campaign',queued:'Queued',preflight:'Checking',running:'Running',pausing:'Saving pause',paused:'Pause saved',completed:'Completed',failed:'Error',needs_review:'Review required',needs_attention:'Attention required',interrupted:'Interrupted',cancelled:'Cancelled',preflight_blocked:'Not started'};
let state=null,busy=false,first=true,reportRequested=false,waveSignature='',qRequestedAt=null,qRequestPending=false;
let openValidation=new Set(),openEvidence=new Set(),preArchiveMode=null;
function validationHTML(id,v={}){
 const labels={passed:'Passed',failed:'Failed',pending:'Waiting for data',future:'Future work · nonblocking'};
 const counts=v.required_counts||v.counts||{},summary=v.project_accepted?'ACCEPTED · qualitative stage':v.smoke?'Technical test':v.run_verification?labels[v.run_verification]+' · '+(counts.passed||0)+' checks passed':'waiting for save and verification';
 const item=c=>{const key=id+'_'+c.id;return '<div class="check"><b class="check-'+esc(c.status)+'">'+esc(labels[c.status])+'</b> · '+esc(c.title)+'<p>'+esc(c.criterion)+'</p><details data-evidence="'+esc(key)+'" '+(openEvidence.has(key)?'open':'')+'><summary>Evidence and values</summary><pre>'+esc(JSON.stringify({values:c.values,files:c.evidence_files},null,2))+'</pre></details></div>'};
 const items=(v.checks||[]).filter(c=>c.group!=='future').map(item).join('');
 const future=(v.checks||[]).filter(c=>c.group==='future');
 const futureHTML=future.length?'<details data-evidence="'+esc(id)+'_future" '+(openEvidence.has(id+'_future')?'open':'')+'><summary>Future work · outside acceptance</summary>'+future.map(item).join('')+'</details>':'';
 return '<details class="validation" data-validation="'+esc(id)+'" '+(openValidation.has(id)?'open':'')+'><summary>Run validation · '+esc(summary)+'</summary><p class="note">'+esc(v.generated_at?new Date(v.generated_at).toLocaleString('en-GB'):'Verification starts automatically after completion.')+' · C01 → preserved configuration → 4 repeatable cycles.</p>'+(v.error?'<p class="check-failed">'+esc(v.error)+'</p>':'')+items+futureHTML+(v.verification_kind==='glhf_saved_state'?'<p class="note">Verified from the transferred SIM and histories.</p>':'<button class="secondary revalidate" data-id="'+esc(id)+'">Check again</button>')+(v.generated_at?' <a href="/validations/'+encodeURIComponent(id)+'.json" target="_blank">Download evidence JSON</a>':'')+'</details>';
}
function selected(){return [...document.querySelectorAll('[name=wave]:checked')].map(x=>x.value)}
function launchLabel(){const n=selected().length;$('#launch').disabled=busy||!n;$('#launch').textContent=n?'Run selected ('+n+')':'Select a wave'}
function notice(text,error=false){$('#notice').hidden=!text;$('#notice').textContent=text;$('#notice').classList.toggle('error',error)}
async function post(path,data={}){
 if(busy)return;
 busy=true;launchLabel();
 try{const r=await fetch('/api/'+path,{method:'POST',headers:{'Content-Type':'application/json','X-NWAR-Token':$('meta[name=nwar-token]').content},body:JSON.stringify(data)});const x=await r.json();if(!r.ok)throw new Error(x.error||r.status);return x}
 finally{busy=false;launchLabel()}
}
function renderWaves(cases){
 const saved=new Set(selected());
 $('#wave-grid').innerHTML=cases.map(c=>'<label class="wave"><input type="checkbox" name="wave" value="'+esc(c.id)+'" '+(!c.ready?'disabled':'')+' '+(saved.has(c.id)?'checked':'')+'><span class="wave-id">'+esc(c.display_id||c.id)+'</span><div class="params">'+(c.condition_label?esc(c.condition_label):fmt(c.H,2)+' <small>m H</small> &nbsp; '+fmt(c.L,1)+' <small>m λ</small>')+'</div><div class="desc">'+esc(c.title)+'</div><span class="note">'+(c.condition_label?'Two encounter periods · M13':'Te ≈ '+fmt(c.T,3)+' s · M13')+'</span><div class="state '+(!c.ready?'blocked':'')+'">'+(c.ready?(c.existing?'● Result saved · ready to queue':'○ New wave · diagnostic run'):esc(c.blocker))+'</div></label>').join('');
 document.querySelectorAll('[name=wave]').forEach(x=>x.addEventListener('change',launchLabel));launchLabel();
}
function render(s){
 openValidation=new Set([...document.querySelectorAll('details[data-validation][open]')].map(d=>d.dataset.validation));
 openEvidence=new Set([...document.querySelectorAll('details[data-evidence][open]')].map(d=>d.dataset.evidence));
 state=s;window.updateWaveView?.(s);$('#connection').textContent='● Connected · '+new Date(s.sampled_at).toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
 const signature=JSON.stringify(s.catalog.map(c=>[c.id,c.display_id,c.ready,c.blocker,c.validation?.project_accepted]));
 if(first||signature!==waveSignature){renderWaves(s.catalog);first=false;waveSignature=signature}
 const jobLabel=id=>{const c=s.catalog.find(w=>w.id===id);return (c?.display_id||id)+(c?.condition_label?' · '+c.condition_label:'')};
 const latestAttempt=c=>s.jobs.find(j=>j.case_id===c.id&&!j.spec?.smoke&&!['cancelled','preflight_blocked'].includes(j.status));
 document.querySelectorAll('.wave').forEach((node,i)=>{const c=s.catalog[i],j=latestAttempt(c);if(c.result?.diagnostic_completed)node.querySelector('.state').textContent='GLHF diagnostic complete · t = '+fmt(c.result.time_s,4)+' s';else if(c.validation?.project_accepted)node.querySelector('.state').textContent='✓ Accepted · 4 repeatable cycles';else if(j)node.querySelector('.state').textContent=(names[j.observed_status||j.status]||j.status)+' · '+(j.live?.time_s!=null?'t = '+fmt(j.live.time_s,4)+' s':'waiting for samples')});
 $('#calm-state').textContent=s.audit.C01?.accepted?'Checkpoint verified':'Waiting for checkpoint audit';
 $('#reference-cells').textContent=s.audit.C01?.reference_id==='C01_PRE_W04_20261102'?'572,176 cells':'309,441 cells';
 $('#comparison-reference').textContent=s.audit.C01?.CD!=null?(s.audit.C01.name||'C01')+': Fz_C01 = '+fmt(s.audit.C01.CL*3855.6,2)+' N · Fx_C01 = '+fmt(s.audit.C01.CD*3855.6,2)+' N.':'Waiting for the accepted campaign reference.';
 const activeOwn=s.jobs.find(j=>['running','preflight','pausing'].includes(j.status)&&!j.observed_status);
 const activeExternal=s.external.find(j=>j.status==='running');
 const preparation=s.preparation;
 const active=activeOwn||activeExternal||(preparation?.active?preparation:null);
 const resumeTarget=s.current_resume;
 const shown=active||(s.current_run?.kind==='preparation'?preparation:[...s.jobs,...s.external].find(j=>j.id===s.current_run?.id));const l=shown?.live||{};
 const shownStatus=shown?.observed_status||shown?.status,stopped=['failed','interrupted','needs_review','needs_attention'].includes(shownStatus);
 $('#live-title').textContent=shown?.preparation?'PRE W04 · calm preparation before the wave':active?(jobLabel(active.case_id)+' · '+(active.external?'continuation of an existing run':active.spec?.smoke?'short automation test':active.spec?.mode==='fresh'?'new wave':'continuation from checkpoint')):shown?jobLabel(shown.case_id)+' · latest wave history':'Solver ready for the next run';
 $('#live-state').textContent=active?(activeOwn&&!(l.step>0)?'Loading checkpoint':l.stale?'Stale data':active.preparation&&active.phase!=='calm_running'?'Preparing mesh':names[active.status]):shown?.preparation?(shown.phase==='ready_for_wave'?'Calm gate passed':names[shown.phase]||'Wave not started'):stopped?'Stopped · review required':shown?names[shownStatus]||shownStatus:s.paused?'Queue paused':'No active solver';
 $('#live-state').classList.toggle('amber',!!active&&!!l.stale||s.paused||stopped||!!shown?.error);
 $('#run-context').textContent=active?'CURRENT RUN':'LAST RUN';
 $('#run-diagnostic').hidden=!l.error;
 $('#run-diagnostic').textContent=l.error?'Stopped: '+l.error+' · Saved history is diagnostic; this run has not passed acceptance.':'';
 const forceChange=k=>Number.isFinite(l[k])&&Number.isFinite(s.audit.C01?.[k])?(l[k]-s.audit.C01[k])*3855.6:null;
 const metrics=[['Physical time',fmt(l.time_s,4)+' s'],['ΔFx · vs C01 [N]',fmt(forceChange('CD'),2)],['ΔFz · vs C01 [N]',fmt(forceChange('CL'),2)],['Time per step',fmt(l.s_per_step,2)+' s'],['Interface CFL',fmt(l.interface_CFL,3)],[shown?.spec?.mode!=='fresh'&&['four_cycles','five_cycles'].includes(shown?.spec?.stop_kind)?'To cycle 5 ≈':'Remaining ≈',duration(l.eta_s)]];
 if(shown?.preparation)metrics[5]=['Inlet speed',fmt(l.current_speed_m_s,2)+' m/s'];
 else if(!active)metrics[5]=['Last checkpoint',l.checkpoint?.time_s!=null?fmt(l.checkpoint.time_s,4)+' s':'—'];
 $('#metrics').innerHTML=metrics.map(([k,v])=>'<div class="metric"><small>'+k+'</small><strong>'+v+'</strong></div>').join('');
 const ramp=shown?.preparation?l.speed_ramp:null,progress=ramp?.percent??l.percent;
 $('#run-progress').hidden=!active&&!shown?.preparation;
 $('#progress-fill').style.width=Math.min(100,Math.max(0,progress||0))+'%';
 $('#run-progress').setAttribute('aria-label',ramp?'Speed ramp to '+fmt(ramp.target_speed_m_s,0)+' m/s':'Run progress');
 if(progress==null)$('#run-progress').removeAttribute('aria-valuenow');else $('#run-progress').setAttribute('aria-valuenow',String(progress));
 $('#progress-text').textContent=ramp?'Speed ramp: '+fmt(ramp.percent,1)+'% · '+fmt(ramp.elapsed_s,3)+' / '+fmt(ramp.duration_s,3)+' s':shown?.preparation?shown.label:active?(l.goal_steps?l.progress_label+': '+fmt(l.percent,1)+'%'+(!active.external&&active.spec?.mode==='fresh'?' · acceptance may take longer':''):'Loading checkpoint and preparing'):shown?'Data through '+fmt(l.time_s,4)+' s · '+fmt(l.complete_cycles,0)+' complete cycles · '+(shown.validation?.project_accepted?'Accepted':'Not accepted'):s.jobs.some(j=>j.status==='queued')?'Queue waiting for resources':'Select a wave below';
 const diagnosticCap=shown?.spec?.mode!=='fresh'&&['four_cycles','five_cycles'].includes(shown?.spec?.stop_kind);
 $('#ramp-detail').hidden=!ramp&&!diagnosticCap;
 if(!ramp&&diagnosticCap)$('#ramp-detail').textContent='Records 5 complete measured cycles. Cycle 1 is excluded; cycles 2-5 must pass repeatability before acceptance.';
 if(ramp){
  const estimate=ramp.remaining_wall_s==null?'':ramp.remaining_wall_s<60?fmt(ramp.remaining_wall_s,0)+' s':duration(ramp.remaining_wall_s);
  const detail=ramp.complete?'Ramp complete · convergence to C01 is checked separately.':!ramp.started?'Waiting for the first calculation step.':l.stale?'Last saved ramp progress · waiting for fresh data.':!shown.active?'Saved ramp progress · preparation is not running.':'Physical ramp time · '+(estimate?'≈ '+estimate+' remaining to full speed.':'Estimating time to full speed…');
  const downstream=(l.global_water_speeds||[]).find(p=>p.x_m===40);
  $('#ramp-detail').textContent=(l.startup_scope?'Whole-domain acceleration. ':'')+'Inlet speed: '+fmt(l.current_speed_m_s,2)+' / '+fmt(ramp.target_speed_m_s,0)+' m/s. '+(downstream?'Water at x = 40 m: '+fmt(downstream.water_mean_Ux_m_s,2)+' m/s. ':'')+detail;
  $('#run-progress').setAttribute('aria-valuetext',$('#progress-text').textContent+'. '+$('#ramp-detail').textContent);
 }else $('#run-progress').removeAttribute('aria-valuetext');
 $('#freshness').textContent=active?(l.age_s!=null?'Sample age: '+fmt(l.age_s,0)+' s':'Waiting for first sample'):shown?.live?.history_samples?'Saved history':'';
 window.renderHistoryChart($('#live-chart'),{...l,force_reference:s.audit.C01},{forceScale:3855.6});
 $('#pre-convergence').hidden=!preparation;
 if(preparation){
  const mode=shown?.preparation?'current':'archive';
  if(preArchiveMode!==mode){$('#pre-convergence').open=mode==='current';preArchiveMode=mode}
  $('#pre-summary').textContent=mode==='current'?'PRE W04 · preparation history and checks':'PRE W04 · completed preparation · expand history and checks';
  window.renderHistoryChart($('#pre-settling-chart'),{...preparation.live,force_reference:s.audit.C01},{fromTime:preparation.live.ramp_s||1,showC01Band:true,absolute:true});
  window.renderConvergenceChart($('#pre-convergence-chart'),preparation);
  $('#pre-downloads').innerHTML=(preparation.downloads||[]).map(name=>'<a href="/pre-w04/'+name+'" target="_blank">'+esc(name.replace('PRE_W04_','').replaceAll('_',' '))+'</a>').join(' · ');
  $('#pre-history-archive').hidden=!!shown?.preparation||!preparation.live.history_samples;
  if(!shown?.preparation&&preparation.live.history_samples)window.renderHistoryChart($('#pre-saved-chart'),{...preparation.live,force_reference:s.audit.C01});
 }
 $('#ownership').textContent=activeExternal?'Monitoring an existing run. Controls apply only to this queue.':s.paused?'Resume a saved pause using the button next to that run.':'A pause is confirmed only after the checkpoint is saved.';
 $('#resume-current').hidden=!resumeTarget;
 $('#resume-current').disabled=busy||!resumeTarget?.available;
 if(resumeTarget)$('#ownership').textContent=resumeTarget.available?'Saved: '+jobLabel(resumeTarget.case_id)+' · '+fmt(resumeTarget.time_s,4)+' s. Resume restores the calculation, live charts and automatic report updates.':resumeTarget.reason;
 $('#pause').disabled=busy||(!activeOwn&&!(preparation?.active&&preparation.phase==='calm_running')&&!s.jobs.some(j=>j.status==='queued'));
 $('#continue').hidden=!s.paused||!!resumeTarget;
 const hw=s.hardware,g=hw.gpu||{};
 $('#hardware').innerHTML='<small>'+esc(g.name||'Reading hardware…')+'</small>'+(activeOwn?'<p>Execution <strong>GPU + '+fmt(activeOwn.spec?.mpi_processes||1,0)+' process'+((activeOwn.spec?.mpi_processes||1)===1?'':'es')+'</strong></p>':'')+'<p>GPU <strong>'+fmt(g.percent,0)+'%</strong></p><p>VRAM <strong>'+fmt(g.used_mb/1024,1)+' / '+fmt(g.total_mb/1024,1)+' GB</strong></p><p>Temperature <strong>'+fmt(g.temperature_c,0)+' °C</strong></p><p>RAM <strong>'+fmt(hw.memory?.percent,0)+'%</strong></p><p>Free E: <strong>'+fmt(hw.disk_free_gb,1)+' GB</strong></p>';
 const list=[...s.external.filter(x=>x.status==='running'),...s.jobs];
 $('#queue-count').textContent=s.jobs.filter(j=>['queued','deferred'].includes(j.status)).length+' waiting';
 $('#queue-list').innerHTML=list.length?list.map(j=>'<div class="job"><div><div class="name">'+esc(jobLabel(j.case_id))+' · '+(j.external?'existing continuation':j.spec.smoke?'automation test':j.spec.mode==='fresh'?'new run':'checkpoint → continuation')+'</div><div class="desc">'+esc(j.display_message||j.message||j.folder.split(/[\\/]/).at(-1))+'</div><div class="note">'+esc(j.created||'Monitoring · external controller')+'</div></div><div class="right"><span class="pill '+(['failed','needs_review','needs_attention','interrupted'].includes(j.status)?'amber':'')+'">'+esc(names[j.observed_status||j.status]||j.status)+'</span>'+(!j.external&&['queued','deferred'].includes(j.status)?'<button class="secondary cancel" data-id="'+esc(j.id)+'">Cancel</button>':'')+(j.can_resume?'<button class="secondary resume" data-id="'+esc(j.id)+'">Resume checkpoint</button>':'')+'</div></div>').join(''):'<p class="note">The queue is empty. Saved wave results are available in the report.</p>';
 document.querySelectorAll('.cancel').forEach(b=>b.onclick=()=>action('cancel',{id:b.dataset.id}));
 document.querySelectorAll('.resume').forEach(b=>b.onclick=()=>action('resume',{id:b.dataset.id,request_key:crypto.randomUUID()}));
 const queueNodes=[...document.querySelectorAll('#queue-list .job')];
 list.forEach((j,i)=>{if(!j.external)queueNodes[i].insertAdjacentHTML('beforeend',validationHTML(j.id,j.validation))});
 $('#report-time').textContent=s.report_busy?'Generating plots and exports…':s.report.generated_at?'Latest report: '+new Date(s.report.generated_at).toLocaleString('en-GB'):'Preparing report';
 if(s.live_report_refresh?.enabled&&active)$('#report-time').textContent+=' · Auto-update every 5 min while calculating';
 $('#refresh-report').disabled=busy||s.report_busy;
 if(qRequestPending&&s.report.generated_at!==qRequestedAt)qRequestPending=false;
 if(s.report_error?.error)qRequestPending=false;
 const qUpdating=s.report_busy||qRequestPending;
 $('#refresh-q').disabled=busy||qUpdating;
 $('#refresh-q').textContent=qUpdating?'Updating…':'Update plots';
 $('#refresh-comparison').disabled=busy||qUpdating;
 $('#refresh-comparison').textContent=qUpdating?'Updating…':'Update comparison';
 $('#q-refresh-status').textContent=s.report_error?.error?'Update failed: '+s.report_error.error:qUpdating?'Checking saved runs and updating force summaries…':s.report.generated_at?'Updated: '+new Date(s.report.generated_at).toLocaleString('en-GB')+' · New accepted runs are also added automatically.':'';
 const test=s.selftest||{};
 $('#automation-test').textContent=test.status==='passed'?'Controller verified in STAR: start, pause/save and continuous resume.':test.status==='failed'?'Controller test requires review: '+test.error:test.status==='paused_by_user'?'Controller test paused by request; start and pause/save verified.':'Controller test: '+(test.status==='waiting_for_existing_solver'?'waiting for the solver':'in progress');
 if(s.report.relative)$('#download').href='/'+s.report.relative+'/nwar_report.zip';
 $('#gaps').innerHTML=s.audit.missing.map(x=>'<li>'+esc(x)+'</li>').join('');
 $('#results').innerHTML='<table><thead><tr><th>Wave</th><th>Wave conditions</th><th>Data through [s]</th><th>Measured cycles</th><th>Mean Cz</th><th>Mean Cx</th><th>Qualitative stage</th></tr></thead><tbody>'+s.catalog.map(c=>{const j=latestAttempt(c);return '<tr><td>'+esc(c.display_id||c.id)+'</td><td>'+(c.condition_label?esc(c.condition_label):fmt(c.H,2)+' / '+fmt(c.L,1)+' m')+'</td><td>'+fmt(c.result.time_s??j?.live?.time_s,4)+'</td><td>'+esc(c.result.diagnostic_completed?'—':c.result.cycles??j?.live?.complete_cycles??'—')+'</td><td>'+fmt(c.result.CL,6)+'</td><td>'+fmt(c.result.CD,6)+'</td><td>'+ (c.result.diagnostic_completed?'<a href="/report#w08bi-snapshot">GLHF diagnostic · 3 beat periods</a>':c.validation?.project_accepted?'✓ Passed':j?esc(names[j.observed_status||j.status]||j.status)+' · not accepted':c.result.time_s!=null?'Awaiting acceptance':'No run')+'</td></tr>'}).join('')+'</tbody></table>';
 $('#validation-results').innerHTML=s.catalog.filter(c=>c.result.time_s!=null&&!c.result.diagnostic_completed).map(c=>'<div><h3>'+esc(jobLabel(c.id))+'</h3>'+validationHTML(c.validation_id,c.validation)+(c.force_wave_plot?'<details data-evidence="plot_'+esc(c.id)+'" '+(openEvidence.has('plot_'+c.id)?'open':'')+'><summary>Force response to waves ↘</summary><a href="/'+s.report.relative+'/'+encodeURIComponent(c.force_wave_plot)+'" target="_blank"><img style="width:100%;height:auto" src="/'+s.report.relative+'/'+encodeURIComponent(c.force_wave_plot)+'" alt="'+esc(c.display_id||c.id)+' · force response to waves"></a><p class="note">Up to four complete measured cycles. Probe location is stated on the plot. Click to enlarge.</p></details>':'')+'</div>').join('');
 const q=s.Q_data||[],drag=s.drag_differences||[],lift=s.lift_differences||[];
 const averaging=r=>r.diagnostic_only?'<a href="/report#w08bi-snapshot">'+esc(r.averaging)+'</a>':'Accepted · cycles 2–5';
 $('#q-reference').textContent=s.audit.C01?.CD!=null?(s.audit.C01.name||'C01')+' calm-water reference: '+fmt(s.audit.C01.CD*3855.6,2)+' N':'';
 $('#q-table').innerHTML=drag.length?'<table><tr><th>Wave</th><th>H / λ [m]</th><th>Mean Fx [N]</th><th>ΔCx</th><th>ΔFx [N]</th><th>Change vs C01</th><th>Averaging</th></tr>'+drag.map(r=>'<tr><td>'+esc(r.display_id||r.case)+'</td><td>'+(r.diagnostic_only?'W01 + W06':fmt(r.H_m,2)+' / '+fmt(r.lambda_m,1))+'</td><td>'+fmt(r.D_wave_N,2)+'</td><td>'+fmt(r.Q_CD,7)+'</td><td>'+fmt(r.delta_D_N,2)+'</td><td>'+fmt(r.relative_change_pct,1)+'%</td><td>'+averaging(r)+'</td></tr>').join('')+'</table>':'Waiting for saved horizontal force results.';
 $('#lift-table').innerHTML=lift.length?'<table><tr><th>Wave</th><th>Mean Fz [N]</th><th>ΔCz</th><th>ΔFz [N]</th><th>Change vs C01</th><th>Averaging</th></tr>'+lift.map(r=>'<tr><td>'+esc(r.display_id||r.case)+'</td><td>'+fmt(r.L_wave_N,2)+'</td><td>'+fmt(r.delta_CL,7)+'</td><td>'+fmt(r.delta_L_N,2)+'</td><td>'+fmt(r.relative_change_pct,2)+'%</td><td>'+averaging(r)+'</td></tr>').join('')+'</table>':'Waiting for saved vertical force results.';
 for(const [element,file,visible] of [['#q-plot','Q_trend.png',q.length],['#lift-plot','lift_trend.png',lift.some(r=>!r.diagnostic_only)]]){
  const plot=$(element),src='/'+s.report.relative+'/'+file;plot.hidden=!visible;
  if(visible&&plot.getAttribute('src')!==src)plot.src=src;
 }
 if(q.length)$('#q-csv').href='/'+s.report.relative+'/Q_summary.csv';
 const comparison=s.report.force_wave_comparison||{},hasComparison=!!comparison.case_count;
 $('#comparison-plot').hidden=!hasComparison;
 $('#comparison-status').textContent=s.report_error?.error?'Update failed: '+s.report_error.error:qUpdating?'Rebuilding comparison and exports…':hasComparison?comparison.cases.join(' · ')+' · Updated '+new Date(s.report.generated_at).toLocaleString('en-GB'):'Waiting for accepted runs with four complete response cycles.';
 if(hasComparison){
  const base='/'+s.report.relative+'/',files=comparison.files,src=base+files.preview;
  if($('#comparison-plot').getAttribute('src')!==src)$('#comparison-plot').src=src;
  $('#comparison-figure').href=base+files.svg;
  $('#comparison-downloads').innerHTML=[['interactive','Interactive · select cases'],['pdf','PDF · vector'],['svg','SVG · vector'],['png','PNG · 600 dpi'],['csv','Curve data · CSV']].filter(([key])=>files[key]).map(([key,label])=>'<a href="'+base+encodeURIComponent(files[key])+'" target="_blank">'+label+'</a>').join('');
  $('#comparison-evidence').innerHTML='<a href="'+base+files.caption+'" target="_blank">Figure caption</a> · <a href="'+base+files.evidence+'" target="_blank">Phase reconstruction and source data</a>';
 }else{$('#comparison-downloads').textContent='';$('#comparison-evidence').textContent=''}
 document.querySelectorAll('.revalidate').forEach(b=>b.onclick=()=>action('validate',{id:b.dataset.id}));
 $('#meshes').innerHTML='<table><tr><th>Mesh</th><th>Cells</th><th>Δt [ms]</th><th>Cz vs M12</th><th>Cx vs M12</th></tr>'+s.audit.mesh.map(m=>'<tr><td>'+esc(m.mesh)+'</td><td>'+fmt(m.cells,0)+'</td><td>'+fmt(m.dt_s*1000,1)+'</td><td>'+fmt(m.delta_CL_pct,2)+'%</td><td>'+fmt(m.delta_CD_pct,2)+'%</td></tr>').join('')+'</table>';
 if(s.stops.length)notice('External STOP prevents new runs: '+s.stops.join(', '),true);
}
async function refresh(){try{const r=await fetch('/api/status',{cache:'no-store'});if(!r.ok)throw new Error('Status request: '+r.status);render(await r.json())}catch(e){$('#connection').textContent='● Disconnected';notice('Could not refresh data. The displayed state may be outdated. '+e.message,true)}}
async function action(path,data={}){
 try{const x=await post(path,data);if(x)notice(x.message||'Request saved.');await refresh()}catch(e){notice(e.message,true)}
}
$('#launch').onclick=async()=>{const cases=selected();if(!cases.length)return;await action('enqueue',{cases,mode:$('#mode').value,extra_cycles:Number($('#extra').value),request_key:crypto.randomUUID()})};
let customRequest=null;
$('#custom-wave-form').onsubmit=async e=>{
 e.preventDefault();if(busy||!e.target.reportValidity())return;
 const H=Number($('#custom-height').value),L=Number($('#custom-length').value);
 if(!customRequest||customRequest.H!==H||customRequest.L!==L)customRequest={H,L,request_key:crypto.randomUUID()};
 const button=$('#custom-submit');button.disabled=true;button.textContent='Adding to queue…';
 try{const result=await post('custom-wave',customRequest);if(!result)return;$('#custom-wave-result').textContent=result.case_id+' · H '+fmt(H,2)+' m / λ '+fmt(L,2)+' m. '+result.message;customRequest=null;await refresh()}
 catch(error){$('#custom-wave-result').textContent=error.message}
 finally{button.disabled=false;button.textContent='Add to queue'}
};
$('#mode').onchange=()=>$('#extra-box').hidden=$('#mode').value!=='extend';
$('#pause').onclick=()=>action('pause');
$('#resume-current').onclick=async()=>{
 if(busy||!state?.current_resume?.available)return;
 const target={...state.current_resume,request_key:crypto.randomUUID()};
 $('#resume-current').disabled=true;$('#resume-current').textContent='Resuming…';
 try{await action('resume-current',target)}finally{$('#resume-current').textContent='Resume simulation'}
};
$('#continue').onclick=()=>action('continue');
$('#refresh-report').onclick=()=>action('report');
async function updatePlots(){
 if(busy||qRequestPending)return;
 qRequestedAt=state?.report.generated_at;qRequestPending=true;$('#refresh-q').disabled=true;$('#refresh-q').textContent='Updating…';
 $('#refresh-comparison').disabled=true;$('#refresh-comparison').textContent='Updating…';
 try{await post('report');notice('Plot update started. Figures and exports will refresh automatically.');await refresh()}
 catch(e){qRequestPending=false;notice(e.message,true);await refresh()}
}
$('#refresh-q').onclick=updatePlots;
$('#refresh-comparison').onclick=updatePlots;
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
refresh();setInterval(()=>{if(!document.hidden&&!busy)refresh()},4000);
})();
