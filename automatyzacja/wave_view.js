/* Interactive derived views only: no solver or queue controls. */
(()=>{'use strict';
const $=id=>document.getElementById(id),host=$('wave-explorer');
if(!host)return;
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt=(v,n=3)=>Number.isFinite(v)?v.toLocaleString('en-GB',{maximumFractionDigits:n,minimumFractionDigits:n}):'—';
const colors=['#087f8c','#b76b13','#6853a6','#bb4d65','#267eb1'];
const cycleColor=c=>colors[(c.number-1)%colors.length];
const displayedCycles=()=>[...(payload?.cycles||[]),...(payload?.in_progress_cycle?[payload.in_progress_cycle]:[])];
let payload=null,requested=0,pending=null,generation=0,catalogKey='',chosen=false,hiddenCycles=new Set(),probePhase=0,probePairKey='',latestState=null;
const settingsKey='nwar-wave-view-settings-v1';
try{const saved=JSON.parse(localStorage.getItem(settingsKey)||'{}');for(const [id,key] of [['view-units','units'],['view-range','range']])if(saved[key]&&[...$(id).options].some(o=>o.value===saved[key]))$(id).value=saved[key];$('view-follow').checked=saved.follow!==false;chosen=!$('view-follow').checked;if(chosen&&saved.caseId)$('view-case').dataset.savedCase=saved.caseId}catch{}
function saveViewSettings(){try{localStorage.setItem(settingsKey,JSON.stringify({units:$('view-units').value,range:$('view-range').value,follow:$('view-follow').checked,caseId:$('view-case').value}))}catch{}}
function renderCycleProgress(){
 const selected=latestState?.catalog.find(c=>c.id===$('view-case').value);
 const bar=$('view-cycle-progress'),wall=s=>s>=3600?fmt(s/3600,1)+' h':Math.max(1,Math.round(s/60))+' min';
 if(payload?.diagnostic_only||selected?.diagnostic_only){
  const arrival=payload?.first_wave_arrival,next=payload?.next_wave;
  const detected=arrival?.detected_time_s,value=next?.percent??arrival?.percent??0;
  $('view-cycle-fill').style.width=value+'%';bar.setAttribute('aria-valuenow',String(value));
  const title=payload?.display_id||selected?.display_id||'Wave';
  if(next){
   bar.setAttribute('aria-label','Next wave crest at the foil');
   $('view-cycle-progress-title').textContent=title+' · Next wave crest · x = 0';
   $('view-cycle-eta').textContent=payload.status==='paused'?'Paused':payload.status!=='running'?'Saved history':next.eta_wall_s!=null?'≈ '+wall(next.eta_wall_s)+' remaining':next.awaiting_crest?'Waiting for measured crest':'Estimating from samples';
   const anchor=next.last_crest_s!=null?'Last crest at t = '+fmt(next.last_crest_s,3)+' s.':'First signal detected at t = '+fmt(detected,3)+' s.';
   $('view-cycle-progress-note').textContent=anchor+' '+(next.awaiting_crest?'The estimated time has passed. The next crest will reset the countdown.':'Next crest estimated near t = '+fmt(next.target_time_s,3)+' s, based on '+(next.from_measured_spacing?'recent crest spacing':'the shorter configured wave period')+'.');
   return;
  }
  bar.setAttribute('aria-label','First wave arrival at the foil');
  $('view-cycle-progress-title').textContent=title+' · First wave arrival · x = 0';
  const elapsed=arrival&&arrival.current_time_s>=arrival.target_time_s;
  $('view-cycle-eta').textContent=detected!=null?'Detected':arrival?.eta_wall_s!=null?'≈ '+wall(arrival.eta_wall_s)+' remaining':elapsed?'Waiting for probe signal':'Estimating from samples';
  $('view-cycle-progress-note').textContent=detected!=null?'First sustained change at the foil probe at t = '+fmt(detected,3)+' s.':arrival?'Estimated arrival near t = '+fmt(arrival.target_time_s,3)+' s of simulation, based on inlet-to-foil travel. '+(elapsed?'The probe has yet to record a sustained change.':arrival.eta_wall_s==null?'A wall-clock estimate requires fresh solver samples.':'The countdown uses the latest solver pace.'):'Waiting for recorded wave samples.';
  return;
 }
 const p=payload?.cycle_progress||payload?.first_cycle_progress,value=p?.percent??0,number=p?.cycle_number||1;
 $('view-cycle-fill').style.width=value+'%';bar.setAttribute('aria-valuenow',String(value));
 bar.setAttribute('aria-label',p?.complete?'Recorded complete cycles':'Completion of cycle '+number);
 $('view-cycle-progress-title').textContent=(payload?.display_id||selected?.display_id||$('view-case').value||'Wave')+' · '+(p?.complete?'Recorded cycles':'Cycle '+number+(payload?.in_progress_cycle?' in progress':''))+' · x = 0';
 $('view-cycle-eta').textContent=p?.complete?'✓ Recorded':p?.eta_wall_s!=null?'≈ '+wall(p.eta_wall_s)+' remaining':p?.state==='awaiting_crossing'?'Waiting for closing crossing':'Estimating from samples';
 $('view-cycle-progress-note').textContent=!p?'Waiting for recorded wave samples.':p.complete?payload.cycle_count+' complete measured cycles at x = 0. Cycles 2–5 appear below; cycle 1 is excluded. Acceptance is checked separately.':p.state==='unavailable'?p.reason:p.state==='recording'?fmt(value,0)+'% of cycle '+number+' recorded · '+payload.cycle_count+' complete · t = '+fmt(p.current_time_s,4)+' s · estimated closing crossing near t = '+fmt(p.target_time_s,3)+' s. The measured crossing completes this cycle and starts the next countdown.':p.state==='awaiting_crossing'?'The estimated period has elapsed. Waiting for a valid measured closing crossing; cycle '+number+' remains incomplete.':p.state==='startup'?'Wave startup is still excluded. The first full cycle is counted after the wave reaches x = 0. Timing includes startup and an approximate cycle window.':'Waiting for the first upward crossing at x = 0. Timing is approximate until the cycle start is measured.';
 if(p&&!p.complete&&p.eta_wall_s==null&&!['awaiting_crossing','unavailable'].includes(p.state))$('view-cycle-progress-note').textContent+=' A remaining-time estimate requires fresh samples from a running solver.';
}

function chart(node,lines,{title,xLabel,yLabel,domain=null,yDomain=null,phaseAxis=false,markers=[],zero=false,empty='Waiting for recorded samples.'}){
 const vectors=lines.filter(l=>l.points.some(p=>p&&p.every(Number.isFinite)));
 const all=vectors.flatMap(l=>l.points.filter(p=>p&&p.every(Number.isFinite)));
 if(!all.length){node.innerHTML='<p class="view-empty">'+esc(empty)+'</p>';return}
 const w=Math.max(320,node.clientWidth||600),h=292,L=70,R=w-18,T=34,B=246;
 let [lo,hi]=domain||[Math.min(...all.map(p=>p[0])),Math.max(...all.map(p=>p[0]))];if(hi<=lo)hi=lo+1;
 const values=all.filter(p=>p[0]>=lo&&p[0]<=hi).map(p=>p[1]);
 if(!values.length){node.innerHTML='<p class="view-empty">No samples in this window.</p>';return}
 let [low,high]=yDomain||[Math.min(...values,...(zero?[0]:[])),Math.max(...values,...(zero?[0]:[]))];
 const pad=(high-low||Math.max(Math.abs(low)*.1,.001))*.1;low-=pad;high+=pad;
 const X=x=>L+(x-lo)/(hi-lo)*(R-L),Y=y=>B-(y-low)/(high-low)*(B-T);
 let svg='<title>'+esc(title)+'</title><text x="'+L+'" y="17" class="axis-label">'+esc(title)+' · '+esc(yLabel)+'</text>';
 for(let i=0;i<=4;i++){
  const y=low+(high-low)*i/4,x=lo+(hi-lo)*i/4;
  svg+='<line x1="'+L+'" x2="'+R+'" y1="'+Y(y)+'" y2="'+Y(y)+'" class="plot-grid"/><text x="'+(L-8)+'" y="'+(Y(y)+4)+'" text-anchor="end">'+fmt(y,high-low<.05?5:high-low<1?3:1)+'</text>';
  svg+='<line x1="'+X(x)+'" x2="'+X(x)+'" y1="'+T+'" y2="'+B+'" class="plot-grid"/><text x="'+X(x)+'" y="'+(B+20)+'" text-anchor="middle">'+fmt(x,2)+'</text>';
 }
 if(zero)svg+='<line x1="'+L+'" x2="'+R+'" y1="'+Y(0)+'" y2="'+Y(0)+'" stroke="#76878d" stroke-dasharray="3 4"/>';
 for(const marker of markers){const x=typeof marker==='number'?marker:marker.time;if(x>=lo&&x<=hi)svg+='<line x1="'+X(x)+'" x2="'+X(x)+'" y1="'+T+'" y2="'+B+'" stroke="'+(marker.color||'#8b9a9e')+'" stroke-dasharray="5 4"><title>'+esc(marker.label||'Resume at '+fmt(x,4)+' s')+'</title></line>'}
 for(const line of vectors){
  let path='',pen=false;
  for(const p of line.points){if(!p||!p.every(Number.isFinite)||p[0]<lo||p[0]>hi){pen=false;continue}path+=(pen?'L':'M')+X(p[0]).toFixed(2)+','+Y(p[1]).toFixed(2)+' ';pen=true}
  svg+='<path class="wave-view-curve"'+(line.cycleNumber?' data-cycle-number="'+line.cycleNumber+'" data-provisional="'+!!line.provisional+'" data-phase-end="'+line.points.at(-1)[0]+'"':'')+' d="'+path+'" fill="none" stroke="'+line.color+'" stroke-width="2"'+(line.dash?' stroke-dasharray="7 4"':'')+'/>';
  if(line.provisional){const end=line.points.filter(p=>p&&p.every(Number.isFinite)&&p[0]>=lo&&p[0]<=hi).at(-1);if(end)svg+='<circle class="wave-live-end" cx="'+X(end[0])+'" cy="'+Y(end[1])+'" r="4" fill="'+line.color+'"><title>Latest recorded sample · '+esc(line.name)+'</title></circle>'}
 }
 svg+='<line class="wave-view-cursor" y1="'+T+'" y2="'+B+'" stroke="#526674" visibility="hidden"/><text x="'+((L+R)/2)+'" y="288" class="axis-label" text-anchor="middle">'+esc(xLabel)+'</text>';
 node.innerHTML='<div class="history-scroll"><svg viewBox="0 0 '+w+' '+h+'" tabindex="0" role="img" aria-label="'+esc(title)+'. Use left and right arrows to read samples.">'+svg+'</svg></div><div class="history-legend">'+vectors.map(l=>'<span style="color:'+l.color+'">'+(l.dash?'┄':'━')+' '+esc(l.name)+'</span>').join(' &nbsp; ')+'</div><div class="history-readout">Point at the plot or use arrow keys to read values.</div>';
 const canvas=node.querySelector('svg'),cursor=node.querySelector('.wave-view-cursor');let fraction=.5;
 function readAt(f){
  fraction=Math.max(0,Math.min(1,f));const target=lo+fraction*(hi-lo),readout=[];
  for(const line of vectors){
   const points=line.points.filter(p=>p&&p.every(Number.isFinite)&&p[0]>=lo&&p[0]<=hi);
   const near=points.reduce((best,p)=>!best||Math.abs(p[0]-target)<Math.abs(best[0]-target)?p:best,null);
   const available=near&&Math.abs(near[0]-target)<(hi-lo)/40;
   readout.push(line.name+': '+(available?fmt(near[1],5)+(line.sourceTimeOffset?' (recorded t = '+fmt(near[0]+line.sourceTimeOffset,4)+' s)':''):'no nearby sample'));
  }
  cursor.setAttribute('x1',X(target));cursor.setAttribute('x2',X(target));cursor.setAttribute('visibility','visible');
  node.querySelector('.history-readout').textContent=(phaseAxis?'Phase ':'t = ')+fmt(target,4)+(phaseAxis?'':' s')+' · '+readout.join(' · ');
 }
 canvas.onpointermove=e=>{const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(canvas.getScreenCTM().inverse());readAt((p.x-L)/(R-L))};
 canvas.onkeydown=e=>{if(['ArrowLeft','ArrowRight','Home','End'].includes(e.key)){e.preventDefault();readAt(e.key==='Home'?0:e.key==='End'?1:fraction+(e.key==='ArrowLeft'?-.01:.01))}};
}

function renderForces(){
 if(!payload||payload.empty)return;
 const force=$('view-units').value==='force',reference=payload.force_reference;
 const available=displayedCycles(),shown=available.filter(c=>!hiddenCycles.has(c.number));
 const empty=payload.diagnostic_only?'For this bichromatic wave, follow the force and probe histories in physical time.':available.length?'Select at least one cycle above.':'Waiting for an eligible measured cycle start at x = 0. The current cycle will draw here as force samples arrive.';
 const hasPartial=shown.some(c=>c.provisional),phaseEnd=Math.max(1,...shown.map(c=>c.phase.at(-1)||0));
 for(const [field,id,title] of [['CL','view-lift','Vertical force · domain z'],['CD','view-drag','Horizontal force · domain x']]){
  const lines=shown.map(c=>({name:'Cycle '+c.number+(c.provisional?' · in progress':''),color:cycleColor(c),cycleNumber:c.number,provisional:c.provisional,dash:c.provisional,points:c.phase.map((p,i)=>[p,force?(c[field][i]-reference[field])*reference.coefficient_denominator_N:c[field][i]])}));
  chart($(id),lines,{title,xLabel:hasPartial?'Cycle phase · live estimate · x = 0':'Measured cycle phase · x = 0',yLabel:force?(field==='CL'?'ΔFz [N]':'ΔFx [N]'):(field==='CL'?'Cz':'Cx'),domain:[0,phaseEnd],phaseAxis:true,zero:force,empty});
 }
}

function renderProbes(){
 if(!payload||payload.empty)return;
 const a=payload.probes.find(p=>String(p.x_m)===$('view-probe-a').value),b=payload.probes.find(p=>String(p.x_m)===$('view-probe-b').value);
 const pairKey=payload.case_id+':'+a?.x_m+':'+b?.x_m;
 if(pairKey!==probePairKey){probePairKey=pairKey;probePhase=0;syncPhaseInputs()}
 const enabled=!!a&&!!b&&a!==b&&Number.isFinite(payload.period_s)&&payload.period_s>0;
 for(const id of ['view-probe-phase','view-probe-phase-value','view-probe-phase-reset'])$(id).disabled=!enabled;
 const shift=enabled?probePhase/360*payload.period_s:0;
 const original=[a,b].filter(Boolean).flatMap(p=>p.points.filter(v=>v&&v.every(Number.isFinite)));
 const end=payload.time_s,start=original.length?Math.min(...original.map(v=>v[0])):end;
 const cutoff=$('view-range').value==='last'?Math.max(start,end-4*payload.period_s):start;
 const vertical=original.filter(v=>v[0]>=cutoff-payload.period_s&&v[0]<=end+payload.period_s).map(v=>v[1]);
 const yDomain=vertical.length?[Math.min(...vertical),Math.max(...vertical)]:null;
 const sign=n=>n>0?'+':'';
 $('view-probe-phase-note').textContent=shift?('Visual phase alignment · B '+sign(probePhase)+fmt(probePhase,1)+'° = '+sign(shift)+fmt(shift,4)+' s; moved '+(shift>0?'left (earlier)':'right (later)')+'. 360° = '+fmt(payload.period_s,4)+' s (configured encounter period). Recorded samples and amplitudes stay unchanged. Dashed resume markers: A teal, B orange; B markers follow its shift.'):('0° · original physical timing. Positive phase moves B left; negative moves it right. 360° = '+fmt(payload.period_s,4)+' s (configured encounter period). Visual adjustment only; recorded data and amplitudes stay unchanged. Dashed vertical lines mark resumes.');
 const lines=[a,b].filter(Boolean).map((p,i)=>({name:'Probe '+(i?'B':'A')+' · x = '+fmt(p.x_m,1)+' m'+(i&&shift?' · '+sign(probePhase)+fmt(probePhase,1)+'°':''),color:colors[i],dash:!!i,sourceTimeOffset:i?shift:0,points:p.points.map(v=>v?[v[0]-(i?shift:0),v[1]]:null)}));
 const markers=shift?payload.resume_markers.flatMap(t=>[{time:t,color:colors[0],label:'Probe A resume at '+fmt(t,4)+' s'},{time:t-shift,color:colors[1],label:'Probe B resume · recorded t = '+fmt(t,4)+' s'}]):payload.resume_markers;
 chart($('view-probes'),lines,{title:shift?'Surface elevation · B shifted':'Recorded surface elevation',xLabel:shift?'Reference time · probe A [s]':'Physical time t [s]',yLabel:'η [m]',domain:[cutoff,end],yDomain,markers,empty:'Waiting for two recorded probe histories.'});
}

function syncPhaseInputs(preserveEntry=false){
 $('view-probe-phase').value=String(probePhase);if(!preserveEntry)$('view-probe-phase-value').value=String(probePhase);
 $('view-probe-phase').setAttribute('aria-valuetext',fmt(probePhase,1)+' degrees; positive moves probe B left');
}
function setProbePhase(value,preserveEntry=false){
 if(value===''||!Number.isFinite(Number(value)))return;
 probePhase=Math.round(Math.max(-360,Math.min(360,Number(value)))*10)/10;syncPhaseInputs(preserveEntry);renderProbes();
}

function render(){
 renderCycleProgress();
 if(payload.empty){$('view-status').textContent=(payload.condition_label?payload.display_id+' · '+payload.condition_label+' · ':'')+payload.message;showWaitingPlots('Waiting for recorded samples from this wave.');for(const id of ['view-probe-a','view-probe-b']){$(id).replaceChildren();$(id).dataset.signature='';$(id).disabled=true}for(const id of ['view-probe-phase','view-probe-phase-value','view-probe-phase-reset'])$(id).disabled=true;probePhase=0;probePairKey='';syncPhaseInputs();$('view-probe-phase-note').textContent='Waiting for two recorded probe histories.';return}
 const status=payload.project_accepted?'Accepted saved result':payload.status==='running'?'Live · diagnostic data':'Saved diagnostic data · not accepted';
 const importCheckpoint=payload.verified_import_checkpoint_s;
 $('view-status').textContent=payload.display_id+(payload.condition_label?' · '+payload.condition_label:'')+' · '+status+' · data through '+fmt(payload.time_s,4)+ ' s'+(payload.diagnostic_only?' · bichromatic diagnostic':' · '+payload.cycle_count+' complete cycles at x = 0')+(importCheckpoint!=null&&payload.time_s>importCheckpoint+1e-7?' · verified checkpoint '+fmt(importCheckpoint,4)+' s':'')+' · updated '+new Date(payload.sampled_at).toLocaleTimeString('en-GB')+(payload.health_ok?'':' · numerical health requires review');
 const alignment=payload.alignment;
 // A new probe on a continuation must not hide the earlier measured cycles.
 $('view-phase').textContent='Cycles 2-5: '+payload.cycles.length+' complete measured cycles (cycle 1 excluded)'+(payload.in_progress_cycle?' plus cycle '+payload.in_progress_cycle.number+' in progress':'')+'; phase zero is the upward crossing at x = 0 m. '+(alignment.method==='direct_measurement'?'Direct x = 0 measurement.':'x = 0 reconstructed from x = '+fmt(alignment.source_probe_x_m,1)+' m using '+(alignment.method==='measured_wave_propagation'?'measured wave propagation':'a wavelength / period estimate')+'.')+(payload.in_progress_cycle?' The dashed line contains recorded samples only; its phase uses '+(payload.cycle_progress?.period_basis==='measured_cycles'?'the measured period':'the configured period')+' until the closing crossing is recorded.':'')+' Target: 5 complete cycles; cycle 1 is startup and excluded from means, repeatability and Q. Force timing and cycle mean offsets are preserved. An incomplete cycle does not count toward acceptance.'+(payload.cycle_error?' '+payload.cycle_error:'');
 if(payload.diagnostic_only)$('view-phase').textContent='Bichromatic diagnostic. Compare the probe histories in physical time.';
 if(alignment.partial_direct_history)$('view-phase').textContent+=' The x = 0 probe was added on resume. This display keeps the full legacy probe history with estimated phase at x = 0; acceptance uses the original fixed probe.';
 const available=displayedCycles(),cycleSignature=available.map(c=>c.number+':'+!!c.provisional).join(',');
 if($('view-cycles').dataset.signature!==cycleSignature){
  $('view-cycles').dataset.signature=cycleSignature;
  $('view-cycles').innerHTML=available.map(c=>'<label style="color:'+cycleColor(c)+'"><input type="checkbox" data-cycle="'+c.number+'" '+(!hiddenCycles.has(c.number)?'checked':'')+'> Cycle '+c.number+(c.provisional?' <b class="cycle-live-label">In progress</b>':'')+' <span class="note" data-cycle-note="'+c.number+'"></span></label>').join('');
 }
 for(const c of available){const note=$('view-cycles').querySelector('[data-cycle-note="'+c.number+'"]');if(note)note.textContent=fmt(c.start,3)+'–'+fmt(c.end,3)+' s'+(c.provisional?' · still recording':'')}
 const positions=payload.probes.map(p=>String(p.x_m));
 let a=positions.includes($('view-probe-a').value)?$('view-probe-a').value:positions.includes('-0.5')?'-0.5':positions.includes('-6')?'-6':positions[0];
 let b=positions.includes($('view-probe-b').value)?$('view-probe-b').value:positions.includes('0')?'0':positions.includes('5')?'5':positions.at(-1);
 if(a===b)b=positions.find(x=>x!==a);
 for(const [id,val] of [['view-probe-a',a],['view-probe-b',b]]){
  const node=$(id),signature=positions.join(',');if(node.dataset.signature!==signature){node.innerHTML=positions.map(x=>'<option value="'+x+'">x = '+fmt(Number(x),1)+' m</option>').join('');node.dataset.signature=signature}node.value=val;node.disabled=positions.length<2;
 }
 renderForces();renderProbes();
}

async function refresh(force=false){
 if(!force&&(pending||Date.now()-requested<8000))return;
 if(!$('view-case').value)return;
 pending?.abort();const controller=new AbortController();pending=controller;const ticket=++generation;requested=Date.now();$('view-refresh').disabled=true;
 const timer=setTimeout(()=>controller.abort(),25000);
 try{
  const response=await fetch('/api/wave-view?case='+encodeURIComponent($('view-case').value),{cache:'no-store',signal:controller.signal});
  const data=await response.json();if(!response.ok)throw new Error(data.error||response.status);
  if(ticket!==generation)return;payload=data;render();
 }catch(e){if(ticket===generation)$('view-status').textContent='Charts could not refresh. '+(payload?'Displayed curves are from the previous snapshot. ':'')+(e.name==='AbortError'?'Request timed out.':e.message)}
 finally{clearTimeout(timer);if(ticket===generation){pending=null;$('view-refresh').disabled=false}}
}

function showWaitingPlots(message){for(const id of ['view-lift','view-drag','view-probes'])$(id).innerHTML='<p class="view-empty">'+esc(message)+'</p>';$('view-cycles').replaceChildren();$('view-cycles').dataset.signature='';$('view-phase').textContent='Recorded force samples will draw the current cycle here, followed by each measured complete cycle at x = 0.'}
function resetWave(){payload=null;hiddenCycles.clear();requested=0;$('view-status').textContent='Loading selected wave…';showWaitingPlots('Loading selected wave…');renderCycleProgress();refresh(true)}
window.updateWaveView=s=>{
 latestState=s;
 const cases=s.catalog.filter(c=>!/^CUSTOM\d+$/i.test(c.display_id||c.id));
 const label=c=>(c.display_id||c.id)+' · '+(c.condition_label||('H '+fmt(c.H,2)+' m / λ '+fmt(c.L,1)+' m'));
 const key=JSON.stringify(cases.map(c=>[c.id,label(c)]));
 if(key!==catalogKey){const selected=$('view-case').value||$('view-case').dataset.savedCase;$('view-case').innerHTML=cases.map(c=>'<option value="'+esc(c.id)+'">'+esc(label(c))+'</option>').join('');if(cases.some(c=>c.id===selected))$('view-case').value=selected;catalogKey=key}
 if(!chosen){const active=[...s.jobs,...s.external].find(j=>j.id===s.current_run?.id);if(active&&cases.some(c=>c.id===active.case_id)&&$('view-case').value!==active.case_id){$('view-case').value=active.case_id;resetWave();return}}
 refresh();
};
$('view-case').onchange=()=>{chosen=true;$('view-follow').checked=false;saveViewSettings();resetWave()};
$('view-follow').onchange=()=>{chosen=!$('view-follow').checked;saveViewSettings();if(latestState)window.updateWaveView(latestState)};
$('view-refresh').onclick=()=>refresh(true);
$('view-units').onchange=()=>{saveViewSettings();renderForces()};
$('view-range').onchange=()=>{saveViewSettings();renderProbes()};
$('view-probe-phase').oninput=e=>setProbePhase(e.target.value);
$('view-probe-phase-value').oninput=e=>setProbePhase(e.target.value,true);
$('view-probe-phase-value').onchange=()=>{syncPhaseInputs();renderProbes()};
$('view-probe-phase-reset').onclick=()=>setProbePhase(0);
for(const [id,other] of [['view-probe-a','view-probe-b'],['view-probe-b','view-probe-a']])$(id).onchange=()=>{if($(id).value===$(other).value)$(other).value=[...$(other).options].find(o=>o.value!==$(id).value)?.value||'';renderProbes()};
$('view-cycles').onchange=e=>{if(e.target.dataset.cycle){const number=Number(e.target.dataset.cycle);e.target.checked?hiddenCycles.delete(number):hiddenCycles.add(number);renderForces()}};
let resizeTimer;window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{renderForces();renderProbes()},100)});
})();
