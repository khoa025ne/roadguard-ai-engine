const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.ROADGUARD_BROWSER});
 try{
  const page=await browser.newPage();await page.goto(process.argv[2]);
  await page.evaluate(j=>localStorage.setItem('roadguard-local-job',j),process.argv[3]);await page.reload();
  await page.waitForSelector('#results:not([hidden])');
  if(!await page.locator('#segment').inputValue())throw Error('Segment model not available');
  if(!await page.locator('#preview').getAttribute('src').then(s=>s.includes('road_overlay_')))throw Error('Overlay missing');
  if(!process.argv.includes('--real')&&!await page.locator('#detections').textContent().then(s=>s.includes('Ngoài/giao biên')))throw Error('Outside warning missing');
  await page.uncheck('#showRoadMask');
  if(!await page.locator('#preview').getAttribute('src').then(s=>s.includes('original_')))throw Error('Original not restored');
  await page.check('#showRoadMask');await page.reload();await page.waitForSelector('#results:not([hidden])');
  if(!await page.locator('#preview').getAttribute('src').then(s=>s.includes('road_overlay_')))throw Error('Overlay not reloaded');
  await page.waitForFunction(()=>document.querySelector('#preview').complete&&document.querySelector('#preview').naturalWidth>0);
  if(process.argv.includes('--real')){
   const job=await page.evaluate(async id=>(await fetch('/api/mvp-video/'+id)).json(),process.argv[3]);
   if(job.reviews&&Object.keys(job.reviews).length)throw Error('Real data must not be reviewed by smoke');
   if(job.result.frames.some(f=>f.mask_is_ground_truth!==false))throw Error('AI mask incorrectly marked GT');
   console.log('real DJI segmentation smoke passed: '+job.result.frames.length+' frames, reload overlay, no GT approval');return;
  }
  await page.selectOption('#frames','1');
  if(!await page.locator('#roadMaskStatus').textContent().then(s=>s.includes('Không có mask')))throw Error('Missing mask warning absent');
  if(!await page.locator('#showRoadMask').isDisabled())throw Error('Missing mask not handled');
  console.log('segmentation browser smoke passed: model, overlay, toggle, outside warning, reload, missing mask');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
