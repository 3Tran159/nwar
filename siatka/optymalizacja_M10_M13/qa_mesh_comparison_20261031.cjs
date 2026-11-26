const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const out=path.join(__dirname,'mesh_comparison_qa');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 const errors=[],writes=[];
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});
  await context.route('**/*',async r=>{if(!['GET','HEAD'].includes(r.request().method())){writes.push(r.request().method());await r.abort()}else await r.continue()});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8771/',{waitUntil:'load',timeout:60000});
  await page.locator('[data-tab=compare]').click();await page.waitForSelector('#comparison-trace');
  const snap=()=>page.evaluate(()=>({tab,group:comparisonGroup,curves:document.querySelectorAll('#comparison-trace [data-mesh-curve]').length,points:document.querySelectorAll('#comparison-means [data-settled-point]').length,rows:document.querySelectorAll('[data-comparison-row]').length,overflow:document.documentElement.scrollWidth>innerWidth,means:data.comparison.runs.filter(r=>r.group==='current').map(r=>({mesh:r.mesh,accepted:r.accepted,dt_s:r.dt_s,CL:r.settled?.CL,CD:r.settled?.CD,delta_CL:r.delta_CL_pct,delta_CD:r.delta_CD_pct,window:r.settled?.window_s,samples:r.settled?.sample_count})),candidate:data.comparison.next_candidate?.id}));
  const desktop=await snap();assert.equal(desktop.tab,'compare');assert.equal(desktop.curves,6);assert.equal(desktop.points,6);assert.equal(desktop.rows,3);assert(!desktop.overflow);
  assert(desktop.means.every(r=>r.accepted&&Number.isFinite(r.CL)&&Number.isFinite(r.CD)));
  assert.equal(desktop.candidate,'M13');
  await page.screenshot({path:path.join(out,'comparison_desktop.png'),fullPage:true});
  await page.locator('[data-mesh-toggle="current:M10"]').click();assert.equal(await page.locator('[data-mesh-curve]').count(),4);
  await page.locator('[data-mesh-toggle="current:M10"]').click();assert.equal(await page.locator('[data-mesh-curve]').count(),6);
  await page.locator('#comparison-range').click();assert.equal(await page.evaluate(()=>comparisonTail),false);
  await page.locator('#comparison-group').selectOption('matched');const matched=await snap();assert.equal(matched.curves,6);assert.equal(matched.points,6);
  await page.locator('#comparison-group').selectOption('initial');const initial=await snap();assert(initial.rows>=7);assert(initial.curves>=10);assert(initial.points>=12);
  await page.locator('#comparison-group').selectOption('all');const all=await snap();assert(all.rows>=13);assert(all.points>=24);
  await page.locator('#comparison-group').selectOption('current');
  const d=page.waitForEvent('download');await page.locator('#comparison-export').click();const download=await d;await download.saveAs(path.join(out,'comparison_export.csv'));
  const csv=fs.readFileSync(path.join(out,'comparison_export.csv'),'utf8');assert(csv.includes('M10')&&csv.includes('M11')&&csv.includes('M12')&&csv.includes('mean_CD'));assert(!csv.includes('undefined'));
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(400);const mobile=await snap();assert(!mobile.overflow);assert.equal(mobile.points,6);assert.equal(mobile.curves,6);
  await page.screenshot({path:path.join(out,'comparison_mobile.png'),fullPage:true});
  await page.locator('[data-tab=archive]').click();assert(await page.locator('#view-archive').isVisible());
  await page.locator('[data-tab=live]').click();assert(await page.locator('#view-live').isVisible());assert.equal(await page.locator('#wave-table tbody tr').count(),12);
  assert.deepStrictEqual(errors,[]);assert.deepStrictEqual(writes,[]);
  const result={passed:true,at:new Date().toISOString(),desktop,mobile,matched:{curves:matched.curves,rows:matched.rows},initial:{curves:initial.curves,rows:initial.rows},all:{curves:all.curves,rows:all.rows},csv:true,errors,writes};
  fs.writeFileSync(path.join(out,'qa.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||String(e));process.exit(1)});
