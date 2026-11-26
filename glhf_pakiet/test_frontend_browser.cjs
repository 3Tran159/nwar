const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs'),crypto=require('node:crypto'),{execFileSync}=require('node:child_process');
const qa='E:/NWAR_portable_20261103/QA_frontend',patch='E:/NWAR_portable_20261103/NWAR_GLHF_UI_hotfix';
const hash=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-gpu']});
 try{
  const request=await browser.newPage(),source='http://127.0.0.1:8782';
  const state=await(await request.request.get(source+'/api/status')).json();
  const current=await(await request.request.get(source+'/api/wave-view?case=W04')).json();
  const before=Object.fromEntries(['2602','2606'].map(v=>[v,JSON.parse(fs.readFileSync(qa+'/live_workspaces/'+v+'/data/server.json'))]));
  const fingerprints=Object.fromEntries(['2602','2606'].map(v=>[v,Object.fromEntries(['server.py','worker.py','NwarWave.java','analysis.py','common.py','wave_view.py'].map(n=>[n,hash(qa+'/live_workspaces/'+v+'/app/'+n)]))]));
  // The old Python servers remain running throughout this actual on-disk installation.
  const installed=execFileSync('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe',[patch+'/apply_frontend_patch.py','--package',qa+'/live_package'],{encoding:'utf8'});
  fs.writeFileSync(qa+'/hot_apply.log',installed);
  const checks=[];
  for(const [release,port] of [['2602',20782],['2606',20783]]){
   const base='http://127.0.0.1:'+port;
   const metadata=JSON.parse(fs.readFileSync(qa+'/live_workspaces/'+release+'/data/server.json'));
   assert.equal(metadata.pid,before[release].pid);assert.equal(metadata.birth,before[release].birth);
   const fetched=await(await request.request.get(base+'/wave_view.js')).body();
   assert.equal(crypto.createHash('sha256').update(fetched).digest('hex'),hash(patch+'/payload/wave_view.js'));
   for(const [n,h] of Object.entries(fingerprints[release]))assert.equal(hash(qa+'/live_workspaces/'+release+'/app/'+n),h);
   for(const mode of ['original','v2','v3']){
    const page=await browser.newPage({viewport:{width:1280,height:1040}}),errors=[],posts=[];
    page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')posts.push(r.url())});
    let payload=structuredClone(current);
    if(mode!=='v3'){
     delete payload.cycle_policy_id;delete payload.target_complete_cycles;
     payload.cycles=[...(current.excluded_cycles||[]),...current.cycles].slice(-4);
     if(mode==='original'){delete payload.cycle_progress;delete payload.in_progress_cycle;}
    }
    await page.route('**/api/status',r=>r.fulfill({json:state}));
    await page.route('**/api/wave-view?case=W04',r=>r.fulfill({json:payload}));
    await page.goto(base);
    await page.waitForFunction(()=>document.querySelector('#view-lift path[data-provisional="true"]'));
    assert.match(await page.locator('#view-cycle-progress-title').innerText(),/in progress/);
    if(mode==='v3')assert.equal(await page.locator('#view-lift path[data-cycle-number="1"]').count(),0);
    else assert.match(await page.locator('#view-phase').innerText(),/installed backend/);
    const beforePath=await page.locator('#view-probes svg path').last().getAttribute('d');
    await page.fill('#view-probe-phase-value','90');assert.equal(await page.inputValue('#view-probe-phase'),'90');
    assert.notEqual(await page.locator('#view-probes svg path').last().getAttribute('d'),beforePath);
    await page.click('#view-probe-phase-reset');
    if(mode==='original')await page.locator('#wave-explorer').screenshot({path:qa+'/ui_hot_'+release+'.png'});
    await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    assert.deepEqual(errors,[]);assert.deepEqual(posts,[]);
    checks.push({release,backend:mode,passed:true,live_partial_curve:true,phase_controls:true,no_mutating_requests:true,server_pid_unchanged:true,backend_files_unchanged:true});
    await page.close();
   }
  }
  fs.writeFileSync(qa+'/browser.json',JSON.stringify({passed:true,checks},null,2));console.log(JSON.stringify({passed:true,scenarios:checks.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
