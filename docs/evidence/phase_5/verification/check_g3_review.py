"""Source/coordinate/static-draft/browser checks; no crossing state machine."""
import base64
import gzip
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

repo=Path(__file__).resolve().parents[4]
root=repo/'docs/evidence/phase_5/review_drafts/G3'
draft=json.loads((root/'candidate_geometry.json').read_text())
feedback=json.loads((repo/draft['feedback_references'][0]).read_text())
svg=ET.parse(root/'TOR3-PAGI-G3.svg').getroot();ns={'s':'http://www.w3.org/2000/svg'}
photo=svg.find('s:image',ns)
raw=base64.b64decode(photo.attrib['href'].split(',',1)[1])
assert raw==(repo/draft['source_frame']['retained_path']).read_bytes()
assert hashlib.sha256(raw).hexdigest()==draft['source_frame']['sha256']
checks=['Embedded raw frame remains byte-identical to retained source']
assert draft['user_supplied_side_a_points']==feedback['requested_side_a_points_in_supplied_order']
assert draft['side_a_polygon_reference']==[draft['user_supplied_side_a_points'][i] for i in [0,1,3,2]]
assert draft['line_endpoints_reference']=={'P1':[4.5,516.5],'P2':[936.4,305.4]}
assert draft['side_a_polygon_reference'][-1]==[936.6,305.8]
assert not draft['line_polygon_endpoint_difference_reference']['snapped']
checks.append('Exact user points and line remain separate; perimeter proposal preserves all four coordinates')
assert draft['original_display_dimensions'] is None
assert draft['template_reference']['claim_type']=='ENGINEER_PROPOSAL_NEW_CANVAS_NOT_DISCOVERED_SOURCE_SIZE'
assert draft['template_reference']['width']==960 and draft['template_reference']['height']==540
assert draft['transfer_policy']['status']=='USER_CONFIRMED_RELATIVE_TEMPLATE_WITH_PER_VIDEO_REVIEW'
assert draft['g2_native_coordinate_assumption_refuted']
checks.append('New reference is explicitly proposed; unknown original size and corrected G2 assumption are retained')
def same_pair(a,b):return all(math.isclose(x,y,rel_tol=1e-12,abs_tol=1e-12) for x,y in zip(a,b))
for ref,norm,native in zip(draft['side_a_polygon_reference']+draft['side_b_polygon_reference'],draft['normalized']['side_a_polygon']+draft['normalized']['side_b_polygon'],draft['rendered_native_pixels']['side_a_polygon']+draft['rendered_native_pixels']['side_b_polygon']):
    assert same_pair(norm,[ref[0]/960,ref[1]/540])
    assert same_pair(native,[norm[0]*1280,norm[1]*720])
    assert all(0<=v<=1 for v in norm)
for key,expected in {'P1':[6,688.6666666666666],'P2':[1248.5333333333333,407.2]}.items():assert same_pair(draft['rendered_native_pixels']['line'][key],expected)
checks.append('Explicit normalized mapping matches reference/native preview; all proposed points fit the reference extent')
line=svg.find(".//s:line[@id='counting-line']",ns)
assert same_pair([float(line.attrib[k]) for k in ['x1','y1']],draft['rendered_native_pixels']['line']['P1'])
assert same_pair([float(line.attrib[k]) for k in ['x2','y2']],draft['rendered_native_pixels']['line']['P2'])
assert draft['side_b_max_x_reference']==875
assert math.isclose(max(x for x,y in draft['rendered_native_pixels']['side_b_polygon']),875/960*1280)
assert float(line.attrib['x2'])>draft['rendered_native_pixels']['side_b_max_x']
for ident,key in [('polygon-a','side_a_polygon'),('polygon-b','side_b_polygon')]:
    actual=[list(map(float,p.split(','))) for p in svg.find(f".//s:polygon[@id='{ident}']",ns).attrib['points'].split()]
    assert actual==draft['rendered_native_pixels'][key]
checks.append('SVG uses mapped polygons/endpoints and B cap without truncating the full line')
def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
def proper_intersection(a,b,c,d):return cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0
def simple(poly):
    n=len(poly)
    return all(not proper_intersection(poly[i],poly[(i+1)%n],poly[j],poly[(j+1)%n]) for i in range(n) for j in range(i+1,n) if j!=(i+1)%n and i!=(j+1)%n)
def area(poly):return sum(poly[i][0]*poly[(i+1)%len(poly)][1]-poly[(i+1)%len(poly)][0]*poly[i][1] for i in range(len(poly)))/2
a,b=draft['side_a_polygon_reference'],draft['side_b_polygon_reference']
assert not simple(draft['user_supplied_side_a_points'])
assert simple(a) and simple(b) and area(a)!=0 and area(b)!=0
for poly,sign in [(a,-1),(b,1)]:
    for p in poly:
        value=cross(a[0],a[-1],p)
        magnitude=abs((a[-1][0]-a[0][0])*(p[1]-a[0][1]))+abs((a[-1][1]-a[0][1])*(p[0]-a[0][0]))
        assert sign*value>=-64*math.ulp(max(1,magnitude))
