"""B v4 render-only audit: exact observation roles and readable raw-ID callouts.

The validated B v3 log compiler is reused unchanged. Layout does not resolve
identity, propagate roles, create observations, or recompute counting. Native
source pixels are not resized; a fixed, separately reserved audit area carries
labels which cannot be placed without collision inside the image.
"""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
import gzip
import json
from pathlib import Path
import shutil
import subprocess
import time

import phase_8_b_v3_annotation as previous

frozen = previous.frozen
VERSION = "phase8_b_v4_annotation_v1"
SEMANTICS = previous.SEMANTICS
CATEGORIES = previous.CATEGORIES
DIRECTIONS = previous.DIRECTIONS
CATEGORY_COLORS = dict(previous.CATEGORY_COLORS)
ROUTE_LABELS = dict(previous.ROUTE_LABELS)
_require = frozen._require
LABEL_SCALE = .45
LABEL_LINE_HEIGHT = 20
PANEL_WIDTH = 640


def build_b_v4_timeline(result, geometry=None, frame_count=None,
                        review_source_sha256=None, component_relations=None,
                        unit_assignments=None):
    """Compile ledger counters and exact-frame assignments, without mutation."""
    timeline = previous.build_timeline(result, frame_count=frame_count,
        component_relations=component_relations, unit_assignments=unit_assignments)
    if geometry is not None:
        identity = timeline["source_identity"]
        previous._geometry_native(geometry, identity["width"], identity["height"])
    if review_source_sha256 is not None:
        _require(isinstance(review_source_sha256, str) and len(review_source_sha256) == 64
                 and all(c in "0123456789abcdef" for c in review_source_sha256),
                 "review_source_sha256 must be a lowercase SHA256")
    audit = result.get("eligibility_audit", [])
    _require(isinstance(audit, list), "eligibility_audit must be an array")
    indexed = []
    for position, entry in enumerate(audit):
        _require(isinstance(entry, dict), "eligibility audit entry must be an object")
        frame = entry.get("frame_index", entry.get("decision_frame"))
        frozen._integer(frame, "eligibility audit frame")
        if frame_count is not None:
            _require(frame < frame_count, "Eligibility audit outside source")
        indexed.append((frame, position, deepcopy(entry)))
    indexed.sort(key=lambda item: (item[0], item[1]))
    timeline["eligibility_audit"] = [item[2] for item in indexed]
    timeline["eligibility_audit_frames"] = [item[0] for item in indexed]
    timeline["review_source_sha256"] = review_source_sha256
    event_logs = defaultdict(list)
    for entry in timeline["display_logs"]:
        event_logs[entry.get("event_id")].append(entry)
    timeline["event_logs"] = dict(event_logs)
    timeline["layout_max_units"] = max((len(items) for items in
        timeline["unit_assignments_by_frame"].values()), default=0)
    timeline["b_v4_timeline"] = True
    return timeline


def timeline_at(timeline, frame_index):
    state = previous.timeline_at(timeline, frame_index)
    upto = bisect_right(timeline.get("eligibility_audit_frames", []), frame_index)
    state["recent_eligibility_audit"] = list(reversed(
        timeline.get("eligibility_audit", [])[max(0, upto - 3):upto]))
    return state


