const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1120}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>route.request().method()==='POST'?route.abort():route.continue());
  await page.goto('http://127.0.0.1:8782',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>document.querySelector('#progress-text').textContent.includes('Speed ramp'));
  const actual=await(await page.request.get('http://127.0.0.1:8782/api/status')).json();
  const measured=Number(await page.locator('#run-progress').getAttribute('aria-valuenow'));
  assert(Math.abs(measured-actual.preparation.live.speed_ramp.percent)<2);
  await page.locator('.live.card').screenshot({path:path.join(__dirname,'qa/pre_w04_ramp_actual.png')});
  await page.unroute('**/api/**');
  let fixture;
  await page.route('**/api/status',route=>route.fulfill({json:fixture}));
  for(const [pct,active] of [[0,true],[25,true],[100,true],[33.6,false]]){
   fixture=JSON.parse(JSON.stringify(actual));const pre=fixture.preparation;
   pre.active=active;pre.phase=active?'calm_running':'needs_review';pre.status=active?'running':'needs_review';pre.error=null;pre.receipt={};
   pre.live.speed_ramp={duration_s:1,elapsed_s:pct/100,percent:pct,complete:pct===100,started:pct>0,target_speed_m_s:18,remaining_wall_s:active?1200:null};
   pre.live.current_speed_m_s=9*(1-Math.cos(Math.PI*pct/100));pre.live.stale=false;
   await page.reload({waitUntil:'networkidle'});
   await page.waitForFunction(p=>Number(document.querySelector('#run-progress').getAttribute('aria-valuenow'))===p,pct);
   const detail=await page.locator('#ramp-detail').textContent();
   if(pct===100)assert(detail.includes('convergence to C01 is checked separately'));
   else if(!active)assert(detail.includes('not running')&&!detail.includes('remaining'));
   else if(pct===0)assert(detail.includes('Waiting for the first'));
   else assert(detail.includes('20 min remaining'));
  }
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile overflow');
  assert.equal(errors.length,0);
  const result={passed:true,actual_percent:actual.preparation.live.speed_ramp.percent,actual_active:actual.preparation.active,
   fixture_states:['loading','partial ramp','full speed before convergence','stopped'],no_solver_actions:true,errors};
  fs.writeFileSync(path.join(__dirname,'qa/ramp_progress_result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
