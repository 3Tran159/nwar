/* Percent units: .5 means 0.5%, never a fraction of one. */
(()=>{'use strict';
const fmt=(v,n=3)=>v==null?'—':Number(v).toLocaleString('en-GB',{maximumFractionDigits:n,minimumFractionDigits:n});
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
window.renderConvergenceChart=(container,pre)=>{
 const rows=(pre.live.convergence||[]).filter(r=>r.complete&&(r.elapsed_s==null||r.elapsed_s>=(pre.live.ramp_s||0)+.4-1e-6)),latest=rows.at(-1),threshold=.5;
 const status=pre.error?'Preparation stopped: '+pre.error:pre.receipt?.passed?'Calm gate passed. Original C01 remains the Q reference.':latest?.stable_reference_mismatch?'Stable flow differs from C01. Wave blocked.':latest?'Consecutive compatible checks: '+latest.consecutive_compatible+' / 2. Wave starts only after the saved checkpoint is verified.':pre.phase==='calm_running'?'Collecting two full 0.2 s windows for the first comparison.':'Waiting for calm calculation. '+pre.label+'.';
 let svg='';const width=920,height=474,left=72,right=900;
 const t0=rows.length?rows[0].time_s:0,t1=rows.length?rows.at(-1).time_s:1,span=Math.max(.2,t1-t0),x=t=>left+(t-t0)/span*(right-left);
 for(const [index,suffix,title] of [[0,'stability_pct','Window stability · max(mean change, previous RMS, current RMS)'],[1,'C01_pct','Mean deviation from original C01']]){
  const top=35+index*230,bottom=top+150;
  const vals=rows.flatMap(r=>[r['CD_'+suffix],r['CL_'+suffix]]).filter(Number.isFinite);
  const high=Math.max(1,...vals)*1.12,y=v=>bottom-v/high*(bottom-top);
  svg+='<text x="'+left+'" y="'+(top-15)+'" class="axis-label">'+title+'</text>';
  for(let j=0;j<=4;j++){
   const v=high*j/4,yy=y(v);svg+='<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" class="plot-grid"/><text x="'+(left-8)+'" y="'+(yy+4)+'" text-anchor="end">'+fmt(v,2)+'%</text>';
  }
  svg+='<rect x="'+left+'" y="'+y(threshold)+'" width="'+(right-left)+'" height="'+(bottom-y(threshold))+'" fill="#087f8c" opacity=".07"/>';
  svg+='<line class="convergence-threshold" x1="'+left+'" x2="'+right+'" y1="'+y(threshold)+'" y2="'+y(threshold)+'" stroke="#b64737" stroke-width="1.5" stroke-dasharray="6 4"/><text x="'+right+'" y="'+(y(threshold)-6)+'" text-anchor="end" fill="#b64737">0.5%</text>';
  for(const [name,color] of [['CD','#087f8c'],['CL','#c17a19']]){
   const data=rows.filter(r=>Number.isFinite(r[name+'_'+suffix]));
   svg+='<path class="convergence-curve" d="'+data.map((r,i)=>(i?'L':'M')+x(r.time_s)+','+y(r[name+'_'+suffix])).join(' ')+'" fill="none" stroke="'+color+'" stroke-width="1.8"/>';
   for(const r of data)svg+='<circle cx="'+x(r.time_s)+'" cy="'+y(r[name+'_'+suffix])+'" r="3" fill="'+color+'"><title>'+name+': '+fmt(r[name+'_'+suffix],4)+'% at '+fmt(r.time_s,4)+' s</title></circle>';
  }
  for(let j=0;j<=5;j++){const t=t0+span*j/5;svg+='<text x="'+x(t)+'" y="'+(bottom+20)+'" text-anchor="middle">'+fmt(t,2)+'</text>'}
 }
 svg+='<text x="485" y="470" text-anchor="middle" class="axis-label">Physical time [s]</text>';
 const table=latest?'<div class="table-wrap"><table><tr><th>Latest 0.2 s window</th><th>Cx</th><th>Cz</th></tr>'+[['Mean','mean'],['Stability [%]','stability_pct'],['Deviation from C01 [%]','C01_pct']].map(([title,suffix])=>'<tr><td>'+title+'</td><td>'+fmt(latest['CD_'+suffix],suffix==='mean'?7:4)+'</td><td>'+fmt(latest['CL_'+suffix],suffix==='mean'?7:4)+'</td></tr>').join('')+'</table></div>':'';
 container.innerHTML='<p class="pre-gate-status">'+esc(status)+'</p><div class="history-legend"><span style="color:#087f8c">● Cx</span> &nbsp; <span style="color:#c17a19">● Cz</span> &nbsp; Dashed red line: 0.5% threshold</div><div class="history-scroll"><svg viewBox="0 0 '+width+' '+height+'" role="img" aria-label="PRE W04 Cz and Cx convergence with 0.5 percent threshold">'+svg+'</svg></div>'+table+'<p class="note">Original C01: Cx = '+fmt(pre.live.reference.CD,8)+' · Cz = '+fmt(pre.live.reference.CL,8)+'. Fresh start with a 1 s ramp from rest to 18 m/s. First eligible stability check at t = '+fmt(pre.live.convergence_eligible_s??1.6,1)+' s, after the ramp. Full samples remain saved.</p>';
};
})();
