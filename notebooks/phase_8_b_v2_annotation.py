"""B v2 audit rendering from retained measurements and a completed event ledger.

No detector, tracker, encoder, association or counting inference occurs here.
The sidebar replays the explicit event log, including upgrades and reversals;
its total is operational and contains inferred passages separately identified.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter, defaultdict
from copy import deepcopy
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

import phase_8_annotation_helpers as frozen


VERSION = "phase8_b_v2_annotation_v1"
SEMANTICS = "OFFLINE_LEDGER_LOG_REPLAY_NOT_AN_ONLINE_DECISION_OR_ACCURACY_MEASUREMENT"
CATEGORIES = ("motorcycle", "car", "truck")
DIRECTIONS = ("A_TO_B", "B_TO_A")
ROUTE_LABELS = {"LINE_MARGIN": "CROSSING_LINE",
                "OCCLUSION_DIFF_POLYGON": "OCCLUSION_DIFF_POLYGON",
                "ESTIMATED_TIMEOUT": "CHANGE_ID (ESTIMASI)"}
_require = frozen._require


def _identity(identity):
    _require(isinstance(identity, dict), "Result source_identity is required")
    for key in ("video_sha256", "records_sha256", "parent_run_id", "variant"):
        frozen._identifier(identity.get(key), "source identity " + key)
    for key in ("width", "height"):
        frozen._integer(identity.get(key), key, 1)
    _require(identity["variant"] == "raw", "B v2 renderer needs raw source measurements")


def build_timeline(result, *, frame_count=None, component_relations=None):
    """Validate one source ledger and compile constant-size counter snapshots.

    Changes in route/category revise the same event; count_delta does not
    accumulate duplicate passage counts. Cancelled events can appear during
    replay before their explicit -1 cancellation even though final totals omit
    them. Input objects are not modified.
    """
    identity = result.get("source_identity")
    _identity(identity)
    if frame_count is not None:
        frozen._integer(frame_count, "frame_count", 1)
    events, cancelled = result.get("events", []), result.get("cancelled_events", [])
    _require(isinstance(events, list) and isinstance(cancelled, list), "Event arrays required")
    by_id, final_ids = {}, set()
    for event in events + cancelled:
        _require(isinstance(event, dict), "Event must be an object")
        event_id = frozen._identifier(event.get("event_id"), "event ID")
        _require(event_id not in by_id, "Duplicate event ID")
        _require(event.get("source_identity") == identity, "Event belongs to another source")
        frozen._identifier(event.get("physical_unit_id"), "physical unit")
        frozen._identifier(event.get("passage_id"), "passage")
        frozen._integer(event.get("track_id"), "vehicle track", 1)
        _require(event.get("category") in CATEGORIES, "Unsupported product category")
        _require(event.get("direction") in DIRECTIONS, "Invalid event direction")
        _require(event.get("route") in ROUTE_LABELS, "Unknown event route")
        measured = event.get("evidence", {}).get("measured_crossing")
        _require(type(measured) is bool, "Event requires explicit measured_crossing evidence")
        _require(event["route"] == "LINE_MARGIN" or measured is False,
                 "Polygon/timeout cannot claim a measured line crossing")
        by_id[event_id] = deepcopy(event)
        if event in events:
            _require(event.get("accepted_count_event") is True,
                     "Final event must explicitly contribute to the operational count")
            _require(event.get("status") == "accepted", "Pending cannot enter accepted ledger")
            final_ids.add(event_id)
    final_passages = [(by_id[key]["physical_unit_id"], by_id[key]["passage_id"]) for key in final_ids]
    _require(len(final_passages) == len(set(final_passages)), "Duplicate final physical passage")
    logs = result.get("passage_log", [])
    _require(isinstance(logs, list), "passage_log must be an array")
    logs = sorted(enumerate(deepcopy(logs)), key=lambda pair: (pair[1].get("frame_index", -1), pair[0]))
    active, active_passages, snapshots, operations, displayed = {}, {}, [], [], []
    pivot = {category: {direction: 0 for direction in DIRECTIONS} for category in CATEGORIES}
    route_counts = {route: 0 for route in ROUTE_LABELS}

    def adjust(event, increment):
        pivot[event["category"]][event["direction"]] += increment
        route_counts[event["route"]] += increment

    for _, log in logs:
        frame = frozen._integer(log.get("frame_index"), "log frame")
        if frame_count is not None:
            _require(frame < frame_count, "Log outside source frames")
        delta = log.get("count_delta", 0)
        _require(type(delta) is int and delta in (-1, 0, 1), "Invalid passage count_delta")
        event_id = log.get("event_id")
        status = log.get("status")
        operational = delta != 0 or status == "upgraded"
        if not operational:
            continue
        _require(event_id in by_id, "Count log has no retained event")
        payload = dict(by_id[event_id])
        for key in ("track_id", "category", "direction", "route"):
            if key in log:
                payload[key] = log[key]
        _require(payload["category"] in CATEGORIES and payload["direction"] in DIRECTIONS
                 and payload["route"] in ROUTE_LABELS, "Invalid logged passage semantics")
        # A final event may have stronger evidence than its earlier timeout or
        # gap log. Never back-project the final evidence into the past, and do
        # not equate a LINE_MARGIN route with a directly measured crossing.
        measured = log.get("measured_crossing")
        _require(type(measured) is bool, "Operational log requires explicit measured_crossing")
        _require(payload["route"] == "LINE_MARGIN" or measured is False,
                 "Polygon/timeout log cannot claim a measured line crossing")
        payload["_measured_crossing"] = measured
        frozen._integer(payload["track_id"], "log vehicle track", 1)
        passage = (payload["physical_unit_id"], payload["passage_id"])
        if delta == 1:
            _require(event_id not in active and passage not in active_passages,
                     "Log attempts to increment one passage twice")
            active[event_id] = payload
            active_passages[passage] = event_id
            adjust(payload, 1)
        elif delta == -1:
            _require(event_id in active, "Cancellation has no active event")
            previous = active.pop(event_id)
            adjust(previous, -1)
            active_passages.pop((previous["physical_unit_id"], previous["passage_id"]))
        else:
            _require(event_id in active, "Upgrade has no previously accepted event")
            previous = active[event_id]
            _require((previous["physical_unit_id"], previous["passage_id"]) == passage,
                     "Upgrade changed physical passage identity")
            adjust(previous, -1)
            active[event_id] = payload
            adjust(payload, 1)
        display = dict(log, track_id=payload["track_id"], category=payload["category"],
                       direction=payload["direction"], route=payload["route"],
                       requested_label=ROUTE_LABELS[payload["route"]])
        displayed.append(display)
        operations.append(frame)
        measured = sum(item["_measured_crossing"] for item in active.values())
        snapshots.append({"pivot": deepcopy(pivot), "route_counts": dict(route_counts),
                          "accepted_so_far": len(active), "measured_so_far": measured,
                          "inferred_so_far": len(active) - measured})
    _require(set(active) == final_ids, "Event log does not reconcile with final accepted ledger")
    for event_id in final_ids:
        for key in ("category", "direction", "route", "track_id"):
            _require(active[event_id][key] == by_id[event_id][key],
                     "Final log/ledger differs: " + key)
        _require(active[event_id]["_measured_crossing"] == by_id[event_id]["evidence"]["measured_crossing"],
                 "Final log/ledger measured evidence differs")
    pending = []
    decisions = result.get("decisions", result.get("machine_decisions", []))
    _require(isinstance(decisions, list), "Decisions must be an array")
    for decision in decisions:
        if decision.get("status") not in ("pending", "pending_review"):
            continue
        _require(decision.get("accepted_count_event") is not True, "Pending decision cannot contribute")
        frame = decision.get("frame_index", decision.get("diagnostic", {}).get("frame_index"))
        frozen._integer(frame, "pending frame")
        if frame_count is not None:
            _require(frame < frame_count, "Pending outside source frames")
        pending.append({"frame_index": frame, "track_id": decision.get("track_id"),
                        "reasons": decision.get("reasons", decision.get("hard_block_reasons", []))})
    pending.sort(key=lambda item: item["frame_index"])
    relations = component_relations if component_relations is not None else result.get("component_links", [])
    links = defaultdict(list)
    for relation in relations:
        _require(relation.get("type") == "COMPONENT_OF", "Only explicit component relations may merge display boxes")
        vehicle = frozen._integer(relation.get("vehicle_track_id"), "component parent", 1)
        component = frozen._integer(relation.get("component_track_id"), "component track", 1)
        _require(vehicle != component, "Component cannot be its own vehicle")
        frozen._identifier(relation.get("relation_id"), "component relation ID")
        support = relation.get("support_frames")
        _require(isinstance(support, list) and bool(support), "Component needs retained measured support frames")
        _require(len(support) == len(set(support)), "Repeated component support frame")
        for frame in support:
            frozen._integer(frame, "component support frame")
            if frame_count is not None:
                _require(frame < frame_count, "Component support outside source frames")
            links[frame].append(deepcopy(relation))
    return {"source_identity": deepcopy(identity), "event_by_id": by_id,
            "final_accepted": len(final_ids), "final_pending": len(pending),
            "operations": operations, "snapshots": snapshots, "display_logs": displayed,
            "pending": pending, "pending_frames": [item["frame_index"] for item in pending],
            "component_links_by_frame": dict(links), "frame_count": frame_count,
            "semantics": SEMANTICS}


def timeline_at(timeline, frame_index):
    frozen._integer(frame_index, "frame index")
    if timeline["frame_count"] is not None:
        _require(frame_index < timeline["frame_count"], "Frame outside source")
    position = bisect_right(timeline["operations"], frame_index)
    pending_n = bisect_right(timeline["pending_frames"], frame_index)
    state = deepcopy(timeline["snapshots"][position - 1]) if position else {
        "pivot": {category: {direction: 0 for direction in DIRECTIONS} for category in CATEGORIES},
        "route_counts": {route: 0 for route in ROUTE_LABELS}, "accepted_so_far": 0,
        "measured_so_far": 0, "inferred_so_far": 0}
    state.update(frame_index=frame_index, accepted_final=timeline["final_accepted"],
                 pending_so_far=pending_n, pending_final=timeline["final_pending"],
                 recent_logs=list(reversed(timeline["display_logs"][max(0, position - 4):position])),
                 recent_pending=list(reversed(timeline["pending"][max(0, pending_n - 2):pending_n])))
    _require(sum(sum(row.values()) for row in state["pivot"].values()) == state["accepted_so_far"],
             "Pivot/event mismatch")
    return state


def _geometry_native(geometry, width, height):
    native = geometry.get("rendered_native_pixels", {})
    _require((native.get("width"), native.get("height")) == (width, height),
             "Geometry source dimensions differ")
    for key in ("side_a_polygon", "side_b_polygon"):
        _require(isinstance(native.get(key), list) and len(native[key]) >= 3, "Polygon missing")
        for point in native[key]:
            _require(isinstance(point, (list, tuple)) and len(point) == 2, "Invalid polygon point")
            for value in point:
                frozen._finite(value, "polygon coordinate")
    line = native.get("line", {})
    for key in ("P1", "P2"):
        _require(isinstance(line.get(key), (list, tuple)) and len(line[key]) == 2, "Line endpoint missing")
        for value in line[key]:
            frozen._finite(value, "line coordinate")
    half_width = geometry.get("line_margin_half_width_px", native.get("line_margin_half_width_px"))
    frozen._finite(half_width, "line margin half width")
    _require(half_width >= 0 and line["P1"] != line["P2"], "Invalid finite line band")
    return native, half_width


def _display_units(by_track, relations):
    """Union only positively supported person->motorcycle boxes at this frame.

    Ambiguous parent assignment is displayed as separate boxes. Bbox unions
    never supply geometry: vehicle_bc is retained from raw vehicle measurement.
    """
    parents = defaultdict(set)
    for relation in relations:
        parent, child = relation["vehicle_track_id"], relation["component_track_id"]
        if parent in by_track and child in by_track:
            if by_track[parent]["class_name"] == "motorcycle" and by_track[child]["class_name"] == "person":
                parents[child].add(parent)
    children = defaultdict(list)
    for child, choices in parents.items():
        if len(choices) == 1:
            children[next(iter(choices))].append(child)
    suppressed = {child for members in children.values() for child in members}
    units = []
    for track, observation in by_track.items():
        if track in suppressed:
            continue
        box = observation["raw_bbox"]
        components = sorted(children.get(track, []))
        boxes = [box] + [by_track[child]["raw_bbox"] for child in components]
        display_box = [min(item[0] for item in boxes), min(item[1] for item in boxes),
                       max(item[2] for item in boxes), max(item[3] for item in boxes)]
        units.append({"track_id": track, "class_name": observation["class_name"],
                      "display_bbox": display_box, "raw_vehicle_bbox": list(box),
                      "vehicle_bc": frozen._bc(box) if observation["class_name"] in ("motorcycle", "car", "truck", "bus") else None,
                      "component_track_ids": components, "component_additional_increment": 0})
    return units


def _render(source_frame, record, timeline, geometry, *, fps, video_id, frame_index=None):
    import cv2
    import numpy as np
    frozen._finite(fps, "FPS"); _require(fps > 0, "FPS must be positive")
    identity = timeline["source_identity"]
    height, width = source_frame.shape[:2]
    _require((width, height) == (identity["width"], identity["height"]), "Native source dimensions differ")
    index = record.get("frame_index") if frame_index is None else frame_index
    by_track = frozen._validate_record(record, index, identity, source_frame)
    native, margin = _geometry_native(geometry, width, height)
    state = timeline_at(timeline, index)
    image = source_frame.copy()
    line = native["line"]
    p1, p2 = np.asarray(line["P1"], dtype=float), np.asarray(line["P2"], dtype=float)
    unit = (p2 - p1) / np.linalg.norm(p2 - p1)
    normal = np.asarray([-unit[1], unit[0]])
    band = np.asarray([p1 + normal * margin, p2 + normal * margin,
                       p2 - normal * margin, p1 - normal * margin])
    overlay = image.copy()
    cv2.fillPoly(overlay, [np.rint(band).astype(np.int32)], (50, 205, 235))
    cv2.addWeighted(overlay, .18, image, .82, 0, image)
    cv2.polylines(image, [np.rint(band).astype(np.int32)], True, (90, 225, 250), 1, cv2.LINE_AA)
    cv2.line(image, tuple(np.rint(p1).astype(int)), tuple(np.rint(p2).astype(int)), (90, 225, 250), 2, cv2.LINE_AA)
    for key, color, letter in (("side_a_polygon", (235, 155, 65), "A"), ("side_b_polygon", (65, 155, 245), "B")):
        points = np.asarray(native[key], dtype=float)
        cv2.polylines(image, [np.rint(points).astype(np.int32)], True, color, 1, cv2.LINE_AA)
        midpoint = points.mean(axis=0)
        frozen._label(image, letter, midpoint[0], midpoint[1], color, width)
    units = _display_units(by_track, timeline["component_links_by_frame"].get(index, []))
    state["display_units"] = units
    state["band_vertices_native"] = band.tolist()
    for unit_info in units:
        box, name, track = unit_info["display_bbox"], unit_info["class_name"], unit_info["track_id"]
        color = frozen.CATEGORY_COLORS.get(name, frozen.CATEGORY_COLORS["other"])
        cv2.rectangle(image, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), color, 2, cv2.LINE_AA)
        text = f"ID {track} | {name}"
        if unit_info["component_track_ids"]:
            text += " | riders " + ",".join(map(str, unit_info["component_track_ids"])) + " (+0)"
        elif name == "person":
            text += " | component unknown +0"
        frozen._label(image, text, box[0], box[1] - 4, color, width)
        if unit_info["vehicle_bc"] is not None:
            point = tuple(round(value) for value in unit_info["vehicle_bc"])
            cv2.circle(image, point, 4, (10, 15, 20), -1, cv2.LINE_AA)
            cv2.circle(image, point, 3, color, -1, cv2.LINE_AA)
    canvas_height = max(height + 240, 960)
    if canvas_height % 2:
        canvas_height += 1
    canvas = np.full((canvas_height, width + 520, 3), (20, 25, 33), dtype=np.uint8)
    canvas[:height, :width] = image
    cv2.rectangle(canvas, (width, 0), (width + 519, canvas_height - 1), (27, 34, 44), -1)
    x, right = width + 18, width + 501
    panel_text = []

    def text(value, y, *, offset=0, scale=.42, color=(225, 232, 239), thickness=1):
        panel_text.append({"text": str(value), "x": x + offset, "y": y})
        frozen._text(canvas, str(value), (x + offset, y), scale=scale, color=color, thickness=thickness)

    text("REVIEW COUNTING B v2", 28, scale=.60, thickness=2)
    text(video_id, 52, scale=.45, color=(170, 192, 211))
    text("OFFLINE FINAL LEDGER / LOG REPLAY", 77, scale=.40, color=(100, 205, 250))
    text("Bukan keputusan online atau ukuran akurasi", 97, scale=.36)
    cv2.line(canvas, (x, 109), (right, 109), (65, 76, 91), 1)
    text("PASSAGE ACCEPTED (OPERASIONAL)", 135, scale=.45)
    text(f"{state['accepted_so_far']} / {state['accepted_final']}", 166, scale=.76, color=(150, 235, 185), thickness=2)
    text(f"Measured {state['measured_so_far']} | inferred {state['inferred_so_far']}", 190, scale=.39)
    text("Kategori", 221, color=(170, 192, 211))
    text("A > B", 221, offset=208, color=(170, 192, 211))
    text("B > A", 221, offset=309, color=(170, 192, 211))
    text("Total", 221, offset=411, color=(170, 192, 211))
    for position, category in enumerate(CATEGORIES):
        y = 250 + position * 28
        color = frozen.CATEGORY_COLORS[category]
        cv2.rectangle(canvas, (x, y - 11), (x + 8, y - 3), color, -1)
        text(frozen.DISPLAY_CATEGORY[category], y, offset=17)
        row = state["pivot"][category]
        for offset, value in zip((228, 330, 424), [row[key] for key in DIRECTIONS] + [sum(row.values())]):
            text(value, y, offset=offset, scale=.48)
    text("A>B mendekati | B>A menjauhi kamera", 335, scale=.36)
    text("LINE / POLYGON / TIMEOUT : " + " / ".join(str(state["route_counts"][key]) for key in ROUTE_LABELS), 359, scale=.38)
    text("Timeout = estimasi; CHANGE_ID belum terbukti", 380, scale=.35, color=(100, 205, 250))
    cv2.line(canvas, (x, 394), (right, 394), (65, 76, 91), 1)
    text("LOG KENDARAAN LEWAT", 420, scale=.46, color=(150, 235, 185))
    text("+1 event baru | +0 revisi | -1 pembatalan", 441, scale=.35)
    if not state["recent_logs"]:
        text("Belum ada passage pada posisi replay ini", 469, scale=.39)
    for position, log in enumerate(state["recent_logs"]):
        y = 469 + position * 65
        direction = log["direction"].replace("_TO_", ">")
        text(f"ID {log['track_id']} - {log['category']}; {direction}", y, scale=.42)
        color = (100, 205, 250) if log["route"] != "LINE_MARGIN" else (150, 235, 185)
        text(log["requested_label"], y + 19, scale=.36, color=color)
        evidence_label = "terukur" if log["measured_crossing"] else "inferensi"
        text(f"f{log['frame_index']} | {log['status']} | delta {log.get('count_delta', 0):+d} | {evidence_label}",
             y + 37, scale=.34)
    cv2.line(canvas, (x, 724), (right, 724), (65, 76, 91), 1)
    text(f"PENDING {state['pending_so_far']} / {state['pending_final']}", 750, scale=.46, color=(100, 205, 250))
    text("Di luar subtotal; kandidat != kendaraan unik", 773, scale=.35)
    for position, pending in enumerate(state["recent_pending"]):
        y = 802 + position * 53
        text(f"ID {pending['track_id']} | f{pending['frame_index']}", y, scale=.38)
        reasons = pending["reasons"]
        reason = ", ".join(map(str, reasons)) if isinstance(reasons, list) else str(reasons)
        lines = frozen._wrap(reason or "Inspect retained decision evidence", 66)
        text(lines[0], y + 18, scale=.30, color=(170, 192, 211))
    text("Rider +0. Satu unit/passage = satu event.", 934, scale=.35)
    frozen._text(canvas, f"FRAME {index:06d} | t ~= {index / fps:.3f}s", (16, height + 30), scale=.58, thickness=2)
    frozen._text(canvas, "Indeks frame nol / FPS; source PTS tidak ditetapkan", (16, height + 55), scale=.37)
    frozen._text(canvas, "BC = raw bbox kendaraan; bbox gabungan hanya tampilan", (16, height + 82), scale=.36)
    frozen._text(canvas, f"Margin half-width {margin:g}px | pita total {2 * margin:g}px | finite flat caps", (16, height + 106), scale=.35)
    frozen._text(canvas, "Warna bbox = kelas pengukuran saat ini; label log = kategori event", (16, height + 132), scale=.34)
    for position, label in enumerate(("motorcycle", "car", "truck", "bus", "person", "other")):
        lx = 16 + position * 102
        cv2.rectangle(canvas, (lx, height + 153), (lx + 9, height + 162), frozen.CATEGORY_COLORS[label], -1)
        frozen._text(canvas, label, (lx + 13, height + 163), scale=.30)
    frozen._text(canvas, "Tanpa asosiasi positif, komponen tidak digabung berdasarkan kedekatan.", (16, height + 192), scale=.33)
    state["panel_text"] = panel_text
    state["panel_sections_y"] = {"accepted": 135, "passage_log": 420, "pending": 750}
    return canvas, state


def render_frame(source_frame, record, result, geometry, *, fps, video_id, frame_index=None):
    """Render a single frame; renderer never computes new passage decisions."""
    timeline = build_timeline(result)
    return _render(source_frame, record, timeline, geometry, fps=fps, video_id=video_id, frame_index=frame_index)


def render_video(video_path, records_path, result, geometry, output_path, *, fps,
                 expected_frame_count, source_identity, component_relations=None, progress=None):
    """Write H.264/yuv420p directly with ffmpeg, then decode-check every frame.

    Requires an explicit, installed libx264 encoder. No silent codec fallback,
    source resizing, skipped frames, model dependencies, or count recomputation.
    Source/cache SHA and every source pixel/raw-detection link are verified.
    """
    import cv2
    frozen._finite(fps, "FPS"); _require(fps > 0, "FPS must be positive")
    frozen._integer(expected_frame_count, "expected frame count", 1)
    _identity(source_identity)
    _require(result.get("source_identity") == source_identity, "Renderer result/source identity differs")
    source = Path(video_path)
    records = Path(records_path)
    target = Path(output_path)
    _require(not target.exists(), "Output already exists; preserve previous evidence")
    _require(target.resolve() not in (source.resolve(), records.resolve()), "Output cannot replace an input")
    _require(target.suffix.lower() == ".mp4", "Output must be an MP4")
    input_hashes = {"video_sha256": frozen.sha256_file(source), "records_sha256": frozen.sha256_file(records)}
    for key, actual in input_hashes.items():
        _require(actual == source_identity[key], "Input source SHA differs: " + key)
    if geometry.get("source_video", {}).get("sha256") is not None:
        _require(geometry["source_video"]["sha256"] == source_identity["video_sha256"], "Geometry belongs to another video")
    timeline = build_timeline(result, frame_count=expected_frame_count, component_relations=component_relations)
    ffmpeg = shutil.which("ffmpeg")
    _require(ffmpeg is not None, "ffmpeg with libx264 must be installed")
    target.parent.mkdir(parents=True, exist_ok=True)
    log_path = target.with_suffix(".ffmpeg.log")
    _require(not log_path.exists(), "Codec log already exists; choose a fresh output")
    capture = cv2.VideoCapture(str(source))
    _require(capture.isOpened(), "Source video decoder unavailable")
    started = time.perf_counter()
    process, count, dimension, final_state, command = None, 0, None, None, None
    try:
        with log_path.open("wb") as codec_log:
            for record in frozen._records(records):
                ok, image = capture.read()
                _require(ok and record.get("frame_index") == count, "Source/cache frame alignment differs")
                canvas, final_state = _render(image, record, timeline, geometry, fps=fps,
                                             video_id=result.get("video_id", source.stem), frame_index=count)
                if process is None:
                    dimension = (canvas.shape[1], canvas.shape[0])
                    _require(all(value % 2 == 0 for value in dimension), "H264 output dimensions must be even")
                    command = [ffmpeg, "-v", "error", "-nostdin", "-n", "-f", "rawvideo", "-pix_fmt", "bgr24",
                               "-s:v", f"{dimension[0]}x{dimension[1]}", "-r", format(fps, ".17g"),
                               "-i", "pipe:0", "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
                               "-threads", "2", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(target)]
                    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=codec_log)
                _require(process.stdin is not None, "Encoder pipe unavailable")
                process.stdin.write(canvas.tobytes())
                count += 1
                if progress and (count % 500 == 0 or count == expected_frame_count):
                    progress({"frames_rendered": count, "expected_frame_count": expected_frame_count})
            more, _ = capture.read()
            _require(not more and count == expected_frame_count, "Full source/cache frame count differs")
            _require(process is not None, "No frames rendered")
            process.stdin.close()
            _require(process.wait() == 0, "H264 encoding failed; inspect codec log")
    finally:
        capture.release()
        if process is not None and process.poll() is None:
            if process.stdin is not None and not process.stdin.closed:
                process.stdin.close()
            process.terminate()
            process.wait()
    verify, decoded = cv2.VideoCapture(str(target)), 0
    try:
        _require(verify.isOpened(), "H264 output cannot be decoded")
        while True:
            ok, image = verify.read()
            if not ok:
                break
            _require((image.shape[1], image.shape[0]) == dimension, "Encoded dimensions changed")
            decoded += 1
    finally:
        verify.release()
    _require(decoded == count, "Encoded full frame count differs")
    for key, path in (("video_sha256", source), ("records_sha256", records)):
        _require(frozen.sha256_file(path) == input_hashes[key], "Source changed during rendering")
    return {"schema_version": VERSION, "claim_type": "ACTUAL_B_V2_LEDGER_RENDER_NOT_MODEL_INFERENCE",
            "semantics": SEMANTICS, "source_identity": deepcopy(source_identity),
            "output_video": {"path": str(target), "sha256": frozen.sha256_file(target),
                             "size_bytes": target.stat().st_size, "codec": "h264", "pixel_format": "yuv420p",
                             "frames_written": count, "frames_redecoded": decoded, "fps": fps,
                             "width": dimension[0], "height": dimension[1], "audio_preserved": False},
            "source_image_region": {"x": 0, "y": 0, "width": source_identity["width"],
                                    "height": source_identity["height"], "resized": False},
            "final_accepted": final_state["accepted_so_far"], "final_pending": final_state["pending_final"],
            "final_pivot": final_state["pivot"], "route_counts": final_state["route_counts"],
            "final_measured": final_state["measured_so_far"], "final_inferred": final_state["inferred_so_far"],
            "frame_pixel_and_raw_link_verified_every_frame": True, "inputs_unchanged_after_render": True,
            "new_detector_tracker_encoder_inference": False, "counting_rerun_by_renderer": False,
            "component_policy": "SUPPORT_FRAME_PERSON_MOTORCYCLE_UNION_DISPLAY_ONLY_RAW_VEHICLE_BC_PRESERVED",
            "pending_excluded_from_pivot": True, "ffmpeg_command": command,
            "codec_log": {"path": str(log_path), "sha256": frozen.sha256_file(log_path)},
            "opencv_version": cv2.__version__, "software_source_sha256": frozen.sha256_file(__file__),
            "render_and_decode_wall_seconds": time.perf_counter() - started}
