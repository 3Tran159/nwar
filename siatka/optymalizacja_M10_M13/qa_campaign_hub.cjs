const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require('C:/Users/ThinkPad/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const out='E:/ntnu_mesh_optimization_20261030/campaign_hub_qa';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true,args:['--disable-gpu']});
 const errors=[],writes=[];
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1100},acceptDownloads:true});
  await context.route('**/*',r=>{if(!['GET','HEAD'].includes(r.request().method())){writes.push(r.request().method());return r.abort()}return r.continue()});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(String(e)));
  const url=process.argv[2]||'http://127.0.0.1:8771/archive_runs/campaign_preview.html';
  await page.goto(url,{waitUntil:'load',timeout:60000});await page.waitForSelector('#live-CD-CL',{timeout:15000});
  const initial=await page.evaluate(()=>({title:document.title,mesh:data.current_foil?.mesh,live:data.current_foil?.status,counts:data.counts,
   firstMeshes:['M01','M02','M03','M04','M05','M06','M07','M08','M09'].filter(m=>data.records.some(r=>r.mesh===m)),
   waves:document.querySelectorAll('#wave-table tbody tr').length,charts:document.querySelectorAll('#live-CD-CL,#live-mean-drift').length,
   overflow:document.documentElement.scrollWidth>innerWidth,etas:[...document.querySelectorAll('[data-eta-long]')].map(e=>e.textContent),
   accepted:data.stages.filter(r=>r.status==='primary_accepted').map(r=>r.mesh)}));
  assert.equal(initial.mesh,'M10');assert.equal(initial.waves,12);assert.equal(initial.charts,2);assert.equal(initial.firstMeshes.length,9);assert.equal(initial.overflow,false);
  assert(initial.accepted.includes('M11')&&initial.accepted.includes('M12'));
  assert(!initial.etas.some(s=>s.includes('NaN')||s.includes('undefined')));
  await page.screenshot({path:path.join(out,'current_desktop.png'),fullPage:true});
  await page.locator('[data-tab="archive"]').click();
  assert(await page.locator('#view-archive').isVisible());
  const archive=await page.evaluate(()=>({rows:document.querySelectorAll('[data-result-row]').length,total:filtered().length,active:filtered().some(r=>r.active)}));
  assert.equal(archive.active,false);assert(archive.total>=70);assert.equal(archive.rows,25);
  await page.locator('#search').fill('M01');
  assert(await page.locator('[data-result-row]').count()>=1);
  const first=await page.locator('[data-result-row]').first().innerText();assert(first.includes('M01'));assert(first.includes('Geometry only'));
  await page.locator('[data-result-row] [data-record]').first().click();
  assert((await page.locator('#record-detail').textContent()).includes('measurement.json'));
  assert((await page.locator('#record-detail').innerText()).includes('37,411'));
  await page.locator('#close-detail').click();await page.locator('#search').fill('');
  await page.locator('#kind').selectOption('foil');await page.locator('#result-filter').selectOption('accepted');
  const accepted=await page.locator('#archive-table').innerText();assert(accepted.includes('M11')&&accepted.includes('M12'));
  await page.screenshot({path:path.join(out,'archive_desktop.png'),fullPage:true});
  const downloadPromise=page.waitForEvent('download');await page.locator('#export-csv').click();const dl=await downloadPromise;await dl.saveAs(path.join(out,'export_test.csv'));
  const csv=fs.readFileSync(path.join(out,'export_test.csv'),'utf8');assert(csv.includes('mean_CL'));assert(csv.includes('M11'));assert(csv.includes('M12'));assert(!csv.includes('undefined'));
  await page.locator('#kind').selectOption('wave');await page.locator('#result-filter').selectOption('all');assert(await page.locator('[data-result-row]').count()>0);
  await page.locator('[data-tab="live"]').click();await page.setViewportSize({width:390,height:844});await page.waitForTimeout(450);
  const mobile=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth,charts:document.querySelectorAll('#live-CD-CL,#live-mean-drift').length,waves:document.querySelectorAll('#wave-table tbody tr').length}));
  assert.equal(mobile.overflow,false);assert.equal(mobile.charts,2);
  await page.screenshot({path:path.join(out,'current_mobile.png'),fullPage:true});
  await page.locator('[data-tab="archive"]').click();await page.locator('#kind').selectOption('all');await page.locator('#search').fill('M02');assert(await page.locator('[data-result-row]').count()>0);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.screenshot({path:path.join(out,'archive_mobile.png'),fullPage:true});
  assert.deepStrictEqual(errors,[]);assert.deepStrictEqual(writes,[]);
  const report={passed:true,checked_at:new Date().toISOString(),url,initial,archive,mobile,errors,writes,CSV_export_pass:true};
  fs.writeFileSync(path.join(out,'qa_report.json'),JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{await browser.close()}
})().catch(e=>{console.error(e.stack||e);process.exit(1)});
