const {chromium}=require('playwright');
const path=require('node:path');
async function capture(page, selector, name) {
 if(process.env.ROADGUARD_SCREENSHOTS) await page.locator(selector).screenshot({path:path.join(process.env.ROADGUARD_SCREENSHOTS,name+'.png')});
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.ROADGUARD_BROWSER});
 try{
  const page=await browser.newPage();const origin=process.argv[2],job=process.argv[3];
  await page.goto(origin);await page.evaluate(id=>localStorage.setItem('roadguard-local-job',id),job);await page.reload();
  await page.waitForSelector('#reviewQueue:not([hidden])');
  await page.waitForFunction(()=>document.querySelector('#visionModel').options.length===1);
  await page.selectOption('#ckeyMode','FT95 + Vision');
  if(await page.locator('#reportModel').inputValue()!=='dungcsnd113/qwen3.8-omni-flash')throw Error('Report model missing');
  await page.click('#ckeyPreview');
  await page.waitForFunction(()=>document.querySelector('#ckeyOutput').textContent.includes('paid_execution_requires_confirmation'));
  await capture(page,'#upload','studio-models');
  await capture(page,'#results','studio-results');
  await page.click('#reviewQueue');await page.waitForURL('**/review-queue/');
  if(process.argv.includes('--read-only')){
   await page.waitForFunction(()=>document.querySelector('#frame-guide').textContent.includes('Frame'));
   const opened=page.waitForEvent('popup');await page.click('#frame-link');
   const image=await opened;await image.waitForLoadState();await image.close();
   const state=await page.evaluate(()=>api('/api/state'));
   if(state.source_binding.job_id!==job||state.state.revision!==0||state.report)throw Error('Real data was modified');
   console.log('read-only integrated real-DJI smoke passed: '+state.source.frames.length+' frames, '+state.source.detections.length+' detections, revision 0');
   return;
  }
  await page.selectOption('#filter','all');await page.waitForSelector('#queue canvas');
  await capture(page,'#queue','review-queue');
  const popupPromise=page.waitForEvent('popup');await page.locator('#queue a').first().click();
  const popup=await popupPromise;await popup.waitForLoadState();await popup.close();
  await page.fill('#reviewer','E2E Fixture Reviewer');
  await page.locator('#queue .box').first().fill('2,2,20,30');await page.locator('#queue .box').first().dispatchEvent('change');
  await page.locator('#queue .choose').first().check();await page.check('#confirm');await page.click('#approve');
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Đã lưu revision'));
  await page.reload();await page.selectOption('#filter','all');
  await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('r000001'));
  if(await page.locator('#queue .box').first().inputValue()!=='2,2,20,30')throw Error('Box did not persist');
  await page.fill('#reviewer','E2E Fixture Reviewer');
  await page.click('#draft');await page.waitForFunction(()=>document.querySelector('#report').textContent.includes('draft'));
  await page.click('#ready');await page.waitForFunction(()=>document.querySelector('#report').textContent.includes('ready_for_approval'));
  await page.check('#limits');page.once('dialog',d=>d.accept());await page.click('#reportapprove');
  await page.waitForFunction(()=>document.querySelector('#report').textContent.includes('approved'));
  const state=await page.evaluate(()=>api('/api/state'));
  if(state.state.revision!==1||state.report.status!=='approved'||Object.keys(state.state.coverage).length)throw Error('Invalid approval or accidental frame GT');
  await capture(page,'#report','review-report');
  console.log('integrated E2E passed: main job -> Review -> edit/reload -> draft -> conditional approval');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