checks.append('Proposed A/B drawings are simple, nonzero-area and on opposite half-planes of their shared polygon edge; no crossing acceptance implied')
records=repo/'docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz'
with gzip.open(records,'rt') as handle:
    for line_text in handle:
        row=json.loads(line_text)
        if row['frame_index']==5140:break
track=next(t for t in row['emitted_tracks'] if t['track_id']==973)
assert track['raw_bbox']==draft['anchor_example']['raw_bbox_xyxy_pixels']
x1,y1,x2,y2=track['raw_bbox']
assert draft['anchor_example']['bottom_center_pixels']==[(x1+x2)/2,y2]
assert track['original_detection_index']==draft['anchor_example']['source_detection_index']
checks.append('Actual retained observation/detection link verifies the selected BC example')
assert not draft['geometry_contract_accepted'] and not draft['synthetic_crossing_tests_executed'] and not draft['accepted_crossing_state_machine_replay_executed'] and not draft['detector_tracker_encoder_rerun']
assert all(value is None for value in draft['thresholds'].values())
assert draft['transfer_policy']['all_video_reliability']=='UNKNOWN_NOT_VALIDATED'
checks.append('Contract/state replay/thresholds and reliability remain unestablished; no model rerun')
errors=[];layers=['regions','line','limit','bbox','center','bottom','legend']
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1296,'height':736},device_scale_factor=1)
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_content('<html><body style="margin:0">'+(root/'TOR3-PAGI-G3.svg').read_text()+'</body></html>',wait_until='load')
    page.locator('svg').screenshot(path=str(root/'TOR3-PAGI-G3.png'))
    r=page.locator('svg').bounding_box();assert [r['width'],r['height']]==[1280,720]
    checks.append('Figure renders at native1280x720 without altering source dimensions')
    page.set_viewport_size({'width':1100,'height':1000})
    page.set_content((root/'review.html').read_text(),wait_until='load')
    page.locator('#original').click();assert all(page.locator('#'+name).evaluate('e=>getComputedStyle(e).display')=='none' for name in layers)
    page.locator('#restore').click();assert all(page.locator('#'+name).evaluate('e=>getComputedStyle(e).display')!='none' for name in layers)
    assert page.locator('#source-frame').get_attribute('href')==photo.attrib['href']
    checks.append('Original/restore controls toggle only separate annotations')
    page.locator('[data-layer="center"]').uncheck();assert page.locator('#center').evaluate('e=>getComputedStyle(e).display')=='none';assert page.locator('#bottom').evaluate('e=>getComputedStyle(e).display')!='none'
    checks.append('BC stays visible independently of the comparator center')
    page.locator('#review-figure').scroll_into_view_if_needed();r=page.locator('#review-figure').bounding_box()
    page.mouse.click(r['x']+r['width']*6/1280,r['y']+r['height']*(688.6666666666666/720))
    output=page.locator('#chosen').inner_text();matches=re.findall(r'\(([0-9.]+),([0-9.]+)\)',output)
    assert len(matches)==3,output
    native,ref,norm=[list(map(float,m)) for m in matches]
    assert abs(native[0]-6)<=1280/r['width']+.1 and abs(native[1]-688.6666666666666)<=720/r['height']+.1
    assert abs(ref[0]-4.5)<=960/r['width']+.1 and abs(ref[1]-516.5)<=540/r['height']+.1
    assert same_pair([round(native[0]/1280,4),round(native[1]/720,4)],norm) or (abs(norm[0]-6/1280)<=1/r['width']+.0001 and abs(norm[1]-688.6666666666666/720)<=1/r['height']+.0001)
    checks.append('Pointer displays native, new-reference and relative coordinates within display quantization')
    assert not errors,errors;checks.append('No JavaScript errors during declared viewer interactions');browser.close()
report={'created_at_utc':datetime.now(timezone.utc).isoformat(),'scope':'Source, coordinate mapping, static proposed polygon topology and browser controls only; not synthetic crossing trajectories or accepted state-machine replay','status':'passed','checks_passed':len(checks),'checks_total':len(checks),'checks':checks,'roundoff_note':'Coordinate comparison and half-plane roundoff checks are numerical verification only; no product noise/gap/neutral-band threshold is selected.','rendered_figure_sha256':hashlib.sha256((root/'TOR3-PAGI-G3.png').read_bytes()).hexdigest()}
(root/'figure_validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
