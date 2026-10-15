"""Synthetic renderer contract tests; fixtures are not actual traffic evidence."""
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import phase_8_annotation_helpers as annotation


def fixture():
    identity = {"video_sha256": "1" * 64, "records_sha256": "2" * 64,
                "geometry_sha256": "3" * 64, "parent_run_id": "synthetic_phase8",
                "variant": "raw", "width": 640, "height": 480}
    observations = []
    for frame in (1, 2, 3):
        box = [100, 100, 200, 200 + frame]
        observations.append({"frame_index": frame, "track_id": 7, "class_name": "motorcycle", "class_id": 3,
            "raw_bbox": box, "bbox": [90, 90, 220, 230], "point": [150.0, 200 + frame],
            "confidence": .8, "emitted": True, "original_detection_index": 0,
            "measurement_provenance": "retained_phase_8_detection"})
    metadata = dict(observations[0], **identity)
    diagnostic = {"type": "GEOMETRY_TRANSITION", "accepted_count_event": False,
        "origin_frame": 1, "crossing_frame_start": 2, "crossing_frame_end": 3, "confirmation_frame": 3,
        "frame_index": 3, "direction": "A_TO_B", "track_id": 7, "crossing_point": [150, 202.5],
        "origin_observation": {"metadata": metadata, "point": [150.0, 201]}}
    relation = {"relation_id": "relation1", "type": "COMPONENT_OF", "status": "SUPPORTED",
        "first_episode_id": "person_episode", "second_episode_id": "vehicle_episode",
        "first_track_id": 21, "second_track_id": 7, "features": {"common_frame_indices": [1, 2, 3, 4]}}
    evidence = {"relation_id": "relation1", "type": "COMPONENT_OF", "status": "SUPPORTED",
        "passage_support_window": [1, 3], "features": {"common_frame_indices": [1, 2]}}
    event = {"type": "CountEvent", "event_id": "event1", "candidate_id": "candidate1",
        "physical_unit_id": "unit1", "passage_id": "passage1", "category": "motorcycle", "direction": "A_TO_B",
        "track_id": 7, "vehicle_measurement_episode_id": "vehicle_episode", "status": "accepted",
        "accepted_count_event": True, "is_causal_online_decision": False, "source_identity": deepcopy(identity),
        "geometry_evidence": diagnostic, "measurement_support": observations, "category_decision_latest_evidence_frame": 4,
        "identity_decision_latest_evidence_frame": 2, "component_episode_ids": ["person_episode"],
        "vehicle_episode_ids": ["vehicle_episode"], "identity_relation_ids": ["relation1"],
        "passage_identity_relation_evidence": [evidence]}
    decision = {key: deepcopy(event[key]) for key in ("event_id", "candidate_id", "physical_unit_id", "passage_id",
        "category", "track_id", "status", "accepted_count_event", "measurement_support", "component_episode_ids",
        "vehicle_episode_ids", "identity_relation_ids", "passage_identity_relation_evidence")}
    decision.update(episode_id="vehicle_episode", diagnostic=deepcopy(diagnostic), reasons=[], hard_block_reasons=[])
    pending = {"candidate_id": "pending1", "track_id": 8, "status": "pending_review", "accepted_count_event": False,
        "category": None, "diagnostic": {"frame_index": 2, "type": "AMBIGUOUS_GAP"},
        "component_episode_ids": ["person_episode"], "reasons": ["AMBIGUOUS_GAP"], "hard_block_reasons": []}
    ledger = {"video_id": "test_video", "source_event_id": "event1", "source_identity": deepcopy(identity),
        "category": "motorcycle", "direction": "A_TO_B", "snapshot_kind": "machine", "run_id": "run1", "event": deepcopy(event)}
    return identity, [event], [decision, pending], [relation], [ledger]


def build(values=None):
    identity, events, decisions, relations, ledger = values or fixture()
    return annotation.build_review_timeline(events, decisions, relations, source_identity=identity, frame_count=6,
        ledger_entries=ledger, video_id="test_video")


