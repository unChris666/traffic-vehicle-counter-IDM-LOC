"""Annotation-only G3-L1: exact accepted geometry, named A vertices.

No original image, geometry coordinate, detector, tracker or encoder is changed.
Run from any directory; Chromium validation/rendering is in check_g3_labels.py.
"""
import base64
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / "docs/evidence/phase_5"
SOURCE = BASE / "review_drafts/G3"
OUT = BASE / "review_drafts/G3-L1"
OUT.mkdir(parents=True, exist_ok=True)
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
ns = {"s": NS}
draft = json.loads((SOURCE / "candidate_geometry.json").read_text())
svg = ET.parse(SOURCE / "TOR3-PAGI-G3.svg").getroot()
svg.set("aria-label", "G3-L1: G3 dengan label P1A, P1B, P1C, P1D; koordinat sama")
svg.find("s:title", ns).text = "G3-L1 — label vertex A; geometri G3 dipertahankan"
# All named coordinates use the same review reference; drawing stays native.
line_labels = svg.find(".//*[@id='line']").find("s:g", ns).findall("s:text", ns)
for text, value in zip(line_labels, ["P1 (4.5, 516.5)", "P2 (936.4, 305.4)"]):
    text.text = value
labels = dict(zip(["P1A", "P1B", "P1C", "P1D"], draft["user_supplied_side_a_points"]))
positions = {"P1A": (18, 606), "P1B": (18, 414), "P1C": (1010, 414), "P1D": (765, 184)}
layer = ET.SubElement(svg, f"{{{NS}}}g", {"id": "a-vertices"})
for name, (rx, ry) in labels.items():
    x, y = rx / 960 * 1280, ry / 540 * 720
    ET.SubElement(layer, f"{{{NS}}}circle", {"id": "vertex-" + name, "cx": str(x), "cy": str(y), "r": "4", "fill": "#7ad7ff", "stroke": "#063461", "stroke-width": "2"})
    lx, ly = positions[name]
    ET.SubElement(layer, f"{{{NS}}}rect", {"x": str(lx), "y": str(ly), "width": "250", "height": "29", "rx": "4", "fill": "#092944", "fill-opacity": ".94"})
    text = ET.SubElement(layer, f"{{{NS}}}text", {"id": "label-" + name, "x": str(lx + 8), "y": str(ly + 20), "fill": "white", "font-size": "16", "font-family": "system-ui,sans-serif"})
    text.text = f"{name} ({rx:.1f}, {ry:.1f})"
legend = svg.find(".//*[@id='legend']")
messages = ["G3-L1 · TOR3-PAGI · frame5140 · preview1280×720", "Koordinat label titik/garis: template960×540", "A→B mendekati kamera · B→A menjauhi kamera · BC", "Keliling A: P1A→P1B→P1D→P1C; titik tidak digeser", "G3/B disetujui; threshold eksperimen belum menjadi default"]
for text, value in zip(legend.findall("s:text", ns), messages):
    text.text = value
raw = base64.b64decode(svg.find("s:image", ns).attrib["href"].split(",", 1)[1])
assert hashlib.sha256(raw).hexdigest() == draft["source_frame"]["sha256"]
svg_text = ET.tostring(svg, encoding="unicode")
(OUT / "TOR3-PAGI-G3-L1.svg").write_text(svg_text + "\n")
html = (SOURCE / "review.html").read_text()
start, end = html.index("<svg"), html.index("</svg>") + len("</svg>")
html = html[:start] + svg_text + html[end:]
html = html.replace("Review TOR3-PAGI G3", "G3-L1 · label vertex A")
html = html.replace("G3 · template relatif untuk review", "G3-L1 · koordinat sama, label A diperjelas")
html = html.replace("Acuan baru yang diusulkan:960×540.", "Acuan G3 yang disetujui:960×540.")
html = html.replace("Urutan usulan A:", "Keliling sederhana A (P1A→P1B→P1D→P1C):")
html = html.replace("Aturan awal — masih usulan", "Aturan awal — persetujuan kontekstual G3")
html = html.replace("Polygon/kontrak ini belum disepakati; tes crossing dan state-machine replay belum dijalankan.", "Persetujuan G3 dibaca dalam konteks pertanyaan yang memuat aturan tersebut; jawaban dan interpretasinya tersimpan di feedback/G3_review_001.json. Hasil tes/replay dirujuk terpisah; gambar ini bukan hasil uji crossing.")
html = html.replace('<button id="original">', '<label><input type="checkbox" checked data-layer="a-vertices"> Label titik A</label><button id="original">')
(OUT / "review.html").write_text(html)
(OUT / "vertex_labels.json").write_text(json.dumps({"figure_id": "G3-L1", "source_geometry": "docs/evidence/phase_5/review_drafts/G3/candidate_geometry.json", "coordinate_reference": {"width": 960, "height": 540}, "labels_reference": labels, "perimeter_labels": ["P1A", "P1B", "P1D", "P1C"], "geometry_changed": False, "source_frame_changed": False}, indent=2) + "\n")
print(json.dumps({"output": str(OUT), "geometry_changed": False, "labels": labels}))
