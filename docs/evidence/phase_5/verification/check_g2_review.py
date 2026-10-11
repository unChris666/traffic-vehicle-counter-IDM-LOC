"""Verify G2 source/feedback and render its review aid, not crossing tests."""
import base64
import gzip
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from playwright.sync_api import sync_playwright

repo = Path(__file__).resolve().parents[4]
root = repo / "docs/evidence/phase_5/review_drafts/G2"
draft = json.loads((root / "candidate_geometry.json").read_text())
feedback = json.loads((repo / draft["feedback_reference"]).read_text())
svg = ET.parse(root / "TOR3-PAGI-G2.svg").getroot()
ns = {"s": "http://www.w3.org/2000/svg"}
photo = svg.find("s:image", ns)
raw = base64.b64decode(photo.attrib["href"].split(",", 1)[1])
assert raw == (repo / draft["source_frame"]["retained_path"]).read_bytes()
assert hashlib.sha256(raw).hexdigest() == draft["source_frame"]["sha256"]
checks = ["Embedded source is byte-identical to the actual retained native frame"]
assert draft["line_endpoints_pixels"] == feedback["user_selected_line_endpoints"]
line = svg.find(".//s:line[@id='counting-line']", ns)
assert [float(line.attrib[k]) for k in ["x1", "y1", "x2", "y2"]] == [4.5, 516.5, 936.4, 305.4]
assert max(x for x, _ in draft["side_b_polygon_pixels"]) == feedback["side_b_max_x"] == 875
assert draft["selected_anchor"] == feedback["selected_anchor"] == "bottom_center"
checks.append("Rendered endpoints, B cap and anchor match actual user feedback; line not truncated at B cap")
assert not draft["geometry_contract_accepted"] and not draft["synthetic_tests_executed"] and not draft["temporal_geometry_replay_executed"]
assert all(v is None for v in draft["thresholds"].values())
assert draft["default_template"]["reliability_all_videos"] == "UNKNOWN_NOT_VALIDATED"
checks.append("Unagreed contract, thresholds and all-video reliability remain explicitly unresolved")
records = repo / "docs/evidence/phase_4/20261011T095924_205716Z_90cf7319/reid_on/track_records.jsonl.gz"
with gzip.open(records, "rt") as handle:
    row = next(json.loads(line) for line in handle if json.loads(line)["frame_index"] == 5140)
track = next(t for t in row["emitted_tracks"] if t["track_id"] == 973)
assert track["raw_bbox"] == draft["anchor_example"]["raw_bbox_xyxy_pixels"]
x1, y1, x2, y2 = track["raw_bbox"]
assert [(x1+x2)/2, y2] == draft["anchor_example"]["bottom_center_pixels"]
assert track["original_detection_index"] == draft["anchor_example"]["source_detection_index"]
checks.append("BC sample matches the actual retained Phase 4 emitted raw observation and detection link")
screen = json.loads((root / "placement_screening.json").read_text())
assert hashlib.sha256(records.read_bytes()).hexdigest() == screen["source_records_gzip_sha256"]
expected = {(o["frame"], int(tid)): o for tid, value in screen["tracks"].items() for bracket in value["arithmetic_brackets"] for o in bracket["observations"]}
found = set()
with gzip.open(records, "rt") as handle:
    for line in handle:
        row = json.loads(line)
        if row["frame_index"] > max(frame for frame, _ in expected):
            break
        for track in row["emitted_tracks"]:
            key = (row["frame_index"], track["track_id"])
            if key not in expected:
                continue
            x1, y1, x2, y2 = track["raw_bbox"]
            o = expected[key]
            assert o["bc"] == [(x1+x2)/2, y2]
            assert o["bbox_width"] == x2-x1 and o["bbox_height"] == y2-y1
            assert o["sourceidx"] == track["original_detection_index"]
            assert o["class"] == track["class_name"]
            found.add(key)
assert found == set(expected)
checks.append("All six placement-screening observations match the actual retained raw boxes and detection links")
errors = []
layers = ["regions", "line", "limit", "bbox", "center", "bottom", "legend"]
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_page(viewport={"width": 1296, "height": 736}, device_scale_factor=1)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content('<html><body style="margin:0">' + (root / "TOR3-PAGI-G2.svg").read_text() + '</body></html>', wait_until="load")
    page.locator("svg").screenshot(path=str(root / "TOR3-PAGI-G2.png"))
    r = page.locator("svg").bounding_box()
    assert [r["width"], r["height"]] == [1280, 720]
    checks.append("SVG browser rendering preserves native1280x720 dimensions")
    page.set_viewport_size({"width": 1100, "height": 1000})
    page.set_content((root / "review.html").read_text(), wait_until="load")
    page.locator("#original").click()
    assert all(page.locator("#"+name).evaluate("e=>getComputedStyle(e).display") == "none" for name in layers)
    page.locator("#restore").click()
    assert all(page.locator("#"+name).evaluate("e=>getComputedStyle(e).display") != "none" for name in layers)
    assert page.locator("#source-frame").get_attribute("href") == photo.attrib["href"]
    checks.append("Raw/restore controls toggle annotations without changing the source photograph")
    page.locator('[data-layer="center"]').uncheck()
    assert page.locator("#center").evaluate("e=>getComputedStyle(e).display") == "none"
    assert page.locator("#bottom").evaluate("e=>getComputedStyle(e).display") != "none"
    checks.append("Selected BC and comparator C remain separate figure layers")
    page.locator("#review-figure").scroll_into_view_if_needed()
    r = page.locator("#review-figure").bounding_box()
    page.mouse.click(r["x"]+r["width"]*4.5/1280, r["y"]+r["height"]*516.5/720)
    match = re.search(r"\(([0-9.]+), ([0-9.]+)\)", page.locator("#chosen").inner_text())
    assert match
    px, py = map(float, match.groups())
    assert abs(px-4.5) <= 1280/r["width"]+.1 and abs(py-516.5) <= 720/r["height"]+.1
    checks.append("Scaled pointer maps to native P1 within one displayed-pixel quantization")
    assert not errors, errors
    checks.append("No browser JavaScript errors during declared review controls")
    browser.close()
result = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "scope": "Figure/source/feedback and browser controls only; not synthetic crossing tests or accepted state-machine replay", "status": "passed", "checks_passed": len(checks), "checks_total": len(checks), "checks": checks, "rendered_figure_sha256": hashlib.sha256((root / "TOR3-PAGI-G2.png").read_bytes()).hexdigest()}
(root / "figure_validation.json").write_text(json.dumps(result, indent=2)+"\n")
print(json.dumps(result, indent=2))
