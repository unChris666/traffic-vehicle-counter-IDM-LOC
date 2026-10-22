"""B v4 rendering invariants. Synthetic checks do not measure traffic accuracy."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import phase_8_b_v3_annotation_tests as baseline_tests
import phase_8_b_v4_annotation as annotation


def fixture():
    values = baseline_tests.fixture()
    values[2]["frame_assignments"][1].update(component_of_unit_id="unit1", component_of_track_id=7,
        association_provenance=[{"source": "synthetic_positive_exact_frame", "frame_index": 5}])
    values[2]["eligibility_audit"] = [{"frame_index": 4, "track_id": 8, "status": "HOLD",
        "reason": "IDENTITY_TIMEOUT_CONFLICT", "last_observed_origin_frame": 3,
        "elapsed_source_frames": 1, "identity_timeout_hold": True}]
    return values


def render(values=None):
    image, record, result, geometry = values or fixture()
    return annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")


class TimelineTests(unittest.TestCase):
    def test_counters_match_frozen_log_compiler_without_input_mutation(self):
        _, _, result, geometry = fixture()
        before = deepcopy(result)
        timeline = annotation.build_timeline(result, geometry, frame_count=6)
        old = annotation.previous.build_timeline(result, frame_count=6)
        for frame in range(6):
            new_state = annotation.timeline_at(timeline, frame)
            old_state = annotation.previous.timeline_at(old, frame)
            self.assertTrue(all(new_state[key] == value for key, value in old_state.items()))
        self.assertEqual(result, before)

    def test_audit_does_not_appear_before_its_frame(self):
        _, _, result, _ = fixture()
        timeline = annotation.build_timeline(result)
        self.assertEqual(annotation.timeline_at(timeline, 3)["recent_eligibility_audit"], [])
        self.assertEqual(annotation.timeline_at(timeline, 4)["recent_eligibility_audit"][0]["track_id"], 8)

    def test_invalid_audit_frame_rejected(self):
        _, _, result, _ = fixture()
        result["eligibility_audit"][0]["frame_index"] = 6
        with self.assertRaisesRegex(ValueError, "outside source"):
            annotation.build_timeline(result, frame_count=6)

    def test_invalid_source_review_hash_rejected(self):
        _, _, result, _ = fixture()
        with self.assertRaisesRegex(ValueError, "lowercase SHA256"):
            annotation.build_timeline(result, review_source_sha256="bad")

    def test_duplicate_passage_still_rejected(self):
        _, _, result, _ = fixture()
        result["events"].append(dict(deepcopy(result["events"][0]), event_id="duplicate", display_id="M2001"))
        with self.assertRaisesRegex(ValueError, "Duplicate final physical passage"):
            annotation.build_timeline(result)


class FrameTests(unittest.TestCase):
    def test_union_only_positive_exact_frame_and_parent_bc_unchanged(self):
        _, state = render()
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertEqual(unit["component_track_ids"], [21])
        self.assertEqual(unit["display_bbox"], [90, 110, 180, 250])
        self.assertEqual(unit["vehicle_bc"], [140, 230])
        self.assertNotEqual(unit["vehicle_bc"], annotation.frozen._bc(unit["display_bbox"]))
        self.assertEqual(unit["component_additional_increment"], 0)
        self.assertEqual(state["raw_ids_visible"], [7, 8, 21])

    def test_link_without_positive_current_role_does_not_union(self):
        values = fixture()
        values[2]["frame_assignments"][1]["role"] = "unknown_person"
        _, state = render(values)
        self.assertEqual(len(state["display_units"]), 3)
        self.assertTrue(all(not unit["component_track_ids"] for unit in state["display_units"]))

    def test_future_relation_never_expands_role_or_union(self):
        values = fixture()
        values[2]["component_links"][0]["support_frames"] = [6]
        values[2]["frame_assignments"][1]["frame_index"] = 6
        _, state = render(values)
        person = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(person["role"], "unknown_person")
        self.assertIn("ROLE UNKNOWN", person["label"])

    def test_positive_assignment_without_link_can_union_with_provenance(self):
        values = fixture()
        values[2]["component_links"] = []
        _, state = render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertEqual(unit["component_track_ids"], [21])

    def test_positive_role_without_parent_provenance_stays_separate(self):
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"][1].pop("association_provenance")
        _, state = render(values)
        self.assertEqual(len(state["display_units"]), 3)

    def test_parent_absent_does_not_invent_parent_box(self):
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"][1]["component_of_unit_id"] = "absent"
        values[2]["frame_assignments"][1]["component_of_track_id"] = 999
        _, state = render(values)
        self.assertEqual(len(state["display_units"]), 3)

    def test_parent_episode_mismatch_never_inherits_old_rider_union(self):
        values = fixture()
        values[2]["frame_assignments"][1]["component_of_episode_id"] = "earlier_motorcycle_episode"
        _, state = render(values)
        self.assertEqual(len(state["display_units"]), 3)
        self.assertTrue(all(not item["component_track_ids"] for item in state["display_units"]))
        rider = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(rider["parent_vehicle_track_ids"], [])

    def test_pedestrian_cannot_be_overridden_by_old_link(self):
        values = fixture()
        values[2]["frame_assignments"][1]["role"] = "pedestrian"
        _, state = render(values)
        person = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(person["class_name"], "pedestrian")
        self.assertEqual(person["person_bc"], [130, 250])
        self.assertEqual(state["pedestrian_so_far"], 0)

    def test_all_raw_ids_start_visible_labels_and_use_constant_font(self):
        _, state = render()
        for layout in state["label_layouts"]:
            self.assertTrue(layout["lines"][0].startswith("raw"))
            self.assertEqual(layout["font_scale"], .45)
            for raw_id in layout["raw_track_ids"]:
                self.assertIn(str(raw_id), layout["lines"][0])

    def test_adjacent_vehicles_are_not_merged_and_labels_do_not_overlap(self):
        _, state = render()
        self.assertEqual([unit["track_id"] for unit in state["display_units"]], [7, 8])
        rectangles = [layout["rectangle"] for layout in state["label_layouts"]]
        for index, rectangle in enumerate(rectangles):
            self.assertFalse(any(annotation._overlaps(rectangle, other) for other in rectangles[index + 1:]))

    def test_before_activation_id_is_explicitly_offline_without_count(self):
        values = fixture()
        values[2]["events"][0]["activation_frame"] = 8
        values[2]["passage_log"][0]["frame_index"] = 8
        _, state = render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertEqual(unit["display_id"], "M2000")
        self.assertFalse(unit["counted_at_frame"])
        self.assertIn("OFFLINE ID / NOT COUNTED YET", unit["label"])
        self.assertEqual(state["accepted_so_far"], 0)

    def test_measured_flag_not_backprojected_before_upgrade(self):
        values = fixture()
        result = values[2]
        result["passage_log"] = [dict(result["passage_log"][0], frame_index=3,
            route="ESTIMATED_TIMEOUT", measured_crossing=False),
            dict(result["passage_log"][0], frame_index=8, status="upgraded", count_delta=0)]
        _, state = render(values)
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertIn("COUNTED ESTIMATE", unit["label"])
        self.assertEqual((state["measured_so_far"], state["inferred_so_far"]), (0, 1))

    def test_log_between_accepted_and_pending_audit_after_pending(self):
        _, state = render()
        sections = state["panel_sections_y"]
        self.assertLess(sections["accepted"], sections["passage_log"])
        self.assertLess(sections["passage_log"], sections["pending"])
        self.assertLess(sections["pending"], sections["eligibility_audit"])
        panel = [item["text"] for item in state["panel_text"]]
        self.assertTrue(any("IDENTITY_TIMEOUT_CONFLICT" in line for line in panel))
        self.assertIn("Event ledger only. Reviewed overlay not added.", panel)

    def test_native_source_dimensions_preserved(self):
        import numpy as np
        image, _, _, _ = fixture()
        canvas, state = render()
        self.assertTrue(np.array_equal(canvas[10:20, 500:510], image[10:20, 500:510]))
        self.assertEqual(state["source_image_region"], {"x": 0, "y": 0, "width": 640, "height": 480, "resized": False})
        self.assertEqual(canvas.shape[1], 1280)

    def test_color_backdrops_differ_between_category_labels(self):
        import numpy as np
        values = fixture()
        values[2]["component_links"] = []
        values[2]["frame_assignments"][1]["role"] = "pedestrian"
        canvas, state = render(values)
        lookup = {unit["track_id"]: unit for unit in state["display_units"]}
        for layout in state["label_layouts"]:
            x, y = layout["rectangle"][:2]
            expected = annotation.CATEGORY_COLORS[lookup[layout["track_id"]]["class_name"]]
            self.assertTrue(np.array_equal(canvas[y + 2, x + 2], expected))
        self.assertNotEqual(annotation.CATEGORY_COLORS["motorcycle"], annotation.CATEGORY_COLORS["pedestrian"])

    def test_crowded_frame_overflows_to_reserved_area_without_hidden_ids(self):
        values = fixture()
        image, record, result, _ = values
        result.update(events=[], passage_log=[], component_links=[], frame_assignments=[])
        record["raw_detections"], record["emitted_tracks"] = [], []
        for track in range(1, 31):
            box = [290, 210, 340, 260]
            record["raw_detections"].append({"bbox_xyxy_pixels": box, "class_name": "person", "class_id": 0, "confidence": .8})
            record["emitted_tracks"].append({"frame_index": 5, "track_id": track, "raw_bbox": box,
                "class_name": "person", "class_id": 0, "confidence": .8,
                "original_detection_index": track - 1, "emitted": True,
                "measurement_provenance": "retained_phase_8_detection"})
        canvas, state = render(values)
        self.assertEqual(state["raw_ids_visible"], list(range(1, 31)))
        self.assertTrue(any(item["outside_source"] for item in state["label_layouts"]))
        for index, layout in enumerate(state["label_layouts"]):
            self.assertLessEqual(layout["rectangle"][3], canvas.shape[0])
            self.assertFalse(any(annotation._overlaps(layout["rectangle"], other["rectangle"])
                                 for other in state["label_layouts"][index + 1:]))

    def test_source_pixel_tamper_rejected(self):
        values = fixture()
        values[0][0, 0, 0] += 1
        with self.assertRaisesRegex(ValueError, "source pixels differ"):
            render(values)


class VideoTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "Explicit ffmpeg dependency unavailable")
    def test_actual_encode_decode_retains_layout_and_ledger(self):
        import cv2
        image, record, result, geometry = fixture()
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            source = base / "source.mp4"
            subprocess.run(["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "640x480",
                "-r", "30", "-i", "pipe:0", "-an", "-c:v", "libx264", "-pix_fmt", "yuv420p", str(source)],
                input=image.tobytes() * 6, check=True)
            cap = cv2.VideoCapture(str(source))
            rows = []
            for frame in range(6):
                ok, decoded = cap.read(); self.assertTrue(ok)
                item = deepcopy(record); item["frame_index"] = frame
                item["detector_input_frame_pixel_sha256"] = hashlib.sha256(decoded.tobytes()).hexdigest()
                for track in item["emitted_tracks"]:
                    track["frame_index"] = frame
                rows.append(item)
            cap.release()
            records = base / "records.jsonl"
            for item in rows:
                item["video_sha256"] = annotation.frozen.sha256_file(source)
            records.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            identity = dict(result["source_identity"], video_sha256=annotation.frozen.sha256_file(source),
                            records_sha256=annotation.frozen.sha256_file(records))
            result["source_identity"] = identity
            result["events"][0]["source_identity"] = deepcopy(identity)
            before = deepcopy(result)
            report = annotation.render_video(source, records, result, geometry, base / "out.mp4", fps=30,
                expected_frame_count=6, source_identity=identity)
            self.assertEqual(report["output_video"]["frames_redecoded"], 6)
            self.assertEqual(report["final_accepted"], 1)
            self.assertFalse(report["counting_rerun_by_renderer"])
            with gzip.open(report["layout_audit"]["path"], "rt") as stream:
                layouts = [json.loads(line) for line in stream]
            self.assertEqual(len(layouts), 6)
            self.assertEqual(layouts[-1]["raw_ids_visible"], [7, 8, 21])
            self.assertEqual(result, before)


if __name__ == "__main__":
    unittest.main()