def _display_units(by_track, timeline, frame_index):
    """Union boxes only when the child is positively assigned at this frame.

    Even a previously supported component link cannot override an unknown or
    pedestrian assignment now. A supported exact-frame link or bounded reviewed
    assignment must identify the same physical parent. Parent absent => no union.
    """
    assignments = timeline["unit_assignments_by_frame"].get(frame_index, {})
    _require(set(assignments).issubset(by_track),
             "Assignment has no measured emitted track at this frame")
    local_relations = timeline["component_links_by_frame"].get(frame_index, [])
    parents = defaultdict(set)
    for child, assignment in assignments.items():
        if assignment["role"] != "rider":
            continue
        _require(by_track[child]["class_name"] == "person", "Rider requires a raw person box")
        parent_unit = assignment.get("component_of_unit_id")
        parent_episode = assignment.get("component_of_episode_id")
        direct_parent = assignment.get("component_of_track_id", assignment.get("parent_vehicle_track_id", assignment.get("vehicle_track_id")))
        supported = {relation["vehicle_track_id"] for relation in local_relations
                     if relation["component_track_id"] == child}
        has_provenance = bool(assignment.get("review_refs") or assignment.get("role_provenance")
                              or assignment.get("association_provenance")
                              or assignment.get("evidence_refs"))
        for parent, parent_assignment in assignments.items():
            if parent == child or parent_assignment["role"] != "vehicle":
                continue
            if by_track[parent]["class_name"] != "motorcycle":
                continue
            same_parent = (parent_unit is not None and
                           parent_assignment["physical_unit_id"] == parent_unit)
            if parent_episode is not None and parent_assignment["episode_id"] != parent_episode:
                continue
            direct = direct_parent == parent
            if parent_unit is not None and not same_parent:
                continue
            if parent in supported and (parent_unit is None or same_parent):
                parents[child].add(parent)
            elif (same_parent or direct) and has_provenance:
                parents[child].add(parent)
    children = defaultdict(list)
    for child, options in parents.items():
        if len(options) == 1:
            children[next(iter(options))].append(child)
    suppressed = {child for members in children.values() for child in members}
    units = []
    for track, observation in sorted(by_track.items()):
        if track in suppressed:
            continue
        assignment = assignments.get(track, {})
        role = assignment.get("role", "unknown_person" if observation["class_name"] == "person" else "vehicle")
        if role != "vehicle":
            _require(observation["class_name"] == "person", "Person role requires raw person measurement")
        else:
            _require(observation["class_name"] != "person", "Raw person cannot silently become a vehicle")
        components = sorted(children.get(track, []))
        boxes = [observation["raw_bbox"]] + [by_track[child]["raw_bbox"] for child in components]
        union = [min(box[0] for box in boxes), min(box[1] for box in boxes),
                 max(box[2] for box in boxes), max(box[3] for box in boxes)]
        candidates = timeline["display_by_unit"].get(
            (assignment.get("physical_unit_id"), assignment.get("episode_id")), [])
        applicable = [candidate for candidate in candidates if candidate["start_frame"] <= frame_index]
        passage = applicable[-1] if applicable and role in ("vehicle", "pedestrian") else {}
        event = timeline["event_by_id"].get(passage.get("event_id"), {})
        if passage:
            _require((passage["category"] == "pedestrian") == (role == "pedestrian"),
                     "Passage display category conflicts with observation role")
        active_logs = [entry for entry in timeline["event_logs"].get(passage.get("event_id"), [])
                       if entry["frame_index"] <= frame_index]
        counted = sum(log.get("count_delta", 0) for log in active_logs) > 0
        category = (passage.get("category") or
                    ("pedestrian" if role == "pedestrian" else observation["class_name"]))
        bc = frozen._bc(observation["raw_bbox"]) if role in ("vehicle", "pedestrian") else None
        parent_tracks = sorted({parent for parent, entry in assignments.items()
            if entry.get("role") == "vehicle" and entry.get("physical_unit_id") == assignment.get("component_of_unit_id")
            and (assignment.get("component_of_episode_id") is None
                 or entry.get("episode_id") == assignment["component_of_episode_id"])})
        if not parent_tracks and assignment.get("component_of_track_id") in by_track:
            supplied_parent = assignment["component_of_track_id"]
            if (assignment.get("component_of_episode_id") is None or
                    assignments.get(supplied_parent, {}).get("episode_id") == assignment["component_of_episode_id"]):
                parent_tracks = [supplied_parent]
        if role == "rider":
            status = "RIDER +0"
        elif role in ("unknown", "unknown_person"):
            status = "ROLE UNKNOWN / NO COUNT"
        elif passage and not counted:
            status = "OFFLINE ID / NOT COUNTED YET"
        elif counted:
            # The log compiler preserves measured/inferred history. Do not
            # back-project stronger final event evidence into earlier frames.
            measured = active_logs[-1]["measured_crossing"]
            status = "COUNTED MEASURED" if measured else "COUNTED ESTIMATE"
        else:
            status = "NO ACCEPTED PASSAGE"
        units.append({"track_id": track, "raw_track_ids": [track] + components,
            "class_name": category, "raw_class_name": observation["class_name"],
            "role": role, "physical_unit_id": assignment.get("physical_unit_id"),
            "episode_id": assignment.get("episode_id"), "display_id": passage.get("display_id"),
            "passage_id": passage.get("passage_id"), "event_id": passage.get("event_id"),
            "event_activation_frame": event.get("activation_frame"), "counted_at_frame": counted,
            "display_bbox": union, "raw_vehicle_bbox": list(observation["raw_bbox"]),
            "vehicle_bc": bc if role == "vehicle" else None, "counting_bc": bc,
            "person_bc": bc if role == "pedestrian" else None,
            "component_track_ids": components, "component_additional_increment": 0,
            "parent_vehicle_track_ids": parent_tracks, "status_label": status,
            "assignment_provenance": deepcopy(assignment)})
    return units


