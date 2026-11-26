const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto'),{execFileSync}=require('node:child_process');
const root='E:/NWAR_portable_20261103',qa=root+'/QA_frontend',hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-gpu']});
 try{
  const request=await browser.newPage();
  const actual=await(await request.request.get('http://127.0.0.1:8782/api/status')).json();
  const view=await(await request.request.get('http://127.0.0.1:8782/api/wave-view?case=W04')).json();
  const before=Object.fromEntries(['2602','2606'].map(v=>[v,JSON.parse(fs.readFileSync(qa+'/live_workspaces/'+v+'/data/server.json'))]));
  const fingerprints=Object.fromEntries(['2602','2606'].map(v=>[v,Object.fromEntries(['app.js','server.py','worker.py','NwarWave.java','analysis.py','common.py','wave_view.py'].map(n=>[n,hash(qa+'/live_workspaces/'+v+'/app/'+n)]))]));
  const output=execFileSync('C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe',['-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',root+'/Update-NWAR-Charts-UI3.ps1','-PackageRoot',qa+'/live_package'],{encoding:'utf8'});
  assert.match(output,/LIVE UI 20261103.3 verified/);fs.writeFileSync(qa+'/powershell_hot_apply.log',output);
  const checks=[];
  for(const [release,port] of [['2602',20782],['2606',20783]]){
   const page=await browser.newPage({viewport:{width:1280,height:1040}}),errors=[],posts=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')posts.push(r.url())});
   const state=structuredClone(actual);state.worker_alive=false;
   const run=state.jobs.find(j=>j.id===view.run_id);run.status='needs_attention';run.observed_status='interrupted';run.live.age_s=1;
   const payload=structuredClone(view);payload.status='needs_attention';payload.cycle_count=1;payload.cycles=[{...view.cycles.at(-1),number:1}];
   delete payload.cycle_policy_id;delete payload.cycle_progress;delete payload.in_progress_cycle;
   let requests=0;
   await page.route('**/api/status',r=>r.fulfill({json:state}));
   await page.route('**/api/wave-view?case=W04',r=>{requests++;const next={...payload,time_s:view.time_s-(requests===1?.004:0)};return r.fulfill({json:next})});
   await page.goto('http://127.0.0.1:'+port);
   await page.waitForFunction(()=>document.querySelector('#view-lift path[data-provisional="true"]'),null,{timeout:22000});
   assert.ok(requests>=2,'Must observe increasing physical time');
   assert.equal(await page.locator('#view-lift path[data-provisional="true"]').getAttribute('data-cycle-number'),'2');
   assert.match(await page.locator('#view-status').innerText(),/UI 20261103.3.*controller requires attention/);
   assert.match(await page.locator('#view-cycle-progress-note').innerText(),/Automatic finalization and the next wave are not confirmed/);
   await page.locator('#wave-explorer').screenshot({path:qa+'/controller_lost_ui3_'+release+'.png'});
   const metadata=JSON.parse(fs.readFileSync(qa+'/live_workspaces/'+release+'/data/server.json'));
   assert.equal(metadata.pid,before[release].pid);assert.equal(metadata.birth,before[release].birth);
   for(const [n,h] of Object.entries(fingerprints[release]))assert.equal(hash(qa+'/live_workspaces/'+release+'/app/'+n),h);
   assert.deepEqual(errors,[]);assert.deepEqual(posts,[]);
   checks.push({release,passed:true,dead_controller_and_advancing_history:true,next_cycle_number:2,controller_warning_visible:true,server_pid_unchanged:true,backend_files_unchanged:true,no_mutating_requests:true});
   await page.close();
  }
  fs.writeFileSync(qa+'/controller_lost_ui3_browser.json',JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,scenarios:checks.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
