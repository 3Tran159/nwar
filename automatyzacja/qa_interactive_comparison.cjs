const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const here=__dirname,latest=JSON.parse(fs.readFileSync(path.join(here,'latest_report.json'),'utf8'));
 const url='http://127.0.0.1:8782/'+latest.relative+'/force_wave_comparison_interactive.html';
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1200}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  const response=await page.goto(url);assert(response.ok());
  const curves=()=>page.locator('.chart path.curve').count();
  assert.equal(await page.locator('#choices input:checked').count(),12);assert.equal(await curves(),48);
  const actual=await page.locator('#comparison-data').textContent(),data=JSON.parse(actual);
  const audit=JSON.parse(fs.readFileSync(path.join(latest.directory,'audit.json'),'utf8'));
  for(const c of data.cases){const source=audit.results.find(r=>(r.display_id||r.case)===c.id&&r.project_accepted).force_wave_response;
   assert.deepEqual(c.vertical,source.lift_minus_C01_mean_N);assert.deepEqual(c.horizontal,source.drag_minus_C01_mean_N);assert.deepEqual(c.eta,source.eta_prime_mean_m);assert.deepEqual(c.phase,source.phase_deg);
  }
  await page.getByRole('checkbox',{name:'W04',exact:true}).uncheck();assert.equal(await curves(),44);assert.equal(await page.locator('.curve[data-case="W04"]').count(),0);
  await page.locator('#none').click();assert.equal(await curves(),0);
  await page.locator('#length').click();assert.equal(await curves(),8);assert.equal(await page.locator('#choices input:checked').count(),2);
  await page.locator('#autoscale').uncheck();assert.equal(await curves(),8);
  await page.locator('#height').click();assert.equal(await curves(),20);
  await page.locator('#vertical-phase').hover({position:{x:300,y:130}});assert((await page.locator('#readout').textContent()).includes('ΔFx'));
  await page.screenshot({path:path.join(here,'qa/interactive_comparison_desktop.png'),fullPage:true});
  await page.locator('#all').click();assert.equal(await curves(),48);
  await page.setViewportSize({width:390,height:844});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'Mobile overflow');
  await page.screenshot({path:path.join(here,'qa/interactive_comparison_mobile.png'),fullPage:true});
  assert.equal(errors.length,0);
  const result={passed:true,cases:12,exact_arrays:true,four_panels_linked:true,checkboxes:true,presets:true,autoscale:true,hover:true,mobile:true,url,errors};
  fs.writeFileSync(path.join(here,'qa/interactive_comparison_browser.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
