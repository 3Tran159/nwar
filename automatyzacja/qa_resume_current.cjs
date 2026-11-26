const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[],posts=[];
  page.on('pageerror',e=>errors.push(String(e)));
  // Every mutation is intercepted: this test must never launch the saved solver.
  await page.route('**/api/**',async route=>{
   if(route.request().method()!=='POST')return route.continue();
   posts.push({url:route.request().url(),data:route.request().postDataJSON()});
   return route.fulfill({status:202,json:{message:'UI test only: no solver launched.'}});
  });
  await page.goto('http://127.0.0.1:8782',{waitUntil:'networkidle'});
  const actual=await(await page.request.get('http://127.0.0.1:8782/api/status')).json();
  assert.equal(actual.preparation.active,false);assert.equal(actual.current_resume.kind,'preparation');
  const button=page.locator('#resume-current');await button.waitFor({state:'visible'});
  assert(await button.isEnabled());assert.equal(await button.textContent(),'Resume simulation');
  assert((await page.locator('#ownership').textContent()).includes('0.7516 s'));
  await page.locator('.live.card').screenshot({path:path.join(__dirname,'qa/resume_current_paused.png')});
  await button.evaluate(b=>{b.click();b.click()});
  await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('UI test only'));
  assert.equal(posts.length,1);assert.equal(posts[0].data.folder,actual.current_resume.folder);
  const wave=JSON.parse(JSON.stringify(actual));wave.preparation=null;wave.external=[];
  wave.jobs=[{id:'wave-fixture',case_id:'W06',folder:'test-wave',status:'paused',can_resume:true,created:'2026-11-02',spec:{mode:'fresh'},live:actual.preparation.live}];
  wave.current_resume={id:'wave-fixture',case_id:'W06',folder:'test-wave',kind:'wave',time_s:12.5,available:true};
  await page.route('**/api/status',route=>route.fulfill({json:wave}));
  await page.reload({waitUntil:'networkidle'});await button.waitFor({state:'visible'});
  assert((await page.locator('#ownership').textContent()).includes('W06'));
  await button.click();await page.waitForFunction(()=>document.querySelector('#notice').textContent.includes('UI test only'));
  assert.equal(posts.length,2);assert.equal(posts[1].data.kind,'wave');assert.equal(posts[1].data.id,'wave-fixture');
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile overflow');
  assert.equal(errors.length,0);
  const result={passed:true,preparation_and_wave:true,double_click_single_request:true,all_posts_intercepted:true,no_solver_started:true,errors};
  fs.writeFileSync(path.join(__dirname,'qa/resume_current_ui.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
