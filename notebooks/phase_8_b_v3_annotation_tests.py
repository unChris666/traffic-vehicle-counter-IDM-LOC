"""Synthetic B v3 renderer checks; these are not traffic performance evidence."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import phase_8_b_v3_annotation as annotation


def fixture():
    import numpy as np
    image = np.full((480, 640, 3), 35, dtype=np.uint8)
    identity = {"video_sha256": "a" * 64, "records_sha256": "b" * 64,
                "parent_run_id": "synthetic_run", "variant": "raw", "width": 640, "height": 480}
    geometry = {"line_margin_half_width_px": 25,
                "rendered_native_pixels": {"width": 640, "height": 480,
                    "line": {"P1": [200, 240], "P2": [440, 240]},
                    "side_a_polygon": [[0, 0], [640, 0], [640, 210], [0, 210]],
                    "side_b_polygon": [[0, 270], [640, 270], [640, 480], [0, 480]]}}
    boxes = [(7, "motorcycle", 3, [100, 150, 180, 230]),
             (21, "person", 0, [90, 110, 170, 250]),
             (8, "motorcycle", 3, [175, 150, 240, 232])]
    raw, emitted = [], []
    for track, name, class_id, box in boxes:
        raw.append({"bbox_xyxy_pixels": box, "class_name": name, "class_id": class_id, "confidence": .8})
        emitted.append({"frame_index": 5, "track_id": track, "raw_bbox": box,
                        "class_name": name, "class_id": class_id, "confidence": .8,
                        "original_detection_index": len(raw) - 1, "emitted": True,
                        "measurement_provenance": "retained_phase_8_detection"})
    record = dict(identity, frame_index=5, raw_detections=raw, emitted_tracks=emitted,
                  detector_input_frame_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest())
    event = {"event_id": "event1", "physical_unit_id": "unit1", "episode_id": "episode1", "passage_id": "passage1",
             "display_id": "M2000",
             "track_id": 7, "category": "motorcycle", "direction": "A_TO_B", "route": "LINE_MARGIN",
             "status": "accepted", "accepted_count_event": True, "activation_frame": 3,
             "source_identity": deepcopy(identity), "evidence": {"measured_crossing": True,
                 "source_refs": [{"frame_index": 1, "track_id": 7}]}}
    log = {"frame_index": 3, "event_id": "event1", "physical_unit_id": "unit1", "passage_id": "passage1",
           "track_id": 7, "category": "motorcycle", "direction": "A_TO_B", "route": "LINE_MARGIN",
           "status": "accepted", "count_delta": 1, "measured_crossing": True, "message": "CROSSING_LINE"}
    relation = {"vehicle_track_id": 7, "component_track_id": 21, "support_frames": [5],
                "relation_id": "relation1", "type": "COMPONENT_OF"}
    assignments = [{"frame_index": 5, "track_id": 7, "physical_unit_id": "unit1", "episode_id": "episode1", "role": "vehicle"},
                   {"frame_index": 5, "track_id": 21, "physical_unit_id": "rider1", "episode_id": "rider_episode1", "role": "rider"},
                   {"frame_index": 5, "track_id": 8, "physical_unit_id": "unit2", "episode_id": "episode2", "role": "vehicle"}]
    result = {"source_identity": identity, "events": [event], "cancelled_events": [],
              "frame_assignments": assignments,
              "passage_log": [log], "decisions": [
                  {"frame_index": 4, "track_id": 9, "status": "pending", "accepted_count_event": False,
                   "reasons": ["CATEGORY_UNRESOLVED"]}], "component_links": [relation], "video_id": "synthetic"}
    return image, record, result, geometry


class TimelineTests(unittest.TestCase):
    def test_pending_excluded_and_directions_separate(self):
        _, _, result, _ = fixture()
        state = annotation.timeline_at(annotation.build_timeline(result, frame_count=6), 5)
        self.assertEqual(state["accepted_so_far"], 1)
        self.assertEqual(state["pending_so_far"], 1)
        self.assertEqual(state["pivot"]["motorcycle"], {"A_TO_B": 1, "B_TO_A": 0})
        self.assertEqual(state["measured_so_far"], 1)
        self.assertEqual(state["inferred_so_far"], 0)

    def test_before_activation_does_not_count(self):
        _, _, result, _ = fixture()
        state = annotation.timeline_at(annotation.build_timeline(result), 2)
        self.assertEqual(state["accepted_so_far"], 0)
        self.assertEqual(state["pending_so_far"], 0)

    def test_timeout_upgrade_does_not_double_count_and_changes_breakdown(self):
        _, _, result, _ = fixture()
        initial = dict(result["passage_log"][0], frame_index=1, route="ESTIMATED_TIMEOUT", measured_crossing=False)
        upgrade = dict(result["passage_log"][0], frame_index=4, status="upgraded", count_delta=0)
        result["passage_log"] = [initial, upgrade]
        timeline = annotation.build_timeline(result)
        before = annotation.timeline_at(timeline, 2)
        after = annotation.timeline_at(timeline, 5)
        self.assertEqual((before["accepted_so_far"], before["measured_so_far"], before["inferred_so_far"]), (1, 0, 1))
        self.assertEqual((after["accepted_so_far"], after["measured_so_far"], after["inferred_so_far"]), (1, 1, 0))
        self.assertEqual(after["route_counts"]["ESTIMATED_TIMEOUT"], 0)

    def test_line_margin_gap_stays_inferred_despite_line_route(self):
        _, _, result, _ = fixture()
        result["events"][0]["evidence"]["measured_crossing"] = False
        result["passage_log"][0]["measured_crossing"] = False
        state = annotation.timeline_at(annotation.build_timeline(result), 5)
        self.assertEqual(state["route_counts"]["LINE_MARGIN"], 1)
        self.assertEqual((state["measured_so_far"], state["inferred_so_far"]), (0, 1))

    def test_timeout_upgrade_to_gap_line_remains_inferred_at_both_times(self):
        _, _, result, _ = fixture()
        result["events"][0]["evidence"]["measured_crossing"] = False
        initial = dict(result["passage_log"][0], frame_index=1, route="ESTIMATED_TIMEOUT", measured_crossing=False)
        upgrade = dict(result["passage_log"][0], frame_index=4, status="upgraded", count_delta=0, measured_crossing=False)
        result["passage_log"] = [initial, upgrade]
        timeline = annotation.build_timeline(result)
        for frame in (2, 5):
            state = annotation.timeline_at(timeline, frame)
            self.assertEqual((state["accepted_so_far"], state["measured_so_far"], state["inferred_so_far"]), (1, 0, 1))

    def test_missing_log_measurement_flag_rejected_instead_of_guessing(self):
        _, _, result, _ = fixture()
        result["passage_log"][0].pop("measured_crossing")
        with self.assertRaisesRegex(ValueError, "explicit measured_crossing"):
            annotation.build_timeline(result)

    def test_polygon_cannot_claim_direct_measurement(self):
        _, _, result, _ = fixture()
        result["events"][0]["route"] = "OCCLUSION_DIFF_POLYGON"
        with self.assertRaisesRegex(ValueError, "cannot claim a measured"):
            annotation.build_timeline(result)

    def test_timeout_cancellation_replays_explicit_minus_one(self):
        _, _, result, _ = fixture()
        event = result["events"].pop()
        event.update(status="cancelled", accepted_count_event=False, route="ESTIMATED_TIMEOUT")
        event["evidence"]["measured_crossing"] = False
        result["cancelled_events"] = [event]
        log = result["passage_log"][0]
        log.update(frame_index=1, route="ESTIMATED_TIMEOUT", measured_crossing=False)
        result["passage_log"].append(dict(log, frame_index=4, status="cancelled", count_delta=-1))
        timeline = annotation.build_timeline(result)
        self.assertEqual(annotation.timeline_at(timeline, 2)["accepted_so_far"], 1)
        self.assertEqual(annotation.timeline_at(timeline, 5)["accepted_so_far"], 0)
        self.assertEqual(timeline["final_accepted"], 0)

    def test_all_three_routes_are_displayed_distinctly(self):
        _, _, result, _ = fixture()
        for position, route in enumerate(("OCCLUSION_DIFF_POLYGON", "ESTIMATED_TIMEOUT"), 2):
            event = dict(deepcopy(result["events"][0]), event_id=f"event{position}", physical_unit_id=f"unit{position}",
                         passage_id=f"passage{position}", route=route, display_id=f"M2{position:03d}")
            event["evidence"]["measured_crossing"] = False
            result["events"].append(event)
            result["passage_log"].append(dict(result["passage_log"][0], event_id=event["event_id"],
                                             physical_unit_id=event["physical_unit_id"], passage_id=event["passage_id"],
                                             route=route, measured_crossing=False))
        state = annotation.timeline_at(annotation.build_timeline(result), 5)
        self.assertEqual(state["route_counts"], {"LINE_MARGIN": 1, "OCCLUSION_DIFF_POLYGON": 1, "ESTIMATED_TIMEOUT": 1})
        self.assertEqual((state["measured_so_far"], state["inferred_so_far"]), (1, 2))
        self.assertEqual({item["requested_label"] for item in state["recent_logs"]}, set(annotation.ROUTE_LABELS.values()))

    def test_duplicate_physical_passage_rejected(self):
        _, _, result, _ = fixture()
        result["events"].append(dict(deepcopy(result["events"][0]), event_id="duplicate", display_id="M2001"))
        with self.assertRaisesRegex(ValueError, "Duplicate final physical passage"):
            annotation.build_timeline(result)

    def test_duplicate_increment_rejected(self):
        _, _, result, _ = fixture()
        result["passage_log"].append(deepcopy(result["passage_log"][0]))
        with self.assertRaisesRegex(ValueError, "increment one passage twice"):
            annotation.build_timeline(result)

    def test_mixed_source_event_rejected(self):
        _, _, result, _ = fixture()
        result["events"][0]["source_identity"]["video_sha256"] = "c" * 64
        with self.assertRaisesRegex(ValueError, "another source"):
            annotation.build_timeline(result)

    def test_ledger_without_log_rejected(self):
        _, _, result, _ = fixture()
        result["passage_log"] = []
        with self.assertRaisesRegex(ValueError, "does not reconcile"):
            annotation.build_timeline(result)

    def test_pending_cannot_claim_accepted(self):
        _, _, result, _ = fixture()
        result["decisions"][0]["accepted_count_event"] = True
        with self.assertRaisesRegex(ValueError, "Pending"):
            annotation.build_timeline(result)


class FrameTests(unittest.TestCase):
    def render(self, values=None):
        image, record, result, geometry = values or fixture()
        return annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")

    def test_requested_log_is_below_accepted_and_above_pending(self):
        canvas, state = self.render()
        positions = state["panel_sections_y"]
        self.assertLess(positions["accepted"], positions["passage_log"])
        self.assertLess(positions["passage_log"], positions["pending"])
        texts = [entry["text"] for entry in state["panel_text"]]
        self.assertIn("M2000 - motorcycle; A>B", texts)
        self.assertIn("CROSSING_LINE", texts)
        self.assertEqual(canvas.shape, (960, 1160, 3))

    def test_motorcycle_rider_union_preserves_vehicle_bc(self):
        _, state = self.render()
        units = {item["track_id"]: item for item in state["display_units"]}
        self.assertEqual(set(units), {7, 8})
        self.assertEqual(units[7]["display_bbox"], [90, 110, 180, 250])
        self.assertEqual(units[7]["vehicle_bc"], [140, 230])
        self.assertNotEqual(units[7]["vehicle_bc"], annotation.frozen._bc(units[7]["display_bbox"]))
        self.assertEqual(units[7]["component_track_ids"], [21])
        self.assertEqual(units[7]["component_additional_increment"], 0)

    def test_adjacent_motorcycles_never_merged_by_proximity(self):
        _, state = self.render()
        self.assertEqual([item["track_id"] for item in state["display_units"]], [7, 8])
        self.assertEqual(state["display_units"][1]["display_bbox"], [175, 150, 240, 232])

    def test_relation_only_drawn_at_retained_local_support_frame(self):
        values = fixture()
        values[2]["component_links"][0]["support_frames"] = [4]
        _, state = self.render(values)
        self.assertEqual(len(state["display_units"]), 3)
        self.assertTrue(all(not item["component_track_ids"] for item in state["display_units"]))

    def test_ambiguous_rider_parent_keeps_boxes_separate(self):
        values = fixture()
        values[2]["component_links"].append(dict(values[2]["component_links"][0], vehicle_track_id=8, relation_id="relation2"))
        _, state = self.render(values)
        self.assertEqual(len(state["display_units"]), 3)

    def test_flat_cap_band_not_extended_past_endpoints(self):
        _, state = self.render()
        self.assertEqual(state["band_vertices_native"], [[200, 265], [440, 265], [440, 215], [200, 215]])

    def test_native_region_and_label_backgrounds_exist(self):
        import numpy as np
        image, record, result, geometry = fixture()
        canvas, _ = self.render((image, record, result, geometry))
        self.assertTrue(np.array_equal(canvas[10:20, 10:20], image[10:20, 10:20]))
        color = annotation.frozen.CATEGORY_COLORS["motorcycle"]
        self.assertGreater(int(np.all(canvas[85:115, 90:300] == color, axis=2).sum()), 100)

    def test_tampered_source_pixels_rejected(self):
        values = fixture()
        values[0][0, 0, 0] += 1
        with self.assertRaisesRegex(ValueError, "source pixels differ"):
            self.render(values)

    def test_source_raw_link_cannot_be_replaced_by_union_box(self):
        values = fixture()
        values[1]["emitted_tracks"][0]["raw_bbox"] = [90, 110, 180, 250]
        with self.assertRaisesRegex(ValueError, "linked raw detector"):
            self.render(values)

    def test_inputs_remain_immutable(self):
        values = fixture()
        before = deepcopy(values[1:])
        self.render(values)
        self.assertEqual(values[1:], before)

    def test_final_display_id_category_and_direction_rules(self):
        for value in ("M0001", "M1000", "C2000", "M20000", "M200", "X2000"):
            values = fixture()
            values[2]["events"][0]["display_id"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.render(values)

    def test_offline_final_display_semantics_do_not_rewrite_historical_pivot(self):
        values = fixture()
        result = values[2]
        result["events"][0].update(category="car", display_id="C2000")
        initial = dict(result["passage_log"][0], frame_index=1, route="ESTIMATED_TIMEOUT", measured_crossing=False)
        upgrade = dict(result["passage_log"][0], frame_index=4, status="upgraded", count_delta=0, category="car")
        result["passage_log"] = [initial, upgrade]
        timeline = annotation.build_timeline(result)
        before = annotation.timeline_at(timeline, 2)
        after = annotation.timeline_at(timeline, 5)
        self.assertEqual(before["pivot"]["motorcycle"]["A_TO_B"], 1)
        self.assertEqual(after["pivot"]["car"]["A_TO_B"], 1)
        self.assertEqual(before["recent_logs"][0]["display_category"], "car")
        self.assertEqual(before["recent_logs"][0]["display_id"], "C2000")

    def test_alias_handoff_keeps_display_passage_and_count(self):
        values = fixture()
        values[1]["emitted_tracks"][0]["track_id"] = 2507
        values[2]["frame_assignments"][0]["track_id"] = 2507
        values[2]["component_links"][0]["vehicle_track_id"] = 2507
        _, state = self.render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 2507)
        self.assertEqual(unit["display_id"], "M2000")
        self.assertIn("raw 2507", unit["label"])
        self.assertEqual(state["accepted_so_far"], 1)

    def test_raw_track_reuse_in_different_episode_does_not_inherit_display(self):
        values = fixture()
        values[2]["frame_assignments"][0]["episode_id"] = "unrelated_motorcycle"
        _, state = self.render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertIsNone(unit["display_id"])

    def test_absent_frame_assignment_never_expands_physical_identity(self):
        values = fixture()
        values[2]["frame_assignments"][0]["frame_index"] = 6
        _, state = self.render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertIsNone(unit["display_id"])

    def test_unreviewed_person_is_not_automatically_pedestrian(self):
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"] = values[2]["frame_assignments"][:1]
        _, state = self.render(values)
        person = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(person["label"], "person | role unknown | not counted | raw 21")
        self.assertIsNone(person["counting_bc"])
        self.assertEqual(state["pedestrian_so_far"], 0)

    def test_rider_without_local_union_relation_remains_rider_plus_zero(self):
        values = fixture()
        values[2]["component_links"] = []
        _, state = self.render(values)
        rider = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(rider["label"], "rider | component +0 | raw 21")
        self.assertEqual(state["pedestrian_so_far"], 0)

    def test_reviewed_rider_parent_exact_frame_can_union_without_old_machine_relation(self):
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"][1].update(component_of_unit_id="unit1",
            review_refs=[{"review_id": "user_rider_2471", "source_frame": 5}])
        _, state = self.render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertEqual(unit["component_track_ids"], [21])
        self.assertEqual(unit["display_bbox"], [90, 110, 180, 250])
        self.assertEqual(unit["vehicle_bc"], [140, 230])

    def test_reviewed_rider_without_parent_measurement_does_not_invent_union(self):
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"][1].update(component_of_unit_id="absent_parent",
            review_refs=[{"review_id": "user_rider_2471", "source_frame": 5}])
        _, state = self.render(values)
        self.assertEqual(len(state["display_units"]), 3)
        self.assertTrue(all(not unit["component_track_ids"] for unit in state["display_units"]))

    def test_future_person_role_does_not_expand_backwards(self):
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"][1].update(frame_index=6, role="pedestrian")
        _, state = self.render(values)
        person = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(person["role"], "unknown_person")
        self.assertIsNone(person["person_bc"])

    def test_pedestrian_own_bc_and_separate_subtotal(self):
        values = fixture()
        result = values[2]
        result["component_links"] = []
        result["frame_assignments"][1].update(role="pedestrian", physical_unit_id="walk1", episode_id="walk_episode1")
        event = dict(deepcopy(result["events"][0]), event_id="walk_event", physical_unit_id="walk1",
                     episode_id="walk_episode1", passage_id="walk_passage", category="pedestrian",
                     track_id=21, display_id="P1000", direction="B_TO_A")
        result["events"].append(event)
        result["passage_log"].append(dict(deepcopy(result["passage_log"][0]), event_id="walk_event",
            physical_unit_id="walk1", passage_id="walk_passage", category="pedestrian", track_id=21, direction="B_TO_A"))
        _, state = self.render(values)
        person = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(person["display_id"], "P1000")
        self.assertEqual(person["person_bc"], [130, 250])
        self.assertIsNone(person["vehicle_bc"])
        self.assertEqual((state["accepted_so_far"], state["vehicle_so_far"], state["pedestrian_so_far"]), (2, 1, 1))
        self.assertEqual(state["pivot"]["pedestrian"], {"A_TO_B": 0, "B_TO_A": 1})

    def test_pedestrian_assignment_cannot_silently_become_rider(self):
        values = fixture()
        values[2]["frame_assignments"][1]["role"] = "pedestrian"
        with self.assertRaisesRegex(ValueError, "conflicts with supported rider"):
            self.render(values)

    def test_return_passage_receives_different_id_and_direction(self):
        values = fixture()
        result = values[2]
        event = dict(deepcopy(result["events"][0]), event_id="return_event", passage_id="return_passage",
                     display_id="M1000", direction="B_TO_A", activation_frame=5)
        event["evidence"]["source_refs"] = [{"frame_index": 4, "track_id": 7}]
        result["events"].append(event)
        result["passage_log"].append(dict(deepcopy(result["passage_log"][0]), event_id="return_event",
            passage_id="return_passage", direction="B_TO_A", frame_index=5))
        _, state = self.render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertEqual(unit["display_id"], "M1000")
        self.assertEqual(state["accepted_so_far"], 2)

    def test_cancelled_event_has_no_final_display_id(self):
        values = fixture()
        result = values[2]
        event = result["events"].pop()
        event.update(status="cancelled", accepted_count_event=False, display_id=None, route="ESTIMATED_TIMEOUT")
        event["evidence"]["measured_crossing"] = False
        result["cancelled_events"] = [event]
        result["passage_log"][0].update(route="ESTIMATED_TIMEOUT", measured_crossing=False)
        result["passage_log"].append(dict(result["passage_log"][0], frame_index=4, count_delta=-1, status="cancelled"))
        _, state = self.render(values)
        self.assertEqual(state["accepted_so_far"], 0)
        self.assertTrue(all(log["display_id"] is None for log in state["recent_logs"]))

    def test_assignment_without_actual_measurement_rejected(self):
        values = fixture()
        values[2]["frame_assignments"][0]["track_id"] = 99999
        with self.assertRaisesRegex(ValueError, "no measured emitted track"):
            self.render(values)

    def test_current_counting_core_contract_renders_without_schema_translation(self):
        from phase_5_geometry_helpers import Geometry
        from phase_8_b_v3_counting import replay_frames
        image, _, original, geometry = fixture()
        identity = original["source_identity"]
        identity["geometry_sha256"] = "c" * 64
        native = geometry["rendered_native_pixels"]
        geom = Geometry(tuple(native["line"]["P1"]), tuple(native["line"]["P2"]),
            tuple(map(tuple, native["side_a_polygon"])), tuple(map(tuple, native["side_b_polygon"])), 640, 480)
        frames, assignments, last_record = [], [], None
        for index, bottom in enumerate((180, 230, 250, 280)):
            box = [300, bottom - 40, 340, bottom]
            observation = {"frame_index": index, "track_id": 7, "unit_id": "vehicle1", "episode_id": "episode1",
                "role": "vehicle", "class_name": "motorcycle", "class_id": 3, "confidence": .8,
                "raw_bbox": box, "original_detection_index": 0, "emitted": True, "observed": True,
                "measurement_provenance": "retained_phase_8_detection"}
            frames.append({"frame_index": index, "observations": [observation]})
            assignments.append({"frame_index": index, "track_id": 7, "physical_unit_id": "vehicle1",
                "episode_id": "episode1", "role": "vehicle"})
            last_record = dict(identity, frame_index=index, emitted_tracks=[observation],
                raw_detections=[{"bbox_xyxy_pixels": box, "class_name": "motorcycle", "class_id": 3, "confidence": .8}],
                detector_input_frame_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        result = replay_frames(frames, geom, source_identity=identity, policy={"line_margin_half_width_px": 25,
            "timeout_frames": 60, "timeout_clock": "last_observed_origin", "category_policy": "band_majority_ties_pending"})
        _, state = annotation.render_frame(image, last_record, result, geometry, fps=30,
            video_id="synthetic", unit_assignments=assignments)
        self.assertEqual(state["accepted_so_far"], 1)
        self.assertEqual(state["display_units"][0]["display_id"], "M2000")


class VideoTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "ffmpeg/libx264 needed")
    def test_full_h264_render_decode_and_source_binding(self):
        import cv2
        import numpy as np
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, records, target = root / "source.mp4", root / "records.jsonl", root / "review.mp4"
            writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 25, (96, 64))
            self.assertTrue(writer.isOpened())
            for index in range(3):
                writer.write(np.full((64, 96, 3), 30 + index * 10, dtype=np.uint8))
            writer.release()
            identity = {"video_sha256": annotation.frozen.sha256_file(source), "parent_run_id": "synthetic_run",
                        "variant": "raw", "width": 96, "height": 64}
            capture = cv2.VideoCapture(str(source))
            with records.open("w", encoding="utf-8") as handle:
                for index in range(3):
                    ok, image = capture.read()
                    self.assertTrue(ok)
                    record = dict(identity, frame_index=index, raw_detections=[], emitted_tracks=[],
                                  detector_input_frame_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest())
                    handle.write(json.dumps(record) + "\n")
            capture.release()
            identity["records_sha256"] = annotation.frozen.sha256_file(records)
            result = {"source_identity": identity, "events": [], "passage_log": [], "decisions": []}
            geometry = {"line_margin_half_width_px": 5, "rendered_native_pixels": {
                "width": 96, "height": 64, "line": {"P1": [5, 32], "P2": [90, 32]},
                "side_a_polygon": [[0, 0], [96, 0], [96, 27], [0, 27]],
                "side_b_polygon": [[0, 37], [96, 37], [96, 64], [0, 64]]}}
            report = annotation.render_video(source, records, result, geometry, target, fps=25,
                                              expected_frame_count=3, source_identity=identity)
            self.assertEqual(report["output_video"]["frames_redecoded"], 3)
            self.assertEqual(report["output_video"]["width"], 616)
            self.assertEqual(report["output_video"]["height"], 960)
            self.assertFalse(report["new_detector_tracker_encoder_inference"])
            self.assertFalse(report["counting_rerun_by_renderer"])
            probe = json.loads(subprocess.check_output([shutil.which("ffprobe"), "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,pix_fmt,nb_frames,r_frame_rate", "-of", "json", str(target)]))["streams"][0]
            self.assertEqual((probe["codec_name"], probe["pix_fmt"], probe["nb_frames"], probe["r_frame_rate"]),
                             ("h264", "yuv420p", "3", "25/1"))
            with self.assertRaisesRegex(ValueError, "already exists"):
                annotation.render_video(source, records, result, geometry, target, fps=25,
                                         expected_frame_count=3, source_identity=identity)


if __name__ == "__main__":
    unittest.main(verbosity=2)
