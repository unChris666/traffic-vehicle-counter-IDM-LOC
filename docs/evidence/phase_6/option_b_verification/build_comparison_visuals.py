"""Render retained-photo Option B case cards; never decode video or run a resolver.

Run from repository root:
    python docs/evidence/phase_6/option_b_verification/build_comparison_visuals.py

Scientific presentation only: the original overlays and original source pixels
remain unchanged. All input files, extracted tile bounds and output PNGs are
bound by SHA256 in the generated index. Display resizing is explicitly logged.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


RUN = "20261013T104301_354775Z"
WIDTH, HEIGHT = 1440, 900
BG = "#101722"
PANEL = "#1a2533"
FG = "#edf3fa"
MUTED = "#bac8d8"
GREEN = "#52dca1"
YELLOW = "#f6c763"
BLUE = "#7dc3ff"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_jsonl(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(str(Path("/usr/share/fonts/truetype/dejavu") / name), size)


def wrapped(draw, text, xy, maximum, *, size=23, fill=FG, bold=False, spacing=8):
    """Draw word-wrapped prose within one known panel width."""
    face = font(size, bold)
    x, y = xy
    lines = []
    for paragraph in text.split("\n"):
        line = ""
        for word in paragraph.split():
            trial = (line + " " + word).strip()
            if draw.textlength(trial, font=face) > maximum and line:
                lines.append(line)
                line = word
            else:
                line = trial
        lines.append(line)
    for line in lines:
        draw.text((x, y), line, font=face, fill=fill)
        y += size + spacing
    return y


def generate(repo):
    retained = repo / "docs/evidence/phase_6/option_b_temporal_review/sample_index.json"
    run = repo / "docs/evidence/phase_6" / RUN
    output = run / "comparison_visualizations"
    output.mkdir(exist_ok=True)
    sample = json.loads(retained.read_text())
    cases = {case["case_id"]: case for case in sample["cases"]}
    machine = {row["track_id"]: row for row in read_jsonl(run / "machine_decisions.jsonl.gz")}
    reviewed = {row["track_id"]: row for row in read_jsonl(run / "reviewed/resolved_decisions.jsonl.gz")}
    relations = read_jsonl(run / "relations.jsonl.gz")
    synthetic = json.loads((run / "synthetic_test_results.json").read_text())
    inputs = [retained, run/"machine_decisions.jsonl.gz", run/"relations.jsonl.gz", run/"reviewed/resolved_decisions.jsonl.gz", run/"reviewed/accepted_events.jsonl.gz", run/"reviewed/report.json", run/"configuration_input.json", run/"synthetic_test_results.json", run/"accepted_events.jsonl.gz"]
    input_hashes_before = {str(p.relative_to(repo)):sha(p) for p in inputs}
    checks = []

    def check(name, condition):
        checks.append({"check": name, "passed": bool(condition)})
        if not condition:
            raise ValueError(name)

    check("machine_accepted1772", machine[1772]["status"] == "accepted")
    check("retained_synthetic63_success", synthetic["successful"] and synthetic["tests_passed"] == 63 and synthetic["tests_run"] == 63)
    check("reviewed_accepted1772", reviewed[1772]["status"] == "accepted")
    check("1772_entire_decision_preserved", machine[1772] == reviewed[1772])
    for track in [923, 964, 973, 1323]:
        check(f"machine_pending{track}", machine[track]["status"] == "pending_review")
    for track in [923, 964]:
        check(f"reviewed_manual_accepted{track}", reviewed[track]["status"] == "accepted" and reviewed[track]["manual_review_applied"])
    check("973_duplicate_suppressed", reviewed[973]["status"] == "duplicate_suppressed" and not reviewed[973]["accepted_count_event"])
    check("1323_car_pending", reviewed[1323]["category"] == "car" and reviewed[1323]["status"] == "pending_review")
    duplicate = next(r for r in relations if r["type"] == "SAME_VEHICLE" and {r["first_track_id"], r["second_track_id"]} == {964, 973})
    negative = next(r for r in relations if r["type"] == "SAME_VEHICLE" and {r["first_track_id"], r["second_track_id"]} == {880, 892})
    check("964973_relation_rejected", duplicate["status"] == "REJECTED")
    check("964973_motion_exceeds_frozen_control", duplicate["features"]["relative_motion_residual_norm_max"] > duplicate["thresholds"]["max_relative_motion_residual_norm"])
    check("880892_relation_rejected", negative["status"] == "REJECTED")
    check("880892_not_counted_in_declared_case_window", 880 not in machine and 892 not in machine)

    specs = [
        {
            "name": "01_motorcycle1772", "case": "motorcycle1772_rider1774",
            "title": "ID1772 + rider1774: satu motorcycle",
            "machine": "ACCEPTED OTOMATIS · 1 passage", "reviewed": "Dipertahankan · event mesin sama",
            "color": GREEN, "frames": [7716, 7721, 7722],
            "labels": ["Origin kendaraan: frame7716", "Sebelum crossing: frame7721", "Crossing + konfirmasi: frame7722"],
            "notes": [
                "B→A. Origin7716; segmen BC kendaraan7721→7722; konfirmasi7722.",
                "Person1774 adalah komponen: tidak membuat event tambahan atau mengganti anchor kendaraan.",
                "Dukungan relasi lokal: tujuh frame7716–7722. Histori person1772 sebelum episode kendaraan tidak diwarisi."
            ],
            "track": 1772,
            "expected_geometry": [7716, 7721, 7722, 7722],
        },
        {
            "name": "02_duplicate964_973", "case": "duplicate964_973",
            "title": "ID964 / ID973: satu skuter, dua kandidat sumber",
            "machine": "PENDING · dua kandidat", "reviewed": "ACCEPTED MANUAL · 1 passage",
            "color": YELLOW, "frames": [5122, 5128, 5129],
            "labels": ["Origin vehicle964: frame5122", "BC vehicle964: frame5128", "BC vehicle964: frame5129"],
            "notes": [
                f"Duplicate motion {duplicate['features']['relative_motion_residual_norm_max']:.6f} > kontrol {duplicate['thresholds']['max_relative_motion_residual_norm']:.2f}; parameter tidak dituning agar lolos.",
                "Review foto menyatukan physical unit/passage. Event memakai964: origin5122, BC5128→5129.",
                "973 disimpan sebagai anggota duplikat, bukan event kedua. Person967 tidak menjadi count tambahan."
            ],
            "track": 964,
            "expected_geometry": [5122, 5128, 5129, 5129],
        },
        {
            "name": "03_car1323", "case": "car1323",
            "title": "ID1323: kategori car, identitas masih belum selesai",
            "machine": "PENDING · car", "reviewed": "PENDING · keputusan kategori car",
            "color": YELLOW, "frames": [6256, 6257, 6258],
            "labels": ["Raw/context: frame6256", "Origin + BC: frame6257", "Crossing + konfirmasi: frame6258"],
            "notes": [
                "Keputusan pengguna: ID1323=car untuk kasus ini. Tidak mengubah taxonomy minivan/angkot global.",
                "BC kendaraan6257→6258 memenuhi geometri, tetapi raw car d3 / ID1336 di tepi kiri belum teridentifikasi.",
                "Belum diketahui: kendaraan lain, bagian badan van, atau false detection. Tidak dipaksa accepted."
            ],
            "track": 1323,
            "expected_geometry": [6257, 6257, 6258, 6258],
        },
        {
            "name": "04_motorcycle923", "case": "motorcycle923_rider912",
            "title": "ID923: bukti identitas harus milik passage yang sama",
            "machine": "PENDING · bukti relasi di luar passage", "reviewed": "ACCEPTED MANUAL · 1 passage",
            "color": YELLOW, "frames": [5017, 5028, 5029],
            "labels": ["Origin vehicle923: frame5017", "Sebelum crossing: frame5028", "Crossing + konfirmasi: frame5029"],
            "notes": [
                "Event reviewed memakai raw BC motorcycle923: origin5017, crossing5028→5029.",
                "Relasi mesin yang didukung pada frame5116+ tidak boleh mengesahkan passage5017–5029.",
                "Review manual memakai foto di window passage ini. Versi v0 yang memakai dukungan masa depan telah digantikan v1."
            ],
            "track": 923,
            "expected_geometry": [5017, 5028, 5029, 5029],
        },
        {
            "name": "05_negative880_892", "case": "negative_motorcycles880_892",
            "title": "Kontrol negatif ID880 / ID892: dua kendaraan berbeda",
            "machine": "SAME_VEHICLE: REJECTED", "reviewed": "Tidak disatukan · kontrol asosiasi",
            "color": BLUE, "frames": [4975, 4977, 4979],
            "labels": ["Koeksistensi: frame4975", "Dua kendaraan: frame4977", "Bergerak terpisah: frame4979"],
            "notes": [
                "Foto menunjukkan dua motorcycle bersamaan; relasi duplikasi ditolak oleh spatial/motion/IoU gates.",
                "Tidak ada count event pada window kontrol4975–4980; crossing880 pada4988 di luar scope ini.",
                "Satu kasus negatif nyata yang diperiksa. Belum membuktikan sistem bebas salah penggabungan secara umum."
            ],
            "track": None,
        },
    ]
    source_hashes = {}
    index_cards = []
    for spec in specs:
        if spec["track"] is not None:
            diagnostic = machine[spec["track"]]["diagnostic"]
            check(f"caption_geometry_matches_source_{spec['name']}", [diagnostic[k] for k in ["origin_frame", "crossing_frame_start", "crossing_frame_end", "confirmation_frame"]] == spec["expected_geometry"])
        case = cases[spec["case"]]
        artifact = case["artifacts"]["crop_overlay"]
        source_path = repo / artifact["path"]
        check(f"source_overlay_sha_{spec['name']}", sha(source_path) == artifact["sha256"])
        source_hashes[artifact["path"]] = sha(source_path)
        source_sheet = Image.open(source_path).convert("RGB")
        view = case["views"]["crop"]
        tiles = {tile["frame_index"]: tile for tile in view["tiles"]}
        x1, y1, x2, y2 = view["native_crop_xyxy"]
        tile_width, tile_height = x2-x1, y2-y1
        card = Image.new("RGB", (WIDTH, HEIGHT), BG)
        draw = ImageDraw.Draw(card)
        draw.rectangle((0, 0, WIDTH, 8), fill=spec["color"])
        draw.text((28, 24), "TOR3-PAGI · PHASE6 OPSI B · REVIEW KASUS", font=font(19, True), fill=MUTED)
        wrapped(draw, spec["title"], (28, 56), WIDTH-56, size=31, bold=True)
        for left, label, status in [(28, "B_MACHINE", spec["machine"]), (740, "B_REVIEWED / AUDIT", spec["reviewed"])]:
            draw.rounded_rectangle((left, 110, left+670, 214), radius=12, fill=PANEL)
            draw.text((left+18, 124), label, font=font(17, True), fill=MUTED)
            wrapped(draw, status, (left+18, 153), 638, size=22, bold=True, fill=spec["color"], spacing=5)
        y = 237
        for note in spec["notes"]:
            y = wrapped(draw, "• " + note, (28, y), WIDTH-56, size=22, spacing=6) + 9
        check(f"text_fits_before_photos_{spec['name']}", y <= 436)
        photo_y, photo_width, photo_height = 490, 448, 288
        source_tiles = []
        for i, (frame, label) in enumerate(zip(spec["frames"], spec["labels"])):
            tile = tiles[frame]
            origin_x, origin_y = tile["sheet_image_origin_xy"]
            bounds = [origin_x, origin_y, origin_x+tile_width, origin_y+tile_height]
            check(f"sheet_bounds_{spec['name']}_{frame}", bounds[2] <= source_sheet.width and bounds[3] <= source_sheet.height)
            if spec["track"] is not None and frame >= machine[spec["track"]]["diagnostic"]["origin_frame"]:
                check(f"retained_track_present_{spec['name']}_{frame}", any(m["track_id"] == spec["track"] for m in tile["emitted_measurements"]))
            extracted = source_sheet.crop(tuple(bounds))
            scale = min(photo_width/extracted.width, photo_height/extracted.height)
            display_size = [round(extracted.width*scale), round(extracted.height*scale)]
            displayed = extracted.resize(display_size, Image.Resampling.LANCZOS)
            left = 28 + i*468
            draw.text((left, 456), label, font=font(19, True), fill=FG)
            draw.rectangle((left, photo_y, left+photo_width, photo_y+photo_height), fill=PANEL)
            card.paste(displayed, (left+(photo_width-display_size[0])//2, photo_y+(photo_height-display_size[1])//2))
            source_tiles.append({"frame_index":frame, "source_sheet_path":artifact["path"], "source_sheet_sha256":artifact["sha256"], "source_sheet_extract_xyxy":bounds, "native_crop_xyxy":view["native_crop_xyxy"], "display_size_width_height":display_size, "display_resize_filter":"Pillow LANCZOS", "extracted_rgb_sha256":hashlib.sha256(extracted.tobytes()).hexdigest()})
        wrapped(draw, "Foto retained + overlay sumber: bbox pengukuran mentah; titik BC kendaraan; garis G3. Resize hanya untuk tampilan.", (28, 798), WIDTH-56, size=18, fill=MUTED, spacing=6)
        draw.text((28, 855), "Scope kasus terbatas · bukan total video · bukan ground truth · tidak ada inference/model replay", font=font(17), fill=MUTED)
        dest = output / (spec["name"] + ".png")
        card.save(dest)
        check(f"output_dimensions_{spec['name']}", Image.open(dest).size == (WIDTH, HEIGHT))
        index_cards.append({"case_id":spec["case"], "title":spec["title"], "machine_status_caption":spec["machine"], "reviewed_status_caption":spec["reviewed"], "path":str(dest.relative_to(repo)), "sha256":sha(dest), "width_height":[WIDTH, HEIGHT], "photo_tiles":source_tiles, "notes":spec["notes"]})

    # One-screen overview uses statuses from the same case records and real-photo
    # thumbnail strips. It is a comparison of case decisions, never a live counter.
    overview = Image.new("RGB", (1440, 1160), BG)
    draw = ImageDraw.Draw(overview)
    draw.text((30, 25), "Opsi B TOR3-PAGI: keputusan per kasus", font=font(34, True), fill=FG)
    draw.text((30, 76), "B mesin: 1 event · B reviewed: 4 event (3 manual + 1 mesin dipertahankan)", font=font(23), fill=MUTED)
    draw.text((30, 113), "Angka subset kasus, bukan total lalu lintas video. Review manual tidak menjadi keberhasilan otomatis.", font=font(19), fill=MUTED)
    for i, (spec, record) in enumerate(zip(specs, index_cards)):
        top = 161 + i*181
        draw.rounded_rectangle((24, top, 1416, top+164), radius=12, fill=PANEL)
        draw.text((44, top+13), spec["title"], font=font(23, True), fill=FG)
        wrapped(draw, "Mesin: " + spec["machine"] + "\nReview: " + spec["reviewed"], (44, top+50), 762, size=21, fill=spec["color"], spacing=10)
        # A wide representative crop is intentionally a display thumbnail, not
        # another source measurement or another source for a counting event.
        card = Image.open(repo / record["path"]).convert("RGB")
        strip = card.crop((28, 490, 1412, 778))
        strip.thumbnail((552, 116), Image.Resampling.LANCZOS)
        overview.paste(strip, (840, top+41))
    draw.text((30, 1115), f"{synthetic['tests_passed']} uji sintetis lulus; bukti negatif video terbatas. Foto sumber dan event historis tidak diubah.", font=font(19), fill=MUTED)
    overview_path = output / "00_overview.png"
    overview.save(overview_path)
    check("overview_dimensions", Image.open(overview_path).size == (1440, 1160))
    machine_accepted = read_jsonl(run/"accepted_events.jsonl.gz")
    reviewed_accepted = read_jsonl(run/"reviewed/accepted_events.jsonl.gz")
    check("overview_count_machine1", len(machine_accepted) == 1)
    check("overview_count_reviewed4", len(reviewed_accepted) == 4)
    for inp in inputs:
        check(f"source_input_unchanged_{inp.name}_{inp.parent.name}", sha(inp) == input_hashes_before[str(inp.relative_to(repo))])
        source_hashes[str(inp.relative_to(repo))] = sha(inp)
    method = Path(__file__).resolve()
    index = {
        "claim_type":"EXECUTED_RETAINED_PHOTO_CASE_VISUALIZATION_NOT_MODEL_BENCHMARK",
        "source_run_id":RUN,
        "method_path":str(method.relative_to(repo)), "method_sha256":sha(method),
        "input_sha256":source_hashes,
        "source_identity":json.loads((run/"configuration_input.json").read_text())["input_identity"],
        "renderer":{"library":"Pillow", "version":Image.__version__, "font":"DejaVuSans / DejaVuSans-Bold", "font_files_sha256":{name:sha(Path('/usr/share/fonts/truetype/dejavu')/name) for name in ['DejaVuSans.ttf','DejaVuSans-Bold.ttf']}},
        "video_decoded":False, "detector_tracker_encoder_resolver_run":False,
        "source_photos_modified":False, "source_events_modified":False,
        "cards":index_cards,
        "overview":{"path":str(overview_path.relative_to(repo)), "sha256":sha(overview_path), "width_height":[1440,1160]},
        "display_semantics":"Headers describe one retained case; source BC comes only from measured vehicle bbox, never rider/union/interpolation. Photos resized for display only.",
        "validation":{"checks":len(checks), "passed":sum(c['passed'] for c in checks), "failed":sum(not c['passed'] for c in checks), "details":checks},
        "visual_review_status":"AWAITING_ACTUAL_TOOL_VIEW",
    }
    index_path = output / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2)+"\n")
    files = [*output.glob("*.png"), index_path]
    manifest = {"claim_type":"HASH_BOUND_VISUALIZATION_ARTIFACT_MANIFEST", "source_run_id":RUN, "method_sha256":sha(method), "files":[{"path":str(p.relative_to(repo)), "sha256":sha(p), "size_bytes":p.stat().st_size} for p in sorted(files)]}
    (output/"manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({"output":str(output), "cards":len(index_cards), "pngs":len(files)-1, "validation":{k:index['validation'][k] for k in ['checks','passed','failed']}}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    generate(args.repo.resolve())
