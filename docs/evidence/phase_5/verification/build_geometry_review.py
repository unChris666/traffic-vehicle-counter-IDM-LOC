"""Compose a technical SVG/HTML review figure over byte-identical retained PNG.

No raster editing, model/tracker execution, crossing rules, or parameter choices.
"""
import base64
import hashlib
import html
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path('/workspace/traffic-vehicle-counter-IDM-LOC')
OUT = REPO / 'docs/evidence/phase_5/review_drafts/G1'
OUT.mkdir(parents=True, exist_ok=True)
FRAME = REPO / 'docs/evidence/phase_2/20261011T052950_360560Z_ed399fb8/samples/frame_000005140_raw.png'
RECORDS = Path('/tmp/kaggle-phase4-reid-output-20261011/reid_comparison/20261011T095924_205716Z_90cf7319/reid_on/representative_temporal_track_records.json')
frame_bytes = FRAME.read_bytes()
rows = json.loads(RECORDS.read_text())
row = next(r for r in rows if r['frame_index'] == 5140)
track = next(t for t in row['emitted_tracks'] if t['track_id'] == 973)
x1, y1, x2, y2 = track['raw_bbox']
center = [(x1 + x2) / 2, (y1 + y2) / 2]
bottom = [(x1 + x2) / 2, y2]
assert center == track['center']
assert [row['width'], row['height']] == [1280, 720]

proposal = {
    'status': 'PROPOSAL_PENDING_USER_FEEDBACK_NOT_EXECUTABLE_PIPELINE_CONFIGURATION',
    'draft_id': 'TOR3-PAGI-G1',
    'created_at_utc': datetime.now(timezone.utc).isoformat(),
    'source_video': {'filename': 'TOR3-PAGI.mp4', 'sha256': row['video_sha256']},
    'source_frame': {'frame_index': 5140, 'coordinate_space': 'native1280x720 pixel coordinates; origin upper-left; x rightward; y downward', 'width': 1280, 'height': 720, 'retained_path': str(FRAME.relative_to(REPO)), 'sha256': hashlib.sha256(frame_bytes).hexdigest()},
    'line_endpoints_pixels': {'P1': [160, 650], 'P2': [620, 500]},
    'side_a_polygon_pixels': [[70,425],[620,500],[160,650],[120,545],[75,470]],
    'side_b_polygon_pixels': [[160,650],[620,500],[850,550],[850,710],[180,710]],
    'spatial_labels': {'A': 'far/upper-left region relative to candidate line', 'B': 'near/lower-right region relative to candidate line', 'not_traffic_lane_polygons': True},
    'proposed_direction_metadata_pending_feedback': {'A_TO_B': 'approaching camera', 'B_TO_A': 'moving away from camera'},
    'anchor_example': {'source_variant': 'reid_on', 'source_run_id': '20261011T095924_205716Z_90cf7319', 'track_id': 973, 'source_detection_index': track['original_detection_index'], 'raw_model_class': track['class_name'], 'raw_bbox_xyxy_pixels': track['raw_bbox'], 'center_pixels': center, 'bottom_center_pixels': bottom, 'selected_anchor': None, 'raw_class_is_not_accepted_product_category': True},
    'source_records_sha256': hashlib.sha256(RECORDS.read_bytes()).hexdigest(),
    'review_notes': ['Each side spans both travel paths; regions are not assigned one-per-lane.', 'P2 extends slightly above asphalt edge to allow reviewing body-center anchor; its position is open.', 'B stops atx850 to avoid much of the burned-in lower-right text; exact boundary remains open.', 'Boundary sharing is drawn as a proposal; no boundary acceptance or neutral-band width is selected.', 'Different bbox components and duplicate physical tracks remain identity/category issues, not solved by this figure.'],
    'thresholds': {'neutral_band_width_pixels': None, 'destination_confirmation': None, 'gap_bridge': None},
    'geometry_contract_accepted': False,
    'synthetic_tests_executed': False,
    'temporal_geometry_replay_executed': False,
    'detector_tracker_encoder_rerun': False,
    'generated_illustration_is_measurement_evidence': False,
    'reference_example_semantics_overwritten': False
}
(OUT / 'candidate_geometry.json').write_text(json.dumps(proposal, indent=2) + '\n')

