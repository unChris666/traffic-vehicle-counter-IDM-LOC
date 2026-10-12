"""Independent Phase 6 Option A contract tests, without models or video decode.

All evidence here is explicitly synthetic software-fixture evidence, never a
review of the actual TOR3 video. Tiny coordinates and b0/c1 are fixture controls,
not selected product parameters. Fixtures obtain diagnostic transitions from
the existing Phase 5 measured-track geometry implementation; counting does not
create or repair their crossings.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

from phase_5_geometry_helpers import Geometry, replay_cached_records
from phase_6_counting_helpers import (
    aggregate_events,
    candidate_key,
    candidate_selector,
    run_counting,
)


VIDEO_SHA = "a" * 64
CLASS_IDS = {"person": 0, "car": 2, "motorcycle": 3, "bus": 5, "truck": 7, "handbag": 26}
PRODUCT_CATEGORIES = {"pedestrian", "motorcycle", "car", "truck", "bus_angkot"}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _jsonl(path, rows):
    Path(path).write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


class CountingFixture:
    """Native 10x10 test canvas; measured BC crosses finite x=5,y=2..8."""

    def __init__(self, root, tracks=None, *, raw_extras=None, band=0, confirmation=1):
        self.root = Path(root)
        self.records_path = self.root / "records.jsonl"
        self.diagnostics_path = self.root / "diagnostics.jsonl"
        self.geometry_path = self.root / "geometry.json"
        self.evidence_path = self.root / "synthetic_evidence.txt"
        self.evidence_path.write_text("SYNTHETIC SOFTWARE FIXTURE; NOT ACTUAL VIDEO PIXEL EVIDENCE\n", encoding="utf-8")
        self.geometry_document = {
            "draft_id": "phase6-synthetic-finite-line",
            "status": "SYNTHETIC_SOFTWARE_FIXTURE_NOT_ACTUAL_VIDEO",
            "source_video": {"sha256": VIDEO_SHA},
            "normalized": {
                "line": {"P1": [0.5, 0.2], "P2": [0.5, 0.8]},
                "side_a_polygon": [[0, 0], [0.5, 0], [0.5, 1], [0, 1]],
                "side_b_polygon": [[0.5, 0], [1, 0], [1, 1], [0.5, 1]],
            },
        }
        self.geometry_path.write_text(json.dumps(self.geometry_document, sort_keys=True), encoding="utf-8")
        self.geometry = Geometry.from_draft(self.geometry_path, 10, 10)
        self.tracks = tracks or {17: [(2, 5, "car"), (8, 5, "car")]}
        self.records = []
        for frame in range(max(len(values) for values in self.tracks.values())):
            record = {
                "video_sha256": VIDEO_SHA, "parent_run_id": "synthetic-software-fixture",
                "variant": "reid_on", "frame_index": frame, "width": 10, "height": 10,
                "timestamp_estimate_from_index_fps_seconds": frame / 30,
                "timestamp_parent_backend_ms": None, "raw_detections": [], "emitted_tracks": [],
                "assigned_observations_including_unconfirmed": [], "lifecycle_snapshots": [],
            }
            for track_id, values in self.tracks.items():
                item = values[frame] if frame < len(values) else None
                if item is None:
                    continue
                x, y, class_name = item
                box = [x - 0.4, y - 1, x + 0.4, y]
                index = len(record["raw_detections"])
                detection = {"bbox_xyxy_pixels": box, "class_id": CLASS_IDS[class_name],
                             "class_name": class_name, "confidence": 0.8}
                observation = {
                    "track_id": track_id, "frame_index": frame, "original_detection_index": index,
                    "raw_bbox": list(box), "bbox": [0, 0, 1, 1], "center": [0.5, 0.5],
                    "class_id": detection["class_id"], "class_name": class_name, "confidence": 0.8,
                    "emitted": True, "is_activated": True,
                    "measurement_provenance": "retained_phase_2_detection",
                }
                record["raw_detections"].append(detection)
                record["emitted_tracks"].append(observation)
            for extra in (raw_extras or {}).get(frame, []):
                record["raw_detections"].append(copy.deepcopy(extra))
            self.records.append(record)
        self.band, self.confirmation = band, confirmation
        self.regenerate()

    def regenerate(self):
        _jsonl(self.records_path, self.records)
        result = replay_cached_records(self.records_path, self.geometry,
                                       neutral_band_px=self.band, confirmation_observations=self.confirmation)
        self.diagnostics = result["diagnostics"]
        self.write_diagnostics()

    def write_diagnostics(self):
        _jsonl(self.diagnostics_path, self.diagnostics)
        self.rebind()

    def rebind(self):
        self.identity = {
            "video_sha256": VIDEO_SHA, "records_sha256": _sha(self.records_path),
            "diagnostics_sha256": _sha(self.diagnostics_path), "geometry_sha256": _sha(self.geometry_path),
            "variant": "reid_on", "width": 10, "height": 10,
            "parent_run_id": "synthetic-software-fixture",
        }
        self.config = {"contract_version": "phase6_option_a_v0", "metric": "passage",
                       "review_policy": "audit_gated", "neutral_band_px": float(self.band),
                       "confirmation_observations": self.confirmation,
                       "input_identity": copy.deepcopy(self.identity)}

    def transitions(self):
        return [d for d in self.diagnostics if d["type"] == "GEOMETRY_TRANSITION"]

    def confirm(self, diagnostic, *, unit="unit-17", passage="passage-1", category="car", role="vehicle", **updates):
        frames = sorted({diagnostic["origin_frame"], diagnostic["crossing_frame_start"],
                         diagnostic["crossing_frame_end"], diagnostic["confirmation_frame"]})
        if diagnostic["crossing_evidence"]["method"] == "measured_touch_then_opposite_sign":
            frames = sorted(set(frames) | set(range(diagnostic["crossing_frame_start"] + 1,
                                                   diagnostic["crossing_frame_end"])))
        decision = {
            "selector": candidate_selector(diagnostic), "decision": "CONFIRM_PASSAGE",
            "role": role, "category": category, "physical_unit_id": unit, "passage_id": passage,
            "unit_confirmed": True, "category_confirmed": True, "identity_confirmed": True,
            "independent_return_confirmed": False, "reviewer": "synthetic-fixture-reviewer-v1",
            "reason": "Explicit software fixture; not actual video inspection",
            "evidence": [{"path": self.evidence_path.name, "sha256": _sha(self.evidence_path),
                          "frame_indices": frames, "observation": "SYNTHETIC FIXTURE NOT ACTUAL VIDEO"}],
        }
        decision.update(updates)
        return decision

    def run(self, decisions=None, *, reviews=None, config=None):
        if reviews is None and decisions is not None:
            reviews = {"input_identity": copy.deepcopy(self.identity), "decisions": decisions}
        return run_counting(self.diagnostics_path, self.records_path, self.geometry_path,
                            config=config or self.config, reviews=reviews,
                            evidence_root=self.root if reviews is not None else None)


class CountingContractTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="phase6-synthetic-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def fixture(self, tracks=None, **kwargs):
        return CountingFixture(self.root, tracks, **kwargs)

    def assert_total(self, result, expected):
        self.assertEqual(result["aggregate"]["total"], expected)
        self.assertEqual(len(result["accepted_events"]), expected)
        self.assertEqual(sum(result["aggregate"]["by_category"].values()), expected)
        self.assertEqual(sum(result["aggregate"]["by_direction"].values()), expected)
        self.assertEqual(set(result["aggregate"]["by_category"]), PRODUCT_CATEGORIES)
        self.assertEqual(result["machine_aggregate"]["total"], 0)
        self.assertEqual(result["machine_events"], [])

    def test_measured_a_to_b_positive_review_produces_one_auditable_event(self):
        f = self.fixture()
        d = f.transitions()[0]
        result = f.run([f.confirm(d)])
        self.assert_total(result, 1)
        event = result["accepted_events"][0]
        self.assertEqual(event["type"], "CountEvent")
        self.assertIs(event["accepted_count_event"], True)
        self.assertEqual(event["status"], "accepted")
        self.assertEqual(event["direction"], "A_TO_B")
        self.assertEqual(event["category"], "car")
        self.assertEqual(event["physical_unit_id"], "unit-17")
        self.assertEqual(event["passage_id"], "passage-1")
        self.assertEqual(result["machine_decisions"][0]["status"], "pending_review")

    def test_measured_b_to_a_has_own_direction_without_image_axis_assumption(self):
        f = self.fixture({17: [(8, 6, "truck"), (2, 4, "truck")]})
        result = f.run([f.confirm(f.transitions()[0], category="truck")])
        self.assert_total(result, 1)
        self.assertEqual(result["accepted_events"][0]["direction"], "B_TO_A")
        self.assertEqual(result["aggregate"]["by_direction"]["B_TO_A"], 1)

    def test_no_overlap_and_consistent_class_do_not_replace_review(self):
        f = self.fixture()
        result = f.run()
        self.assert_total(result, 0)
        self.assertTrue(all(d["status"] == "pending_review" for d in result["resolved_decisions"]))

    def test_each_positive_unit_category_identity_gate_is_required(self):
        f = self.fixture()
        for gate in ("unit_confirmed", "category_confirmed", "identity_confirmed"):
            with self.subTest(gate=gate):
                result = f.run([f.confirm(f.transitions()[0], **{gate: False})])
                self.assert_total(result, 0)

    def test_walking_person_requires_explicit_pedestrian_role_and_full_review(self):
        f = self.fixture({17: [(2, 5, "person"), (8, 5, "person")]})
        self.assert_total(f.run(), 0)
        result = f.run([f.confirm(f.transitions()[0], role="pedestrian", category="pedestrian")])
        self.assert_total(result, 1)
        self.assertEqual(result["aggregate"]["by_category"]["pedestrian"], 1)

    def test_rider_and_passenger_are_rejected_not_silently_pedestrian(self):
        f = self.fixture({17: [(2, 5, "person"), (8, 5, "person")]})
        for role in ("rider", "passenger"):
            with self.subTest(role=role):
                review = f.confirm(f.transitions()[0], role=role, category=None, decision="REJECT_COMPONENT")
                result = f.run([review])
                self.assert_total(result, 0)
                self.assertEqual(result["resolved_decisions"][0]["status"], "rejected")

    def test_person_to_vehicle_anywhere_in_full_window_is_hard_blocked(self):
        f = self.fixture({17: [(2, 5, "person"), (3, 5, "motorcycle"), (8, 5, "motorcycle")]})
        result = f.run([f.confirm(f.transitions()[0], category="motorcycle")])
        self.assert_total(result, 0)
        self.assertIn("UNIT_COMPONENT_CHANGE", json.dumps(result["resolved_decisions"]))

    def test_mid_window_component_change_cannot_be_hidden_by_motorcycle_endpoints(self):
        f = self.fixture({17: [(2, 5, "motorcycle"), (3, 5, "person"), (8, 5, "motorcycle")]})
        result = f.run([f.confirm(f.transitions()[0], category="motorcycle")])
        self.assert_total(result, 0)
        self.assertIn("UNIT_COMPONENT_CHANGE", json.dumps(result["resolved_decisions"]))

    def test_car_truck_conflict_pending_until_evidence_backed_category_resolution(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "truck")]})
        self.assert_total(f.run(), 0)
        result = f.run([f.confirm(f.transitions()[0], category="truck", reason="Synthetic physical truck evidence; no pickup policy invented")])
        self.assert_total(result, 1)
        self.assertEqual(result["accepted_events"][0]["category"], "truck")

    def test_bus_angkot_mapping_open_cannot_be_forced_by_review(self):
        f = self.fixture({17: [(2, 5, "bus"), (8, 5, "bus")]})
        result = f.run([f.confirm(f.transitions()[0], category="bus_angkot")])
        self.assert_total(result, 0)
        self.assertEqual(result["resolved_decisions"][0]["status"], "pending_review")

    def test_review_category_requires_supporting_raw_class_history(self):
        f = self.fixture({17: [(2, 5, "motorcycle"), (8, 5, "motorcycle")]})
        self.assert_total(f.run([f.confirm(f.transitions()[0], category="car")]), 0)

    def test_unsupported_raw_class_is_not_invented_product_category(self):
        f = self.fixture({17: [(2, 5, "handbag"), (8, 5, "handbag")]})
        result = f.run([f.confirm(f.transitions()[0], category="car")])
        self.assert_total(result, 0)

    def test_origin_window_raw_vehicle_overlap_is_screened_even_if_not_emitted(self):
        extra = {"bbox_xyxy_pixels": [1.7, 3, 2.5, 5.2], "class_id": 3,
                 "class_name": "motorcycle", "confidence": 0.7}
        f = self.fixture({17: [(2, 5, "car"), (3, 5, "car"), (8, 5, "car")]}, raw_extras={0: [extra]})
        result = f.run()
        self.assert_total(result, 0)
        self.assertIn("OVERLAP", json.dumps(result["machine_decisions"]))
        self.assert_total(f.run([f.confirm(f.transitions()[0])]), 1)

    def test_raw_person_overlap_does_not_automatically_reject_vehicle(self):
        extra = {"bbox_xyxy_pixels": [1.7, 3, 2.5, 5.2], "class_id": 0,
                 "class_name": "person", "confidence": 0.7}
        f = self.fixture(raw_extras={0: [extra]})
        self.assert_total(f.run([f.confirm(f.transitions()[0])]), 1)

    def test_same_physical_unit_and_same_passage_multiple_ids_count_once(self):
        f = self.fixture({17: [(2, 5, "motorcycle"), (8, 5, "motorcycle")],
                          18: [(2.1, 5.1, "motorcycle"), (8.1, 5.1, "motorcycle")]})
        result = f.run([f.confirm(d, category="motorcycle") for d in f.transitions()])
        self.assert_total(result, 1)
        event_blob = json.dumps(result["accepted_events"])
        self.assertIn("17", event_blob)
        self.assertIn("18", event_blob)

    def test_two_distinct_reviewed_units_are_not_merged_by_spatial_overlap(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car")],
                          18: [(2.1, 5.1, "car"), (8.1, 5.1, "car")]})
        reviews = [f.confirm(d, unit=f"unit-{d['track_id']}", passage=f"passage-{d['track_id']}") for d in f.transitions()]
        self.assert_total(f.run(reviews), 2)

    def test_same_group_never_selects_earlier_unit_changing_id_as_representative(self):
        f = self.fixture({964: [(2, 5, "person"), (8, 5, "motorcycle"), None],
                          973: [(2.1, 5.1, "motorcycle"), (3, 5.1, "motorcycle"), (8.1, 5.1, "motorcycle")]})
        result = f.run([f.confirm(d, category="motorcycle", unit="one-skuter", passage="one-passage") for d in f.transitions()])
        self.assert_total(result, 1)
        decisions = {item["selector"]["track_id"]: item for item in result["resolved_decisions"]}
        self.assertEqual(decisions[964]["status"], "pending_review")
        self.assertEqual(decisions[973]["status"], "accepted")

    def test_reverse_passage_without_independent_return_proof_stays_pending(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car"), (2, 5, "car")]})
        reviews = [f.confirm(d, passage=f"passage-{i}") for i, d in enumerate(f.transitions())]
        result = f.run(reviews)
        self.assert_total(result, 1)
        self.assertIn("RETURN_EPISODE_REVIEW_REQUIRED", json.dumps(result["resolved_decisions"]))

    def test_independently_reviewed_return_counts_new_passage_not_once_per_id(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car"), (2, 5, "car")]})
        reviews = [f.confirm(d, passage=f"passage-{i}", independent_return_confirmed=i > 0) for i, d in enumerate(f.transitions())]
        result = f.run(reviews)
        self.assert_total(result, 2)
        self.assertEqual({e["direction"] for e in result["accepted_events"]}, {"A_TO_B", "B_TO_A"})

    def test_repeated_same_side_updates_never_create_extra_event(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car"), (8.2, 5, "car"), (8.3, 5, "car")]})
        self.assertEqual(len(f.transitions()), 1)
        self.assert_total(f.run([f.confirm(f.transitions()[0])]), 1)

    def test_neutral_band_fixture_blocks_near_line_jitter_before_counting(self):
        f = self.fixture({17: [(4.8, 5, "car"), (5.2, 5, "car"), (4.9, 5, "car"), (5.1, 5, "car")]}, band=1)
        self.assertEqual(f.transitions(), [])
        self.assert_total(f.run(), 0)

    def test_two_required_destination_observations_are_retained_before_acceptance(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car"), (8.2, 5, "car")]}, confirmation=2)
        d = f.transitions()[0]
        self.assertEqual(d["confirmation_frame"], 2)
        self.assertEqual(len(d["confirmation_observations"]), 2)
        self.assert_total(f.run([f.confirm(d)]), 1)

    def test_repeated_physical_unit_across_changed_ids_requires_episode_proof(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car"), None, None],
                          18: [None, None, (8, 5, "car"), (2, 5, "car")]})
        reviews = [f.confirm(d, passage=f"passage-{i}") for i, d in enumerate(f.transitions())]
        self.assert_total(f.run(reviews), 1)
        reviews[1]["independent_return_confirmed"] = True
        self.assert_total(f.run(reviews), 2)

    def test_simultaneous_passages_cannot_be_confirmed_as_independent_return_episodes(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car")],
                          18: [(2, 6, "car"), (8, 6, "car")]})
        reviews = [f.confirm(d, passage=f"passage-{i}", independent_return_confirmed=True)
                   for i, d in enumerate(f.transitions())]
        result = f.run(reviews)
        self.assert_total(result, 0)
        self.assertTrue(all(d["status"] == "pending_review" for d in result["resolved_decisions"]))
        self.assertIn("OVERLAPPING_PASSAGE_EPISODES", json.dumps(result["resolved_decisions"]))

    def test_same_direction_later_independently_reviewed_reentry_is_not_forbidden(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car"), None, None],
                          18: [None, None, (2, 5, "car"), (8, 5, "car")]})
        reviews = [f.confirm(d, passage=f"passage-{i}", independent_return_confirmed=i > 0)
                   for i, d in enumerate(f.transitions())]
        result = f.run(reviews)
        self.assert_total(result, 2)
        self.assertTrue(all(e["direction"] == "A_TO_B" for e in result["accepted_events"]))

    def test_initial_presence_touch_and_incomplete_crossing_emit_no_event(self):
        for points in ([(2, 5)], [(2, 5), (5, 5), (2, 5)], [(2, 1), (8, 1)], [(5, 5)]):
            with self.subTest(points=points):
                f = self.fixture({17: [(x, y, "car") for x, y in points]})
                self.assertEqual(f.transitions(), [])
                self.assert_total(f.run(), 0)

    def test_gap_diagnostic_is_never_promoted_by_manual_confirmation(self):
        f = self.fixture({17: [(2, 5, "car"), None, (8, 5, "car")]})
        self.assertEqual(f.transitions(), [])
        result = f.run()
        self.assert_total(result, 0)
        ambiguous = next(d for d in f.diagnostics if d["type"] == "AMBIGUOUS_GAP")
        review = {"selector": candidate_selector(ambiguous), "decision": "CONFIRM_PASSAGE",
                  "role": "vehicle", "category": "car", "physical_unit_id": "u", "passage_id": "p",
                  "unit_confirmed": True, "category_confirmed": True, "identity_confirmed": True,
                  "reviewer": "synthetic", "reason": "Must not repair geometry",
                  "evidence": [{"path": f.evidence_path.name, "sha256": _sha(f.evidence_path),
                                "frame_indices": [0, 2], "observation": "Synthetic gap fixture; not actual video"}]}
        self.assert_total(f.run([review]), 0)

    def test_endpoint_diagnostic_never_produces_count(self):
        f = self.fixture({17: [(2, 2, "car"), (8, 2, "car")]})
        self.assertEqual(f.transitions(), [])
        self.assertTrue(any(d["type"] == "AMBIGUOUS_ENDPOINT" for d in f.diagnostics))
        self.assert_total(f.run(), 0)

    def test_manual_review_cannot_override_endpoint_ambiguity(self):
        f = self.fixture({17: [(2, 2, "car"), (8, 2, "car")]})
        ambiguous = next(d for d in f.diagnostics if d["type"] == "AMBIGUOUS_ENDPOINT")
        review = {"selector": candidate_selector(ambiguous), "decision": "CONFIRM_PASSAGE",
                  "role": "vehicle", "category": "car", "physical_unit_id": "u", "passage_id": "p",
                  "unit_confirmed": True, "category_confirmed": True, "identity_confirmed": True,
                  "reviewer": "synthetic", "reason": "Must not repair endpoint crossing",
                  "evidence": [{"path": f.evidence_path.name, "sha256": _sha(f.evidence_path),
                                "frame_indices": [0, 1], "observation": "Synthetic endpoint fixture"}]}
        self.assert_total(f.run([review]), 0)

    def test_measured_touch_then_opposite_sign_remains_valid_with_full_contact_evidence(self):
        f = self.fixture({17: [(2, 5, "car"), (5, 5, "car"), (5, 6, "car"), (8, 6, "car")]})
        self.assertEqual(len(f.transitions()), 1)
        result = f.run([f.confirm(f.transitions()[0])])
        self.assert_total(result, 1)

    def test_contact_evidence_cannot_omit_measured_line_contact_frames(self):
        f = self.fixture({17: [(2, 5, "car"), (5, 5, "car"), (5, 6, "car"), (8, 6, "car")]})
        review = f.confirm(f.transitions()[0])
        review["evidence"][0]["frame_indices"] = [0, 3]
        self.assert_total(f.run([review]), 0)

    def test_retained_intersection_claims_are_rederived_from_measured_sources(self):
        for method in ("touch", "consecutive"):
            points = [(2, 5, "car"), (5, 5, "car"), (8, 5, "car")] if method == "touch" else [(2, 5, "car"), (8, 5, "car")]
            for mutation in ("point", "kind", "t", "u"):
                with self.subTest(method=method, mutation=mutation):
                    f = self.fixture({17: points})
                    diagnostic = f.transitions()[0]
                    intersection = diagnostic["crossing_evidence"]["intersection"]
                    if mutation == "point":
                        diagnostic["crossing_point"] = [999, 999]
                        intersection["point"] = [999, 999]
                    elif mutation == "kind":
                        intersection["kind"] = "proper" if method == "touch" else "touch"
                    else:
                        intersection[mutation] = 0.12345
                    f.write_diagnostics()
                    with self.assertRaises(ValueError):
                        f.run([f.confirm(diagnostic)])

    def test_lifecycle_prediction_and_unconfirmed_observation_cannot_supply_passage(self):
        f = self.fixture()
        prediction = copy.deepcopy(f.records[1]["emitted_tracks"][0])
        prediction["emitted"] = False
        f.records[1]["emitted_tracks"] = []
        f.records[1]["assigned_observations_including_unconfirmed"] = [prediction]
        f.records[1]["lifecycle_snapshots"] = [{"track_id": 17, "bbox": [7.5, 4, 8.5, 5], "is_prediction": True}]
        f.regenerate()
        self.assertEqual(f.transitions(), [])
        self.assert_total(f.run(), 0)

    def test_actual_input_hash_bindings_reject_mutated_records_without_rebinding(self):
        f = self.fixture()
        f.records_path.write_text(f.records_path.read_text() + "\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            f.run()

    def test_review_is_bound_to_exact_input_hash_namespace(self):
        f = self.fixture()
        reviews = {"input_identity": copy.deepcopy(f.identity), "decisions": [f.confirm(f.transitions()[0])]}
        reviews["input_identity"]["records_sha256"] = "b" * 64
        with self.assertRaises(ValueError):
            f.run(reviews=reviews)

    def test_evidence_hash_tampering_is_not_accepted(self):
        f = self.fixture()
        review = f.confirm(f.transitions()[0])
        f.evidence_path.write_text("tampered synthetic evidence", encoding="utf-8")
        with self.assertRaises(ValueError):
            f.run([review])

    def test_missing_evidence_file_is_not_accepted(self):
        f = self.fixture()
        review = f.confirm(f.transitions()[0])
        review["evidence"][0]["path"] = "missing.txt"
        with self.assertRaises(ValueError):
            f.run([review])

    def test_evidence_path_cannot_escape_explicit_root(self):
        f = self.fixture()
        review = f.confirm(f.transitions()[0])
        review["evidence"][0]["path"] = "../outside.txt"
        with self.assertRaises(ValueError):
            f.run([review])

    def test_contact_sheet_frame_coverage_must_include_origin_and_passage(self):
        f = self.fixture({17: [(2, 5, "car"), (3, 5, "car"), (8, 5, "car")]})
        review = f.confirm(f.transitions()[0])
        review["evidence"][0]["frame_indices"] = [2]
        self.assert_total(f.run([review]), 0)

    def test_invalid_measurement_provenance_cannot_be_accepted_even_with_valid_hash(self):
        f = self.fixture()
        f.records[0]["emitted_tracks"][0]["measurement_provenance"] = "Kalman_prediction"
        _jsonl(f.records_path, f.records)
        f.rebind()
        with self.assertRaises(ValueError):
            f.run([f.confirm(f.transitions()[0])])

    def test_source_bbox_link_and_native_dimension_mismatch_fail_closed(self):
        for mutation in ("bbox", "dimensions", "class", "index"):
            with self.subTest(mutation=mutation):
                f = self.fixture()
                if mutation == "bbox":
                    f.records[0]["emitted_tracks"][0]["raw_bbox"][0] -= 0.1
                elif mutation == "dimensions":
                    f.records[0]["width"] = 20
                elif mutation == "class":
                    f.records[0]["emitted_tracks"][0]["class_name"] = "truck"
                else:
                    f.records[0]["emitted_tracks"][0]["original_detection_index"] = 5
                _jsonl(f.records_path, f.records)
                f.rebind()
                with self.assertRaises(ValueError):
                    f.run()

    def test_geometry_diagnostic_coordinate_tampering_cannot_be_reviewed_away(self):
        f = self.fixture()
        f.transitions()[0]["confirmation_point"] = [7, 5]
        f.write_diagnostics()
        with self.assertRaises(ValueError):
            f.run([f.confirm(f.transitions()[0])])

    def test_required_parameters_and_review_policy_have_no_silent_fallback(self):
        f = self.fixture()
        for key in ("neutral_band_px", "confirmation_observations", "review_policy", "metric", "input_identity"):
            config = copy.deepcopy(f.config)
            config.pop(key)
            with self.subTest(key=key):
                with self.assertRaises((ValueError, TypeError)):
                    f.run(config=config)

    def test_invalid_numeric_controls_and_alternate_metric_fail_explicitly(self):
        f = self.fixture()
        for key, value in (("neutral_band_px", -1), ("neutral_band_px", True),
                           ("confirmation_observations", 0), ("confirmation_observations", True),
                           ("metric", "unique_vehicles"), ("review_policy", "automatic")):
            with self.subTest(key=key, value=value):
                config = copy.deepcopy(f.config)
                config[key] = value
                with self.assertRaises(ValueError):
                    f.run(config=config)

    def test_diagnostic_confirmation_evidence_does_not_match_unexecuted_config(self):
        f = self.fixture()
        config = copy.deepcopy(f.config)
        config["confirmation_observations"] = 3
        with self.assertRaises(ValueError):
            f.run(config=config)

    def test_same_inputs_and_reviews_rerun_are_idempotent(self):
        f = self.fixture()
        reviews = [f.confirm(f.transitions()[0])]
        first, second = f.run(reviews), f.run(reviews)
        self.assertEqual(first["accepted_events"], second["accepted_events"])
        self.assertEqual(first["aggregate"], second["aggregate"])
        self.assertEqual(first["resolved_decisions"], second["resolved_decisions"])

    def test_execution_timestamp_is_not_part_of_candidate_or_event_identity(self):
        f = self.fixture()
        review = f.confirm(f.transitions()[0])
        first_config = copy.deepcopy(f.config)
        second_config = copy.deepcopy(f.config)
        first_config["execution_started_at_utc"] = "2000-01-01T00:00:00Z"
        second_config["execution_started_at_utc"] = "2099-01-01T00:00:00Z"
        first, second = f.run([review], config=first_config), f.run([review], config=second_config)
        self.assertEqual(first["accepted_events"][0]["event_id"], second["accepted_events"][0]["event_id"])
        self.assertEqual(candidate_key(f.transitions()[0], f.identity), candidate_key(f.transitions()[0], f.identity))

    def test_source_cache_identity_change_changes_candidate_namespace(self):
        f = self.fixture()
        d = f.transitions()[0]
        changed = copy.deepcopy(f.identity)
        changed["records_sha256"] = "b" * 64
        self.assertNotEqual(candidate_key(d, f.identity), candidate_key(d, changed))

    def test_category_correction_does_not_create_new_physical_event_id(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "truck")]})
        d = f.transitions()[0]
        first = f.run([f.confirm(d, category="car")])
        second = f.run([f.confirm(d, category="truck")])
        self.assertEqual(first["accepted_events"][0]["event_id"], second["accepted_events"][0]["event_id"])

    def test_repeating_identical_diagnostic_is_not_duplicate_count(self):
        f = self.fixture()
        d = copy.deepcopy(f.transitions()[0])
        f.diagnostics.append(copy.deepcopy(d))
        f.write_diagnostics()
        self.assert_total(f.run([f.confirm(d)]), 1)

    def test_same_candidate_identifier_conflicting_payload_fails(self):
        f = self.fixture()
        d = copy.deepcopy(f.transitions()[0])
        d["confirmation_point"] = [9, 5]
        f.diagnostics.append(d)
        f.write_diagnostics()
        with self.assertRaises(ValueError):
            f.run()

    def test_contradictory_duplicate_reviews_for_one_candidate_fail(self):
        f = self.fixture()
        review = f.confirm(f.transitions()[0])
        contradictory = copy.deepcopy(review)
        contradictory["decision"] = "REJECT"
        with self.assertRaises(ValueError):
            f.run([review, contradictory])

    def test_contradictory_category_in_confirmed_same_passage_group_fails(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "truck")],
                          18: [(2.1, 5.1, "car"), (8.1, 5.1, "truck")]})
        reviews = [f.confirm(d, category=category) for d, category in zip(f.transitions(), ("car", "truck"))]
        with self.assertRaises(ValueError):
            f.run(reviews)

    def test_contradictory_direction_in_confirmed_same_passage_group_fails(self):
        f = self.fixture({17: [(2, 5, "car"), (8, 5, "car")],
                          18: [(8, 6, "car"), (2, 6, "car")]})
        reviews = [f.confirm(d) for d in f.transitions()]
        with self.assertRaises(ValueError):
            f.run(reviews)

    def test_aggregation_is_unique_idempotent_and_exactly_reconciled(self):
        f = self.fixture()
        event = f.run([f.confirm(f.transitions()[0])])["accepted_events"][0]
        aggregate = aggregate_events([event, copy.deepcopy(event)])
        self.assertEqual(aggregate["total"], 1)
        self.assertEqual(aggregate["by_category"]["car"], 1)
        self.assertEqual(sum(aggregate["by_category"].values()), 1)
        self.assertEqual(set(aggregate["by_category"]), PRODUCT_CATEGORIES)

    def test_aggregate_rejects_same_event_id_with_conflicting_category(self):
        f = self.fixture()
        event = f.run([f.confirm(f.transitions()[0])])["accepted_events"][0]
        conflict = copy.deepcopy(event)
        conflict["category"] = "truck"
        with self.assertRaises(ValueError):
            aggregate_events([event, conflict])

    def test_aggregate_rejects_accepted_candidate_without_count_event_type(self):
        f = self.fixture()
        event = f.run([f.confirm(f.transitions()[0])])["accepted_events"][0]
        event["type"] = "GEOMETRY_TRANSITION"
        with self.assertRaises(ValueError):
            aggregate_events([event])

    def test_aggregate_rejects_count_event_without_positive_accepted_marker(self):
        f = self.fixture()
        event = f.run([f.confirm(f.transitions()[0])])["accepted_events"][0]
        event["accepted_count_event"] = False
        with self.assertRaises(ValueError):
            aggregate_events([event])

    def test_unknown_product_category_does_not_create_new_aggregate_row(self):
        f = self.fixture()
        event = f.run([f.confirm(f.transitions()[0])])["accepted_events"][0]
        event["category"] = "unknown-made-up-class"
        with self.assertRaises(ValueError):
            aggregate_events([event])


class _RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        super().startTest(test)
        self.records.append({"id": test.id(), "status": "running"})

    def _status(self, test, status):
        for record in reversed(self.records):
            if record["id"] == test.id():
                record["status"] = status
                return

    def addSuccess(self, test):
        super().addSuccess(test)
        self._status(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._status(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._status(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._status(test, "skipped")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._status(test, "failed" if issubclass(err[0], test.failureException) else "error")


def run_tests():
    """Actually execute software fixtures and return a notebook-guard report."""
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(CountingContractTests)
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=_RecordingResult).run(suite)
    return {
        "claim_type": "ACTUALLY_EXECUTED_SYNTHETIC_SOFTWARE_CONTRACT_TESTS",
        "scope": "Phase6 audit-gated counting, synthetic evidence only; not actual-video identity or accuracy",
        "fixture_controls_are_product_defaults": False,
        "successful": result.wasSuccessful(), "tests_run": result.testsRun,
        "tests_passed": sum(record["status"] == "passed" for record in result.records),
        "failures": [{"id": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"id": test.id(), "traceback": trace} for test, trace in result.errors],
        "skipped": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
        "tests": result.records, "output": output.getvalue(),
    }


if __name__ == "__main__":
    summary = run_tests()
    print(json.dumps(summary, indent=2))
    sys.exit(0 if summary["successful"] else 1)
