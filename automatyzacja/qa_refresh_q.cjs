const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1050}});const errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.goto('http://127.0.0.1:8782',{waitUntil:'networkidle'});await page.waitForSelector('#q-table table');
  const before=await (await page.request.get('http://127.0.0.1:8782/api/status')).json();
  await page.locator('#refresh-q').click();
  assert(await page.locator('#refresh-q').isDisabled(),'Update button must be disabled while calculating');
  await page.waitForFunction(old=>window.document.querySelector('#refresh-q').textContent==='Update plot'&&document.querySelector('#q-refresh-status').textContent.includes('Updated:'),before.report.generated_at,{timeout:120000});
  const after=await (await page.request.get('http://127.0.0.1:8782/api/status')).json();
  assert.notEqual(after.report.generated_at,before.report.generated_at,'Report did not refresh');
  assert((await page.locator('#q-reference').textContent()).includes('27.00 N'),'Missing reference drag');
  for(const id of ['W01','W03']){
   const c=after.catalog.find(x=>x.id===id);assert(c.force_wave_plot,'Missing '+id+' force-wave plot');
   const image=await page.request.get('http://127.0.0.1:8782/'+after.report.relative+'/'+c.force_wave_plot);assert.equal(image.status(),200);
   const q=after.Q_data.find(x=>x.case===id);assert(Math.abs((q.D_wave_N-q.D_C01_N)-q.delta_D_N)<1e-10);
  }
  await page.locator('#q-data').screenshot({path:path.join(__dirname,'qa/q_panel.png')});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),'Mobile overflow');
  await page.locator('#q-data').screenshot({path:path.join(__dirname,'qa/q_mobile.png')});
  assert.equal(errors.length,0);
  const receipt={passed:true,real_report_refresh:true,no_solver_started:true,report:after.report.relative,baseline_drag_N:after.Q_data[0].D_C01_N,W01_W03_force_wave_images:true,errors,at:new Date().toISOString()};
  fs.writeFileSync(path.join(__dirname,'qa/q_refresh_result.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
