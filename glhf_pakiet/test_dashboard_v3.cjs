const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const assert=require('node:assert/strict'),fs=require('node:fs');
const qa='E:/NWAR_portable_20261103/QA_v3';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--disable-gpu']});
 try{
  for(const [release,port] of [['2602',19782],['2606',19783]]){
   const page=await browser.newPage({viewport:{width:1280,height:1040}}),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   const base='http://127.0.0.1:'+port;
   const before=await(await page.request.get(base+'/api/status')).json();
   const real=await(await page.request.get('http://127.0.0.1:8782/api/wave-view?case=W04')).json();
   assert.equal(real.cycle_policy_id,'five_measured_cycles_discard_first_20261103');
   assert.ok(real.in_progress_cycle);
   let fixture=structuredClone(real),requests=0;
   const partial=real.in_progress_cycle,half=Math.max(2,Math.floor(partial.phase.length/2));
   for(const key of ['phase','time_s','CL','CD'])fixture.in_progress_cycle[key]=partial[key].slice(0,half);
   fixture.in_progress_cycle.end=fixture.in_progress_cycle.time_s.at(-1);
   await page.route('**/api/wave-view?case=W04',r=>{requests++;return r.fulfill({json:fixture})});
   await page.goto(base);
   await page.waitForFunction(()=>document.querySelector('#view-lift path[data-provisional="true"]'));
   assert.equal(await page.locator('#view-lift path[data-cycle-number="1"]').count(),0);
   assert.match(await page.locator('#view-phase').innerText(),/cycle 1 excluded/);
   const curve=page.locator('#view-lift path[data-provisional="true"]');
   const short=Number(await curve.getAttribute('data-phase-end')),prior=requests;
   fixture=structuredClone(real);
   await page.waitForFunction(v=>Number(document.querySelector('#view-lift path[data-provisional="true"]').dataset.phaseEnd)>v,short,{timeout:20000});
   assert.ok(requests>prior);
   await page.uncheck('#view-cycles input[data-cycle="'+partial.number+'"]');
   await page.click('#view-refresh');await page.waitForTimeout(100);
   assert.equal(await page.isChecked('#view-cycles input[data-cycle="'+partial.number+'"]'),false);
   await page.check('#view-cycles input[data-cycle="'+partial.number+'"]');
   const probeBefore=await page.locator('#view-probes svg path').last().getAttribute('d');
   await page.fill('#view-probe-phase-value','90');
   assert.equal(await page.inputValue('#view-probe-phase'),'90');
   const probeAfter=await page.locator('#view-probes svg path').last().getAttribute('d');
   assert.notEqual(probeBefore,probeAfter);
   await page.click('#view-probe-phase-reset');assert.equal(await page.inputValue('#view-probe-phase-value'),'0');
   await page.locator('#wave-explorer').screenshot({path:qa+'/dashboard_'+release+'.png'});
   // Browser-only completion fixture: the final bar stops at five, with no sixth curve.
   fixture={...real,cycle_count:5,in_progress_cycle:null,cycle_progress:{...real.cycle_progress,complete:true,percent:100,cycle_number:5,state:'saved'},cycles:[...real.cycles,{...real.cycles.at(-1),number:5}]};
   await page.click('#view-refresh');await page.waitForFunction(()=>document.querySelector('#view-cycle-eta').textContent.includes('Recorded'));
   assert.equal(await page.locator('#view-lift path[data-cycle-number="6"]').count(),0);
   await page.selectOption('#view-case','W06');await page.waitForFunction(()=>document.querySelector('#view-status').textContent.includes('no recorded samples'));
   assert.match(await page.locator('#view-cycle-progress-title').innerText(),/W06/);
   await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   const after=await(await page.request.get(base+'/api/status')).json();assert.deepEqual(after.jobs.map(j=>j.id),before.jobs.map(j=>j.id));assert.deepEqual(errors,[]);
   const proof={passed:true,release,growing_live_curve:true,phase_controls:true,first_cycle_excluded:true,stops_at_five:true,next_wave_layout:true,mobile:true,jobs_unchanged:true,page_errors:errors};
   fs.writeFileSync(qa+'/browser_'+release+'.json',JSON.stringify(proof,null,2));console.log(JSON.stringify(proof));
   await page.close();
  }
  const verification=JSON.parse(fs.readFileSync(qa+'/verification.json'));
  verification.browser=Object.fromEntries(['2602','2606'].map(v=>[v,JSON.parse(fs.readFileSync(qa+'/browser_'+v+'.json'))]));
  fs.writeFileSync(qa+'/verification.json',JSON.stringify(verification,null,2));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
