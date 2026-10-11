"""Read-only source-identity and browser figure checks, not crossing tests."""
import base64
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

repo = Path('/workspace/traffic-vehicle-counter-IDM-LOC')
root = repo / 'docs/evidence/phase_5/review_drafts/G1'
proposal = json.loads((root / 'candidate_geometry.json').read_text())
svg = ET.parse(root / 'TOR3-PAGI-G1.svg').getroot()
photo = svg.find('{http://www.w3.org/2000/svg}image')
original = repo / proposal['source_frame']['retained_path']
embedded = base64.b64decode(photo.get('href').split(',', 1)[1])
assert embedded == original.read_bytes()
assert hashlib.sha256(embedded).hexdigest() == proposal['source_frame']['sha256']
assert proposal['geometry_contract_accepted'] is False
assert proposal['synthetic_tests_executed'] is False
assert proposal['temporal_geometry_replay_executed'] is False
assert all(v is None for v in proposal['thresholds'].values())
assert proposal['anchor_example']['selected_anchor'] is None
checks = ['Embedded source PNG is byte-identical to actual retained frame5140', 'Geometry, anchor, thresholds, tests and replay are explicitly pending']
errors = []
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
    page = browser.new_page(viewport={'width': 1296, 'height': 736}, device_scale_factor=1)
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.set_content('<html><body style="margin:0">' + (root / 'TOR3-PAGI-G1.svg').read_text() + '</body></html>', wait_until='load')
    page.locator('svg').screenshot(path=str(root / 'TOR3-PAGI-G1.png'))
    figure = page.locator('svg').bounding_box()
    assert figure['width'] == 1280 and figure['height'] == 720
    checks.append('Standalone vector figure renders at native1280x720, device scale1')
    page.set_viewport_size({'width': 1100, 'height': 1000})
    page.set_content((root / 'review.html').read_text(), wait_until='load')
    assert page.locator('#source-frame').get_attribute('href') == photo.get('href')
    page.locator('#original').click()
    assert all(page.locator('#' + name).evaluate("e=>getComputedStyle(e).display") == 'none' for name in ['regions','line','bbox','center','bottom','legend'])
    page.locator('#restore').click()
    assert all(page.locator('#' + name).evaluate("e=>getComputedStyle(e).display") != 'none' for name in ['regions','line','bbox','center','bottom','legend'])
    checks.append('Frame-original and restore controls toggle only separate vector annotation layers')
    page.locator('[data-layer="center"]').uncheck()
    assert page.locator('#center').evaluate("e=>getComputedStyle(e).display") == 'none'
    assert page.locator('#bottom').evaluate("e=>getComputedStyle(e).display") != 'none'
    page.locator('[data-layer="center"]').check()
    checks.append('Center and bottom-center can be reviewed independently')
    page.locator('#review-figure').scroll_into_view_if_needed()
    r = page.locator('#review-figure').bounding_box()
    page.mouse.click(r['x'] + r['width'] * 160 / 1280, r['y'] + r['height'] * 650 / 720)
    import re
    chosen = page.locator('#chosen').inner_text()
    match = re.search(r'\(([0-9.]+), ([0-9.]+)\)', chosen)
    assert match, chosen
    px, py = map(float, match.groups())
    limit_x, limit_y = 1280 / r['width'] + .1, 720 / r['height'] + .1
    assert abs(px - 160) <= limit_x and abs(py - 650) <= limit_y, (r, chosen, limit_x, limit_y)
    checks.append('Scaled click maps back to nativepixelP1 within one displayed-pixel quantization; output is a pointer estimate')
    assert not errors, errors
    checks.append('No browser JavaScript errors during declared control checks')
    browser.close()

result = {'created_at_utc': datetime.now(timezone.utc).isoformat(), 'scope': 'Figure/source preservation and actual local browser interaction checks only; not synthetic geometry tests, model inference or temporal crossing replay.', 'status': 'passed', 'checks_passed': len(checks), 'checks_total': len(checks), 'checks': checks, 'browser': '/usr/bin/chromium via Playwright', 'rendered_figure': 'TOR3-PAGI-G1.png', 'rendered_figure_sha256': hashlib.sha256((root / 'TOR3-PAGI-G1.png').read_bytes()).hexdigest()}
(root / 'figure_validation.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
