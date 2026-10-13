"""Independent synthetic contract tests for Phase 6 Option B.

The coordinates, labels and association controls below are purpose-built
software fixtures. They are neither actual video observations nor product
defaults. No detector, tracker, ReID encoder or video decoder is executed.
Assertions concern unit identity, source preservation and count-event gates;
they do not measure model or counting accuracy.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from phase_5_geometry_helpers import Geometry
from phase_6_counting_helpers import aggregate_events
import phase_6_identity_resolution_helpers as resolver


VIDEO_SHA = "d" * 64
CLASS_IDS = {"person": 0, "car": 2, "motorcycle": 3, "bus": 5,
             "truck": 7, "handbag": 26}
FIXTURE_ASSOCIATION_CONTROLS = {
    "component": {
        "min_common_frames": 3, "min_consecutive_common_frames": 3,
        "min_first_bc_inside_second_fraction": 1.0,
        "max_center_distance_norm": 1.0,
        "max_relative_motion_residual_norm": 0.1,
    },
    "same_vehicle": {
        "min_common_frames": 3, "min_consecutive_common_frames": 3,
        "min_iou": 0.90, "max_center_distance_norm": 0.05,
        "max_relative_motion_residual_norm": 0.05,
    },
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _measurement(track_id, frame, box, label="motorcycle", index=0):
    return {
        "track_id": track_id, "frame_index": frame,
        "raw_bbox": list(box), "class_name": label,
        "class_id": CLASS_IDS[label], "confidence": 0.8,
        "original_detection_index": index,
        "measurement_provenance": "retained_phase_2_detection",
        "timestamp_estimate_from_index_fps_seconds": frame / 30,
    }


def _vehicle(x, *, y=60, label="motorcycle", width=20, height=12):
    return ([x - width / 2, y - height, x + width / 2, y], label)


def _person(x, *, bottom=52, width=10, height=24):
    return ([x - width / 2, bottom - height, x + width / 2, bottom], "person")


class ResolutionFixture:
    """Measured 100x100 fixture, finite x=50 line from y20 to y80."""

    def __init__(self, root, tracks, *, raw_extras=None):
        self.root = Path(root)
        self.records_path = self.root / "source_records.jsonl"
        self.geometry_path = self.root / "geometry.json"
        self.geometry_document = {
            "draft_id": "option-b-synthetic-finite-line",
            "status": "SYNTHETIC_SOFTWARE_FIXTURE_NOT_ACTUAL_VIDEO",
            "source_video": {"sha256": VIDEO_SHA},
            "normalized": {
                "line": {"P1": [0.5, 0.2], "P2": [0.5, 0.8]},
                "side_a_polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
                "side_b_polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
            },
        }
        self.geometry_path.write_text(json.dumps(self.geometry_document, sort_keys=True), encoding="utf-8")
        self.geometry = Geometry.from_draft(self.geometry_path, 100, 100)
        self.records = []
        self.measurements = []
        for frame in range(max(len(values) for values in tracks.values())):
            record = {
                "video_sha256": VIDEO_SHA, "parent_run_id": "synthetic-option-b",
                "variant": "reid_on", "frame_index": frame,
                "width": 100, "height": 100,
                "timestamp_estimate_from_index_fps_seconds": frame / 30,
                "timestamp_parent_backend_ms": None,
                "raw_detections": [], "emitted_tracks": [],
                "assigned_observations_including_unconfirmed": [],
                "lifecycle_snapshots": [],
            }
            for track_id, values in sorted(tracks.items()):
                item = values[frame] if frame < len(values) else None
                if item is None:
                    continue
                box, label = item
                index = len(record["raw_detections"])
                observation = _measurement(track_id, frame, box, label, index)
                self.measurements.append(copy.deepcopy(observation))
                observation.update({"emitted": True, "is_activated": True,
                                    "bbox": [0, 0, 1, 1], "center": [0.5, 0.5]})
                record["raw_detections"].append({
                    "bbox_xyxy_pixels": list(box), "class_id": CLASS_IDS[label],
                    "class_name": label, "confidence": 0.8,
                })
                record["emitted_tracks"].append(observation)
            for extra in (raw_extras or {}).get(frame, []):
                box, label = extra
                record["raw_detections"].append({
                    "bbox_xyxy_pixels": list(box), "class_id": CLASS_IDS[label],
                    "class_name": label, "confidence": 0.8,
                })
            self.records.append(record)
        self.write_source()

    def write_source(self):
        self.records_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in self.records), encoding="utf-8")
        self.identity = {
            "video_sha256": VIDEO_SHA, "records_sha256": _sha(self.records_path),
            "geometry_sha256": _sha(self.geometry_path), "variant": "reid_on",
            "width": 100, "height": 100, "parent_run_id": "synthetic-option-b",
        }
        self.config = {
            "policy_version": "phase6_option_b_v1", "metric": "passage",
            "parameter_claim_type": "SYNTHETIC_ENGINEERING_CONTROLS_NOT_PRODUCT_DEFAULTS",
            "neutral_band_px": 0.0, "confirmation_observations": 1,
            "input_identity": copy.deepcopy(self.identity),
            "association": copy.deepcopy(FIXTURE_ASSOCIATION_CONTROLS),
        }

    def run(self, config=None):
        return resolver.run_identity_resolution(
            self.records_path, self.geometry_path, config=config or self.config)


class _FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase6-option-b-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fixture(self, tracks, **kwargs):
        return ResolutionFixture(self.root, tracks, **kwargs)

    def episodes(self, fixture):
        return resolver.extract_episodes(fixture.measurements, source_identity=fixture.identity)


class IdentityEpisodeTests(_FixtureTestCase):

    def test_person_origin_is_not_inherited_by_new_vehicle_episode(self):
        f = self.fixture({51: [_person(25), _person(35), _vehicle(40), _vehicle(60), _vehicle(70)]})
        episodes = self.episodes(f)
        self.assertEqual([ep["family"] for ep in episodes], ["person", "vehicle"])
        vehicle = episodes[1]
        self.assertEqual(vehicle["start_frame"], 2)
        self.assertEqual([o["frame_index"] for o in vehicle["observations"]], [2, 3, 4])
        self.assertTrue(all(o["class_name"] == "motorcycle" for o in vehicle["observations"]))
        self.assertEqual([o["frame_index"] for o in vehicle["excluded_preceding_observations"]], [0, 1])

    def test_vehicle_person_vehicle_creates_three_episodes_without_cherry_picking(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(35), _person(45), _vehicle(60), _vehicle(70)]})
        episodes = self.episodes(f)
        self.assertEqual([ep["family"] for ep in episodes], ["vehicle", "person", "vehicle"])
        self.assertEqual([[o["frame_index"] for o in ep["observations"]] for ep in episodes], [[0, 1], [2], [3, 4]])

    def test_missing_frame_starts_new_episode_and_preserves_both_sides(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), None, _vehicle(60), _vehicle(70)]})
        episodes = self.episodes(f)
        self.assertEqual(len(episodes), 2)
        self.assertEqual([[o["frame_index"] for o in ep["observations"]] for ep in episodes], [[0, 1], [3, 4]])

    def test_category_flip_inside_vehicle_family_is_preserved_as_evidence(self):
        f = self.fixture({51: [_vehicle(25, label="car"), _vehicle(40, label="truck"), _vehicle(60, label="car")]})
        episodes = self.episodes(f)
        self.assertEqual(len(episodes), 1)
        self.assertEqual([o["class_name"] for o in episodes[0]["observations"]], ["car", "truck", "car"])

    def test_input_measurements_are_not_modified_by_episode_extraction(self):
        f = self.fixture({51: [_person(25), _vehicle(40), _vehicle(60)]})
        before = copy.deepcopy(f.measurements)
        self.episodes(f)
        self.assertEqual(f.measurements, before)

    def test_episode_order_and_ids_do_not_depend_on_input_track_order(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), _vehicle(60)],
                          52: [_vehicle(25, y=75), _vehicle(40, y=75), _vehicle(60, y=75)]})
        forward = self.episodes(f)
        reversed_measurements = resolver.extract_episodes(
            list(reversed(f.measurements)), source_identity=f.identity)
        self.assertEqual(forward, reversed_measurements)


class IdentityResolutionContractTests(_FixtureTestCase):
    """Expected physical-world outcomes are specified independently of scoring."""

    def total(self, result, expected):
        self.assertEqual(len(result["accepted_events"]), expected)
        self.assertEqual(result["aggregate"]["total"], expected)
        self.assertEqual(sum(result["aggregate"]["by_category"].values()), expected)
        self.assertEqual(sum(result["aggregate"]["by_direction"].values()), expected)
        for event in result["accepted_events"]:
            self.assertEqual(event["type"], "CountEvent")
            self.assertIs(event["accepted_count_event"], True)
            self.assertEqual(event["status"], "accepted")

    def supported(self, result, relation_type):
        return [r for r in result["relations"]
                if r["type"] == relation_type and r["status"] == "SUPPORTED"]

    def plain_track(self, label="motorcycle", *, y=60):
        return [_vehicle(x, label=label, y=y) for x in (25, 35, 45, 55, 65, 75)]

    def test_consistent_motorcycle_without_positive_identity_evidence_stays_pending(self):
        f = self.fixture({51: self.plain_track()})
        result = f.run()
        self.total(result, 0)
        self.assertIn("NO_POSITIVE_PHYSICAL_IDENTITY_EVIDENCE", json.dumps(result["machine_decisions"]))

    def test_rider_is_component_and_does_not_add_pedestrian_count(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x) for x in xs]})
        result = f.run()
        self.total(result, 1)
        self.assertEqual(len(self.supported(result, "COMPONENT_OF")), 1)
        self.assertEqual(result["aggregate"]["by_category"]["motorcycle"], 1)
        self.assertEqual(result["aggregate"]["by_category"]["pedestrian"], 0)

    def test_rider_bottom_center_crossing_cannot_replace_vehicle_crossing(self):
        xs = (28, 35, 42, 49, 56, 63)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x + 7) for x in xs]})
        result = f.run()
        self.total(result, 1)
        diagnostic = result["accepted_events"][0]["geometry_evidence"]
        self.assertEqual(diagnostic["track_id"], 51)
        self.assertEqual((diagnostic["crossing_frame_start"], diagnostic["crossing_frame_end"]), (3, 4))
        self.assertEqual(diagnostic["crossing_evidence"]["start_observation"]["point"], [49.0, 60.0])
        self.assertEqual(diagnostic["crossing_evidence"]["end_observation"]["point"], [56.0, 60.0])

    def test_two_passengers_still_make_only_one_motorcycle(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x - 3) for x in xs],
                          53: [_person(x + 3) for x in xs]})
        result = f.run()
        self.total(result, 1)
        self.assertEqual(len(self.supported(result, "COMPONENT_OF")), 2)

    def test_two_motorcycles_beside_each_other_are_not_duplicates(self):
        f = self.fixture({51: self.plain_track(),
                          52: self.plain_track(y=75)})
        result = f.run()
        self.assertEqual(self.supported(result, "SAME_VEHICLE"), [])
        accepted_units = [e["physical_unit_id"] for e in result["accepted_events"]]
        self.assertEqual(len(accepted_units), len(set(accepted_units)))

    def test_nearby_pedestrian_outside_vehicle_is_not_a_rider(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x + 15) for x in xs]})
        result = f.run()
        self.assertEqual(self.supported(result, "COMPONENT_OF"), [])
        self.assertTrue(all(e["category"] != "pedestrian" for e in result["accepted_events"]))

    def test_opposing_motion_despite_spatial_overlap_is_not_component(self):
        xs = (40, 42, 44, 46, 48, 50)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x) for x in reversed(xs)]})
        result = f.run()
        self.assertEqual(self.supported(result, "COMPONENT_OF"), [])

    def test_one_frame_overlap_does_not_establish_component_identity(self):
        f = self.fixture({51: self.plain_track(),
                          52: [None, None, _person(45), None, None, None]})
        result = f.run()
        self.assertEqual(self.supported(result, "COMPONENT_OF"), [])

    def test_later_component_relation_cannot_authorize_earlier_vehicle_passage(self):
        xs = (25, 35, 45, 55, 65, 70, 75, 80, 85, 90)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [None if frame < 6 else _person(x)
                               for frame, x in enumerate(xs)]})
        config = copy.deepcopy(f.config)
        config["scope"] = {"association_frame_windows": [[0, 3], [6, 9]]}
        result = f.run(config)
        self.assertEqual(len(self.supported(result, "COMPONENT_OF")), 1)
        self.total(result, 0)
        self.assertEqual(len(result["machine_decisions"]), 1)
        candidate = result["machine_decisions"][0]
        self.assertEqual((candidate["diagnostic"]["origin_frame"], candidate["diagnostic"]["confirmation_frame"]), (0, 3))
        self.assertTrue(any("IDENTITY" in reason for reason in candidate["reasons"]))

    def test_later_duplicate_relation_cannot_authorize_earlier_vehicle_passage(self):
        xs = (25, 35, 45, 55, 65, 70, 75, 80, 85, 90)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [None if frame < 6 else _vehicle(x + 0.2)
                               for frame, x in enumerate(xs)]})
        config = copy.deepcopy(f.config)
        config["scope"] = {"association_frame_windows": [[0, 3], [6, 9]]}
        result = f.run(config)
        self.assertEqual(len(self.supported(result, "SAME_VEHICLE")), 1)
        self.total(result, 0)
        self.assertTrue(any("IDENTITY" in reason for reason in result["machine_decisions"][0]["reasons"]))

    def test_early_component_support_within_passage_window_still_authorizes_vehicle(self):
        xs = (25, 35, 45, 55, 65, 70, 75, 80, 85, 90)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x) if frame < 4 else None
                               for frame, x in enumerate(xs)]})
        config = copy.deepcopy(f.config)
        config["scope"] = {"association_frame_windows": [[0, 3], [6, 9]]}
        result = f.run(config)
        self.total(result, 1)
        diagnostic = result["accepted_events"][0]["geometry_evidence"]
        self.assertEqual((diagnostic["origin_frame"], diagnostic["confirmation_frame"]), (0, 3))

    def test_too_few_component_frames_inside_passage_cannot_borrow_later_support(self):
        xs = (25, 35, 45, 55, 65, 70, 75, 80)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [None if frame < 2 else _person(x)
                               for frame, x in enumerate(xs)]})
        result = f.run()
        self.assertEqual(len(self.supported(result, "COMPONENT_OF")), 1)
        self.total(result, 0)
        # The passage has only two common observations; the fixture requires 3.
        self.assertEqual(result["machine_decisions"][0]["diagnostic"]["confirmation_frame"], 3)

    def test_local_consecutive_requirement_cannot_borrow_run_from_later_window(self):
        xs = (25, 32, 39, 46, 53, 60, 67, 74, 81, 88)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x) for x in xs]})
        config = copy.deepcopy(f.config)
        config["scope"] = {"association_frame_windows": [[0, 1], [3, 4], [6, 9]]}
        result = f.run(config)
        self.assertEqual(len(self.supported(result, "COMPONENT_OF")), 1)
        self.total(result, 0)
        # Local common frames are 0,1,3,4: four observations, no run of 3.
        self.assertEqual(result["machine_decisions"][0]["diagnostic"]["confirmation_frame"], 4)

    def test_equally_plausible_two_motorcycle_assignment_stays_unresolved(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x - 3) for x in xs],
                          52: [_vehicle(x + 3) for x in xs],
                          53: [_person(x) for x in xs]})
        result = f.run()
        self.assertEqual(self.supported(result, "COMPONENT_OF"), [])
        self.assertIn("ALTERNATIVE_ASSIGNMENT_AMBIGUITY", json.dumps(result["relations"]))

    def test_rider_of_verified_duplicate_vehicle_group_has_one_assignment(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_vehicle(x + 0.2) for x in xs],
                          53: [_person(x) for x in xs]})
        result = f.run()
        self.total(result, 1)
        self.assertEqual(len(self.supported(result, "SAME_VEHICLE")), 1)
        # Multiple duplicate members are evidence for one physical assignment.
        self.assertNotIn("ALTERNATIVE_ASSIGNMENT_AMBIGUITY", json.dumps(result["relations"]))

    def test_duplicate_vehicle_tracks_produce_one_event_without_bbox_union(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_vehicle(x + 0.2) for x in xs]})
        result = f.run()
        self.total(result, 1)
        diagnostic = result["accepted_events"][0]["geometry_evidence"]
        self.assertIn(diagnostic["track_id"], (51, 52))
        selected_track = diagnostic["track_id"]
        selected_episode = next(ep for ep in result["episodes"] if ep["track_id"] == selected_track)
        source_boxes = {tuple(o["raw_bbox"]) for o in f.measurements if o["track_id"] == selected_track}
        self.assertTrue(all(tuple(o["raw_bbox"]) in source_boxes for o in selected_episode["observations"]))

    def test_duplicate_member_without_vehicle_origin_cannot_replace_eligible_member(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_person(x) if frame < 3 else _vehicle(x)
                              for frame, x in enumerate(xs)],
                          52: [_vehicle(x) for x in xs]})
        config = copy.deepcopy(f.config)
        # Delay confirmation to frame5, so the vehicle duplicate relation has
        # its required three common observations before event confirmation.
        config["confirmation_observations"] = 3
        result = f.run(config)
        self.total(result, 1)
        diagnostic = result["accepted_events"][0]["geometry_evidence"]
        self.assertEqual(diagnostic["track_id"], 52)
        self.assertEqual(diagnostic["origin_frame"], 0)

    def test_nonclique_transitive_duplicate_chain_is_not_one_supported_vehicle(self):
        xs = (25, 35, 45, 55, 65, 75)
        # A-B and B-C pass the strict duplicate screen; A-C fails its IoU.
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_vehicle(x + 0.8) for x in xs],
                          53: [_vehicle(x + 1.6) for x in xs]})
        result = f.run()
        self.assertIn("TRANSITIVE_IDENTITY_CONFLICT", json.dumps(result["relations"]))
        self.total(result, 0)

    def test_component_person_labels_do_not_vote_against_motorcycle_category(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x - 3) for x in xs],
                          53: [_person(x + 3) for x in xs],
                          54: [_person(x) for x in xs]})
        result = f.run()
        self.total(result, 1)
        self.assertEqual(result["accepted_events"][0]["category"], "motorcycle")

    def test_temporal_car_truck_conflict_is_not_majority_vote_resolved(self):
        labels = ("car", "car", "truck", "car", "car", "car")
        f = self.fixture({51: [_vehicle(x, label=label) for x, label in zip((25, 35, 45, 55, 65, 75), labels)]})
        self.total(f.run(), 0)

    def test_duplicate_spatial_support_cannot_resolve_motorcycle_car_category_conflict(self):
        f = self.fixture({51: self.plain_track(label="motorcycle"),
                          52: self.plain_track(label="car")})
        result = f.run()
        self.total(result, 0)
        self.assertIn("CATEGORY_CONFLICT", json.dumps(result["machine_decisions"]))

    def test_bus_taxonomy_is_not_silently_mapped_to_bus_angkot(self):
        f = self.fixture({51: self.plain_track(label="bus")})
        self.total(f.run(), 0)

    def test_person_without_vehicle_cannot_automatically_become_pedestrian(self):
        f = self.fixture({51: [_person(x) for x in (25, 35, 45, 55, 65, 75)]})
        self.total(f.run(), 0)

    def test_family_reset_rebuilds_vehicle_origin_and_creates_new_candidate(self):
        f = self.fixture({51: [_person(25), _person(35), _vehicle(40), _vehicle(45), _vehicle(55), _vehicle(65)],
                          52: [None, None, _person(40), _person(45), _person(55), _person(65)]})
        result = f.run()
        self.total(result, 1)
        diagnostic = result["accepted_events"][0]["geometry_evidence"]
        self.assertEqual(diagnostic["origin_frame"], 2)
        self.assertEqual(diagnostic["crossing_frame_start"], 3)
        self.assertEqual(diagnostic["crossing_frame_end"], 4)

    def test_new_vehicle_episode_without_its_own_origin_cannot_count_old_person_path(self):
        f = self.fixture({51: [_person(25), _person(40), _vehicle(60), _vehicle(65), _vehicle(70)]})
        self.total(f.run(), 0)

    def test_vehicle_person_vehicle_does_not_stitch_across_excluded_component(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), _person(45), _vehicle(60), _vehicle(70)]})
        self.total(f.run(), 0)

    def test_crossing_over_missing_observation_cannot_be_recovered_by_episode_reset(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), None, _vehicle(60), _vehicle(70)]})
        self.total(f.run(), 0)

    def test_initial_presence_on_arrival_side_is_not_a_passage(self):
        f = self.fixture({51: [_vehicle(x) for x in (60, 65, 70, 75)]})
        self.total(f.run(), 0)

    def test_touch_line_and_return_to_same_side_is_not_a_passage(self):
        f = self.fixture({51: [_vehicle(x) for x in (25, 40, 50, 40, 25)]})
        self.total(f.run(), 0)

    def test_measured_touch_followed_by_opposite_side_preserves_contact_evidence(self):
        xs = (25, 40, 50, 50, 60, 70)
        f = self.fixture({51: [_vehicle(x) for x in xs], 52: [_person(x) for x in xs]})
        result = f.run()
        self.total(result, 1)
        diagnostic = result["accepted_events"][0]["geometry_evidence"]
        self.assertEqual(diagnostic["crossing_evidence"]["method"], "measured_touch_then_opposite_sign")
        self.assertEqual(diagnostic["crossing_frame_start"], 1)
        self.assertEqual(diagnostic["crossing_frame_end"], 4)

    def test_exact_line_endpoint_crossing_stays_ambiguous(self):
        f = self.fixture({51: self.plain_track(y=20)})
        self.total(f.run(), 0)

    def test_infinite_line_extension_crossing_outside_segment_cannot_count(self):
        f = self.fixture({51: self.plain_track(y=90)})
        self.total(f.run(), 0)

    def test_independent_return_is_held_not_unconditionally_counted(self):
        xs = (25, 35, 45, 55, 65, 55, 45, 35, 25)
        f = self.fixture({51: [_vehicle(x) for x in xs], 52: [_person(x) for x in xs]})
        result = f.run()
        self.total(result, 1)
        self.assertTrue(any("RETURN" in " ".join(d.get("reasons", []))
                            for d in result["machine_decisions"]))

    def test_later_complete_episode_same_track_after_gap_is_not_automatic_return(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), _vehicle(60), None,
                              _vehicle(65), _vehicle(55), _vehicle(45), _vehicle(35)],
                          52: [_person(25), _person(40), _person(60), None,
                              _person(65), _person(55), _person(45), _person(35)]})
        result = f.run()
        self.total(result, 1)
        self.assertTrue(any("RETURN" in " ".join(d.get("reasons", []))
                            for d in result["machine_decisions"]))

    def test_later_complete_episode_same_track_after_family_change_needs_return_review(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), _vehicle(60), _person(65),
                              _vehicle(65), _vehicle(55), _vehicle(45), _vehicle(35)],
                          52: [_person(25), _person(40), _person(60), None,
                              _person(65), _person(55), _person(45), _person(35)]})
        result = f.run()
        self.total(result, 1)
        self.assertTrue(any("RETURN" in " ".join(d.get("reasons", []))
                            for d in result["machine_decisions"]))

    def test_pending_earlier_category_conflict_does_not_make_later_crossing_first_passage(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40, label="car"), _vehicle(60), _person(65),
                              _vehicle(65), _vehicle(55), _vehicle(45), _vehicle(35)],
                          52: [_person(25), _person(40), _person(60), None,
                              _person(65), _person(55), _person(45), _person(35)]})
        result = f.run()
        self.total(result, 0)
        self.assertTrue(any("RETURN" in " ".join(d.get("reasons", []))
                            for d in result["machine_decisions"] if d["diagnostic"].get("origin_frame") == 4))

    def test_pending_earlier_raw_competitor_does_not_release_later_return(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), _vehicle(60), None,
                              _vehicle(65), _vehicle(55), _vehicle(45), _vehicle(35)],
                          52: [_person(25), _person(40), _person(60), None,
                              _person(65), _person(55), _person(45), _person(35)]},
                         raw_extras={frame: [_vehicle(x + 1)]
                                     for frame, x in enumerate((25, 40, 60))})
        result = f.run()
        self.total(result, 0)
        self.assertTrue(any("RETURN" in " ".join(d.get("reasons", []))
                            for d in result["machine_decisions"] if d["diagnostic"].get("origin_frame") == 4))

    def test_selecting_only_later_window_does_not_hide_earlier_source_passage(self):
        f = self.fixture({51: [_vehicle(25), _vehicle(40), _vehicle(60), None,
                              _vehicle(65), _vehicle(55), _vehicle(45), _vehicle(35)],
                          52: [_person(25), _person(40), _person(60), None,
                              _person(65), _person(55), _person(45), _person(35)]})
        config = copy.deepcopy(f.config)
        config["scope"] = {"association_frame_windows": [[4, 7]]}
        result = f.run(config)
        self.total(result, 0)
        transitions = [d for d in result["derived_diagnostics"] if d["type"] == "GEOMETRY_TRANSITION"]
        self.assertEqual(len(transitions), 2)
        self.assertEqual(len(result["machine_decisions"]), 1)
        self.assertIn("GENUINE_RETURN_REVIEW_REQUIRED", result["machine_decisions"][0]["reasons"])

    def test_grouping_ablation_preserves_geometry_without_automatic_identity_acceptance(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs], 52: [_person(x) for x in xs]})
        grouped = f.run()
        config = copy.deepcopy(f.config)
        config["grouping_enabled"] = False
        ablated = f.run(config)
        self.total(grouped, 1)
        self.total(ablated, 0)
        self.assertEqual(grouped["derived_diagnostics"], ablated["derived_diagnostics"])
        self.assertFalse(any(r["status"] == "SUPPORTED" for r in ablated["relations"]))

    def test_raw_unemitted_vehicle_competitor_is_not_ignored(self):
        f = self.fixture({51: self.plain_track()}, raw_extras={
            frame: [_vehicle(x + 1)] for frame, x in enumerate((25, 35, 45, 55, 65, 75))})
        result = f.run()
        self.total(result, 0)
        self.assertIn("RAW_UNRESOLVED_VEHICLE_COMPETITOR", json.dumps(result["machine_decisions"]))

    def test_raw_bbox_tamper_is_rejected_even_after_source_hash_rebinding(self):
        f = self.fixture({51: self.plain_track()})
        f.records[1]["emitted_tracks"][0]["raw_bbox"][0] += 1
        f.write_source()
        with self.assertRaises(ValueError):
            f.run()

    def test_raw_class_tamper_is_not_a_valid_category_correction(self):
        f = self.fixture({51: self.plain_track()})
        f.records[1]["emitted_tracks"][0]["class_name"] = "car"
        f.records[1]["emitted_tracks"][0]["class_id"] = CLASS_IDS["car"]
        f.write_source()
        with self.assertRaises(ValueError):
            f.run()

    def test_predicted_track_box_cannot_substitute_for_measured_bbox(self):
        f = self.fixture({51: self.plain_track()})
        f.records[1]["emitted_tracks"][0]["measurement_provenance"] = "tracker_prediction"
        f.write_source()
        with self.assertRaises(ValueError):
            f.run()

    def test_one_raw_detection_cannot_supply_two_track_measurements(self):
        f = self.fixture({51: self.plain_track()})
        duplicate = copy.deepcopy(f.records[2]["emitted_tracks"][0])
        duplicate["track_id"] = 52
        f.records[2]["emitted_tracks"].append(duplicate)
        f.write_source()
        with self.assertRaises(ValueError):
            f.run()

    def test_source_sha_mismatch_does_not_silently_rebind(self):
        f = self.fixture({51: self.plain_track()})
        config = copy.deepcopy(f.config)
        config["input_identity"]["records_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            f.run(config)

    def test_same_source_rerun_is_idempotent_and_keeps_event_ids(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs], 52: [_person(x) for x in xs]})
        first, second = f.run(), f.run()
        self.total(first, 1)
        self.assertEqual(first["accepted_events"], second["accepted_events"])
        self.assertEqual(first["aggregate"], second["aggregate"])
        self.assertEqual(first["machine_decisions"], second["machine_decisions"])

    def test_repeated_count_event_is_idempotent_in_aggregate(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs], 52: [_person(x) for x in xs]})
        event = f.run()["accepted_events"][0]
        aggregate = aggregate_events([event, copy.deepcopy(event)])
        self.assertEqual(aggregate["total"], 1)

    def test_pending_decision_cannot_enter_typed_event_aggregate(self):
        f = self.fixture({51: self.plain_track(label="bus")})
        decision = f.run()["machine_decisions"][0]
        with self.assertRaises(ValueError):
            aggregate_events([decision])

    def test_episode_processing_order_cannot_change_assignment_or_event_ids(self):
        xs = (25, 35, 45, 55, 65, 75)
        f = self.fixture({51: [_vehicle(x) for x in xs],
                          52: [_person(x) for x in xs]})
        episodes = self.episodes(f)
        context = {row["frame_index"]: row for row in f.records}
        first = resolver.resolve_episodes(episodes, f.geometry, config=f.config, context_by_frame=context)
        second = resolver.resolve_episodes(list(reversed(episodes)), f.geometry, config=f.config, context_by_frame=context)
        self.assertEqual(first["accepted_events"], second["accepted_events"])
        self.assertEqual(first["aggregate"], second["aggregate"])

    def test_case_specific_manual_ids_do_not_change_generic_resolution(self):
        xs = (25, 35, 45, 55, 65, 75)
        first = self.fixture({51: [_vehicle(x) for x in xs], 52: [_person(x) for x in xs]}).run()
        second = self.fixture({1772: [_vehicle(x) for x in xs], 1774: [_person(x) for x in xs]}).run()
        self.total(first, 1)
        self.total(second, 1)
        self.assertEqual(first["aggregate"]["by_category"], second["aggregate"]["by_category"])
        self.assertEqual(first["aggregate"]["by_direction"], second["aggregate"]["by_direction"])

    def test_missing_explicit_association_control_is_not_filled_by_hidden_default(self):
        f = self.fixture({51: self.plain_track()})
        config = copy.deepcopy(f.config)
        del config["association"]["component"]["min_common_frames"]
        with self.assertRaises(ValueError):
            f.run(config)

    def test_nonfinite_association_control_is_rejected(self):
        f = self.fixture({51: self.plain_track()})
        config = copy.deepcopy(f.config)
        config["association"]["same_vehicle"]["min_iou"] = float("nan")
        with self.assertRaises(ValueError):
            f.run(config)

    def test_missing_full_frame_competitor_context_does_not_grant_acceptance(self):
        f = self.fixture({51: self.plain_track()})
        result = resolver.resolve_episodes(self.episodes(f), f.geometry, config=f.config)
        self.total(result, 0)
        self.assertIn("UNKNOWN_RAW_COMPETITORS", json.dumps(result["machine_decisions"]))

    def test_direct_episode_resolution_rejects_mismatched_native_geometry_dimensions(self):
        f = self.fixture({51: self.plain_track()})
        different_native = Geometry.from_draft(f.geometry_path, 101, 100)
        with self.assertRaises(ValueError):
            resolver.resolve_episodes(self.episodes(f), different_native, config=f.config)

    def test_direct_episode_resolution_rejects_geometry_for_different_video(self):
        f = self.fixture({51: self.plain_track()})
        document = copy.deepcopy(f.geometry_document)
        document["source_video"]["sha256"] = "e" * 64
        other_path = self.root / "different_video_geometry.json"
        other_path.write_text(json.dumps(document), encoding="utf-8")
        different_video = Geometry.from_draft(other_path, 100, 100)
        with self.assertRaises(ValueError):
            resolver.resolve_episodes(self.episodes(f), different_video, config=f.config)

    def test_direct_episode_resolution_rejects_bounds_that_hide_source_observation(self):
        f = self.fixture({51: self.plain_track()})
        episodes = self.episodes(f)
        episodes[0]["start_frame"] += 1
        with self.assertRaises(ValueError):
            resolver.resolve_episodes(episodes, f.geometry, config=f.config)

    def test_direct_episode_resolution_rejects_mixed_raw_track_identities(self):
        f = self.fixture({51: self.plain_track()})
        episodes = self.episodes(f)
        episodes[0]["observations"][1]["track_id"] = 99
        with self.assertRaises(ValueError):
            resolver.resolve_episodes(episodes, f.geometry, config=f.config)


class _RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({"id": test.id(), "status": "passed"})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({"id": test.id(), "status": "failed"})

    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({"id": test.id(), "status": "error"})


def run_tests():
    suite = unittest.defaultTestLoader.loadTestsFromModule(__import__(__name__))
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=_RecordingResult).run(suite)
    return {
        "claim_type": "ACTUALLY_EXECUTED_SYNTHETIC_SOFTWARE_CONTRACT_TESTS",
        "scope": "Option B physical-unit relations and vehicle episodes; no actual-video results or accuracy",
        "fixture_controls_are_product_defaults": False,
        "successful": result.wasSuccessful(), "tests_run": result.testsRun,
        "tests_passed": sum(item["status"] == "passed" for item in result.records),
        "failures": [{"id": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"id": test.id(), "traceback": trace} for test, trace in result.errors],
        "skipped": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
        "tests": result.records, "output": output.getvalue(),
    }


if __name__ == "__main__":
    summary = run_tests()
    print(json.dumps(summary, indent=2))
    raise SystemExit(0 if summary["successful"] else 1)