class TimelineTests(unittest.TestCase):
    def assert_reject(self, edit):
        values = fixture()
        edit(*values)
        with self.assertRaises(ValueError):
            build(values)

    def test_confirmation_timing_is_offline_and_late_evidence_remains_visible(self):
        timeline = build()
        self.assertEqual(annotation.timeline_at(timeline, 2)["accepted_so_far"], 0)
        self.assertEqual(annotation.timeline_at(timeline, 3)["accepted_so_far"], 1)
        self.assertEqual(timeline["event_cards"][0]["category_latest_evidence_frame"], 4)
        self.assertFalse(timeline["event_cards"][0]["replay_is_causal"])
        self.assertIn("NOT_CAUSAL", timeline["semantics"])

    def test_pending_and_person_component_do_not_increment(self):
        state = annotation.timeline_at(build(), 5)
        self.assertEqual((state["accepted_so_far"], state["pending_so_far"]), (1, 1))
        self.assertEqual(state["pivot"]["motorcycle"], {"A_TO_B": 1, "B_TO_A": 0})
        self.assertEqual(state["recent_events"][0]["component_additional_increment"], 0)
        self.assertEqual(state["recent_events"][0]["component_track_ids"], [21])
        self.assertIsNone(state["pivot"]["pedestrian"]["A_TO_B"])

    def test_component_connection_only_on_retained_local_frames(self):
        timeline = build()
        connections = annotation.timeline_at(timeline, 1)["connections"]
        self.assertEqual(len(connections), 1)
        self.assertEqual(connections[0]["unit_alias"],
                         timeline["source_measurements_by_frame"][1][(7, 0)]["unit_alias"])
        self.assertEqual(annotation.timeline_at(timeline, 3)["connections"], [])
        self.assertEqual(annotation.timeline_at(timeline, 4)["connections"], [])

    def test_inputs_not_mutated(self):
        values = fixture()
        original = deepcopy(values)
        timeline = build(values)
        annotation.timeline_at(timeline, 5)
        self.assertEqual(values, original)

    def test_duplicate_event_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: e.append(deepcopy(e[0])))

    def test_duplicate_physical_passage_rejected(self):
        def edit(i, e, d, r, l):
            second = deepcopy(e[0]); second["event_id"] = "event2"; e.append(second)
        self.assert_reject(edit)

    def test_unaccepted_event_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: e[0].update(accepted_count_event=False))

    def test_decision_conflict_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: d[0].update(hard_block_reasons=["COMPETITOR"]))

    def test_ledger_snapshot_mix_rejected(self):
        def edit(i, e, d, r, l):
            l.append(dict(deepcopy(l[0]), snapshot_kind="reviewed"))
        self.assert_reject(edit)

    def test_foreign_source_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: e[0]["source_identity"].update(video_sha256="4" * 64))

    def test_direction_mismatch_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: e[0].update(direction="B_TO_A"))

    def test_missing_representative_event_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: e.clear())

    def test_pending_cannot_have_accepted_flag(self):
        self.assert_reject(lambda i, e, d, r, l: d[1].update(accepted_count_event=True))

    def test_ambiguous_geometry_cannot_be_promoted(self):
        def edit(i, e, d, r, l):
            e[0]["geometry_evidence"]["type"] = "AMBIGUOUS_GAP"
            d[0]["diagnostic"] = deepcopy(e[0]["geometry_evidence"])
        self.assert_reject(edit)

    def test_rider_box_cannot_replace_vehicle_anchor(self):
        def edit(i, e, d, r, l):
            e[0]["measurement_support"][0]["class_name"] = "person"
            d[0]["measurement_support"] = deepcopy(e[0]["measurement_support"])
        self.assert_reject(edit)

    def test_filtered_box_cannot_supply_bc(self):
        def edit(i, e, d, r, l):
            e[0]["measurement_support"][0]["point"] = [155, 230]
            d[0]["measurement_support"] = deepcopy(e[0]["measurement_support"])
        self.assert_reject(edit)

    def test_measurement_gap_rejected(self):
        def edit(i, e, d, r, l):
            e[0]["measurement_support"].pop(1)
            d[0]["measurement_support"] = deepcopy(e[0]["measurement_support"])
        self.assert_reject(edit)

    def test_nonfinite_confirmation_rejected(self):
        def edit(i, e, d, r, l):
            e[0]["geometry_evidence"]["confirmation_frame"] = float("nan")
            d[0]["diagnostic"] = deepcopy(e[0]["geometry_evidence"])
        self.assert_reject(edit)

    def test_relation_outside_passage_rejected(self):
        def edit(i, e, d, r, l):
            e[0]["passage_identity_relation_evidence"][0]["features"]["common_frame_indices"] = [1, 4]
            d[0]["passage_identity_relation_evidence"] = deepcopy(e[0]["passage_identity_relation_evidence"])
        self.assert_reject(edit)

    def test_unsupported_local_relation_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: r[0].update(status="REJECTED"))

    def test_missing_relation_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: r.clear())

    def test_relation_episode_swap_rejected(self):
        self.assert_reject(lambda i, e, d, r, l: r[0].update(first_episode_id="other_person"))

    def test_no_events_is_valid_and_pending_stays_pending(self):
        identity, events, decisions, relations, ledger = fixture()
        timeline = annotation.build_review_timeline([], decisions[1:], [], source_identity=identity,
            frame_count=6, ledger_entries=[], video_id="test_video")
        self.assertEqual(annotation.timeline_at(timeline, 5)["accepted_so_far"], 0)
        self.assertEqual(timeline["final_pending"], 1)
        self.assertEqual(timeline["connections_by_frame"], {})


