const {chromium} = require('playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.ROADGUARD_BROWSER});
 try {
  const page=await browser.newPage();
  await page.goto(process.argv[2]);
  await page.selectOption('#filter','all');
  await page.waitForSelector('#queue canvas');
  const popupPromise=page.waitForEvent('popup');
  await page.locator('#queue a').first().click();
  const popup=await popupPromise;
  await popup.waitForLoadState();
  if(!popup.url().includes('/api/frame/')) throw Error('Frame not opened');
  await popup.close();
  if(process.argv.includes('--read-only')){
   const state=await page.evaluate(()=>fetch(resource('/api/state')).then(r=>r.json()));
   if(state.state.revision!==0||state.report)throw Error('Real-data smoke must stay unreviewed');
   console.log('read-only real-video smoke passed: '+state.source.frames.length+' frames, '+state.source.detections.length+' detections, revision 0');
   return;
  }
  await page.fill('#reviewer','Browser Tester');
  await page.locator('#queue .box').first().fill('2,2,20,30');
  await page.locator('#queue .box').first().dispatchEvent('change');
  await page.locator('#queue .choose').first().check();
  await page.waitForSelector('#batch-preview img');
  await page.check('#confirm');
  await page.click('#approve');
  await page.waitForFunction(()=>document.querySelector('#status').textContent.includes('Đã lưu revision'));
  await page.reload();
  await page.selectOption('#filter','all');
  await page.waitForFunction(()=>document.querySelector('#history').textContent.includes('r000001.json'));
  const box=await page.locator('#queue .box').first().inputValue();
  if(box!=='2,2,20,30')throw Error('Box not persisted: '+box);
  console.log('browser smoke passed: frame, group, edit, batch preview, save, reload');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
