const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1120}}),errors=[],actions=[];
  page.on('pageerror',e=>errors.push(String(e)));
  await page.route('**/api/**',route=>{
   if(route.request().method()!=='POST')return route.continue();
   actions.push(new URL(route.request().url()).pathname);
   return route.fulfill({json:{message:'Isolated browser test: no report or solver action executed.'}});
  });
  await page.goto('http://127.0.0.1:8782/#response-comparison',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>{const img=document.querySelector('#comparison-plot');return img&&!img.hidden&&img.complete&&img.naturalWidth>0});
  const src=await page.locator('#comparison-plot').getAttribute('src');
  assert((await page.locator('#comparison-status').textContent()).includes('W01 · W02 · W03e'));
  assert.equal(await page.locator('#comparison-downloads a').count(),4);
  const chart=page.locator('#live-chart svg[data-reference="C01"]');
  await chart.waitFor();
  assert.equal(await chart.locator('.c01-reference').count(),2);
  const status=await(await page.request.get('http://127.0.0.1:8782/api/status')).json();
  const live=status.preparation.active?status.preparation.live:status.current.live;
  assert.equal(await chart.locator('.resume-marker').count(),2*(live.resume_markers||[]).length);
  await chart.hover({position:{x:300,y:100}});
  const readout=await page.locator('#live-chart .history-readout').textContent();
  assert(readout.includes('ΔCD =')&&readout.includes('ΔCL =')&&readout.includes(' · CD =')&&readout.includes(' · CL ='));
  for(const url of await page.locator('#comparison-downloads a').evaluateAll(links=>links.map(a=>a.href))){
   const r=await page.request.get(url);assert(r.ok(),url);assert((await r.body()).length>500);
  }
  await page.locator('#response-comparison').screenshot({path:path.join(__dirname,'qa/comparison_dashboard.png')});
  const report=await(await page.request.get('http://127.0.0.1:8782/report')).text();
  assert(report.includes('id="force-wave-comparison"'));
  await page.locator('#refresh-comparison').click();
  assert.deepEqual(actions,['/api/report']);
  await page.waitForFunction(()=>document.querySelector('#refresh-comparison').disabled);
  await page.setViewportSize({width:390,height:844});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile overflow');
  assert.equal(errors.length,0);
  const result={passed:true,image:src,downloads:['pdf','svg','600dpi_png','csv'],update_button_action:'/api/report',no_solver_actions:true,errors};
  fs.writeFileSync(path.join(__dirname,'qa/comparison_result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
