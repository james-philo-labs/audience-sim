// Recorded study presentation only. No provider calls or secret-bearing requests.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),http=require('node:http'),os=require('node:os');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'../site');
const output=process.env.STUDY_REPORT_DIR||fs.mkdtempSync(path.join(os.tmpdir(),'audience-study-'));
fs.mkdirSync(output,{recursive:true});
const server=http.createServer((req,res)=>{
 const file=path.resolve(root,'.'+new URL(req.url,'http://local').pathname.replace(/\/$/,'/index.html'));
 if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);return res.end('Missing');}
 const ext=path.extname(file);res.setHeader('Content-Type',({'.html':'text/html','.json':'application/json','.css':'text/css','.js':'text/javascript','.svg':'image/svg+xml','.csv':'text/csv'})[ext]||'text/plain');res.end(fs.readFileSync(file));
});
(async()=>{
 let browser;
 try {
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const origin=process.env.STUDY_URL||`http://127.0.0.1:${server.address().port}`;
  browser=await chromium.launch({headless:true,...(process.env.BUNDLE_CHROMIUM_PATH?{executablePath:process.env.BUNDLE_CHROMIUM_PATH}:{})});
  const page=await browser.newPage({viewport:{width:1440,height:1100},acceptDownloads:true});
  const errors=[],bad=[],requests=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('response',r=>{if(r.status()>=400)bad.push(r.url())});page.on('request',r=>requests.push({url:r.url(),method:r.method()}));
  await page.goto(origin,{waitUntil:'networkidle'});await page.waitForSelector('html[data-study-ready=true]');
  assert.equal(await page.locator('#run-rows tr').count(),9);
  assert.match(await page.locator('.decision').innerText(),/KEEP/);
  assert.match(await page.locator('#validation').innerText(),/Mismatches are unavailable, not zero/);
  for(const id of ['a-visual-01','a-visual-02','a-visual-03','a-posttraining-01','a-posttraining-02','a-posttraining-03','a-evaluation-01','a-evaluation-02','a-evaluation-03']) {
   await page.locator('#run-select').selectOption(id);assert.match(await page.locator('#trace-content').innerText(),new RegExp(id));
   assert.equal(await page.locator('#run-rows .selected-row').count(),1);
  }
  await page.locator('[data-select="a-visual-03"]').click();assert.equal(await page.locator('#run-select').inputValue(),'a-visual-03');
  assert.match(await page.locator('.formula').first().innerText(),/218.05 read \+ 8.06 playback \+ 18.00 interaction − 4.05 overlap = 240.06/);
  await page.getByText('Ordered section exposure and dwell accounting',{exact:true}).click();assert.match(await page.locator('#trace-content').innerText(),/unallocated/);
  assert.equal(await page.locator('#metric-list details').count(),9);
  for(const summary of await page.locator('#metric-list summary').all())await summary.click();
  assert.equal(await page.locator('#metric-list details[open]').count(),9);
  assert.equal(await page.locator('#enhancements article').count(),7);
  const downloadEvent=page.waitForEvent('download');await page.getByText('Download nine-row CSV ↗',{exact:true}).click();
  const download=await downloadEvent;assert.equal(fs.readFileSync(await download.path(),'utf8').trim().split(/\r?\n/).length,10);
  await page.screenshot({path:path.join(output,'desktop.png'),fullPage:true});
  for(const width of [390,320]){await page.setViewportSize({width,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth),width);await page.screenshot({path:path.join(output,`mobile-${width}.png`),fullPage:true});}
  assert.deepEqual(errors,[]);assert.deepEqual(bad,[]);assert.ok(requests.every(r=>r.method==='GET'&&r.url.startsWith(origin)));
  fs.writeFileSync(path.join(output,'report.json'),JSON.stringify({status:'passed',origin,checks:['all nine runs','every run selectable','exact overlap reconciliation','unallocated dwell visible','nine metric definitions','seven enhancement topics','reader accuracy unavailable','CSV download','390/320px reflow','no console or network errors','GET-only same-origin data'],requests:requests.length,model_calls:0},null,2)+'\n');
  console.log('Study UI passed; evidence: '+output);
 } finally {if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
})().catch(e=>{console.error(e);process.exitCode=1});
