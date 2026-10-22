"""Synthetic render/export invariants; these checks are not traffic accuracy."""
from copy import deepcopy
import csv
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import phase_8_b_v4_annotation_tests as old_tests
import phase_8_b_v6_annotation as annotation


def fixture():
    return old_tests.fixture()


def add_invalid(result):
    """Candidate active at f2, rejected offline at f5; never a final +1."""
    rejected = deepcopy(result["events"][0])
    rejected.update(event_id="cancelled2", physical_unit_id="unit2", episode_id="episode2",
        passage_id="passage2", track_id=8, display_id=None, activation_frame=2,
        status="cancelled", accepted_count_event=False)
    rejected["evidence"]["source_refs"] = [{"frame_index": 1, "track_id": 8}]
    result["cancelled_events"].append(rejected)
    start = dict(result["passage_log"][0], event_id="cancelled2", physical_unit_id="unit2",
        passage_id="passage2", track_id=8, frame_index=2)
    result["passage_log"].extend([start,
        dict(start, frame_index=5, status="cancelled", count_delta=-1)])
    invalid = {"status": "invalid", "accepted_count_event": False, "count_delta": 0,
        "track_id": 8, "physical_unit_id": "unit2", "episode_id": "episode2",
        "passage_id": "passage2", "frame_index": 5,
        "invalid_reason": "INVALID_AMBIGUOUS_UNIT", "reasons": ["UNIT_AMBIGUOUS"],
        "cancelled_candidate_event_id": "cancelled2",
        "source_ref": {"frame_index": 1, "track_id": 8}}
    result["invalid_decisions"] = [invalid]
    result["decisions"].append(deepcopy(invalid))
    return invalid


def add_bus(result):
    bus = deepcopy(result["events"][0])
    bus.update(event_id="bus3", physical_unit_id="unit3", episode_id="episode3",
        passage_id="passage3", track_id=30, category="bus", display_id="B1000",
        direction="B_TO_A", activation_frame=4)
    result["events"].append(bus)
    result["passage_log"].append(dict(result["passage_log"][0], event_id="bus3",
        physical_unit_id="unit3", passage_id="passage3", track_id=30, category="bus",
        direction="B_TO_A", frame_index=4))
    return bus