class SourceAndRenderingTests(unittest.TestCase):
    def record(self, identity, frame):
        import numpy as np
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        value = fixture()[1][0]["measurement_support"][0]
        observation = deepcopy(value); observation["frame_index"] = frame
        raw = {"bbox_xyxy_pixels": deepcopy(value["raw_bbox"]), "class_name": "motorcycle", "class_id": 3, "confidence": .8}
        record = dict(identity, frame_index=frame, raw_detections=[raw], emitted_tracks=[observation],
                      detector_input_frame_pixel_sha256=hashlib.sha256(image.tobytes()).hexdigest())
        return image, record

    def test_raw_class_and_resolved_event_category_remain_distinct(self):
        image, record = self.record(fixture()[0], 1)
        record["raw_detections"][0].update(class_name="car", class_id=2)
        record["emitted_tracks"][0].update(class_name="car", class_id=2)
        observations = annotation._validate_record(record, 1, fixture()[0], image)
        self.assertEqual(observations[7]["class_name"], "car")
        self.assertEqual(build()["event_cards"][0]["category"], "motorcycle")
        self.assertNotEqual(annotation.CATEGORY_COLORS["car"], annotation.CATEGORY_COLORS["motorcycle"])

    def test_source_pixel_mismatch_rejected(self):
        image, record = self.record(fixture()[0], 1)
        image[0, 0, 0] = 1
        with self.assertRaises(ValueError):
            annotation._validate_record(record, 1, fixture()[0], image)

    def test_filtered_bbox_never_replaces_raw_source(self):
        image, record = self.record(fixture()[0], 1)
        record["emitted_tracks"][0]["raw_bbox"] = [90, 90, 220, 230]
        with self.assertRaises(ValueError):
            annotation._validate_record(record, 1, fixture()[0], image)

    def test_duplicate_source_id_rejected(self):
        image, record = self.record(fixture()[0], 1)
        record["emitted_tracks"].append(deepcopy(record["emitted_tracks"][0]))
        with self.assertRaises(ValueError):
            annotation._validate_record(record, 1, fixture()[0], image)

    def test_canvas_expands_without_resizing_native_road(self):
        # No observations/geometry cover the selected pixel; input remains untouched.
        import numpy as np
        identity = fixture()[0]
        image, record = self.record(identity, 0)
        record.update(emitted_tracks=[], raw_detections=[])
        image[20, 20] = (10, 20, 30)
        record["detector_input_frame_pixel_sha256"] = hashlib.sha256(image.tobytes()).hexdigest()
        timeline = annotation.build_review_timeline([], [], [], source_identity=identity, frame_count=6,
            ledger_entries=[], video_id="test_video")
        geometry = {"rendered_native_pixels": {"width": 640, "height": 480,
            "side_a_polygon": [[1, 200], [1, 300], [300, 200]],
            "side_b_polygon": [[1, 310], [1, 400], [300, 310]],
            "line": {"P1": [1, 300], "P2": [600, 250]}}}
        original = image.copy()
        canvas, state = annotation.render_review_frame(image, record, timeline, geometry,
            fps=30, video_id="synthetic_test_video")
        self.assertEqual(canvas.shape, (720, 1160, 3))
        self.assertTrue(np.array_equal(canvas[20, 20], image[20, 20]))
        self.assertTrue(np.array_equal(image, original))
        self.assertEqual(state["accepted_so_far"], 0)

    def test_untracked_raw_detection_visible_but_never_counted(self):
        identity = fixture()[0]
        image, record = self.record(identity, 0)
        record["emitted_tracks"] = []
        timeline = annotation.build_review_timeline([], [], [], source_identity=identity, frame_count=6,
            ledger_entries=[], video_id="test_video")
        geometry = {"rendered_native_pixels": {"width": 640, "height": 480,
            "side_a_polygon": [[1, 200], [1, 300], [300, 200]],
            "side_b_polygon": [[1, 310], [1, 400], [300, 310]],
            "line": {"P1": [1, 300], "P2": [600, 250]}}}
        canvas, state = annotation.render_review_frame(image, record, timeline, geometry,
            fps=30, video_id="synthetic_test_video")
        self.assertEqual(state["raw_only_detection_count"], 1)
        self.assertEqual(state["accepted_so_far"], 0)
        self.assertEqual(state["pivot"]["motorcycle"]["A_TO_B"], 0)
        self.assertNotEqual(tuple(canvas[100, 100]), (0, 0, 0))

    def test_relation_stream_large_items_exact_and_trailing_invalid(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "relations.json.gz"
            expected = [{"blob": "x" * 140000}, {"blob": "y"}]
            with gzip.open(path, "wt") as handle:
                json.dump(expected, handle)
            self.assertEqual(list(annotation.iter_json_array(path)), expected)
            with gzip.open(path, "wt") as handle:
                handle.write('[{},]')
            with self.assertRaises(ValueError):
                list(annotation.iter_json_array(path))


if __name__ == "__main__":
    unittest.main()
