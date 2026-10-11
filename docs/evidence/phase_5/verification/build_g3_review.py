"""Build a proposed normalized template over an unchanged retained raw frame.

960x540 is a new engineering reference, not recovered source-display dimensions.
The output is a review draft, not an accepted crossing/counting configuration.
"""
import copy
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
BASE = REPO / 'docs/evidence/phase_5'
OUT = BASE / 'review_drafts/G3'
OUT.mkdir(parents=True, exist_ok=True)
old = BASE / 'review_drafts/G2'
previous = json.loads((old / 'candidate_geometry.json').read_text())
feedback = json.loads((BASE / 'feedback/G2_review_001.json').read_text())
ref_w, ref_h = 960.0, 540.0
p1, p2 = [4.5, 516.5], [936.4, 305.4]
supplied = feedback['requested_side_a_points_in_supplied_order']
perimeter_indices = [0, 1, 3, 2]
side_a = [supplied[i] for i in perimeter_indices]
b_max_x = 875.0
last_a = side_a[-1]
b_top_y = p1[1] + (b_max_x-p1[0]) * (last_a[1]-p1[1]) / (last_a[0]-p1[0])
side_b = [p1, [b_max_x,b_top_y], [b_max_x,532.5], [4.5,532.5]]
def normalized(point):
    return [point[0]/ref_w, point[1]/ref_h]
def native(point):
    return [normalized(point)[0]*previous['source_frame']['width'], normalized(point)[1]*previous['source_frame']['height']]
draft = {
    'draft_id': 'TOR3-PAGI-G3',
    'status': 'PROPOSED_NEW_REFERENCE_TEMPLATE_PENDING_GEOMETRY_AND_CONTRACT_REVIEW',
    'created_at_utc': datetime.now(timezone.utc).isoformat(),
    'source_video': previous['source_video'], 'source_frame': previous['source_frame'],
    'feedback_references': ['docs/evidence/phase_5/feedback/G2_review_001.json','docs/evidence/phase_5/feedback/G2_review_002.json'],
    'original_display_dimensions': None,
    'original_display_crop_or_margins': None,
    'g2_native_coordinate_assumption_refuted': True,
    'g2_placement_findings_apply_to_intended_gate': False,
    'template_reference': {'width':ref_w,'height':ref_h,'claim_type':'ENGINEER_PROPOSAL_NEW_CANVAS_NOT_DISCOVERED_SOURCE_SIZE','reason':'Fits all supplied points and uses16:9 like this TOR3-PAGI frame'},
    'user_supplied_side_a_points': supplied,
    'proposed_perimeter_indices_zero_based': perimeter_indices,
    'line_endpoints_reference': {'P1':p1,'P2':p2},
    'side_a_polygon_reference': side_a, 'side_b_polygon_reference': side_b,
    'side_b_max_x_reference': b_max_x,
    'normalization_convention': 'u=x/reference_width, v=y/reference_height; origin upper-left, x rightward, y downward; continuous image-edge coordinates',
    'normalized': {'line': {'P1':normalized(p1),'P2':normalized(p2)},'side_a_polygon':[normalized(p) for p in side_a],'side_b_polygon':[normalized(p) for p in side_b],'side_b_max_u':b_max_x/ref_w},
    'rendered_native_pixels': {'width':1280,'height':720,'line':{'P1':native(p1),'P2':native(p2)},'side_a_polygon':[native(p) for p in side_a],'side_b_polygon':[native(p) for p in side_b],'side_b_max_x':b_max_x/ref_w*1280},
    'line_polygon_endpoint_difference_reference': {'line_P2':p2,'polygon_A_right_vertex':last_a,'line_minus_polygon':[-0.2,-0.4],'snapped':False},
    'polygon_proposal_notes': ['A preserves all four user points; perimeter is reordered to prevent self-intersection.', 'B uses A1-to-A3 as its shared edge, not a snapped counting line; clips at user X875.', 'B lower extent532.5/540 retains the previous drawing margin710/720 as a proposal.', 'The complete counting segment is not truncated at B cap. Line and shared-region boundary differ slightly and remain explicit.'],
    'transfer_policy': {'status':'USER_CONFIRMED_RELATIVE_TEMPLATE_WITH_PER_VIDEO_REVIEW','application':'Map normalized points to native decoded-frame width/height for the full-frame preview; no crop, rotation or letterbox transform inferred. Viewpoint/path alignment still needs per-video review.','future_setup_page':'Phase11 UI; no production UI implemented here','all_video_reliability':'UNKNOWN_NOT_VALIDATED'},
    'selected_anchor':'bottom_center', 'anchor_selection_status':'USER_SELECTED',
    'anchor_example': copy.deepcopy(previous['anchor_example']),
    'anchor_source_status':'PROPOSAL_RAW_DETECTOR_LINKED_EMITTED_OBSERVATION_NOT_YET_AGREED',
    'confirmed_direction_metadata':previous['confirmed_direction_metadata'],
    'thresholds':previous['thresholds'],
    'geometry_contract_accepted':False,'synthetic_crossing_tests_executed':False,'accepted_crossing_state_machine_replay_executed':False,'detector_tracker_encoder_rerun':False,
}
(OUT / 'candidate_geometry.json').write_text(json.dumps(draft,indent=2)+'\n')
NS = 'http://www.w3.org/2000/svg'
ET.register_namespace('', NS)
svg = ET.parse(old / 'TOR3-PAGI-G2.svg').getroot()
ns={'s':NS}
def element(ident): return svg.find(f".//*[@id='{ident}']")
def points(poly): return ' '.join(f'{x},{y}' for x,y in poly)
svg.set('aria-label','G3 TOR3-PAGI: template relatif baru960x540, empat titik A dan BC terpilih')
svg.find('s:title',ns).text='G3 — new engineering template; source display size unknown; pending review'
element('polygon-a').set('points',points(draft['rendered_native_pixels']['side_a_polygon']))
element('polygon-b').set('points',points(draft['rendered_native_pixels']['side_b_polygon']))
line=element('counting-line')
np1,np2=native(p1),native(p2)
for key,value in zip(['x1','y1','x2','y2'],np1+np2): line.set(key,str(value))
line_group=element('line')
for circle, point in zip(line_group.findall('s:circle',ns),[np1,np2]):
    circle.set('cx',str(point[0])); circle.set('cy',str(point[1]))