class TimelineTests(unittest.TestCase):
    def test_zero_and_nonzero_bus_checkpoint_reconciliation(self):
        _, _, result, geometry = fixture()
        timeline = annotation.build_timeline(result, geometry, frame_count=6)
        self.assertEqual(annotation.timeline_at(timeline, 5)["pivot"]["bus"],
                         {"A_TO_B": 0, "B_TO_A": 0})
        add_bus(result)
        timeline = annotation.build_timeline(result, geometry, frame_count=6)
        for frame, expected in ((0, 0), (2, 0), (3, 1), (4, 2), (5, 2)):
            state = annotation.timeline_at(timeline, frame)
            self.assertEqual(state["accepted_so_far"], expected)
            self.assertEqual(sum(sum(row.values()) for row in state["pivot"].values()), expected)
        self.assertEqual(annotation.timeline_at(timeline, 5)["pivot"]["bus"]["B_TO_A"], 1)

    def test_invalid_never_enters_pivot_even_before_eof_cancellation(self):
        _, _, result, geometry = fixture()
        add_invalid(result)
        before = deepcopy(result)
        timeline = annotation.build_timeline(result, geometry, frame_count=6)
        for frame in range(6):
            state = annotation.timeline_at(timeline, frame)
            self.assertEqual(state["accepted_so_far"], int(frame >= 3))
            self.assertEqual(state["invalid_so_far"], int(frame >= 2))
            self.assertEqual(state["pending_so_far"], int(frame >= 4))
        self.assertEqual(timeline["final_invalid"], 1)  # duplicated serialization, one passage
        void = [entry for entry in timeline["display_logs"] if entry["event_id"] == "cancelled2"]
        self.assertEqual([entry["count_delta"] for entry in void], [0, 0])
        self.assertEqual([entry["original_count_delta"] for entry in void], [1, -1])
        self.assertTrue(all(entry["status"] == "offline_void" for entry in void))
        self.assertEqual(result, before)

    def test_invalid_source_time_and_decision_time_are_separate(self):
        _, _, result, _ = fixture()
        add_invalid(result)
        timeline = annotation.build_timeline(result, frame_count=6)
        row = annotation.timeline_at(timeline, 2)["recent_invalid"][0]
        self.assertEqual((row["frame_index"], row["decision_frame"], row["offline_attribution_frame"]), (5, 5, 2))
        self.assertEqual(row["attribution_semantics"], "OFFLINE_FINAL_REVIEW_NOT_CAUSAL")

    def test_invalid_without_source_candidate_uses_retained_ref(self):
        _, _, result, _ = fixture()
        row = add_invalid(result)
        result["cancelled_events"] = []
        result["passage_log"] = result["passage_log"][:1]
        row.pop("cancelled_candidate_event_id")
        result["decisions"][-1] = deepcopy(row)
        invalid = annotation.invalid_decisions(result, 6)[0]
        self.assertEqual(invalid["offline_attribution_frame"], 1)

    def test_pending_invalid_and_not_eligible_are_separate(self):
        _, _, result, _ = fixture()
        add_invalid(result)
        result["decisions"].append({"frame_index": 4, "track_id": 22,
            "status": "not_eligible", "accepted_count_event": False, "resolution_reason": "RIDER_COMPONENT"})
        state = annotation.timeline_at(annotation.build_timeline(result), 5)
        self.assertEqual((state["accepted_so_far"], state["invalid_final"],
                          state["pending_final"], state["not_eligible_final"]), (1, 1, 1, 1))

    def test_measured_not_backprojected_before_upgrade(self):
        _, _, result, _ = fixture()
        initial = dict(result["passage_log"][0], frame_index=1,
            route="ESTIMATED_TIMEOUT", measured_crossing=False)
        result["passage_log"] = [initial,
            dict(result["passage_log"][0], frame_index=4, status="upgraded", count_delta=0)]
        timeline = annotation.build_timeline(result)
        self.assertEqual(annotation.timeline_at(timeline, 2)["inferred_so_far"], 1)
        self.assertEqual(annotation.timeline_at(timeline, 5)["measured_so_far"], 1)

    def test_bus_display_prefix_and_direction_parity_validated(self):
        _, _, result, _ = fixture()
        bus = add_bus(result)
        for invalid in ("B2000", "C1000", "B0001"):
            bus["display_id"] = invalid
            with self.assertRaises(ValueError):
                annotation.build_timeline(result)

    def test_accepted_and_invalid_same_passage_rejected(self):
        _, _, result, _ = fixture()
        row = add_invalid(result)
        row.update(physical_unit_id="unit1", episode_id="episode1", passage_id="passage1")
        result["decisions"][-1] = deepcopy(row)
        with self.assertRaisesRegex(ValueError, "cannot also be invalid"):
            annotation.build_timeline(result)


class RenderTests(unittest.TestCase):
    def test_bus_panel_renders_zero_and_nonzero_pivot(self):
        image, record, result, geometry = fixture()
        for expected in (0, 1):
            if expected:
                add_bus(result)
            _, state = annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")
            self.assertEqual(state["pivot"]["bus"]["B_TO_A"], expected)
            self.assertIn("bus", [entry["text"] for entry in state["panel_text"]])
            self.assertEqual(state["accepted_so_far"], 1 + expected)
        self.assertEqual(len({annotation.CATEGORY_COLORS[category] for category in annotation.CATEGORIES}), 5)

    def test_all_raw_ids_visible_and_rider_union_preserves_vehicle_bc(self):
        image, record, result, geometry = fixture()
        canvas, state = annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")
        unit = next(item for item in state["display_units"] if item["track_id"] == 7)
        self.assertEqual(state["raw_ids_visible"], [7, 8, 21])
        self.assertEqual(unit["component_track_ids"], [21])
        self.assertEqual(unit["vehicle_bc"], [140, 230])
        self.assertEqual(unit["display_bbox"], [90, 110, 180, 250])
        self.assertEqual(state["role_parent_links"][0]["component_track_id"], 21)
        self.assertTrue(all(layout["font_scale"] == .45 for layout in state["label_layouts"]))
        self.assertTrue(all(layout["lines"][0].startswith("raw") for layout in state["label_layouts"]))
        self.assertEqual(canvas.shape[1], 1280)
        self.assertLess(state["panel_sections_y"]["passage_log"], state["panel_sections_y"]["pending"])

    def test_invalid_status_is_offline_and_has_no_final_display_id(self):
        image, record, result, geometry = fixture()
        add_invalid(result)
        _, state = annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")
        unit = next(item for item in state["display_units"] if item["track_id"] == 8)
        self.assertEqual(unit["status_label"], "INVALID +0 / OFFLINE FINAL")
        self.assertIsNone(unit["display_id"])
        self.assertFalse(unit["counted_at_frame"])
        self.assertTrue(any("OFFLINE final exclusions" in str(line) for line in state["panel_text"]))

    def test_unresolved_person_role_is_not_promoted_by_previous_link(self):
        image, record, result, geometry = fixture()
        result["frame_assignments"][1]["role"] = "unknown_person"
        _, state = annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")
        person = next(item for item in state["display_units"] if item["track_id"] == 21)
        self.assertEqual(person["status_label"], "ROLE UNKNOWN / NO COUNT")
        self.assertEqual(len(state["display_units"]), 3)

    def test_source_pixel_tamper_rejected(self):
        image, record, result, geometry = fixture()
        image[0, 0, 0] += 1
        with self.assertRaisesRegex(ValueError, "source pixels differ"):
            annotation.render_frame(image, record, result, geometry, fps=30, video_id="synthetic")


