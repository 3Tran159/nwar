/* Full time history with separate coefficient scales and explicit restart markers. */
(()=>{'use strict';
const fmt=(v,n=4)=>Number(v).toLocaleString('en-GB',{minimumFractionDigits:n,maximumFractionDigits:n});
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
window.renderHistoryChart=(container,live,options={})=>{
 const segments=(live.history_segments||[{points:live.series||[]}]).map(s=>({...s,points:s.points.filter(r=>options.fromTime==null||r[0]>=options.fromTime-1e-9)})).filter(s=>s.points.length);
 const points=segments.flatMap(s=>s.points).filter(r=>r.every(Number.isFinite));
 if(points.length<2){container.innerHTML='<p>'+ (options.fromTime==null?'Waiting for domain force history.':'Waiting for domain force samples after the speed ramp.')+'</p>';return}
 const reference=live.force_reference||live.reference;
 if(!reference||!Number.isFinite(reference.CD)||!Number.isFinite(reference.CL)){container.innerHTML='<p>Waiting for the original C01 reference.</p>';return}
 const width=920,height=422,left=85,right=900,t0=Math.min(...points.map(r=>r[0])),t1=Math.max(...points.map(r=>r[0])),dt=t1-t0||1;
 const x=t=>left+(t-t0)/dt*(right-left),markers=(live.resume_markers||[]).filter(m=>m.time_s>=t0&&m.time_s<=t1);
 const absolute=options.absolute===true,scale=options.forceScale||1;
 const [xName,zName]=options.forceScale?['Fx','Fz']:['Cx','Cz'];
 const units=options.forceScale?' [N]':'';
 let svg='<title>'+ (absolute?'Normalized domain forces Cx and Cz':'Domain force differences from original C01')+'; dashed vertical lines mark resumes</title>';
 for(let k=1;k<=2;k++){
  const top=k===1?32:226,bottom=top+145,base=k===1?reference.CD:reference.CL,offset=absolute?0:base,target=absolute?base*scale:0,values=points.map(r=>(r[k]-offset)*scale);
  const band=options.showC01Band?Math.abs(base)*scale*.005:0;
  let low=Math.min(target-band,...values),high=Math.max(target+band,...values),pad=(high-low)*.08||Math.max(Math.abs(low)*.02,.00001);low-=pad;high+=pad;
  const y=v=>bottom-(v-low)/(high-low)*(bottom-top),color=k===1?'#087f8c':'#c17a19';
  svg+='<text x="10" y="'+(top-10)+'" class="axis-label">'+(absolute?'':'Δ')+(k===1?xName:zName)+units+'</text>';
  if(markers.length){const last=markers.at(-1).time_s;svg+='<rect x="'+x(last)+'" y="'+top+'" width="'+Math.max(0,right-x(last))+'" height="145" fill="#edf7f5"/>'}
  if(options.showC01Band){
   svg+='<rect class="c01-tolerance-band" x="'+left+'" y="'+y(target+band)+'" width="'+(right-left)+'" height="'+(y(target-band)-y(target+band))+'" fill="#76ba9a" opacity=".2"/>';
   for(const limit of [target-band,target+band])svg+='<line x1="'+left+'" x2="'+right+'" y1="'+y(limit)+'" y2="'+y(limit)+'" stroke="#338565" stroke-dasharray="2 3"/>';
  }
  for(let j=0;j<=4;j++){
   const value=low+(high-low)*j/4,yy=y(value);
   svg+='<line x1="'+left+'" x2="'+right+'" y1="'+yy+'" y2="'+yy+'" class="plot-grid"/><text x="'+(left-9)+'" y="'+(yy+4)+'" text-anchor="end">'+fmt(value,options.forceScale?1:k===1?5:4)+'</text>';
  }
  for(let j=0;j<=6;j++){
   const time=t0+dt*j/6,xx=x(time);
   svg+='<line x1="'+xx+'" x2="'+xx+'" y1="'+top+'" y2="'+bottom+'" class="plot-grid"/><text x="'+xx+'" y="'+(bottom+20)+'" text-anchor="middle">'+fmt(time,2)+'</text>';
  }
  svg+='<path d="M'+left+','+top+' V'+bottom+' H'+right+'" fill="none" stroke="#83969c"/>';
  svg+='<line class="c01-reference" x1="'+left+'" x2="'+right+'" y1="'+y(target)+'" y2="'+y(target)+'" stroke="#526674" stroke-width="1.1" stroke-dasharray="3 3"><title>Original C01</title></line>';
  for(const segment of segments){
   const d=segment.points.map((r,i)=>(i?'L':'M')+x(r[0]).toFixed(2)+','+y((r[k]-offset)*scale).toFixed(2)).join(' ');
   svg+='<path class="history-curve" d="'+d+'" fill="none" stroke="'+color+'" stroke-width="1.6"/>';
  }
  for(const [i,m] of markers.entries()){
   svg+='<line class="resume-marker" data-time="'+m.time_s+'" x1="'+x(m.time_s)+'" x2="'+x(m.time_s)+'" y1="'+(top-8)+'" y2="'+bottom+'" stroke="#536670" stroke-width="1.3" stroke-dasharray="6 4"/><text x="'+x(m.time_s)+'" y="'+(top-12)+'" text-anchor="middle">↻ '+(i+1)+'</text>';
  }
  svg+='<line class="history-cursor" y1="'+top+'" y2="'+bottom+'" stroke="#a65b08" visibility="hidden"/>';
 }
 svg+='<text x="492" y="418" text-anchor="middle" class="axis-label">Physical time t [s]</text>';
 const restart=markers.map((m,i)=>'↻ '+(i+1)+' Resume: '+fmt(m.time_s)+' s').join(' · ');
 const context=options.showC01Band?'After the speed ramp at t = '+fmt(options.fromTime,2)+' s · Green band: ±0.5% of C01. Window stability is checked below.':live.history_label||'History from wave start at C01';
 const definition=absolute?'Cx and Cz (normalized domain forces) · Dashed line: original C01':'Δ'+xName+' / Δ'+zName+units+' · Fixed domain axes · Zero = original C01';
 container.innerHTML='<div class="history-scroll"><svg viewBox="0 0 '+width+' '+height+'" role="img" data-reference="C01" data-mode="'+(absolute?'coefficients':'differences')+'" aria-label="'+esc(definition)+'">'+svg+'</svg></div><div class="history-legend">'+esc(definition)+'<br>'+esc(context)+(restart?'<br>'+esc(restart):'')+'</div><div class="history-readout">Point at the plot to read force differences and absolute values.</div><div class="note">'+(options.fromTime==null?fmt(live.history_samples||points.length,0)+' samples · ':'')+esc(live.display_sampling||'')+'</div>'+(live.history_warnings||[]).map(w=>'<p class="check-failed">'+esc(w)+'</p>').join('');
 const scroll=container.querySelector('.history-scroll');
 if(scroll.scrollWidth>scroll.clientWidth+1)scroll.insertAdjacentHTML('afterend','<p class="note">Swipe horizontally to view the full timeline.</p>');
 const canvas=container.querySelector('svg');
 canvas.onpointermove=event=>{
  const pt=new DOMPoint(event.clientX,event.clientY).matrixTransform(canvas.getScreenCTM().inverse()),target=t0+Math.max(0,Math.min(1,(pt.x-left)/(right-left)))*dt;
  const near=points.reduce((best,r)=>Math.abs(r[0]-target)<Math.abs(best[0]-target)?r:best,points[0]);
  container.querySelector('.history-readout').textContent='t = '+fmt(near[0])+' s · Δ'+xName+' = '+fmt((near[1]-reference.CD)*scale,options.forceScale?2:6)+units+' · Δ'+zName+' = '+fmt((near[2]-reference.CL)*scale,options.forceScale?2:6)+units+' · '+xName+' = '+fmt(near[1]*scale,options.forceScale?2:6)+units+' · '+zName+' = '+fmt(near[2]*scale,options.forceScale?2:6)+units;
  container.querySelectorAll('.history-cursor').forEach(line=>{line.setAttribute('x1',x(near[0]));line.setAttribute('x2',x(near[0]));line.setAttribute('visibility','visible')});
 };
};
})();
