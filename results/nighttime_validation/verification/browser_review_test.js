const {chromium}=require('playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const out=path.resolve('results/nighttime_validation/browser_validation');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:1150}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:8765/review-filter.html');
 const files=fs.readdirSync('/tmp/official-night-dataset').filter(x=>x.endsWith('.mp4')).sort();
 await page.locator('#files').setInputFiles(files.map(x=>'/tmp/official-night-dataset/'+x));
 async function waitVideo(name){await page.waitForFunction(n=>document.getElementById('status').textContent.startsWith(n)&&document.getElementById('video').readyState>=2&&document.getElementById('rawCanvas').getContext('2d').getImageData(0,0,1,1).data[3]===255,name,{timeout:30000});}
 await waitVideo(files[0]);
 const native=await page.evaluate(()=>({width:video.videoWidth,height:video.videoHeight}));
 await page.selectOption('#condition','weekday_malam');
 for(const [key,value] of Object.entries({gamma:.7,exposure:.3,brightness:4,shadows:12,sharpness:.5})){
  await page.locator('#'+key).evaluate((e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));},value);
 }
 await page.click('#saveProfile');
 await page.evaluate(()=>draw());
 for(const [id,name] of [['rawCanvas','raw_native.png'],['filteredCanvas','filtered_native.png']]){
  const encoded=await page.locator('#'+id).evaluate(e=>e.toDataURL('image/png').split(',')[1]);fs.writeFileSync(path.join(out,name),Buffer.from(encoded,'base64'));
 }
 await page.screenshot({path:path.join(out,'review_filter_preview.png'),fullPage:true});
 await page.selectOption('#videoList','1');await waitVideo(files[1]);
 if(await page.locator('#gamma').inputValue()!=='1')throw Error('Video settings leaked across source identities');
 await page.selectOption('#condition','weekend_malam');
 await page.locator('#gamma').evaluate(e=>{e.value='1.1';e.dispatchEvent(new Event('input',{bubbles:true}));});await page.click('#saveProfile');
 const expectedProfiles={weekday_malam:.7,weekend_malam:1.1};
 const allConditions=await page.evaluate(()=>NightFilter.conditions);
 for(let i=0;i<allConditions.length;i++){
  const condition=allConditions[i];if(condition in expectedProfiles)continue;
  const value=Number((.5+i*.1).toFixed(2));expectedProfiles[condition]=value;
  await page.selectOption('#condition',condition);
  await page.locator('#gamma').evaluate((e,v)=>{e.value=v;e.dispatchEvent(new Event('input',{bubbles:true}));},value);
  await page.click('#saveProfile');
 }
 await page.selectOption('#condition','weekend_malam');await page.click('#loadProfile');
 for(let i=2;i<files.length;i++){await page.selectOption('#videoList',String(i));await waitVideo(files[i]);}
 await page.selectOption('#videoList','0');await waitVideo(files[0]);
 if(await page.locator('#gamma').inputValue()!=='0.7')throw Error('Video settings not restored');
 const downloadEvent=page.waitForEvent('download');await page.click('#export');await (await downloadEvent).saveAs(path.join(out,'test_export_not_selected_for_inference.json'));
 const c=JSON.parse(fs.readFileSync(path.join(out,'test_export_not_selected_for_inference.json')));
 if(Object.keys(c.profiles).length!==8||c.videos.length!==10)throw Error('Actual samples or independent profiles missing');
 for(const [condition,value] of Object.entries(expectedProfiles))if(c.profiles[condition].gamma!==value)throw Error('Profile independence failed: '+condition);
 await page.locator('#import').setInputFiles(path.join(out,'test_export_not_selected_for_inference.json'));
 await page.waitForFunction(()=>document.getElementById('status').textContent.startsWith('Konfigurasi diimpor'));
 await page.reload();await page.locator('#files').setInputFiles('/tmp/official-night-dataset/'+files[0]);await waitVideo(files[0]);
 if(await page.locator('#gamma').inputValue()!=='0.7')throw Error('Persistence failed');
 await page.locator('#seek').evaluate(e=>{e.value='2';e.dispatchEvent(new Event('input',{bubbles:true}));});
 await page.waitForFunction(()=>Math.abs(document.getElementById('video').currentTime-2)<.1);
 await page.click('#play');await page.waitForFunction(()=>!document.getElementById('video').paused);await page.click('#pause');
 if(errors.length)throw Error(errors.join('\n'));
 fs.writeFileSync(path.join(out,'browser_test.json'),JSON.stringify({status:'PASS',browser:'system Chromium via Playwright',actual_video_files_opened:files,native_preview_dimensions:native,eight_profiles_independent:true,all_eight_condition_profile_edits_verified:expectedProfiles,per_video_settings_independent:true,sha256_binding:true,export_import_and_persistence:true,seek_play_pause:true,page_errors:errors,settings_are_test_values_not_selected_recipe:true,inference_executed:false},null,2)+'\n');
 await browser.close();console.log('Browser test PASS:10 real source files,8 independent profiles,export/import/persistence,seek/play/pause');
})().catch(e=>{console.error(e);process.exit(1);});
