"""Render a coordinate review figure over the unchanged retained source frame.

This is an annotation aid, not a geometry/crossing implementation or benchmark.
Run from any directory; reads repository-retained G1 provenance, not a Kaggle path.
"""
import base64
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / "docs/evidence/phase_5"
G1 = BASE / "review_drafts/G1"
OUT = BASE / "review_drafts/G2"
OUT.mkdir(parents=True, exist_ok=True)
geometry = copy.deepcopy(json.loads((G1 / "candidate_geometry.json").read_text()))
source = REPO / geometry["source_frame"]["retained_path"]
raw = source.read_bytes()
assert hashlib.sha256(raw).hexdigest() == geometry["source_frame"]["sha256"]
p1, p2 = [4.5, 516.5], [936.4, 305.4]
b_max_x = 875.0
b_line_y = p1[1] + (b_max_x - p1[0]) * (p2[1] - p1[1]) / (p2[0] - p1[0])
geometry.update({
    "draft_id": "TOR3-PAGI-G2",
    "status": "USER_SELECTED_LINE_DIRECTION_ANCHOR_WITH_PROPOSED_POLYGONS_AND_OPEN_CONTRACT",
    "created_at_utc": datetime.now(timezone.utc).isoformat(),
    "supersedes_draft": "TOR3-PAGI-G1",
    "feedback_reference": "docs/evidence/phase_5/feedback/G1_review_002.json",
    "coordinate_reference_status": "ASSUMPTION: user coordinates refer to the native1280x720 G1 viewer",
    "line_endpoints_pixels": {"P1": p1, "P2": p2},
    "line_selection_status": "USER_SELECTED; not demonstrated reliable across videos",
    "side_a_polygon_pixels": [[50, 425], [330, 425], p2, p1, [45, 470]],
    "side_b_polygon_pixels": [p1, [b_max_x, b_line_y], [b_max_x, 710], [180, 710], [120, 545]],
    "polygon_selection_status": "PROPOSAL: engineer-adjusted coverage for review; no exact vertices supplied by user",
    "side_b_max_x_pixels": b_max_x,
    "side_b_limit_selection_status": "USER_SELECTED",
    "selected_anchor": "bottom_center",
    "anchor_selection_status": "USER_SELECTED_BC",
    "anchor_measurement_source_status": "PROPOSAL: raw_bbox of detector-linked emitted observations; not Kalman predicted bbox",
    "confirmed_direction_metadata": {"A_TO_B": "approaching camera", "B_TO_A": "moving away from camera", "scope": "TOR3-PAGI"},
    "executed_scope": "Figure/source checks and bounded read-only placement screening only; temporal_geometry_replay_executed refers to accepted crossing state-machine replay, not placement algebra.",
    "default_template": {"requested_by_user": True, "reliability_all_videos": "UNKNOWN_NOT_VALIDATED", "resolution_aspect_transfer_policy": None, "per_video_geometry_review_required": True},
    "review_notes": [
        "P1/P2 are preserved exactly; limiting B to x875 does not truncate P2 atx936.4.",
        "The line intersects the distant left road view and extends above buildings to the right; placement requires review, not automatic acceptance as universally reliable.",
        "A/B are opposite spatial zones, not one polygon per traffic lane. Their proposed envelopes include background, not an accepted asphalt segmentation.",
        "A/B polygon vertices are engineer proposals under the user's instruction to adapt coverage to the new line.",
        "BC is user-selected; its sample point comes from the same actual raw_bbox as G1.",
        "Boundary, finite endpoint, gap/prediction and jitter policies remain proposals until agreed. Thresholds stay unset.",
        "A shared default template needs a declared resize/aspect policy and per-video evidence; no all-video reliability is claimed."
    ],
})
geometry.pop("proposed_direction_metadata_pending_feedback", None)
geometry["anchor_example"]["selected_anchor"] = "bottom_center"
(OUT / "candidate_geometry.json").write_text(json.dumps(geometry, indent=2) + "\n")

def points(poly):
    return " ".join(f"{x},{y}" for x, y in poly)