class ExportTests(unittest.TestCase):
    def test_csv_pivot_and_manifest_reconcile_and_do_not_mutate(self):
        _, _, result, _ = fixture()
        add_bus(result)
        add_invalid(result)
        before = deepcopy(result)
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "export"
            report = annotation.export_audit(result, target)
            self.assertEqual((report["accepted"], report["invalid"], report["pending"]), (2, 1, 1))
            with (target / "summary_pivot.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 10)
            self.assertEqual(sum(int(row["accepted"]) for row in rows), 2)
            bus = [row for row in rows if row["category"] == "bus"]
            self.assertEqual([int(row["accepted"]) for row in bus], [0, 1])
            with (target / "invalid_passages.csv").open() as stream:
                invalid = list(csv.DictReader(stream))
            self.assertEqual(len(invalid), 1)
            self.assertEqual(invalid[0]["count_delta"], "0")
            self.assertEqual((invalid[0]["offline_attribution_frame"], invalid[0]["decision_frame"]), ("2", "5"))
            for item in report["files"]:
                self.assertEqual(hashlib.sha256((target / item["path"]).read_bytes()).hexdigest(), item["sha256"])
            with self.assertRaisesRegex(ValueError, "exists"):
                annotation.export_audit(result, target)
        self.assertEqual(result, before)

    def test_absent_bus_remains_zero_not_invented_observation(self):
        _, _, result, _ = fixture()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "export"
            annotation.export_audit(result, target)
            with (target / "summary_pivot.csv").open() as stream:
                buses = [row for row in csv.DictReader(stream) if row["category"] == "bus"]
            self.assertEqual([row["accepted"] for row in buses], ["0", "0"])
            with (target / "accepted_events.csv").open() as stream:
                self.assertFalse(any(row["category"] == "bus" for row in csv.DictReader(stream)))


class VideoTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("ffmpeg"), "Explicit ffmpeg dependency unavailable")
    def test_actual_encode_decode_with_invalid_final_ledger(self):
        import cv2
        image, record, result, geometry = fixture()
        add_invalid(result)
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
                row = deepcopy(record); row["frame_index"] = frame
                row["detector_input_frame_pixel_sha256"] = hashlib.sha256(decoded.tobytes()).hexdigest()
                for item in row["emitted_tracks"]:
                    item["frame_index"] = frame
                row["video_sha256"] = annotation.frozen.sha256_file(source)
                rows.append(row)
            cap.release()
            records = base / "records.jsonl"
            records.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            identity = dict(result["source_identity"], video_sha256=annotation.frozen.sha256_file(source),
                records_sha256=annotation.frozen.sha256_file(records))
            result["source_identity"] = identity
            for event in result["events"] + result["cancelled_events"]:
                event["source_identity"] = deepcopy(identity)
            before = deepcopy(result)
            report = annotation.render_video(source, records, result, geometry, base / "out.mp4", fps=30,
                expected_frame_count=6, source_identity=identity)
            self.assertEqual(report["output_video"]["frames_redecoded"], 6)
            self.assertEqual((report["final_accepted"], report["final_invalid"], report["final_pending"]), (1, 1, 1))
            self.assertFalse(report["counting_rerun_by_renderer"])
            with gzip.open(report["layout_audit"]["path"], "rt") as stream:
                audit = [json.loads(line) for line in stream]
            self.assertEqual([row["accepted_so_far"] for row in audit], [0, 0, 0, 1, 1, 1])
            self.assertEqual([row["invalid_so_far"] for row in audit], [0, 0, 1, 1, 1, 1])
            self.assertEqual(audit[-1]["raw_ids_visible"], [7, 8, 21])
            self.assertEqual(result, before)


if __name__ == "__main__":
    unittest.main()
