from pathlib import Path
D=Path(r'C:\Users\ThinkPad\Documents\ChatGPT\ntnu science\mobile-dashboard-mesh-gci')
css=r"""
.gci-panel{margin:24px 0;background:#fff;border:1px solid #cadbd6;border-radius:18px;padding:24px;min-width:0}.gci-panel h2{font-size:26px;letter-spacing:-.7px;margin:5px 0 10px}.gci-panel h3{font-size:17px;margin:0 0 10px}.gci-panel p{font-size:13px}.gci-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px}.gci-top .pill{white-space:normal;text-align:center}.gci-summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:18px 0}.gci-summary>div{background:#f2f7f5;padding:13px;border-radius:10px}.gci-summary b{display:block;font-size:20px;font-weight:650}.gci-summary small{font-size:11px;color:#61777b}.gci-tabs{display:flex;gap:6px;border-bottom:1px solid #dce6e3;margin:18px 0}.gci-tabs button{flex:1;min-height:44px;border:0;background:transparent;padding:10px 6px;font:600 13px system-ui;color:#60777b;cursor:pointer;border-bottom:3px solid transparent}.gci-tabs button[aria-selected=true]{color:#195e4e;border-color:#368b73}.gci-controls{display:flex;flex-wrap:wrap;gap:12px;align-items:end;margin:16px 0}.gci-controls label{display:flex;flex:1;min-width:130px;flex-direction:column;gap:7px;font-size:12px;color:#526e72}.gci-controls select{width:100%;min-height:44px;max-width:100%;border:1px solid #b7cbc6;border-radius:9px;background:white;padding:8px;font:14px system-ui;color:#173138}.gci-controls button{min-height:44px}.gci-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:16px 0}.gci-metric{background:#f3f7f5;padding:13px;border-radius:10px;min-width:0}.gci-metric b{font-size:20px;display:block;font-variant-numeric:tabular-nums;margin:7px 0}.gci-metric small{font-size:11px;color:#5e787c;display:block;line-height:1.7}.gci-metric .pass{color:#267257}.gci-metric .fail{color:#9d641c}.gci-plots{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.gci-plot{border:1px solid #e1ebe7;border-radius:12px;padding:14px;min-width:0;margin:12px 0}.gci-plot h3{font-size:15px;margin:0 0 8px}.gci-plot svg{width:100%;height:auto;display:block;overflow:visible}.gci-chart-note{font-size:11px!important;line-height:1.6}.gci-empty{padding:22px 10px;color:#6a7f83;font-size:13px;background:#f6f8f7;border-radius:8px;line-height:1.6}.gci-legend{display:flex;flex-wrap:wrap;gap:7px 16px;font-size:11px;margin:7px 0}.gci-legend i{display:inline-block;width:12px;height:3px;vertical-align:middle;margin-right:5px}.gci-audit-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.gci-audit-card{padding:16px;background:#f3f7f5;border-radius:10px;min-width:0}.gci-audit-card p{font-size:12px;overflow-wrap:anywhere}.gci-audit-card.active{box-shadow:inset 0 0 0 2px #3d947d}.gci-callout{border-left:3px solid #c88a39;padding:10px 13px;background:#fff6e8;font-size:12px;line-height:1.7;margin:12px 0}.gci-stage{font-size:12px;color:#557377;overflow-wrap:anywhere}.gci-panel [role=tab]:focus-visible,.gci-panel select:focus-visible{outline:3px solid #68ab9b;outline-offset:2px}@media(max-width:620px){.gci-panel{padding:18px}.gci-panel h2{font-size:23px}.gci-summary{gap:7px}.gci-summary>div{padding:10px}.gci-summary b{font-size:17px}.gci-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.gci-plots,.gci-audit-grid{grid-template-columns:minmax(0,1fr)}.gci-plot{padding:10px}.gci-top{flex-wrap:wrap}.gci-tabs button{font-size:12px}.gci-controls{gap:9px}}
"""
js=r"""
const GCI_KEYS=['CL_total','CD','CD_pressure','CD_viscous'];
const GCI_NAMES={CL_total:'CL · lift',CD:'CD · total drag',CD_pressure:'CD · pressure',CD_viscous:'CD · viscous'};
const GCI_COLORS={CL_total:'#426fa1',CD:'#277e68',CD_pressure:'#b27625',CD_viscous:'#8b60a3'};
const GCI_MESH_COLORS={W01a:'#277e68',G10_M:'#b27625',G10_F:'#426fa1'};
const GCI_STATES={loading:'Loading saved fields',running:'Calculating',no_recent_samples:'No recent samples',stopped:'Process stopped',settled:'Stabilized',pilot_complete:'CFL pilot complete',window_complete:'Window complete',saved:'Saved continuation',preparing:'Preparing',queued:'Waiting'};
let gciTab='convergence',gciMesh='auto',gciMetric='CD',gciFull=false,gciRendered={};
const gciCells=n=>n>=1e6?(n/1e6).toFixed(3)+'M':Math.round(n/1000)+'k';
function gciPlot(series,{scatter=false,threshold=null,xCells=false,yPercent=false,label='Coefficient history'}={}){
 const valid=series.map(s=>({...s,points:s.points.filter(p=>p.length>=2&&p.slice(0,2).every(Number.isFinite))}));
 const all=valid.flatMap(s=>s.points);
 if(!all.length)return '<div class="gci-empty">No samples yet. This chart will update as calculations progress.</div>';
 let xmin=Math.min(...all.map(p=>p[0])),xmax=Math.max(...all.map(p=>p[0]));
 if(xCells){xmin=250000;xmax=1250000}
 if(xmax-xmin<1e-10){xmin-=xCells?10000:.0001;xmax+=xCells?10000:.0001}
 let ymin=Math.min(...all.map(p=>p[1])),ymax=Math.max(...all.map(p=>p[1]));
 if(threshold!==null){ymin=Math.min(0,ymin);ymax=Math.max(ymax,threshold*1.25)}
 const pad=(ymax-ymin||Math.max(Math.abs(ymin)*.01,1e-6))*.12;ymin-=pad;ymax+=pad;
 if(yPercent)ymin=Math.max(0,ymin);
 const x=t=>94+(t-xmin)/(xmax-xmin)*482,y=v=>174-(v-ymin)/(ymax-ymin)*148;
 const fmt=v=>yPercent?v.toFixed(v<10?2:1):v.toFixed(5);
 let h='<svg viewBox="0 0 600 225" role="img" aria-label="'+esc(label)+'" data-series-count="'+valid.filter(s=>s.points.length).length+'"><title>'+esc(label)+'</title>';
 for(let i=0;i<3;i++){const v=ymin+(ymax-ymin)*i/2;h+='<path d="M94 '+y(v)+'H576" stroke="#e2ebe7"/><text x="85" y="'+(y(v)+7)+'" text-anchor="end" font-size="21" fill="#60787b">'+fmt(v)+'</text>'}
 const ticks=xCells?[317277,595285,1154199]:[xmin,(xmin+xmax)/2,xmax];
 ticks.forEach((v,i)=>{h+='<text x="'+x(v)+'" y="207" text-anchor="'+(i===0?'start':i===ticks.length-1?'end':'middle')+'" font-size="20" fill="#60787b">'+(xCells?gciCells(v):v.toFixed(4))+'</text>'});
 if(threshold!==null)h+='<path d="M94 '+y(threshold)+'H576" stroke="#b66528" stroke-dasharray="8 7" stroke-width="2"/>';
 for(const s of valid){
  if(!scatter&&s.points.length>1){const d=s.points.map((p,i)=>(i?'L':'M')+x(p[0]).toFixed(2)+','+y(p[1]).toFixed(2)).join(' ');h+='<path data-mesh-series="'+esc(s.id||s.label)+'" d="'+d+'" fill="none" stroke="'+s.color+'" stroke-width="2.4" vector-effect="non-scaling-stroke"/>'}
  if(scatter||s.points.length===1)s.points.forEach(p=>{h+='<circle data-mean-confirmed="'+(p[2]===true)+'" cx="'+x(p[0])+'" cy="'+y(p[1])+'" r="6" fill="'+(p[2]===true?s.color:'#fff')+'" stroke="'+s.color+'" stroke-width="2.5"><title>'+esc(s.label)+': '+fmt(p[1])+(p[2]===true?' · stabilized mean':' · provisional latest sample')+'</title></circle>'});
 }
 h+='</svg><div class="gci-legend">'+valid.filter(s=>s.points.length).map(s=>'<span><i style="background:'+s.color+'"></i>'+esc(s.label)+'</span>').join('')+'</div>';
 return h;
}
function gciConvergence(m){
 const points=(m.series||[]).filter(p=>gciFull||p[0]>=(m.time_s||0)-.8);
 const s=m.stability||{},metrics=s.metrics||{};
 let h='<div class="gci-controls"><label>Displayed mesh<select id="gci-mesh"><option value="auto" '+(gciMesh==='auto'?'selected':'')+'>Follow active calculation</option>'+cached.activity.mesh_gci.meshes.map(v=>'<option value="'+v.id+'" '+(gciMesh===v.id?'selected':'')+'>'+gciCells(v.cells)+' · '+esc(v.role)+'</option>').join('')+'</select></label><button id="gci-range" class="button secondary">'+(gciFull?'Show recent 0.8 s':'Show full saved history')+'</button></div>';
 h+='<p class="gci-stage"><b>'+gciCells(m.cells)+' · '+esc(m.role)+'</b> · '+esc(GCI_STATES[m.status]||m.status)+'<br>'+esc(m.phase==='pilot'?'CFL screening; force stabilization not yet assessed':m.phase==='settling'?'Force stabilization':m.phase==='later_window'?'Later-window check':'Awaiting calculation')+' · t = '+num(m.time_s,4)+' s · Δt '+num(m.dt_s*1000,3)+' ms · '+num(m.inner,0)+' inner iterations</p>';
 if(!s.ready)h+='<div class="gci-callout">Insufficient history for the 0.5% test. Current continuation: '+num(m.history_duration_s,4)+' s. Two 0.2 s windows are needed for one check; two successive passing checks are required.</div>';
 else h+='<div class="gci-callout">'+(s.confirmed?'All four coefficients passed two consecutive stabilization checks.':s.pass_all?'Current windows pass; confirmation is still pending.':'One or more coefficients have not reached the 0.5% criterion.')+'</div>';
 h+='<div class="gci-metrics">'+GCI_KEYS.map(k=>{const q=metrics[k];return '<div class="gci-metric"><small>'+GCI_NAMES[k]+'</small><b>'+num(m.latest?.[k],6)+'</b><small>Latest · instantaneous</small>'+(q?'<small class="'+(q.pass?'pass':'fail')+'">Mean change '+num(q.mean_change_pct,3)+'%<br>Max. window RMS '+num(q.rms_pct?.every(Number.isFinite)?Math.max(...q.rms_pct):null,3)+'%</small>':'<small>Settling check pending</small>')+'</div>'}).join('')+'</div>';
 h+='<div class="gci-plots">'+GCI_KEYS.map((k,i)=>'<section class="gci-plot"><h3>'+GCI_NAMES[k]+' · convergence</h3>'+gciPlot([{id:m.id,label:gciCells(m.cells),color:GCI_COLORS[k],points:points.map(p=>[p[0],p[i+1]])}],{label:GCI_NAMES[k]+' versus physical time'})+'<p class="gci-chart-note">Physical time [s] · dimensionless coefficient</p></section>').join('')+'</div>';
 h+='<section class="gci-plot"><h3>Stabilization error · limit 0.5%</h3>'+gciPlot(GCI_KEYS.map((k,i)=>({label:GCI_NAMES[k],color:GCI_COLORS[k],points:(m.convergence||[]).map(p=>[p[0],p[i+1]])})),{threshold:.5,yPercent:true,label:'Maximum of adjacent-window mean change and within-window RMS, in percent'})+'<p class="gci-chart-note">Each line is the larger of the mean change and the RMS in either 0.2 s window. Dashed line: 0.5%. Statistics use all raw samples; chart traces are reduced only for display.</p></section>';
 h+='<p class="gci-chart-note">Flow CFL '+num(m.cfl,2)+' · interface CFL '+num(m.interface_cfl,3)+' · mean y+ '+num(m.mean_yplus,3)+' · max y+ '+num(m.max_yplus,1)+'. Local y+ exceedances remain available for review.</p>';
 return h;
}
function gciComparison(g){
 let h='<div class="gci-controls"><label>Comparison quantity<select id="gci-compare-metric">'+GCI_KEYS.map(k=>'<option value="'+k+'" '+(gciMetric===k?'selected':'')+'>'+GCI_NAMES[k]+'</option>').join('')+'</select></label></div>';
 const index=GCI_KEYS.indexOf(gciMetric)+1;
 const series=g.meshes.map(m=>({id:m.id,label:gciCells(m.cells),color:GCI_MESH_COLORS[m.id],points:(m.series||[]).map(p=>[p[0],p[index]])}));
 h+='<section class="gci-plot"><h3>'+GCI_NAMES[gciMetric]+' · mesh histories</h3>'+gciPlot(series,{label:'Comparison of '+GCI_NAMES[gciMetric]+' histories across meshes'})+'<p class="gci-chart-note">Physical time [s]. Only saved calm-water continuations are included. Pilot and transient samples are provisional.</p></section>';
 const values=g.meshes.map(m=>{const s=m.stability||{},q=s.metrics?.[gciMetric],confirmed=s.confirmed===true&&q?.pass===true;const v=confirmed?q.mean:m.latest?.[gciMetric];return {label:gciCells(m.cells)+(confirmed?' · stabilized':' · provisional'),color:GCI_MESH_COLORS[m.id],points:Number.isFinite(v)?[[m.cells,v,confirmed]]:[]}});
 h+='<section class="gci-plot"><h3>'+GCI_NAMES[gciMetric]+' · result versus cell count</h3>'+gciPlot(values,{scatter:true,xCells:true,label:'Coefficient versus number of mesh cells'})+'<p class="gci-chart-note">Cell count →. Filled points: confirmed stabilized means over the last 0.4 s. Hollow points: latest provisional samples; these do not establish mesh agreement.</p></section>';
 const waiting=g.meshes.filter(m=>!m.series?.length);
 if(waiting.length)h+='<p class="gci-callout">Awaiting flow results: '+waiting.map(m=>gciCells(m.cells)).join(', ')+'. No values are invented for uncomputed meshes.</p>';
 h+='<p class="gci-chart-note">GCI: '+esc(String(g.gci_status||'pending').replaceAll('_',' '))+'. A stable force trace alone is not proof of mesh independence. This study covers calm water only.</p>';
 return h;
}
function gciAudit(g){
 return '<div class="gci-audit-grid">'+g.meshes.map(m=>'<article class="gci-audit-card '+(m.active?'active':'')+'"><div class="eyebrow">'+esc(m.role)+'</div><h3>'+Number(m.cells).toLocaleString('en-GB')+' cells</h3><span class="pill '+(m.geometry_pass?'':'warning')+'">'+(m.geometry_pass?'Geometry audit passed':'Audit pending')+'</span><p>Flow: '+esc(GCI_STATES[m.status]||m.status)+'<br>Current time: '+num(m.time_s,4)+' s</p><p>Min. cell quality '+num(m.quality?.min_cell_quality,4)+'<br>Min. face validity '+num(m.quality?.min_face_validity,3)+'<br>Max. skewness '+num(m.quality?.max_skewness_angle_deg,2)+'°<br>Negative-volume cells '+num(m.quality?.NegativeVolumeCells,0)+'</p></article>').join('')+'</div><p class="gci-chart-note">Systematic refinement covers the in-plane mesh and the whole prism layer. One spanwise cell is retained; this is an in-plane convergence study. Geometry approval, force stabilization and GCI are separate checks.</p>';
}
function renderMeshGci(d,online){
 const g=d.activity?.mesh_gci,host=el('mesh-gci');
 host.classList.toggle('hidden',!g);if(!g)return;
 const key=[gciTab,gciMesh,gciMetric,gciFull].join('|');
 if(gciRendered.data===g&&gciRendered.online===online&&gciRendered.key===key)return;
 if(host.contains(document.activeElement)&&document.activeElement.tagName==='SELECT'&&gciRendered.data!==g)return;
 gciRendered={data:g,online,key};
 const selected=g.meshes.find(m=>m.id===gciMesh)||(g.meshes.find(m=>m.active))||g.meshes.find(m=>m.id==='G10_F')||g.meshes[0];
 const active=g.meshes.find(m=>m.active),label=!online?'Offline · saved status':g.solver_alive?'CPU calculation active':g.controller_alive?'CPU queue active':'Check recorded status';
 let h='<div class="gci-top"><div><div class="eyebrow">W01a domain · CPU mesh study</div><h2>Mesh convergence</h2></div><span class="pill '+(!online||g.status==='review'?'warning':'')+'">'+label+'</span></div><p>Calm water · a fine reference for a lightweight production mesh.</p>';
 h+='<div class="gci-summary"><div><b>≈300k</b><small>Target cell count</small></div><div><b>'+num(g.workers,0)+' CPU</b><small>Cores 0–1 reserved for C01</small></div><div><b>'+num(g.geometry_gates_passed,0)+'/'+num(g.geometry_gates_total,0)+'</b><small>Geometry checks passed</small></div></div>';
 h+='<p class="gci-stage">'+(active?gciCells(active.cells)+' · '+esc(active.role)+' · '+esc(GCI_STATES[active.status]||active.status)+' · last sample '+num(active.sample_age_s,0)+' s ago':esc(String(g.controller_status||'Waiting').replaceAll('_',' ')))+'</p>';
 h+='<div class="gci-tabs" role="tablist" aria-label="Mesh study views">'+[['convergence','Convergence'],['comparison','Compare meshes'],['audit','Mesh audit']].map(([id,label])=>'<button type="button" role="tab" id="gci-tab-'+id+'" data-gci-tab="'+id+'" aria-selected="'+(gciTab===id)+'" aria-controls="gci-content">'+label+'</button>').join('')+'</div><div id="gci-content" role="tabpanel" aria-labelledby="gci-tab-'+gciTab+'">'+(gciTab==='comparison'?gciComparison(g):gciTab==='audit'?gciAudit(g):gciConvergence(selected))+'</div>';
 host.innerHTML=h;
 host.querySelectorAll('[data-gci-tab]').forEach(b=>b.onclick=()=>{gciTab=b.dataset.gciTab;render()});
 if(el('gci-mesh'))el('gci-mesh').onchange=e=>{gciMesh=e.target.value;render()};
 if(el('gci-range'))el('gci-range').onclick=()=>{gciFull=!gciFull;render()};
 if(el('gci-compare-metric'))el('gci-compare-metric').onchange=e=>{gciMetric=e.target.value;render()};
}
"""
p=D/'worker/dashboard.js';t=p.read_text(encoding='utf-8')
assert 'function renderMeshGci' not in t
t=t.replace('</style></head>',css+'</style></head>',1)
t=t.replace('<section id="activity"', '<section id="mesh-gci" class="gci-panel hidden" aria-label="Calm-water mesh convergence"></section><section id="activity"',1)
t=t.replace('function render(){',js+'\nfunction render(){',1)
assert t.count('renderActivity(d,online);')==1
t=t.replace('renderActivity(d,online);','renderActivity(d,online);renderMeshGci(d,online);',1)
t=t.replace("path==='/api/snapshot'?250000:25000000","path==='/api/snapshot'?750000:25000000")
p.write_text(t,encoding='utf-8')
p=D/'uploader.py';t=p.read_text()
assert 'from mesh_gci_activity import collect_mesh_gci' not in t
t=t.replace('from mesh_activity import collect_mesh_activity','from mesh_activity import collect_mesh_activity\nfrom mesh_gci_activity import collect_mesh_gci',1)
assert t.count("activity['mesh_review']=collect_mesh_review(ROOT,read,alive,history)")==1
t=t.replace("activity['mesh_review']=collect_mesh_review(ROOT,read,alive,history)","activity['mesh_review']=collect_mesh_review(ROOT,read,alive,history)\n    activity['mesh_gci']=collect_mesh_gci(read,alive)",1)
p.write_text(t,encoding='utf-8')
print('Added calm mesh telemetry and three mobile dashboard views.')
