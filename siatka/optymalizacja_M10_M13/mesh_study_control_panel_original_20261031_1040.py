"""Small live controls for the independent mesh campaign."""
def panel():
 return r'''<section id="mesh-run-controls" style="border:1px solid #cbd7df;border-left:4px solid #318367;padding:16px;margin:16px 0;background:#f3f8f5;break-inside:avoid">
<h3 style="margin:0 0 8px">Mesh calculation · pause and resume</h3>
<p data-mesh-control-status role="status" aria-live="polite">Reading the current mesh calculation…</p>
<div style="display:flex;gap:10px;flex-wrap:wrap"><button type="button" data-mesh-action="pause" disabled style="font:inherit;padding:10px 16px;cursor:pointer">Pause &amp; save</button><button type="button" data-mesh-action="resume" disabled style="font:inherit;padding:10px 16px;cursor:pointer">Resume saved calculation</button></div>
<p data-mesh-control-message role="status" style="margin:10px 0 0"></p>
<small>Controls M10–M12 mesh tests. Pause finishes the current step and saves the calculated fields. Wait for <b>Paused and saved</b> before disconnecting power. Wave controls remain separate.</small>
</section><script>
(()=>{
const root=document.getElementById('mesh-run-controls');if(!root||root.dataset.bound)return;root.dataset.bound='1';
let state=null,busy=false;
const note=root.querySelector('[data-mesh-control-status]'),msg=root.querySelector('[data-mesh-control-message]');
function show(){
 if(!state)return;
 note.textContent=(state.job?state.job+' · ':'')+state.message;
 root.querySelector('[data-mesh-action=pause]').disabled=busy||!state.can_pause;
 root.querySelector('[data-mesh-action=resume]').disabled=busy||!state.can_resume;
 if(state.file){note.append(document.createElement('br'));const path=document.createElement('code');path.style.overflowWrap='anywhere';path.textContent=state.file;note.append(path)}
}
async function refresh(){
 if(location.protocol==='file:'){note.textContent='Use the local control server to pause or resume: http://127.0.0.1:8771/';return}
 try{const r=await fetch('/api/mesh-study',{cache:'no-store'});const d=await r.json();if(!r.ok)throw Error(d.error||'Control status unavailable');state=d;show()}
 catch(e){note.textContent=e.message;root.querySelectorAll('button').forEach(b=>b.disabled=true)}
}
root.querySelectorAll('[data-mesh-action]').forEach(b=>b.addEventListener('click',async()=>{
 if(busy||!state)return;
 if(!window.NTNU_LOCAL_TOKEN){msg.textContent='Open http://127.0.0.1:8771/ to use local controls.';return}
 busy=true;show();msg.textContent=b.dataset.meshAction==='pause'?'Requesting safe save…':'Verifying saved continuation…';
 try{const r=await fetch('/api/mesh-study/'+b.dataset.meshAction,{method:'POST',headers:{'Content-Type':'application/json','X-NTNU-Control':window.NTNU_LOCAL_TOKEN},body:JSON.stringify({generation:state.generation})});const d=await r.json();if(!r.ok)throw Error(d.error||'Action refused');msg.textContent=d.message}
 catch(e){msg.textContent=e.message}
 finally{busy=false;await refresh()}
}));
refresh();setInterval(refresh,3000);
})();
</script>'''
