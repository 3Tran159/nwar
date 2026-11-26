const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1120}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>route.request().method()==='POST'?route.abort():route.continue());
  await page.goto('http://127.0.0.1:8782',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.querySelector('#live-title').textContent.includes('PRE W04'));
  const actual=await(await page.request.get('http://127.0.0.1:8782/api/status')).json();
  for(const [id,L] of [['W05',20],['W06',30],['W07',50]]){
   const c=actual.catalog.find(c=>c.id===id);assert.equal(c.H,1);assert.equal(c.L,L);assert.equal(c.ready,false);
  }
  assert.equal(await page.locator('.convergence-threshold').count(),2);
  await page.locator('.live.card').screenshot({path:path.join(__dirname,'qa/pre_w04_actual.png')});
  // Isolated browser response only: no synthetic evidence is written to the run.
  const fixture=JSON.parse(JSON.stringify(actual)),pre=fixture.preparation;
  pre.active=true;pre.phase='calm_running';pre.status='running';pre.error=null;pre.receipt={};pre.label='Calm flow at 18 m/s · waiting for convergence';
  const points=Array.from({length:2200},(_,i)=>[4.6992+(i+1)*.0004,.0070023169117*(1+.02*Math.exp(-i/500)),.315659504951*(1-.01*Math.exp(-i/500))]);
  pre.live={...pre.live,series:points,history_segments:[{points}],history_warnings:[],history_samples:2200,age_s:1,time_s:points.at(-1)[0],CD:points.at(-1)[1],CL:points.at(-1)[2],
   convergence:[.4,.6,.8].map((t,i)=>({time_s:4.6992+t,complete:true,CD_stability_pct:[.9,.4,.1][i],CL_stability_pct:[.7,.3,.1][i],CD_C01_pct:[1,.6,.3][i],CL_C01_pct:[.8,.5,.2][i],CD_mean:.00702,CL_mean:.316,consecutive_compatible:i===2?1:0}))};
  await page.unroute('**/api/**');
  await page.route('**/api/status',route=>route.fulfill({json:fixture}));
  await page.reload({waitUntil:'networkidle'});await page.waitForSelector('#live-chart svg');
  assert.equal(await page.locator('#pre-convergence-chart .convergence-curve').count(),4);
  assert.equal(await page.locator('#live-chart .history-curve').count(),2);
  assert((await page.locator('#pre-convergence-chart').textContent()).includes('1 / 2'));
  assert(!/[ąćęłńóśźżĄĆĘŁŃÓŚŹŻ]/.test(await page.locator('body').textContent()));
  await page.locator('.live.card').screenshot({path:path.join(__dirname,'qa/pre_w04_synthetic_layout.png')});
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile overflow');
  assert.equal(errors.length,0);
  const result={passed:true,actual_phase:actual.preparation.phase,numbering:'W05=1/20 W06=1/30 W07=1/50',threshold_lines:2,full_history_preserved:true,synthetic_layout_test_only:true,no_solver_started:true,errors};
  fs.writeFileSync(path.join(__dirname,'qa/pre_w04_result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