def _overlaps(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _label_lines(unit):
    raw = "raw" + "+".join(map(str, unit["raw_track_ids"]))
    first = raw + " | " + unit["class_name"].upper()
    if unit["display_id"]:
        first += " | " + unit["display_id"]
    second = unit["status_label"]
    if unit["component_track_ids"]:
        second += " | rider " + ",".join(map(str, unit["component_track_ids"])) + " +0"
    if unit["role"] == "rider":
        second += (" -> raw" + ",".join(map(str, unit["parent_vehicle_track_ids"]))) if unit["parent_vehicle_track_ids"] else " | parent not observed"
    return [first, second]


def _text_size(lines):
    import cv2
    return max(cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, LABEL_SCALE, 1)[0][0]
               for line in lines) + 12, len(lines) * LABEL_LINE_HEIGHT + 6


def _layout_labels(units, width, height, max_units):
    """Deterministic, fixed-font placement; collision => outside-source callout."""
    occupied, layouts, overflow = [], [], 0
    for item in units:
        lines = _label_lines(item)
        label_width, label_height = _text_size(lines)
        _require(label_width <= width - 8, "Label exceeds source width; use a wider explicit audit canvas")
        x1, y1, x2, y2 = item["display_bbox"]
        clamp_x = lambda x: max(4, min(int(x), width - label_width - 4))
        candidates = [(clamp_x(x1), int(y1) - label_height - 4),
                      (clamp_x(x1), int(y2) + 4),
                      (clamp_x(x2 + 4), int(y1)),
                      (clamp_x(x1 - label_width - 4), int(y1))]
        # Search fixed rows after the local choices. Never shrink the font.
        candidates += [(4, y) for y in range(4, height - label_height - 3, label_height + 4)]
        rectangle = None
        for x, y in candidates:
            candidate = [x, y, x + label_width, y + label_height]
            if (0 <= y and candidate[2] <= width and candidate[3] <= height
                    and not any(_overlaps(candidate, prior) for prior in occupied)):
                rectangle = candidate
                break
        outside = rectangle is None
        if outside:
            y = height + 166 + overflow * (2 * LABEL_LINE_HEIGHT + 10)
            rectangle = [4, y, 4 + label_width, y + label_height]
            overflow += 1
            _require(overflow <= max_units, "Reserved callout capacity exceeded")
        occupied.append(rectangle)
        layouts.append({"track_id": item["track_id"], "raw_track_ids": item["raw_track_ids"],
            "lines": lines, "text": " / ".join(lines), "rectangle": rectangle,
            "outside_source": outside, "font_scale": LABEL_SCALE,
            "connector_from": [min(width - 1, max(0, round((x1 + x2) / 2))),
                               min(height - 1, max(0, round(y1)))],
            "connector_to": [rectangle[0], rectangle[1] + label_height // 2]})
        layout = layouts[-1]
        layout["connector_polyline"] = ([layout["connector_from"],
            [width - 2, layout["connector_from"][1]],
            [width - 2, layout["connector_to"][1]], layout["connector_to"]]
            if outside else [layout["connector_from"], layout["connector_to"]])
    return layouts


def _audit_lines(entry):
    track = entry.get("track_id", entry.get("raw_track_id", "?"))
    status = entry.get("status", entry.get("decision", entry.get("eligibility", "AUDIT")))
    reason = entry.get("reasons", entry.get("reason", entry.get("reason_codes", [])))
    if isinstance(reason, list):
        reason = "; ".join(map(str, reason))
    frame = entry.get("frame_index", entry.get("decision_frame"))
    lines = [f"raw{track} | f{frame} | {status}", str(reason or "Inspect retained eligibility evidence")]
    details = []
    for key in ("last_origin_frame", "last_observed_origin_frame", "timeout_frame", "elapsed_source_frames",
                "identity_conflict", "identity_timeout_hold", "episode_id"):
        if key in entry:
            details.append(f"{key}={entry[key]}")
    if details:
        lines.append(" | ".join(details))
    return lines


def _render(source_frame, record, timeline, geometry, *, fps, video_id, frame_index=None):
    import cv2
    import numpy as np
    frozen._finite(fps, "FPS"); _require(fps > 0, "FPS must be positive")
    height, width = source_frame.shape[:2]
    identity = timeline["source_identity"]
    _require((width, height) == (identity["width"], identity["height"]), "Native source dimensions differ")
    index = record.get("frame_index") if frame_index is None else frame_index
    by_track = frozen._validate_record(record, index, identity, source_frame)
    native, margin = previous._geometry_native(geometry, width, height)
    state = timeline_at(timeline, index)
    image = source_frame.copy()
    p1, p2 = np.asarray(native["line"]["P1"], float), np.asarray(native["line"]["P2"], float)
    direction = (p2 - p1) / np.linalg.norm(p2 - p1)
    normal = np.asarray([-direction[1], direction[0]])
    band = np.asarray([p1 + normal * margin, p2 + normal * margin,
                       p2 - normal * margin, p1 - normal * margin])
    overlay = image.copy()
    cv2.fillPoly(overlay, [np.rint(band).astype(np.int32)], (50, 205, 235))
    cv2.addWeighted(overlay, .18, image, .82, 0, image)
    cv2.polylines(image, [np.rint(band).astype(np.int32)], True, (90, 225, 250), 1, cv2.LINE_AA)
    cv2.line(image, tuple(np.rint(p1).astype(int)), tuple(np.rint(p2).astype(int)), (90, 225, 250), 2, cv2.LINE_AA)
    for key, color in (("side_a_polygon", (235, 155, 65)), ("side_b_polygon", (65, 155, 245))):
        cv2.polylines(image, [np.rint(native[key]).astype(np.int32)], True, color, 1, cv2.LINE_AA)
    units = _display_units(by_track, timeline, index)
    maximum = max(len(units), timeline.get("layout_max_units", 0), 1)
    layouts = _layout_labels(units, width, height, maximum)
    overflow_capacity = timeline.get("layout_callout_capacity", sum(item["outside_source"] for item in layouts))
    _require(sum(item["outside_source"] for item in layouts) <= overflow_capacity, "Reserved callout capacity exceeded")
    canvas_height = max(1160, height + 174 + overflow_capacity * (2 * LABEL_LINE_HEIGHT + 10))
    canvas_height += canvas_height % 2
    canvas = np.full((canvas_height, width + PANEL_WIDTH, 3), (20, 25, 33), np.uint8)
    canvas[:height, :width] = image
    source_canvas = canvas[:height, :width]
    # Draw all geometry/boxes first; labels are drawn last and cannot be erased
    # by another bbox. BC always derives from the raw measured parent box.
    for item in units:
        box = item["display_bbox"]
        color = CATEGORY_COLORS.get(item["class_name"], CATEGORY_COLORS["other"])
        cv2.rectangle(source_canvas, (round(box[0]), round(box[1])), (round(box[2]), round(box[3])), color, 2, cv2.LINE_AA)
        if item["counting_bc"] is not None:
            point = tuple(round(value) for value in item["counting_bc"])
            cv2.circle(source_canvas, point, 4, (10, 15, 20), -1, cv2.LINE_AA)
            cv2.circle(source_canvas, point, 3, color, -1, cv2.LINE_AA)
    for item, layout in zip(units, layouts):
        item["label"] = layout["text"]
        color = CATEGORY_COLORS.get(item["class_name"], CATEGORY_COLORS["other"])
        cv2.polylines(canvas, [np.asarray(layout["connector_polyline"], dtype=np.int32)],
                      False, color, 1, cv2.LINE_AA)
    # Callout connectors precede every filled label; no connector crosses text.
    for item, layout in zip(units, layouts):
        color = CATEGORY_COLORS.get(item["class_name"], CATEGORY_COLORS["other"])
        x1, y1, x2, y2 = layout["rectangle"]
        cv2.rectangle(canvas, (x1, y1), (x2 - 1, y2 - 1), color, -1)
        for offset, line in enumerate(layout["lines"]):
            frozen._text(canvas, line, (x1 + 6, y1 + 17 + offset * LABEL_LINE_HEIGHT),
                         scale=LABEL_SCALE, color=(8, 12, 18))
    x, right = width + 18, width + PANEL_WIDTH - 18
    cv2.rectangle(canvas, (width, 0), (width + PANEL_WIDTH - 1, canvas_height - 1), (27, 34, 44), -1)
    panel_text = []

    def text(value, y, *, offset=0, scale=.45, color=(225, 232, 239), thickness=1):
        value = str(value)
        _require(cv2.getTextSize(value, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)[0][0] <= right - x - offset,
                 "Panel text exceeds reserved width")
        panel_text.append({"text": value, "x": x + offset, "y": y})
        frozen._text(canvas, value, (x + offset, y), scale=scale, color=color, thickness=thickness)

    def wrapped(value, y, *, max_chars=76, scale=.40, max_lines=None):
        lines = frozen._wrap(str(value), max_chars)
        if max_lines is not None:
            lines = lines[:max_lines]
        for line in lines:
            text(line, y, scale=scale); y += 18
        return y

    text("REVIEW COUNTING B v4", 28, scale=.62, thickness=2)
    wrapped(video_id, 52)
    text("OFFLINE FINAL ID; COUNTERS FOLLOW LOG FRAME", 77, scale=.42, color=(100, 205, 250))
    text("Event ledger only. Reviewed overlay not added.", 99, scale=.40)
    cv2.line(canvas, (x, 111), (right, 111), (65, 76, 91), 1)
    text("PASSAGE ACCEPTED (OPERASIONAL)", 137, scale=.49)
    text(f"{state['accepted_so_far']} / {state['accepted_final']}", 169, scale=.80, thickness=2, color=(150, 235, 185))
    text(f"Measured {state['measured_so_far']} | inferred {state['inferred_so_far']}", 193)
    text(f"Vehicle {state['vehicle_so_far']} | pedestrian {state['pedestrian_so_far']}", 217)
    text("Kategori", 246); text("A > B", 246, offset=290); text("B > A", 246, offset=400); text("Total", 246, offset=515)
    for position, category in enumerate(CATEGORIES):
        y = 272 + position * 25
        text(category, y, color=CATEGORY_COLORS[category])
        row = state["pivot"][category]
        for offset, number in zip((310, 420, 533), [row[key] for key in DIRECTIONS] + [sum(row.values())]):
            text(number, y, offset=offset)
    text("A>B mendekati | B>A menjauhi kamera", 379, scale=.42)
    text("LINE / POLYGON / TIMEOUT : " + " / ".join(str(state["route_counts"][key]) for key in ROUTE_LABELS), 402, scale=.42)
    text("Timeout = ESTIMATE, not proof of ID change.", 425, scale=.40, color=(100, 205, 250))
    text("LOG KENDARAAN LEWAT", 461, scale=.49, color=(150, 235, 185))
    text("+1 event | +0 revision | -1 cancellation", 482, scale=.40)
    if not state["recent_logs"]:
        text("No accepted passage at this replay frame", 507)
    for position, log in enumerate(state["recent_logs"]):
        y = 508 + position * 60
        name = log.get("display_id") or "NO FINAL ID"
        text(f"raw{log['track_id']} | {name} | {log['display_category']} | {log['display_direction'].replace('_TO_', '>')}", y)
        text(f"{log['requested_label']} | {'MEASURED' if log['measured_crossing'] else 'INFERRED'}", y + 18, scale=.40)
        text(f"f{log['frame_index']} | delta {log.get('count_delta', 0):+d}", y + 36, scale=.40)
    cv2.line(canvas, (x, 746), (right, 746), (65, 76, 91), 1)
    text(f"PENDING {state['pending_so_far']} / {state['pending_final']}", 772, scale=.49, color=(100, 205, 250))
    text("Outside subtotal; pending keys != physical vehicles", 793, scale=.40)
    for position, entry in enumerate(state["recent_pending"]):
        y = 819 + position * 55
        text(f"raw{entry['track_id']} | f{entry['frame_index']}", y)
        wrapped(", ".join(map(str, entry["reasons"])), y + 18, max_lines=1)
    text("ELIGIBILITY / CLOCK / IDENTITY AUDIT", 947, scale=.46, color=(170, 205, 240))
    if not state["recent_eligibility_audit"]:
        text("No eligibility audit entry at this frame", 972, scale=.40)
    for position, entry in enumerate(state["recent_eligibility_audit"][:2]):
        y = 972 + position * 55
        lines = _audit_lines(entry)
        text(lines[0], y, scale=.40)
        wrapped(lines[1], y + 18, max_lines=1)
        if len(lines) > 2:
            wrapped(lines[2], y + 36, max_lines=1)
    parent_links = []
    for item in units:
        parent_links += [{"component_track_id": child, "vehicle_track_id": item["track_id"],
                          "frame_index": index, "additional_increment": 0}
                         for child in item["component_track_ids"]]
        if item["role"] == "rider" and len(item["parent_vehicle_track_ids"]) == 1:
            parent_links.append({"component_track_id": item["track_id"],
                "vehicle_track_id": item["parent_vehicle_track_ids"][0],
                "frame_index": index, "additional_increment": 0})
    text("RIDER PARENT / EXACT OBSERVATION FRAME", 1092, scale=.42)
    for position, link in enumerate(parent_links[:2]):
        text(f"raw{link['component_track_id']} -> motorcycle raw{link['vehicle_track_id']} | +0 | f{index}",
             1114 + position * 19, scale=.40)
    if not parent_links:
        text("No positive parent link at this measured frame", 1114, scale=.40)
    frozen._text(canvas, f"FRAME {index:06d} | t ~= {index / fps:.3f}s", (12, height + 28), scale=.60, thickness=2)
    frozen._text(canvas, "Native image, zero-based frame index / recorded FPS.", (12, height + 53), scale=.43)
    frozen._text(canvas, "BC from raw parent; union bbox is display-only. Rider +0.", (12, height + 78), scale=.41)
    frozen._text(canvas, f"Finite band half-width {margin:g}px. A blue / B orange.", (12, height + 103), scale=.42)
    frozen._text(canvas, "OVERFLOW RAW-ID CALLOUTS (fixed font, no hidden labels)", (12, height + 140), scale=.41)
    state.update(display_units=units, band_vertices_native=band.tolist(), label_layouts=layouts,
        panel_text=panel_text, panel_sections_y={"accepted": 137, "passage_log": 461, "pending": 772, "eligibility_audit": 947},
        label_font_scale=LABEL_SCALE, maximum_visible_units=maximum,
        role_parent_links=parent_links,
        source_image_region={"x": 0, "y": 0, "width": width, "height": height, "resized": False},
        raw_ids_visible=sorted(track for item in layouts for track in item["raw_track_ids"]))
    _require(state["raw_ids_visible"] == sorted(by_track), "A raw ID is missing or duplicated in visible labels")
    for layout in layouts:
        _require(0 <= layout["rectangle"][0] < layout["rectangle"][2] <= width
                 and 0 <= layout["rectangle"][1] < layout["rectangle"][3] <= canvas_height,
                 "Label outside reserved canvas")
    return canvas, state


def render_b_v4_frame(source_frame, record, result_or_timeline, geometry, *, fps, video_id,
                      frame_index=None, unit_assignments=None, component_relations=None,
                      review_source_sha256=None):
    timeline = result_or_timeline if result_or_timeline.get("b_v4_timeline") else build_b_v4_timeline(
        result_or_timeline, geometry, review_source_sha256=review_source_sha256,
        unit_assignments=unit_assignments, component_relations=component_relations)
    return _render(source_frame, record, timeline, geometry, fps=fps, video_id=video_id, frame_index=frame_index)


def render_b_v4_video(video_path, records_path, result, geometry, output_path, *, fps,
                      expected_frame_count, source_identity, component_relations=None,
                      unit_assignments=None, progress=None, review_source_sha256=None):
    """Sequential source verification, H264 encode and full decode; no inference."""
    import cv2
    frozen._finite(fps, "FPS"); _require(fps > 0, "FPS must be positive")
    frozen._integer(expected_frame_count, "expected frame count", 1)
    previous._identity(source_identity)
    _require(result.get("source_identity") == source_identity, "Renderer result/source identity differs")
    source, records, target = Path(video_path), Path(records_path), Path(output_path)
    _require(not target.exists(), "Output already exists; preserve previous evidence")
    _require(target.resolve() not in (source.resolve(), records.resolve()), "Output cannot replace an input")
    _require(target.suffix.lower() == ".mp4", "Output must be an MP4")
    hashes = {"video_sha256": frozen.sha256_file(source), "records_sha256": frozen.sha256_file(records)}
    for key, actual in hashes.items():
        _require(actual == source_identity[key], "Input source SHA differs: " + key)
    if geometry.get("source_video", {}).get("sha256") is not None:
        _require(geometry["source_video"]["sha256"] == hashes["video_sha256"], "Geometry belongs to another video")
    timeline = build_b_v4_timeline(result, geometry, frame_count=expected_frame_count,
        component_relations=component_relations, unit_assignments=unit_assignments,
        review_source_sha256=review_source_sha256)
    # Reserve one output size for the entire video. The deterministic layout
    # prepass reads boxes/assignments only, including unassigned measured tracks;
    # it never creates a role, association, count or missing observation.
    maximum, overflow_capacity = 0, 0
    for record in frozen._records(records):
        by_track = {item["track_id"]: item for item in record.get("emitted_tracks", [])}
        units = _display_units(by_track, timeline, record["frame_index"])
        maximum = max(maximum, len(by_track))
        layouts = _layout_labels(units, source_identity["width"], source_identity["height"], max(len(by_track), 1))
        overflow_capacity = max(overflow_capacity, sum(item["outside_source"] for item in layouts))
    timeline["layout_max_units"] = maximum
    timeline["layout_callout_capacity"] = overflow_capacity
    ffmpeg = shutil.which("ffmpeg")
    _require(ffmpeg is not None, "ffmpeg with libx264 must be installed")
    target.parent.mkdir(parents=True, exist_ok=True)
    log_path, labels_path = target.with_suffix(".ffmpeg.log"), target.with_suffix(".labels.jsonl.gz")
    _require(not log_path.exists() and not labels_path.exists(), "Render evidence exists; choose a fresh output")
    capture = cv2.VideoCapture(str(source))
    _require(capture.isOpened(), "Source video decoder unavailable")
    started = time.perf_counter()
    process, count, dimension, final_state, command = None, 0, None, None, None
    try:
        with log_path.open("wb") as codec_log, gzip.open(labels_path, "wt", encoding="utf-8") as labels:
            for record in frozen._records(records):
                ok, image = capture.read()
                _require(ok and record.get("frame_index") == count, "Source/cache frame alignment differs")
                canvas, final_state = _render(image, record, timeline, geometry, fps=fps,
                    video_id=result.get("video_id", source.stem), frame_index=count)
                if process is None:
                    dimension = (canvas.shape[1], canvas.shape[0])
                    _require(all(value % 2 == 0 for value in dimension), "H264 dimensions must be even")
                    command = [ffmpeg, "-v", "error", "-nostdin", "-n", "-f", "rawvideo", "-pix_fmt", "bgr24",
                        "-s:v", f"{dimension[0]}x{dimension[1]}", "-r", format(fps, ".17g"), "-i", "pipe:0", "-an",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-threads", "2", "-pix_fmt",
                        "yuv420p", "-movflags", "+faststart", str(target)]
                    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=codec_log)
                _require((canvas.shape[1], canvas.shape[0]) == dimension, "Layout dimensions changed during video")
                process.stdin.write(canvas.tobytes())
                labels.write(json.dumps({"frame_index": count, "raw_ids_visible": final_state["raw_ids_visible"],
                    "label_layouts": final_state["label_layouts"], "accepted_so_far": final_state["accepted_so_far"],
                    "measured_so_far": final_state["measured_so_far"], "inferred_so_far": final_state["inferred_so_far"],
                    "pending_so_far": final_state["pending_so_far"],
                    "role_parent_links": final_state["role_parent_links"],
                    "display_units": [{key: item.get(key) for key in ("track_id", "raw_track_ids", "role",
                        "physical_unit_id", "episode_id", "display_id", "passage_id", "event_id",
                        "event_activation_frame", "counted_at_frame", "component_track_ids",
                        "parent_vehicle_track_ids", "status_label", "raw_vehicle_bbox", "counting_bc")}
                        for item in final_state["display_units"]]}, sort_keys=True) + "\n")
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
            process.terminate(); process.wait()
    decoder, decoded = cv2.VideoCapture(str(target)), 0
    try:
        _require(decoder.isOpened(), "H264 output cannot be decoded")
        while True:
            ok, image = decoder.read()
            if not ok:
                break
            _require((image.shape[1], image.shape[0]) == dimension, "Encoded dimensions changed")
            decoded += 1
    finally:
        decoder.release()
    _require(decoded == count, "Encoded full frame count differs")
    for key, path in (("video_sha256", source), ("records_sha256", records)):
        _require(frozen.sha256_file(path) == hashes[key], "Source changed during rendering")
    return {"schema_version": VERSION, "claim_type": "ACTUAL_B_V4_LEDGER_RENDER_NOT_MODEL_INFERENCE",
        "semantics": SEMANTICS, "source_identity": deepcopy(source_identity),
        "output_video": {"path": str(target), "sha256": frozen.sha256_file(target), "size_bytes": target.stat().st_size,
            "codec": "h264", "pixel_format": "yuv420p", "frames_written": count, "frames_redecoded": decoded,
            "fps": fps, "width": dimension[0], "height": dimension[1], "audio_preserved": False},
        "source_image_region": final_state["source_image_region"],
        "final_accepted": final_state["accepted_so_far"], "final_pending": final_state["pending_final"],
        "final_vehicle": final_state["vehicle_so_far"], "final_pedestrian": final_state["pedestrian_so_far"],
        "final_pivot": final_state["pivot"], "route_counts": final_state["route_counts"],
        "final_measured": final_state["measured_so_far"], "final_inferred": final_state["inferred_so_far"],
        "frame_pixel_and_raw_link_verified_every_frame": True, "inputs_unchanged_after_render": True,
        "new_detector_tracker_encoder_inference": False, "counting_rerun_by_renderer": False,
        "component_policy": "EXACT_FRAME_POSITIVE_RIDER_PARENT_ASSIGNMENT_UNION_RAW_PARENT_BC_PRESERVED",
        "display_id_policy": "RAW_ID_FIRST_WITH_OFFLINE_PREACTIVATION_VS_COUNTED_STATUS",
        "label_layout_policy": "FIXED_FONT_COLLISION_FREE_OR_RESERVED_OUTSIDE_SOURCE_CALLOUT",
        "maximum_visible_units": timeline["layout_max_units"], "pending_excluded_from_pivot": True,
        "maximum_overflow_callouts": timeline["layout_callout_capacity"],
        "layout_audit": {"path": str(labels_path), "sha256": frozen.sha256_file(labels_path)},
        "review_source_sha256": review_source_sha256, "ffmpeg_command": command,
        "codec_log": {"path": str(log_path), "sha256": frozen.sha256_file(log_path)},
        "opencv_version": cv2.__version__, "software_source_sha256": frozen.sha256_file(__file__),
        "render_and_decode_wall_seconds": time.perf_counter() - started}


build_timeline = build_b_v4_timeline
render_frame = render_b_v4_frame
render_video = render_b_v4_video
