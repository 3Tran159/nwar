const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1120}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>route.request().method()==='POST'&&!route.request().url().endsWith('/api/report')?route.abort():route.continue());
  await page.goto('http://127.0.0.1:8782',{waitUntil:'networkidle'});
  await page.waitForSelector('#live-chart svg');
  const before=await (await page.request.get('http://127.0.0.1:8782/api/status')).json();
  const job=before.jobs.find(j=>j.case_id==='W02'&&!j.spec.smoke),live=job.live;
  assert(Math.abs(live.history_start_s-4.6992)<1e-7,'History must start at C01');
  assert(live.history_samples>18000,'Entire original history and extension must be loaded');
  assert.equal(live.resume_markers.length,1);assert(Math.abs(live.resume_markers[0].time_s-11.3792)<1e-7);
  assert.equal(await page.locator('.resume-marker').count(),2,'One resume marker on each coefficient axis');
  assert((await page.locator('.history-legend').textContent()).includes('11.3792'));
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  assert((await page.locator('#q-reference').textContent()).includes('27.00 N'));
  assert((await page.locator('#q-table').textContent()).includes('W03e'));
  assert(!/[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/.test(await page.locator('body').textContent()),'Polish text remains in dashboard or collapsed evidence');
  const chart=page.locator('#live-chart svg');await chart.hover({position:{x:450,y:100}});
  assert((await page.locator('.history-readout').textContent()).includes('CD ='));
  await page.locator('.live.card').screenshot({path:path.join(__dirname,'qa/history_desktop.png')});
  await page.locator('#refresh-q').click();assert(await page.locator('#refresh-q').isDisabled());
  await page.waitForFunction(()=>document.querySelector('#refresh-q').textContent==='Update plot'&&!document.querySelector('#refresh-q').disabled,{},{timeout:120000});
  const after=await (await page.request.get('http://127.0.0.1:8782/api/status')).json();
  assert.notEqual(after.report.generated_at,before.report.generated_at);
  const reportDir=after.report.directory,audit=JSON.parse(fs.readFileSync(path.join(reportDir,'audit.json'),'utf8'));
  assert.deepEqual(audit.results.map(r=>r.display_id),['W01','W02','W03e']);
  assert(audit.results.every(r=>r.force_wave_plot),'Every reported run has a force-wave plot');
  assert(!fs.existsSync(path.join(reportDir,'W03_forces.png')),'Old W03 must not be separately exported');
  for(const r of audit.results){
   const response=await page.request.get('http://127.0.0.1:8782/'+after.report.relative+'/'+r.force_wave_plot);assert.equal(response.status(),200);
   if(r.display_id==='W03e'){assert.equal(r.source_segments.length,2);assert.equal(r.resume_markers.length,1)}
  }
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile document overflow');
  await page.locator('.live.card').screenshot({path:path.join(__dirname,'qa/history_mobile.png')});
  await page.goto('http://127.0.0.1:8782/report',{waitUntil:'networkidle'});
  assert.equal(await page.locator('html').getAttribute('lang'),'en');
  const reportText=await page.locator('body').textContent();
  assert(!/[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/.test(reportText),'Polish text remains in report');
  assert((await page.locator('h2').allTextContents()).some(t=>t.startsWith('W03e ·')));
  assert(!(await page.locator('h2').allTextContents()).some(t=>t.startsWith('W03 ·')));
  assert(await page.locator('img').evaluateAll(images=>images.every(im=>im.complete&&im.naturalWidth>0)),'Missing report image');
  assert.equal(errors.length,0);
  const receipt={passed:true,no_solver_started:true,report:after.report.relative,full_history_samples:live.history_samples,start_s:live.history_start_s,end_s:live.history_end_s,resume_s:live.resume_markers.map(m=>m.time_s),English_dashboard_and_report:true,real_update_button:true,current_results:audit.results.map(r=>({id:r.display_id,accepted:r.project_accepted,cycles:r.cycles.count})),errors,at:new Date().toISOString()};
  fs.writeFileSync(path.join(__dirname,'qa/history_english_result.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
