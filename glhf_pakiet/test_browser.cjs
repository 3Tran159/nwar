const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const out=process.env.NWAR_QA_DIR||'E:/NWAR_portable_20261103/QA';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-gpu']});
 const results=[];
 try {
  for(const [release,port] of [['2602',18782],['2606',18783]]) {
   const page=await browser.newPage({viewport:{width:1280,height:1000}}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   const base='http://127.0.0.1:'+port;
   await page.goto(base);await page.waitForFunction(()=>document.querySelectorAll('#wave-grid .wave').length>0);
   assert.match(await page.locator('.heading .eyebrow').innerText(),new RegExp(release));
   const real=await(await page.request.get(base+'/api/status')).json();
   assert.equal(real.preparation.active,false);assert.equal(real.preparation.receipt.passed,true);
   assert.ok(real.catalog.every(c=>c.ready));
   assert.ok(real.jobs.every(j=>j.status==='cancelled'));
   await page.selectOption('#view-case','W04');await page.click('#view-refresh');
   await page.waitForFunction(()=>document.querySelector('#view-status').textContent.includes('no recorded samples'));
   assert.equal(await page.locator('#view-lift .view-empty').count(),1);
   assert.equal(await page.locator('#view-drag .view-empty').count(),1);
   assert.equal(await page.locator('#view-cycle-progress').getAttribute('aria-valuenow'),'0');
   await page.locator('#wave-explorer').screenshot({path:out+'/portable_'+release+'_empty.png'});
   const token=await page.locator('meta[name=nwar-token]').getAttribute('content');
   assert.equal((await page.request.post(base+'/api/custom-wave',{data:{H:1.6,L:40,request_key:'portable-ui-test'}})).status(),403);
   assert.equal((await page.request.post(base+'/api/custom-wave',{headers:{'X-NWAR-Token':token},data:{H:1.6,L:40,request_key:'portable-ui-test'}})).status(),400);
   const report=await page.request.get(base+'/report');assert.equal(report.status(),200);
   // Read-only snapshots of the existing W04 are used ONLY as browser route fixtures.
   const sample=await(await page.request.get('http://127.0.0.1:8782/api/wave-view?case=W04')).json();
   assert.equal(sample.case_id,'W04');assert.ok(sample.probes.length>1);
   await page.route('**/api/wave-view?case=W04',r=>r.fulfill({json:sample}));
   await page.click('#view-refresh');await page.waitForFunction(()=>document.querySelector('#view-probe-a').options.length>1);
   assert.ok(Number(await page.locator('#view-cycle-progress').getAttribute('aria-valuenow'))>0);
   await page.fill('#view-probe-phase-value','90');await page.locator('#view-probe-phase-value').dispatchEvent('input');
   assert.match(await page.locator('#view-probe-phase-note').innerText(),/90/);
   await page.click('#view-probe-phase-reset');assert.equal(await page.inputValue('#view-probe-phase-value'),'0');
   await page.selectOption('#view-units','coefficient');await page.selectOption('#view-range','all');
   await page.reload();await page.waitForFunction(()=>document.querySelector('#view-case').value==='W04');
   assert.equal(await page.inputValue('#view-units'),'coefficient');assert.equal(await page.inputValue('#view-range'),'all');
   await page.locator('#wave-explorer').screenshot({path:out+'/portable_'+release+'_wave_fixture.png'});
   let submitted;
   await page.route('**/api/custom-wave',async r=>{submitted=r.request().postDataJSON();await r.fulfill({status:202,json:{id:'mock-only',case_id:'CUSTOM999',message:'Custom wave saved.'}})});
   await page.fill('#custom-height','1.51');await page.click('#custom-submit');assert.equal(submitted,undefined);
   await page.fill('#custom-height','1.5');await page.fill('#custom-length','40');await page.click('#custom-submit');
   await page.waitForFunction(()=>document.querySelector('#custom-wave-result').textContent.includes('CUSTOM999'));
   assert.equal(submitted.H,1.5);assert.equal(submitted.L,40);
   await page.setViewportSize({width:390,height:844});
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   await page.locator('#custom-wave-form').screenshot({path:out+'/portable_'+release+'_mobile.png'});
   const after=await(await page.request.get(base+'/api/status')).json();
   assert.deepEqual(after.jobs.map(j=>j.id),real.jobs.map(j=>j.id));assert.deepEqual(errors,[]);
   results.push({release,passed:true,empty_layout:true,progress_with_recorded_fixture:true,probe_phase_control:true,persistent_settings:true,custom_form_bounds:true,mutations_require_token:true,report_accessible:true,mobile_overflow:false,native_solver_started:false,real_queue_unchanged:true,page_errors:errors});
   await page.close();
  }
  fs.writeFileSync(out+'/browser_checks.json',JSON.stringify({passed:true,results},null,2));console.log(JSON.stringify(results));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