box = geometry["anchor_example"]["raw_bbox_xyxy_pixels"]
x1, y1, x2, y2 = box
cx, cy = geometry["anchor_example"]["center_pixels"]
bx, by = geometry["anchor_example"]["bottom_center_pixels"]
uri = "data:image/png;base64," + base64.b64encode(raw).decode()
svg = f'''<svg xmlns="http://www.w3.org/2000/svg" id="review-figure" viewBox="0 0 1280 720" width="1280" height="720" role="img" aria-label="G2 TOR3-PAGI: garis pilihan pengguna, usulan polygon, anchor BC terpilih">
<title>TOR3-PAGI G2 — selected line and BC; polygon and contract review</title>
<image id="source-frame" href="{uri}" x="0" y="0" width="1280" height="720"/>
<g id="regions" stroke-width="3" stroke-linejoin="round">
<polygon id="polygon-a" points="{points(geometry['side_a_polygon_pixels'])}" fill="#2475ff" fill-opacity=".2" stroke="#2475ff"/>
<polygon id="polygon-b" points="{points(geometry['side_b_polygon_pixels'])}" fill="#ff8b24" fill-opacity=".17" stroke="#ff8b24"/>
<g font-family="Arial,sans-serif" font-size="19" fill="white">
<rect x="132" y="437" width="170" height="29" rx="4" fill="#174aac"/><text x="141" y="458">A · wilayah jauh</text>
<rect x="497" y="633" width="180" height="30" rx="4" fill="#954100"/><text x="508" y="655">B · wilayah dekat</text>
</g></g>
<g id="limit" stroke="#ff8b24" stroke-width="2" stroke-dasharray="7 5"><line x1="875" y1="{b_line_y}" x2="875" y2="710"/>
<g stroke="none" font-family="Arial,sans-serif" font-size="17" fill="#ffd4ae"><rect x="756" y="566" width="114" height="28" fill="#111"/><text x="764" y="586">B: X≤875</text></g></g>
<g id="line" stroke="#fff047" stroke-width="4">
<line id="counting-line" x1="{p1[0]}" y1="{p1[1]}" x2="{p2[0]}" y2="{p2[1]}"/>
<circle cx="{p1[0]}" cy="{p1[1]}" r="6" fill="#fff047" stroke="#111" stroke-width="2"/>
<circle cx="{p2[0]}" cy="{p2[1]}" r="6" fill="#fff047" stroke="#111" stroke-width="2"/>
<g stroke="none" font-family="Arial,sans-serif" font-size="17" fill="#fff047">
<rect x="17" y="519" width="160" height="28" fill="#111"/><text x="25" y="539">P1 (4.5, 516.5)</text>
<rect x="909" y="270" width="192" height="28" fill="#111"/><text x="917" y="290">P2 (936.4, 305.4)</text>
</g></g>
<g id="bbox"><rect x="{x1}" y="{y1}" width="{x2-x1}" height="{y2-y1}" fill="none" stroke="white" stroke-width="2"/></g>
<g id="center"><circle cx="{cx}" cy="{cy}" r="5" fill="#36efff" stroke="#111" stroke-width="2"/><text x="278" y="513" fill="#36efff" font-family="Arial,sans-serif" font-size="18" stroke="#111" stroke-width=".5">C pembanding</text></g>
<g id="bottom"><circle cx="{bx}" cy="{by}" r="6" fill="#ff40dd" stroke="#111" stroke-width="2"/><rect x="277" y="532" width="110" height="28" fill="#111"/><text x="284" y="552" fill="#ff40dd" font-family="Arial,sans-serif" font-size="18">BC terpilih</text></g>
<g id="legend" font-family="Arial,sans-serif" fill="white">
<rect x="16" y="16" width="655" height="145" rx="8" fill="#101820" fill-opacity=".86"/>
<text x="31" y="42" font-size="20" font-weight="bold">G2 · TOR3-PAGI · frame 5140 · 1280×720</text>
<text x="31" y="70" font-size="17">Garis + BC: pilihan kamu · Polygon: usulan penyesuaian</text>
<text x="31" y="97" font-size="17">A→B mendekati kamera · B→A menjauhi kamera</text>
<text x="31" y="124" font-size="16">Template default: diminta · Keandalan semua video: belum diuji</text>
<text x="31" y="146" font-size="14">Kontrak batas/gap/jitter dan threshold belum ditetapkan</text>
</g></svg>'''
(OUT / "TOR3-PAGI-G2.svg").write_text(svg)
style = '''body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#f2f5f8;color:#142330}main{max-width:1320px;margin:auto;padding:20px}.card{background:white;border:1px solid #d5dfe8;border-radius:8px;padding:14px;margin:12px 0}.controls{display:flex;gap:18px;flex-wrap:wrap}svg{display:block;width:100%;height:auto}button{font:inherit;padding:6px 12px}li{margin:7px 0}output{font-variant-numeric:tabular-nums}'''
controls = " ".join(f'<label><input type="checkbox" checked data-layer="{ident}"> {label}</label>' for ident, label in [("regions", "Polygon A/B"), ("line", "Garis"), ("limit", "Batas B"), ("bbox", "BBox"), ("center", "C pembanding"), ("bottom", "BC terpilih"), ("legend", "Legenda")])
script = '''const figure=document.getElementById('review-figure');const boxes=[...document.querySelectorAll('[data-layer]')];function sync(){boxes.forEach(b=>document.getElementById(b.dataset.layer).style.display=b.checked?'':'none');}boxes.forEach(b=>b.addEventListener('change',sync));document.getElementById('original').onclick=()=>{boxes.forEach(b=>b.checked=false);sync();};document.getElementById('restore').onclick=()=>{boxes.forEach(b=>b.checked=true);sync();};function pos(e){return new DOMPoint(e.clientX,e.clientY).matrixTransform(figure.getScreenCTM().inverse());}figure.onpointermove=e=>{let p=pos(e);document.getElementById('cursor').textContent=`Koordinat native≈(${p.x.toFixed(1)}, ${p.y.toFixed(1)})`;};figure.onclick=e=>{let p=pos(e);document.getElementById('chosen').textContent=`Titik terakhir≈(${p.x.toFixed(1)}, ${p.y.toFixed(1)})`;};'''
document = f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Review TOR3-PAGI G2</title><style>{style}</style></head><body><main>
<h1>Revisi G2 · TOR3-PAGI</h1><p>Endpoint, batas B dan BC mengikuti feedback kamu. Polygon di bawah adalah usulan penyesuaian. Koordinat dianggap berasal dari viewer G1 native 1280×720; beri tahu jika acuanmu berbeda.</p>
<div class="card controls">{controls}<button id="original">Lihat frame asli</button><button id="restore">Pulihkan overlay</button></div><div class="card" style="padding:0;overflow:hidden">{svg}</div>
<div class="card">P1=(4.5,516.5); P2=(936.4,305.4). B berhenti X=875, sedangkan endpoint garis tetap X=936.4. Origin kiri-atas, X kanan, Y bawah.<br><output id="cursor">Gerakkan pointer untuk membaca koordinat.</output><br><output id="chosen"></output></div>
<div class="card"><strong>Hal yang terlihat pada penempatan baru</strong><p>Garis memotong bagian jalan yang lebih jauh di sebelah kiri dan memanjang di atas bangunan di sebelah kanan. Kendaraan di dekat bagian jauh tampak kecil pada frame sumber; ini risiko penempatan yang perlu diperiksa dengan observasi tersimpan, bukan bukti counting salah. Polygon adalah envelope ruang A/B, bukan segmentasi aspal.</p><p>BC≈(248.88,545.71) berasal dari raw bbox track 973, detection 1, ReID-on; titik C tetap tampil hanya sebagai pembanding. Tidak ada detector, tracker atau encoder yang dijalankan ulang.</p></div>
<div class="card"><strong>Usulan aturan untuk disepakati sebelum tes</strong><ul><li>Uji terhadap segmen P1–P2; melewati perpanjangannya atau hanya menyentuh belum menjadi crossing diterima.</li><li>Interior polygon tidak overlap; batas dan zona dekat garis bersifat netral sampai bukti arah cukup.</li><li>BC dari observasi detector-linked, bukan posisi prediksi Kalman. Kehilangan observasi tidak diisi sebagai crossing; kandidat yang melewati gap ditandai untuk review.</li><li>Asal A/B → lintasan melewati garis → tiba di sisi lawan. Lebar zona netral dan durasi konfirmasi dipilih setelah replay; belum ada nilai default.</li></ul><p>Identitas kendaraan ganda, kategori dan aturan crossing kembali belum diselesaikan oleh gambar ini. Proposal lengkap ada pada README G2.</p></div>
<div class="card"><strong>Template antarvideo — belum diputuskan</strong><p>Usulan: simpan koordinat relatif terhadap referensi 1280×720, lalu hasilkan koordinat pixel pada ukuran video tujuan. Ini hanya memindahkan template pada gambar; posisi kamera, crop dan bentuk jalan tetap perlu review per video. Geometri ini belum terbukti reliable untuk semua video.</p><p>Salin revisi/keputusan ke chat. Klik viewer tidak menyimpan perubahan, mengirim feedback atau menyetujui konfigurasi.</p></div>
</main><script>{script}</script></body></html>'''
(OUT / "review.html").write_text(document)
print(json.dumps({"draft": str(OUT), "line": geometry["line_endpoints_pixels"], "b_line_y_at_x875": b_line_y, "selected_anchor": geometry["selected_anchor"], "scope": "figure composition only"}))
