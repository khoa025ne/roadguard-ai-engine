const {chromium}=require('playwright');
const path=require('node:path');
async function capture(page, selector, name){
 if(process.env.ROADGUARD_SCREENSHOTS)await page.locator(selector).screenshot({path:path.join(process.env.ROADGUARD_SCREENSHOTS,name+'.png')});
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.ROADGUARD_BROWSER});
 try{
  const page=await browser.newPage();const origin=process.argv[2],job=process.argv[3];
  await page.goto(origin);
  await page.waitForFunction(()=>document.querySelector('#config').textContent.includes('Xử lý local'));
  if(await page.locator('#ckeyMode').inputValue()!=='FT95 + Vision'||!await page.locator('#roadMaskEnabled').isChecked())throw Error('Incorrect defaults');
  await page.selectOption('#ckeyMode','FT95');
  await page.selectOption('#ckeyMode','Vision');
  await page.selectOption('#ckeyMode','FT95 + Vision');
  await capture(page,'#upload','v2-models');
  await page.setViewportSize({width:390,height:850});
  if(!await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))throw Error('Mobile horizontal overflow');
  await capture(page,'#upload','v2-mobile');
  await page.setViewportSize({width:1280,height:720});
  await page.evaluate(()=>localStorage.setItem('roadguard-local-job','0'.repeat(32)));
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('fixture.mp4'));
  if(await page.locator('#error').isVisible())throw Error('Stale job shown as an error');
  await page.evaluate(id=>localStorage.setItem('roadguard-local-job',id),job);await page.reload();
  await page.waitForSelector('#reviewQueue:not([hidden])');
  await page.waitForFunction(()=>document.querySelector('#reportModel').options.length===1);
  if(!await page.locator('#ckeyReport').isDisabled())throw Error('Unverified report must be locked');
  await page.click('#reportPreview');
  await page.waitForFunction(()=>document.querySelector('#reportInput').textContent.includes('1 request · 0 ảnh'));
  const reportUrl=await page.locator('#localHtml').getAttribute('href');
  const localReport=await page.request.get(origin+reportUrl);
  if(localReport.status()!==200||!(await localReport.text()).includes('Khuyết tật và rà soát'))throw Error('Local report unavailable');
  await capture(page,'#reportSection','report-v2');
  if(await page.locator('#reportModel').inputValue()!=='dungcsnd113/qwen3.8-omni-flash')throw Error('Report model missing');
  await page.click('#ckeyPreview');
  await page.waitForFunction(()=>document.querySelector('#ckeyOutput').textContent.includes('paid_execution_requires_confirmation'));
  if(!process.argv.includes('--read-only')){
   if(!await page.locator('#ckeyVision').isDisabled())throw Error('Consent bypass');
   await page.check('#ckeyConsent');await page.click('#ckeyVision');
   await page.waitForFunction(()=>document.querySelector('#visionProposals').textContent.includes('Fixture Gemini'));
   if(await page.locator('#ckeyConsent').isChecked())throw Error('Consent reused');
   await page.uncheck('#showRoadMask');await page.check('#showRoadMask');
   await capture(page,'#results','v2-comparison');
  }
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
  await page.waitForFunction(()=>document.querySelector('#guide-vision').textContent.includes('Fixture Gemini'));
  await page.check('#guide-mask');
  await capture(page,'section:has(#guide-canvas)','v2-review');
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
  console.log('integrated E2E passed: main job -> Review -> edit/reload -> draft -> conditional approval');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