labels=line_group.find('s:g',ns)
for rect,x,y,width in zip(labels.findall('s:rect',ns),[18,1010],[651,366],[185,242]):
    rect.set('x',str(x));rect.set('y',str(y));rect.set('width',str(width))
for text,x,y,value in zip(labels.findall('s:text',ns),[26,1018],[671,386],[f'P1 ({np1[0]:.1f}, {np1[1]:.1f})',f'P2 ({np2[0]:.1f}, {np2[1]:.1f})']):
    text.set('x',str(x));text.set('y',str(y));text.text=value
region_labels=element('regions').find('s:g',ns)
for rect,x,y in zip(region_labels.findall('s:rect',ns),[345,620],[446,640]):rect.set('x',str(x));rect.set('y',str(y))
for text,x,y in zip(region_labels.findall('s:text',ns),[354,631],[467,662]):text.set('x',str(x));text.set('y',str(y))
limit=element('limit');limit_line=limit.find('s:line',ns)
for key,value in {'x1':native([875,0])[0],'x2':native([875,0])[0],'y1':native([0,b_top_y])[1],'y2':710}.items():limit_line.set(key,str(value))
limit_label=limit.find('s:g',ns)
limit_label.find('s:rect',ns).set('x','942');limit_label.find('s:rect',ns).set('width','218')
limit_label.find('s:text',ns).set('x','950');limit_label.find('s:text',ns).text='B: u≤875/960 ≈0.9115'
legend=element('legend');legend.find('s:rect',ns).set('width','744')
for text,value in zip(legend.findall('s:text',ns),['G3 · TOR3-PAGI · frame5140 · preview1280×720','Template baru960×540 · ukuran gambar asal tidak diketahui','A→B mendekati kamera · B→A menjauhi kamera · BC terpilih','Empat titik A dipertahankan · urutan perimeter: usulan','Gambar untuk review · kontrak/threshold belum ditetapkan']):text.text=value
source=REPO/draft['source_frame']['retained_path']
assert hashlib.sha256(source.read_bytes()).hexdigest()==draft['source_frame']['sha256']
svg_text=ET.tostring(svg,encoding='unicode')
(OUT/'TOR3-PAGI-G3.svg').write_text(svg_text+'\n')
style='body{font:16px/1.5 system-ui,sans-serif;margin:0;background:#f2f5f8;color:#142330}main{max-width:1320px;margin:auto;padding:20px}.card{background:white;border:1px solid #d5dfe8;border-radius:8px;padding:14px;margin:12px 0}.controls{display:flex;gap:18px;flex-wrap:wrap}svg{display:block;width:100%;height:auto}button{font:inherit;padding:6px 12px}li{margin:7px 0}output{font-variant-numeric:tabular-nums}'
controls=' '.join(f'<label><input type="checkbox" checked data-layer="{ident}"> {label}</label>' for ident,label in [('regions','Polygon A/B'),('line','Garis'),('limit','Batas B'),('bbox','BBox'),('center','C pembanding'),('bottom','BC terpilih'),('legend','Legenda')])
js="""const figure=document.getElementById('review-figure');const boxes=[...document.querySelectorAll('[data-layer]')];function sync(){boxes.forEach(b=>document.getElementById(b.dataset.layer).style.display=b.checked?'':'none');}boxes.forEach(b=>b.addEventListener('change',sync));document.getElementById('original').onclick=()=>{boxes.forEach(b=>b.checked=false);sync();};document.getElementById('restore').onclick=()=>{boxes.forEach(b=>b.checked=true);sync();};function pos(e){return new DOMPoint(e.clientX,e.clientY).matrixTransform(figure.getScreenCTM().inverse());}function description(p){return `Native≈(${p.x.toFixed(1)},${p.y.toFixed(1)}) · template960×540≈(${(p.x*.75).toFixed(1)},${(p.y*.75).toFixed(1)}) · relatif≈(${(p.x/1280).toFixed(4)},${(p.y/720).toFixed(4)})`;}figure.onpointermove=e=>document.getElementById('cursor').textContent=description(pos(e));figure.onclick=e=>document.getElementById('chosen').textContent='Titik terakhir: '+description(pos(e));"""
document=f'''<!doctype html><html lang="id"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Review TOR3-PAGI G3</title><style>{style}</style></head><body><main>
<h1>G3 · template relatif untuk review</h1><p>Kamu memilih template relatif dengan review per video dan meminta default disiapkan. <strong>Acuan baru yang diusulkan:960×540.</strong> Ukuran gambar asal tetap tidak diketahui. Empat titikmu dipertahankan; hubungan perimeter dibuat sederhana agar polygon tidak menyilang.</p>
<div class="card controls">{controls}<button id="original">Lihat frame asli</button><button id="restore">Pulihkan overlay</button></div><div class="card" style="padding:0;overflow:hidden">{svg_text}</div>
<div class="card"><strong>Koordinat</strong><p>Dalam template: P1=(4.5,516.5), P2=(936.4,305.4), B maxX875. Urutan usulan A: (4.5,516.5)→(4.5,348.2)→(557.5,165.3)→(936.6,305.8). Normalisasi u=x/960,v=y/540. Preview1280×720 memakai x=u×1280,y=v×720.</p><output id="cursor">Gerakkan pointer untuk membaca tiga acuan koordinat.</output><br><output id="chosen"></output></div>
<div class="card"><strong>Perbedaan yang dipertahankan</strong><p>P2 garis (936.4,305.4) berbeda dari vertex polygon (936.6,305.8). B berbagi tepi polygon A lalu berhenti diX875. Garis tetap lengkap. Titik tidak disamakan otomatis dan belum ada toleransi yang dipilih.</p><p>Preview tidak memulihkan skala/crop gambar asal. Observasi penempatan G2 pada asumsi native tidak boleh dipakai sebagai penilaian garis yang kamu maksud. Source frame dan contoh BC dari track973 tetap dapat ditelusuri.</p></div>
<div class="card"><strong>Aturan awal — masih usulan</strong><p>BC dari bbox observasi mentah yang terhubung ke track; segmen P1–P2; batas polygon netral; sentuhan saja tidak diterima; endpoint/gap ambigu; prediksi tidak mengesahkan crossing. Threshold jitter dan konfirmasi dipilih setelah replay. Polygon/kontrak ini belum disepakati; tes crossing dan state-machine replay belum dijalankan.</p></div>
<div class="card"><strong>Penggunaan per video</strong><p>Template menjadi titik awal yang dapat direvisi, lalu konfigurasi efektif disimpan per video. Ukuran, crop/rotasi/letterbox dan posisi jalan perlu pemetaan eksplisit. Halaman setup garis/polygon termasuk fase UI berikutnya. Viewer ini hanya gambar review lokal; klik tidak menyimpan konfigurasi atau menyetujui aturan. Keandalan semua video belum terbukti.</p></div>
</main><script>{js}</script></body></html>'''
(OUT/'review.html').write_text(document)
print(json.dumps({'draft':str(OUT),'reference':[ref_w,ref_h],'native_line':draft['rendered_native_pixels']['line'],'all_coordinates_preserved_in_template':True,'scope':'Review draft only'}))
