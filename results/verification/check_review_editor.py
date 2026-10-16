from pathlib import Path
from collections import Counter
from datetime import datetime,timezone
from playwright.sync_api import sync_playwright
import json,hashlib,base64,copy
root=Path(__file__).resolve().parents[2]
html=(root/'results/review.html').read_text()
checks=[]
def check(ok,name):
 assert ok,name
 checks.append(name)
with sync_playwright() as w:
 browser=w.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
 page=browser.new_page(viewport={'width':1440,'height':1100},accept_downloads=True)
 errors=[];requests=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.on('request',lambda r:requests.append(r.url) if not r.url.startswith('data:') else None)
 page.set_content(html,wait_until='load')
 page.wait_for_function('loadedImage !== null')
 def snap():return page.evaluate('exportedEntry(current())')
 def setnum(label,value):
  element=page.get_by_role('spinbutton',name=label,exact=True)
  element.fill(str(value));element.press('Tab')
 def download(all=False):
  with page.expect_download() as got:page.locator('#export-all' if all else '#export-current').click()
  d=got.value
  return json.loads(Path(d.path()).read_text())
 check(page.title()=='Review geometri · TGDI','page renders with correct title')
 check(page.evaluate('current().id')=='TGDI-WEEKDAY-PAGI','default opens actual morning source')
 check(page.locator('#canvas').evaluate('(e)=>[e.width,e.height]')==[640,480],'native canvas dimensions 640x480')
 originals=page.evaluate('EMBEDDED')
 check(len(originals)==8,'eight retained TGDI sources embedded')
 for e in originals:
  data=base64.b64decode(e['image_data_url'].split(',',1)[1])
  check(hashlib.sha256(data).hexdigest()==e['source_frame']['sha256'],e['id']+' frame SHA matches retained source')
  native=json.loads((root/e['base_geometry']['path']).read_text())['rendered_native_pixels']
  check(e['geometry_native']==native,e['id']+' starts at approved native geometry unchanged')
 all_initial=download(True)
 check(len(all_initial['videos'])==8 and all(not v['pipeline_approval'] and not v['counting_execution_allowed'] and v['line_margin']['half_width_px']==0 for v in all_initial['videos']),'all-video JSON download preserves draft and pipeline guards')
 page.locator('#target').select_option('line')
 setnum('P2 X',610.25);setnum('P2 Y',265.5)
 page.locator('#margin').fill('12.5');page.locator('#margin').press('Tab')
 page.locator('#notes').fill('Review uji browser, bukan keputusan pengguna');page.locator('#notes').press('Tab')
 draft=download()['videos'][0]
 check(draft['geometry_native']['line']['P2']==[610.25,265.5],'numeric endpoint edits export in native coordinates')
 check(draft['geometry_normalized']['line']['P2']==[610.25/640,265.5/480],'normalization uses independent native width and height')
 check(draft['line_margin']['half_width_px']==12.5 and draft['line_margin']['full_width_px']==25,'margin halfwidth and fullwidth exported explicitly')
 check(not draft['anchor']['union_bbox_is_crossing_source'],'raw vehicle BC remains proposed anchor source')
 check(draft['geometry_native']['side_a_polygon']==originals[1]['geometry_native']['side_a_polygon'],'line editing does not silently move polygon')
 page.locator('#confirmed').check()
 check(snap()['user_review']['confirmed'],'local review checkbox recorded')
 page.locator('#margin').fill('13');page.locator('#margin').press('Tab')
 check(not snap()['user_review']['confirmed'],'geometry change clears previous local confirmation')
 page.locator('#margin').fill('12.5');page.locator('#margin').press('Tab')
 current_id=page.locator('#video').input_value()
 page.locator('#video').select_option('3');page.wait_for_function('loadedImage !== null')
 check(snap()['line_margin']['half_width_px']==0,'editing one video does not alter other video margins')
 page.locator('#video').select_option(current_id);page.wait_for_function('loadedImage !== null')
 check(snap()['geometry_native']['line']['P2']==[610.25,265.5] and snap()['line_margin']['half_width_px']==12.5,'per-video geometry edits survive video switching')
 page.locator('#target').select_option('line')
 page.set_viewport_size({'width':1100,'height':1000})
 box=page.locator('#canvas').bounding_box();before=snap()['geometry_native']['line']['P2']
 start=(box['x']+before[0]/640*box['width'],box['y']+before[1]/480*box['height'])
 finish=(box['x']+600/640*box['width'],box['y']+260/480*box['height'])
 page.mouse.move(*start);page.mouse.down();page.mouse.move(*finish,steps=5);page.mouse.up()
 moved=snap()['geometry_native']['line']['P2']
 check(abs(moved[0]-600)<1 and abs(moved[1]-260)<1,'pointer drag maps CSS display to native coordinates')
 page.locator('#canvas').focus();page.keyboard.press('ArrowLeft')
 nudged=snap()['geometry_native']['line']['P2']
 check(abs(nudged[0]-(moved[0]-1))<1e-6,'keyboard nudge moves selected native endpoint by one pixel')
 exported=download()
 page.locator('#json-file').set_input_files({'name':'review.json','mimeType':'application/json','buffer':json.dumps(exported).encode()})
 page.wait_for_function("document.getElementById('status').textContent.includes('berhasil diimpor')")
 check(snap()['geometry_native']==exported['videos'][0]['geometry_native'],'JSON import round-trip preserves edited geometry')
 check(not snap()['user_review']['confirmed'] and not snap()['counting_execution_allowed'],'import requires local re-review and cannot approve pipeline')
 before=copy.deepcopy(snap()['geometry_native'])
 bad=copy.deepcopy(exported);bad['videos'][0]['source_video']['sha256']='0'*64
 page.locator('#json-file').set_input_files({'name':'wrong-source.json','mimeType':'application/json','buffer':json.dumps(bad).encode()})
 page.wait_for_function("document.getElementById('status').textContent.includes('Impor dibatalkan')")
 check(snap()['geometry_native']==before,'wrong-source import rejected without mutation')
 bad=copy.deepcopy(exported);bad['videos'][0]['geometry_normalized']['line']['P2'][0]=0.01
 page.locator('#json-file').set_input_files({'name':'wrong-normalized.json','mimeType':'application/json','buffer':json.dumps(bad).encode()})
 page.wait_for_function("document.getElementById('status').textContent.includes('tidak konsisten')")
 check(snap()['geometry_native']==before,'inconsistent native/normalized import rejected atomically')
 page.locator('#target').select_option('line')
 p1=snap()['geometry_native']['line']['P1']
 setnum('P2 X',p1[0]);setnum('P2 Y',p1[1])
 check(page.locator('#export-current').is_disabled() and page.locator('#confirmed').is_disabled(),'zero-length line blocks export and approval')
 page.locator('#undo').click()
 check(not page.locator('#export-current').is_disabled(),'undo restores export after invalid geometry')
 page.set_viewport_size({'width':390,'height':900})
 check(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth+1'),'mobile viewport has no document horizontal overflow')
 page.set_viewport_size({'width':1440,'height':1100})
 page.screenshot(path='/tmp/tgdi-review-browser-final.png',full_page=True)
 check(not errors,'no browser JavaScript errors')
 check(not requests,'embedded editor runs without external resource requests')
 browser.close()
report={'status':'PASS','checked_at_utc':datetime.now(timezone.utc).isoformat(),'html_sha256':hashlib.sha256(html.encode()).hexdigest(),'browser':'system Chromium via Python Playwright','load_method':'page.set_content with embedded images; file:// navigation blocked by managed Chromium policy','desktop_file_open_tested':False,'checks_passed':len(checks),'checks':checks,'counting_models_or_pipeline_executed':False,'app_state_changes_from_checks':'In-memory browser only; no edited coordinates persisted to repository'}
Path('/tmp/tgdi-review-browser-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'status':'PASS','checks_passed':len(checks),'html_sha256':report['html_sha256']}))
