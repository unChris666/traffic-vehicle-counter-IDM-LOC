"""Verify annotation-only G3-L1 change and render unchanged geometry/photo."""
import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET
from playwright.sync_api import sync_playwright

repo = Path(__file__).resolve().parents[4]
base = repo / "docs/evidence/phase_5/review_drafts"
out = base / "G3-L1"
ns = {"s": "http://www.w3.org/2000/svg"}
old = ET.parse(base / "G3/TOR3-PAGI-G3.svg").getroot()
new = ET.parse(out / "TOR3-PAGI-G3-L1.svg").getroot()
labels = json.loads((out / "vertex_labels.json").read_text())
checks = []
def ident(svg, name):
    return svg.find(f".//*[@id='{name}']")
raw = base64.b64decode(ident(new, "source-frame").attrib["href"].split(",", 1)[1])
assert ident(old, "source-frame").attrib == ident(new, "source-frame").attrib
assert hashlib.sha256(raw).hexdigest() == "65123bf8207ff223841bcc8f6a50287aef75909e2bcf4a9abb608370de0d72ee"
checks.append("Source photograph remains byte-identical")
for name in ["polygon-a", "polygon-b", "counting-line", "bbox", "center", "bottom", "limit"]:
    assert ET.tostring(ident(old, name)) == ET.tostring(ident(new, name)), name
checks.append("Line, A/B polygons, B cap and actual anchor example remain identical to G3")
for name, (rx, ry) in labels["labels_reference"].items():
    marker = ident(new, "vertex-" + name)
    assert float(marker.attrib["cx"]) == rx / 960 * 1280
    assert float(marker.attrib["cy"]) == ry / 540 * 720
    assert ident(new, "label-" + name).text == f"{name} ({rx:.1f}, {ry:.1f})"
assert labels["perimeter_labels"] == ["P1A", "P1B", "P1D", "P1C"]
assert [t.text for t in ident(new, "line").find("s:g", ns).findall("s:text", ns)] == ["P1 (4.5, 516.5)", "P2 (936.4, 305.4)"]
checks.append("All four vertex identities match exact reference coordinates; simple perimeter retained")
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path="/usr/bin/chromium", headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
    page = browser.new_page(viewport={"width": 1296, "height": 736}, device_scale_factor=1)
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.set_content('<html><body style="margin:0">' + (out / "TOR3-PAGI-G3-L1.svg").read_text() + '</body></html>', wait_until="load")
    page.locator("svg").screenshot(path=str(out / "TOR3-PAGI-G3-L1.png"))
    box = page.locator("svg").bounding_box()
    assert [box["width"], box["height"]] == [1280, 720]
    checks.append("Labelled vector figure renders at unchanged native dimensions")
    page.set_content((out / "review.html").read_text(), wait_until="load")
    page.locator('[data-layer="a-vertices"]').uncheck()
    assert page.locator("#a-vertices").evaluate("e=>getComputedStyle(e).display") == "none"
    assert page.locator("#regions").evaluate("e=>getComputedStyle(e).display") != "none"
    page.locator("#restore").click()
    assert page.locator("#a-vertices").evaluate("e=>getComputedStyle(e).display") != "none"
    page.locator("#original").click()
    assert page.locator("#a-vertices").evaluate("e=>getComputedStyle(e).display") == "none"
    assert page.locator("#source-frame").evaluate("e=>getComputedStyle(e).display") != "none"
    assert not errors, errors
    checks.append("Vertex layer toggles independently; original/restore preserve photo; no JavaScript errors")
    browser.close()
report = {"created_at_utc": datetime.now(timezone.utc).isoformat(), "scope": "Annotation/source/browser verification only, not synthetic crossing tests", "status": "passed", "checks_passed": len(checks), "checks_total": len(checks), "checks": checks, "rendered_figure_sha256": hashlib.sha256((out / "TOR3-PAGI-G3-L1.png").read_bytes()).hexdigest()}
(out / "figure_validation.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report))