def points(values):
    return ' '.join(f'{x},{y}' for x, y in values)

source_uri = 'data:image/png;base64,' + base64.b64encode(frame_bytes).decode()
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" id="review-figure" viewBox="0 0 1280 720" width="1280" height="720" role="img" aria-label="Draf geometri G1 TOR3-PAGI: polygon A dan B, garis P1 P2, center dan bottom-center dari observasi tersimpan">
<title>TOR3-PAGI G1 — proposal pending feedback</title>
<image id="source-frame" href="{source_uri}" x="0" y="0" width="1280" height="720"/>
<g id="regions" stroke-width="3" stroke-linejoin="round">
<polygon points="{points(proposal['side_a_polygon_pixels'])}" fill="#2475ff" fill-opacity=".18" stroke="#2475ff"/>
<polygon points="{points(proposal['side_b_polygon_pixels'])}" fill="#ff8b24" fill-opacity=".17" stroke="#ff8b24"/>
<g font-family="Arial,sans-serif" font-size="19" fill="white" stroke="none">
<rect x="276" y="514" width="160" height="30" rx="4" fill="#174aac"/><text x="288" y="536">A · wilayah jauh</text>
<rect x="521" y="634" width="176" height="30" rx="4" fill="#954100"/><text x="533" y="656">B · wilayah dekat</text>
</g></g>
<g id="line" stroke="#fff047" stroke-width="4">
<line x1="160" y1="650" x2="620" y2="500"/>
<circle cx="160" cy="650" r="7" fill="#fff047" stroke="#151515" stroke-width="2"/>
<circle cx="620" cy="500" r="7" fill="#fff047" stroke="#151515" stroke-width="2"/>
<g font-family="Arial,sans-serif" font-size="19" fill="#fff047" stroke="none">
<rect x="112" y="652" width="40" height="29" fill="#111"/><text x="119" y="674">P1</text>
<rect x="627" y="470" width="40" height="29" fill="#111"/><text x="634" y="492">P2</text>
</g></g>
<g id="bbox"><rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="none" stroke="#fff" stroke-width="2"/>
<rect x="281" y="456" width="128" height="24" fill="#111" fill-opacity=".8"/><text x="287" y="473" fill="white" font-family="Arial,sans-serif" font-size="14">Observasi motor973</text></g>
<g id="center" stroke="#111" stroke-width="2"><circle cx="{center[0]}" cy="{center[1]}" r="5.5" fill="#36efff"/>
<rect x="280" y="494" width="28" height="26" fill="#111" stroke="none"/><text x="286" y="514" fill="#36efff" stroke="none" font-family="Arial,sans-serif" font-size="20">C</text></g>
<g id="bottom"><circle cx="{bottom[0]}" cy="{bottom[1]}" r="5.5" fill="#ff40dd" stroke="#111" stroke-width="2"/>
<rect x="277" y="532" width="39" height="26" fill="#111"/><text x="282" y="552" fill="#ff40dd" font-family="Arial,sans-serif" font-size="20">BC</text></g>
<g id="legend" font-family="Arial,sans-serif" fill="white">
<rect x="16" y="16" width="572" height="126" rx="8" fill="#101820" fill-opacity=".83"/>
<text x="31" y="42" font-size="20" font-weight="bold">DRAF G1 · TOR3-PAGI · frame5140</text>
<text x="31" y="68" font-size="17">Biru A · Oranye B · Kuning garis P1–P2</text>
<text x="31" y="94" font-size="17"><tspan fill="#36efff">C: center</tspan><tspan> · </tspan><tspan fill="#ff40dd">BC: bottom-center</tspan></text>
<text x="31" y="121" font-size="16">Belum disetujui · anchor/threshold belum dipilih</text>
</g></svg>'''
(OUT / 'TOR3-PAGI-G1.svg').write_text(svg)

document = '''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Review geometri TOR3-PAGI G1</title>
<style>body{font:16px/1.5 system-ui,sans-serif;background:#f2f5f8;color:#142330;margin:0}main{max-width:1320px;margin:auto;padding:22px}h1{font-size:24px;margin:0 0 8px}.card{background:white;border:1px solid #d5dfe8;border-radius:10px;padding:14px;margin:12px 0}.controls{display:flex;gap:20px;flex-wrap:wrap}label{cursor:pointer}svg{display:block;width:100%;height:auto;background:white}code{background:#edf2f6;padding:2px 5px;border-radius:3px}output{font-variant-numeric:tabular-nums}li{margin:7px 0}.small{font-size:14px;color:#46586a}textarea{width:100%;box-sizing:border-box;font:inherit;padding:10px;min-height:150px}button{font:inherit;padding:7px 12px;border:1px solid #9daebb;border-radius:6px;background:#fff;cursor:pointer}</style></head><body><main>
<h1>Review kandidat G1 · TOR3-PAGI</h1><p>Ini <strong>usulan geometri</strong> di atas frame asli1280×720. A adalah wilayah jauh dan B wilayah dekat; keduanya mencakup lintasan dua arah. Bentuk dan pemetaan arah menunggu feedback kamu.</p>
<div class="card controls"><label><input type="checkbox" checked data-layer="regions"> Polygon A/B</label><label><input type="checkbox" checked data-layer="line"> Garis P1–P2</label><label><input type="checkbox" checked data-layer="bbox"> Kotak observasi motor</label><label><input type="checkbox" checked data-layer="center"> Center C</label><label><input type="checkbox" checked data-layer="bottom"> Bottom-center BC</label><label><input type="checkbox" checked data-layer="legend"> Legenda</label><button id="original">Lihat frame asli</button><button id="restore">Pulihkan overlay</button></div>
<div class="card" style="padding:0;overflow:hidden">__SVG__</div>
<div class="card"><strong>Patokan koordinat:</strong> kiri-atas(0,0), X ke kanan, Y ke bawah. P1=(160,650), P2=(620,500).<br><output id="cursor">Gerakkan pointer atau klik gambar untuk melihat koordinat piksel asli.</output><br><output id="chosen"></output></div>
<div class="card"><strong>Yang perlu kamu review</strong><ol><li>Garis: apakah P1/P2 berada di lokasi yang diinginkan? P2 sedikit di atas tepi aspal untuk membandingkan anchor center.</li><li>Polygon: apakah A/B menyediakan ruang kendaraan sebelum dan sesudah garis? B berhenti sekitarX850 agar tidak banyak tertutup teks kanan-bawah.</li><li>Arah: usulan <strong>A→B mendekati kamera; B→A menjauhi</strong>. Konfirmasi dari pergerakan kendaraan; satu frame ini tidak membuktikan arah.</li><li>Anchor: C dan BC berasal dari bbox observasi model yang sama. Belum dipilih salah satu; keduanya akan dibandingkan secara temporal.</li></ol><p class="small">Kotak ini merupakan observasi model pada frame5140, track ReID-on973, source detection1. Duplikasi track/kategori belum diselesaikan oleh geometri. Posisi C≈(249,509), BC≈(249,546). Tidak ada crossing, traffic count atau threshold yang diterapkan.</p></div>
<div class="card"><label for="feedback"><strong>Template feedback</strong></label><textarea id="feedback">Garis P1–P2: setuju / geser ke ...
Polygon A: setuju / perlu diperluas atau diperkecil di ...
Polygon B: setuju / perlu diperluas atau diperkecil di ...
Arah A→B mendekat dan B→A menjauh: benar / koreksi ...
Catatan anchor C/BC: ...</textarea><p class="small">Salin feedback dan kirim di chat. Halaman ini bekerja offline; mengetik atau klik tidak mengirim feedback maupun menyetujui konfigurasi secara otomatis.</p></div>
<p class="small">Frame sumber dipertahankan byte-identik dalam SVG. Anotasi adalah vector terpisah. Ilustrasi generatif yang pernah ditampilkan bukan sumber koordinat. Urutan berikutnya: feedback→revisi→kontrak disepakati→tes sintetis→replay record tersimpan→keputusan parameter.</p>
</main><script>
const figure=document.getElementById('review-figure');
const boxes=Array.from(document.querySelectorAll('[data-layer]'));
function sync(){boxes.forEach(b=>document.getElementById(b.dataset.layer).style.display=b.checked?'':'none');}
boxes.forEach(b=>b.addEventListener('change',sync));
document.getElementById('original').addEventListener('click',()=>{boxes.forEach(b=>b.checked=false);sync();});
document.getElementById('restore').addEventListener('click',()=>{boxes.forEach(b=>b.checked=true);sync();});
function position(event){const p=new DOMPoint(event.clientX,event.clientY).matrixTransform(figure.getScreenCTM().inverse());return {x:p.x,y:p.y};}
figure.addEventListener('pointermove',e=>{const p=position(e);document.getElementById('cursor').textContent=`Pointer pada piksel asli: (${p.x.toFixed(1)}, ${p.y.toFixed(1)})`;});
figure.addEventListener('click',e=>{const p=position(e);document.getElementById('chosen').textContent=`Titik usulan terakhir: (${p.x.toFixed(1)}, ${p.y.toFixed(1)}). Sebutkan titik ini dalam feedback jika diperlukan.`;});
</script></body></html>'''.replace('__SVG__', svg)
(OUT / 'review.html').write_text(document)
(OUT / 'README.md').write_text('''# G1 — draft review geometry for TOR3-PAGI

**PROPOSAL, awaiting user feedback:** the user authorized the staged workflow: visual candidate → feedback → geometry revision → agreed contract → synthetic tests → retained temporal replay → parameter decision. Only the first visual candidate is prepared here. No crossing/counting logic, synthetic acceptance test, temporal geometry replay or threshold selection is claimed.

Open [review.html](review.html) in a browser. Toggle overlays, compare the original frame, and click to read native pixel coordinates. [TOR3-PAGI-G1.svg](TOR3-PAGI-G1.svg) is the deterministic vector figure over an embedded byte-identical original PNG. [candidate_geometry.json](candidate_geometry.json) preserves exact proposed coordinates, source hashes and actual bbox/anchor linkage; it is not an accepted pipeline configuration.

Source: retained Phase2 native raw frame5140,1280×720; anchor example from the actual Phase4 ReID-on record, ID973/source detection1. Center≈(249,509), bottom-center≈(249,546), from the same raw motorcycle bbox. Neither is selected. Source PNG is embedded unchanged; annotations occupy separate SVG layers. Any separately displayed imagegen illustration is conceptual and is not measurement evidence or the source of configuration coordinates.

Candidate line P1=(160,650), P2=(620,500). A is far/upper-left, B near/lower-right; both span the two travel paths rather than assigning one polygon per lane. Proposed direction mapping A→B approaching and B→A away requires user confirmation. The earlier example's accepted metadata is not overwritten. P2 extends slightly above the asphalt edge to permit comparing center; its position is open. B stops atX850 to reduce overlap with lower-right burned-in text. Detection remains full-frame.

Provide feedback in chat about line/P1/P2, polygon extent, and approaching/away mapping. The HTML notes box is local; editing does not send feedback, approve settings or save a new configuration. Raw bbox/model label is evidence, not an accepted product category or verified unique physical identity.

Neutral-band width, confirmation, gap/prediction rules, boundary/endpoint policies and final anchor remain OPEN. Later implementation must follow [PHASE_5_TASK.md](../../../../PHASE_5_TASK.md), [COUNTING_LOGIC.md](../../../../COUNTING_LOGIC.md), and the approved contract. No detector, tracker or encoder rerun was performed to prepare this figure.
''')
print(json.dumps({'draft': str(OUT), 'frame_sha256': proposal['source_frame']['sha256'], 'center': center, 'bottom_center': bottom, 'status': proposal['status']}))
