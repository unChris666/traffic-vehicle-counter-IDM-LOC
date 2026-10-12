"""Independent, deterministic Phase 5 contract tests; no models or video decode.

All small numeric controls below are explicit synthetic-fixture values. They
are not selected product thresholds. Geometric diagnostics remain separate
from physical identity, product-category decisions and accepted count events.

Run ``python notebooks/phase_5_synthetic_tests.py`` or import ``run_tests``.
The returned JSON-serializable summary records actual test execution; a caller
must stop dependent replay when ``successful`` is false.
"""

from __future__ import annotations

import copy
import gzip
import io
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest

from phase_5_geometry_helpers import (
    Geometry,
    GeometryStateMachine,
    point_in_polygon,
    replay_cached_records,
    segment_intersection,
    signed_distance,
)


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
G3_DRAFT = REPOSITORY_ROOT / "docs/evidence/phase_5/review_drafts/G3/candidate_geometry.json"
FIXTURE_VIDEO_HASH = "a" * 64


def rectangular_geometry(*, dimensions=False):
    """Two interiors meet at x=5; the finite line covers only y=2..8."""
    return Geometry(
        p1=(5, 2),
        p2=(5, 8),
        side_a=((0, 0), (5, 0), (5, 10), (0, 10)),
        side_b=((5, 0), (10, 0), (10, 10), (5, 10)),
        width=10 if dimensions else None,
        height=10 if dimensions else None,
        geometry_id="synthetic-rectangles-finite-line",
        video_sha256=FIXTURE_VIDEO_HASH if dimensions else None,
    )


def transitions(diagnostics):
    return [item for item in diagnostics if item["type"] == "GEOMETRY_TRANSITION"]


def replay_points(points, *, geometry=None, band=0, confirmation=1, frames=None):
    machine = GeometryStateMachine(
        geometry or rectangular_geometry(),
        neutral_band_px=band,
        confirmation_observations=confirmation,
    )
    indices = list(range(len(points))) if frames is None else frames
    diagnostics = []
    for frame, point in zip(indices, points):
        diagnostics.extend(machine.update(frame, point, metadata={"fixture_frame": frame}))
    return diagnostics


class GeometryPrimitivesTests(unittest.TestCase):
    def test_concave_polygon_is_not_its_bounding_rectangle(self):
        polygon = ((0, 0), (6, 0), (6, 2), (2, 2), (2, 6), (0, 6))
        self.assertEqual(point_in_polygon((1, 4), polygon), "inside")
        self.assertEqual(point_in_polygon((4, 4), polygon), "outside")
        self.assertEqual(point_in_polygon((2, 4), polygon), "boundary")
        self.assertEqual(point_in_polygon((0, 0), polygon), "boundary")

    def test_signed_distance_is_metric_and_has_no_side_semantics(self):
        p1, p2 = (5, 2), (5, 8)
        self.assertAlmostEqual(abs(signed_distance((2, 5), p1, p2)), 3)
        self.assertAlmostEqual(signed_distance((2, 5), p1, p2), -signed_distance((2, 5), p2, p1))
        self.assertEqual(signed_distance((5, 5), p1, p2), 0)

    def test_intersection_distinguishes_proper_endpoint_touch_and_overlap(self):
        p1, p2 = (5, 2), (5, 8)
        proper = segment_intersection((2, 3), (8, 7), p1, p2)
        self.assertEqual(proper["kind"], "proper")
        self.assertEqual(proper["point"], [5, 5])
        self.assertAlmostEqual(proper["t"], 0.5)
        self.assertAlmostEqual(proper["u"], 0.5)
        self.assertEqual(segment_intersection((2, 2), (8, 2), p1, p2)["kind"], "endpoint")
        self.assertEqual(segment_intersection((2, 5), (5, 5), p1, p2)["kind"], "touch")
        self.assertEqual(segment_intersection((5, 3), (5, 7), p1, p2)["kind"], "overlap")

    def test_parallel_and_infinite_extension_are_not_finite_intersections(self):
        self.assertEqual(segment_intersection((2, 3), (2, 7), (5, 2), (5, 8))["kind"], "none")
        self.assertEqual(segment_intersection((2, 1), (8, 1), (5, 2), (5, 8))["kind"], "none")

    def test_polygon_boundaries_and_outside_are_neutral(self):
        geometry = rectangular_geometry()
        self.assertEqual(geometry.side((2, 5)), "A")
        self.assertEqual(geometry.side((8, 5)), "B")
        for point in ((5, 5), (0, 5), (8, 0), (-1, 5), (12, 5)):
            with self.subTest(point=point):
                self.assertIsNone(geometry.side(point))

    def test_invalid_line_self_intersecting_polygon_and_nonfinite_point_rejected(self):
        base = rectangular_geometry()
        invalid_a = ((0, 0), (5, 10), (5, 0), (0, 10))
        for kwargs in ({"p2": base.p1}, {"side_a": invalid_a}, {"p1": (math.nan, 2)}):
            with self.subTest(kwargs=kwargs):
                arguments = {"p1": base.p1, "p2": base.p2, "side_a": base.side_a, "side_b": base.side_b}
                arguments.update(kwargs)
                with self.assertRaises(ValueError):
                    Geometry(**arguments)

    def test_polygon_interior_overlap_rejected_even_with_different_vertex_sampling(self):
        base = rectangular_geometry()
        for side_b in (
            ((4, 0), (10, 0), (10, 10), (4, 10)),
            ((1, 1), (4, 1), (4, 9), (1, 9)),
            ((0, 0), (2, 0), (5, 0), (5, 10), (0, 10)),
        ):
            with self.subTest(side_b=side_b):
                with self.assertRaises(ValueError):
                    Geometry(base.p1, base.p2, base.side_a, side_b)

    def test_required_controls_do_not_supply_silent_threshold_defaults(self):
        geometry = rectangular_geometry()
        with self.assertRaises(TypeError):
            GeometryStateMachine(geometry)
        with self.assertRaises(TypeError):
            GeometryStateMachine(geometry, neutral_band_px=0)
        for band, confirmation in ((-1, 1), (math.nan, 1), (0, 0), (0, 1.5), (True, 1), (0, True)):
            with self.subTest(band=band, confirmation=confirmation):
                with self.assertRaises(ValueError):
                    GeometryStateMachine(geometry, neutral_band_px=band, confirmation_observations=confirmation)

    def test_g3_normalization_preserves_distinct_line_and_polygon_vertex(self):
        geometry = Geometry.from_draft(G3_DRAFT, 1280, 720)
        self.assertAlmostEqual(geometry.p1[0], 6)
        self.assertAlmostEqual(geometry.p1[1], 516.5 * 720 / 540)
        self.assertAlmostEqual(geometry.p2[0], 936.4 * 1280 / 960)
        self.assertAlmostEqual(geometry.side_a[-1][0], 936.6 * 1280 / 960)
        self.assertNotEqual(geometry.p2, geometry.side_a[-1])
        self.assertAlmostEqual(max(p[0] for p in geometry.side_b), 875 * 1280 / 960)
        self.assertGreater(geometry.p2[0], max(p[0] for p in geometry.side_b))


class CrossingStateMachineTests(unittest.TestCase):
    def test_diagonal_a_to_b_retains_measured_origin_crossing_and_arrival(self):
        diagnostics = replay_points([(2, 3), (8, 7)])
        items = transitions(diagnostics)
        self.assertEqual(len(items), 1)
        transition = items[0]
        self.assertEqual(transition["direction"], "A_TO_B")
        self.assertEqual(transition["origin_frame"], 0)
        self.assertEqual((transition["crossing_frame_start"], transition["crossing_frame_end"]), (0, 1))
        self.assertEqual(transition["crossing_point"], [5, 5])
        self.assertEqual(transition["confirmation_frame"], 1)
        self.assertFalse(transition["accepted_count_event"])
        self.assertTrue(transition["repeat_business_policy_open"])
        self.assertEqual(transition["origin_observation"]["metadata"], {"fixture_frame": 0})

    def test_diagonal_b_to_a_is_not_inferred_from_fixed_image_axes(self):
        items = transitions(replay_points([(8, 7), (2, 3)]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "B_TO_A")
        reversed_line = rectangular_geometry()
        reversed_line = Geometry(reversed_line.p2, reversed_line.p1, reversed_line.side_a, reversed_line.side_b)
        items = transitions(replay_points([(2, 3), (8, 7)], geometry=reversed_line))
        self.assertEqual(items[0]["direction"], "A_TO_B")

    def test_diagonal_configured_line_supports_both_directions(self):
        geometry = Geometry(
            (2, 2), (8, 8),
            ((0, 0), (10, 0), (10, 10)),
            ((0, 0), (10, 10), (0, 10)),
            geometry_id="synthetic-diagonal-gate",
        )
        for points, direction in (([(7, 3), (3, 7)], "A_TO_B"), ([(3, 7), (7, 3)], "B_TO_A")):
            with self.subTest(direction=direction):
                items = transitions(replay_points(points, geometry=geometry))
                self.assertEqual(len(items), 1)
                self.assertEqual(items[0]["direction"], direction)
                self.assertEqual(items[0]["crossing_point"], [5, 5])

    def test_initial_presence_and_repeated_same_side_are_not_transitions(self):
        self.assertEqual(transitions(replay_points([(8, 5), (8, 6), (7, 7)])), [])
        items = transitions(replay_points([(8, 5), (2, 5), (2, 6), (3, 7)]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "B_TO_A")

    def test_infinite_line_extension_does_not_complete_directional_transition(self):
        self.assertEqual(transitions(replay_points([(2, 1), (8, 1), (8, 1.5)])), [])

    def test_exact_line_endpoint_is_ambiguous_not_confirmed(self):
        diagnostics = replay_points([(2, 2), (8, 2), (8, 3)])
        self.assertEqual(transitions(diagnostics), [])
        self.assertTrue(any(item["type"] == "AMBIGUOUS_ENDPOINT" for item in diagnostics))

    def test_parallel_motion_and_line_touch_return_do_not_complete(self):
        for points in (
            [(2, 3), (2, 5), (2, 7)],
            [(2, 5), (5, 5), (2, 5)],
            [(2, 5), (5, 5), (5, 7), (2, 7)],
        ):
            with self.subTest(points=points):
                self.assertEqual(transitions(replay_points(points)), [])

    def test_measured_contact_then_opposite_side_is_a_real_contiguous_passage(self):
        items = transitions(replay_points([(2, 5), (5, 5), (8, 5)]))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "A_TO_B")
        self.assertEqual(items[0]["confirmation_frame"], 2)

    def test_line_contact_sliding_beyond_finite_endpoint_cannot_reuse_old_touch(self):
        # The final segment leaves the infinite extension, not the finite gate.
        diagnostics = replay_points([(2, 5), (5, 5), (5, 9), (8, 9)])
        self.assertEqual(transitions(diagnostics), [])
        self.assertTrue(any(item["type"] == "AMBIGUOUS_ENDPOINT" for item in diagnostics))

    def test_boundary_and_outside_origin_do_not_establish_crossing_eligibility(self):
        for origin in ((0, 5), (-1, 5), (5, 5)):
            with self.subTest(origin=origin):
                self.assertEqual(transitions(replay_points([origin, (8, 5)])), [])

    def test_line_passage_without_opposite_roi_arrival_is_incomplete(self):
        self.assertEqual(transitions(replay_points([(2, 5), (12, 5), (12, 6)])), [])
        self.assertEqual(transitions(replay_points([(2, 5), (8, 0)])), [])

    def test_missing_observation_cannot_interpolate_crossing_and_resets_origin(self):
        diagnostics = replay_points([(2, 5), (8, 5), (8, 6), (2, 6)], frames=[0, 2, 3, 4])
        items = transitions(diagnostics)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "B_TO_A")
        self.assertEqual(items[0]["origin_frame"], 2)
        gaps = [item for item in diagnostics if item["type"] == "AMBIGUOUS_GAP"]
        self.assertEqual(len(gaps), 1)
        self.assertFalse(gaps[0]["interpolation_used"])

    def test_prediction_cannot_supply_crossing_or_destination_confirmation(self):
        machine = GeometryStateMachine(rectangular_geometry(), neutral_band_px=0, confirmation_observations=1)
        diagnostics = machine.update(0, (2, 5))
        diagnostics += machine.update(1, (8, 5), observed=False, metadata={"synthetic_prediction": True})
        diagnostics += machine.update(2, (8, 5))
        diagnostics += machine.update(3, (8, 6))
        self.assertEqual(transitions(diagnostics), [])
        self.assertTrue(any(item["type"] == "PREDICTION_IGNORED" for item in diagnostics))

    def test_destination_confirmation_requires_consecutive_measured_arrivals(self):
        machine = GeometryStateMachine(rectangular_geometry(), neutral_band_px=0, confirmation_observations=3)
        diagnostics = []
        for frame, point in enumerate([(2, 5), (8, 5), (12, 5), (8, 5), (8, 6)]):
            diagnostics += machine.update(frame, point)
            self.assertEqual(transitions(diagnostics), [])
        diagnostics += machine.update(5, (8, 7))
        items = transitions(diagnostics)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["confirmation_frame"], 5)
        self.assertEqual([item["frame_index"] for item in items[0]["confirmation_observations"]], [3, 4, 5])

    def test_missing_arrival_discards_pending_confirmation(self):
        diagnostics = replay_points([(2, 5), (8, 5), (8, 6), (8, 7)], confirmation=3, frames=[0, 1, 3, 4])
        self.assertEqual(transitions(diagnostics), [])
        self.assertTrue(any(item["type"] == "AMBIGUOUS_GAP" for item in diagnostics))

    def test_jitter_inside_explicit_neutral_band_does_not_emit_repeated_transitions(self):
        diagnostics = replay_points([(3, 5), (4.9, 5), (5.1, 5), (4.9, 5), (5.2, 5)], band=1)
        self.assertEqual(transitions(diagnostics), [])
        points = [(3, 5), (7, 5), (5.1, 5), (4.9, 5), (5.2, 5), (7, 6)]
        items = transitions(replay_points(points, band=1))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "A_TO_B")

    def test_exact_band_edge_is_neutral_not_stable_arrival(self):
        machine = GeometryStateMachine(rectangular_geometry(), neutral_band_px=1, confirmation_observations=1)
        diagnostics = machine.update(0, (3, 5))
        diagnostics += machine.update(1, (6, 5))
        self.assertEqual(transitions(diagnostics), [])
        diagnostics += machine.update(2, (7, 5))
        self.assertEqual(len(transitions(diagnostics)), 1)

    def test_true_return_remains_diagnostic_with_business_policy_open(self):
        points = [(2, 5), (8, 5), (8, 6), (2, 6), (2, 7), (8, 7)]
        items = transitions(replay_points(points))
        self.assertEqual([item["direction"] for item in items], ["A_TO_B", "B_TO_A", "A_TO_B"])
        self.assertTrue(all(item["accepted_count_event"] is False for item in items))
        self.assertTrue(all(item["repeat_business_policy_open"] is True for item in items))

    def test_nonmonotonic_track_frames_are_rejected(self):
        machine = GeometryStateMachine(rectangular_geometry(), neutral_band_px=0, confirmation_observations=1)
        machine.update(3, (2, 5))
        for frame in (3, 2, -1, True):
            with self.subTest(frame=frame):
                with self.assertRaises(ValueError):
                    machine.update(frame, (8, 5))

    def test_g3_crossing_line_inside_a_requires_later_b_arrival(self):
        geometry = Geometry.from_draft(G3_DRAFT, 960, 540)
        x = 500
        line_y = 516.5 + (305.4 - 516.5) * (x - 4.5) / (936.4 - 4.5)
        shared_edge_y = 516.5 + (305.8 - 516.5) * (x - 4.5) / (936.6 - 4.5)
        strip = (x, (line_y + shared_edge_y) / 2)
        self.assertLess(line_y, shared_edge_y)
        self.assertEqual(geometry.side(strip), "A")
        self.assertGreater(signed_distance(strip, geometry.p1, geometry.p2), 0)
        machine = GeometryStateMachine(geometry, neutral_band_px=0, confirmation_observations=1)
        diagnostics = machine.update(0, (x, line_y - 10))
        diagnostics += machine.update(1, strip)
        self.assertEqual(transitions(diagnostics), [])
        diagnostics += machine.update(2, (x, shared_edge_y + 10))
        self.assertEqual([item["direction"] for item in transitions(diagnostics)], ["A_TO_B"])
        self.assertEqual(transitions(replay_points([strip, (x, shared_edge_y + 10)], geometry=geometry)), [])

    def test_g3_origin_in_offset_strip_can_later_cross_from_deeper_a_to_b(self):
        geometry = Geometry.from_draft(G3_DRAFT, 960, 540)
        x = 500
        line_y = 516.5 + (305.4 - 516.5) * (x - 4.5) / (936.4 - 4.5)
        shared_edge_y = 516.5 + (305.8 - 516.5) * (x - 4.5) / (936.6 - 4.5)
        strip = (x, (line_y + shared_edge_y) / 2)
        deep_a = (x, line_y - 10)
        side_b = (x, shared_edge_y + 10)
        self.assertEqual([geometry.side(point) for point in (strip, deep_a, side_b)], ["A", "A", "B"])
        self.assertGreater(signed_distance(strip, geometry.p1, geometry.p2), 0)
        self.assertLess(signed_distance(deep_a, geometry.p1, geometry.p2), 0)
        items = transitions(replay_points([strip, deep_a, side_b], geometry=geometry))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "A_TO_B")
        self.assertEqual((items[0]["crossing_frame_start"], items[0]["crossing_frame_end"]), (1, 2))

    def test_g3_continued_a_strip_after_line_passage_preserves_pending_arrival(self):
        geometry = Geometry.from_draft(G3_DRAFT, 960, 540)
        x = 500
        line_y = 516.5 + (305.4 - 516.5) * (x - 4.5) / (936.4 - 4.5)
        shared_edge_y = 516.5 + (305.8 - 516.5) * (x - 4.5) / (936.6 - 4.5)
        strip = (x, (line_y + shared_edge_y) / 2)
        points = [(x, line_y - 10), strip, strip, (x, shared_edge_y + 10)]
        items = transitions(replay_points(points, geometry=geometry))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["confirmation_frame"], 3)
        self.assertEqual((items[0]["crossing_frame_start"], items[0]["crossing_frame_end"]), (0, 1))

    def test_g3_return_to_origin_roi_discards_unconfirmed_stale_crossing(self):
        geometry = Geometry.from_draft(G3_DRAFT, 960, 540)
        x = 500
        line_y = 516.5 + (305.4 - 516.5) * (x - 4.5) / (936.4 - 4.5)
        shared_edge_y = 516.5 + (305.8 - 516.5) * (x - 4.5) / (936.6 - 4.5)
        strip = (x, (line_y + shared_edge_y) / 2)
        deep_a, b = (x, line_y - 10), (x, shared_edge_y + 10)
        # B arrival has only one measurement before returning to the A strip.
        # A strip->B stays on one line-sign, so it cannot reuse the old passage.
        points = [deep_a, b, strip, b, b]
        self.assertEqual(transitions(replay_points(points, geometry=geometry, confirmation=2)), [])
        points.extend([deep_a, b, b])
        items = transitions(replay_points(points, geometry=geometry, confirmation=2))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["confirmation_frame"], 7)
        self.assertEqual((items[0]["crossing_frame_start"], items[0]["crossing_frame_end"]), (5, 6))


class RetainedTrackBoundaryTests(unittest.TestCase):
    """Synthetic serialized input verifies the measured-track boundary only."""

    def _records(self):
        records = []
        for frame, box, class_id, class_name in (
            (0, [1.5, 1, 2.5, 5], 0, "fixture-person"),
            (1, [7.5, 1, 8.5, 5], 3, "fixture-motorcycle"),
        ):
            detection = {"bbox_xyxy_pixels": box, "class_id": class_id, "class_name": class_name, "confidence": 0.95}
            observation = {
                "track_id": 17, "frame_index": frame, "original_detection_index": 1,
                "raw_bbox": box, "bbox": [7.5, 1, 8.5, 5] if frame == 0 else [1.5, 1, 2.5, 5],
                "center": [2 if frame == 0 else 8, 3],
                "class_id": class_id, "class_name": class_name, "confidence": 0.95,
                "emitted": True, "is_activated": True,
                "measurement_provenance": "retained_phase_2_detection",
            }
            records.append({
                "video_sha256": FIXTURE_VIDEO_HASH, "parent_run_id": "synthetic-fixture",
                "frame_index": frame, "width": 10, "height": 10, "variant": "reid_on",
                "timestamp_estimate_from_index_fps_seconds": frame / 30,
                "raw_detections": [{"bbox_xyxy_pixels": [3, 1, 4, 2], "class_id": 99, "class_name": "fixture-other", "confidence": 0.4}, detection],
                "emitted_tracks": [observation],
            })
        return records

    def _replay(self, records):
        with tempfile.TemporaryDirectory(prefix="phase5-synthetic-") as directory:
            path = Path(directory) / "track_records.jsonl.gz"
            with gzip.open(path, "wt", encoding="utf-8") as target:
                for record in records:
                    target.write(json.dumps(record) + "\n")
            return replay_cached_records(path, rectangular_geometry(dimensions=True), neutral_band_px=0, confirmation_observations=1)

    def test_raw_bbox_bc_and_source_links_override_filtered_box_and_stored_center(self):
        result = self._replay(self._records())
        items = transitions(result["diagnostics"])
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["direction"], "A_TO_B")
        self.assertEqual(items[0]["origin_point"], [2, 5])
        self.assertEqual(items[0]["confirmation_point"], [8, 5])
        self.assertEqual(items[0]["track_id"], 17)
        self.assertEqual(items[0]["metadata"]["original_detection_index"], 1)
        self.assertEqual(items[0]["origin_observation"]["metadata"]["class_name"], "fixture-person")
        self.assertEqual(items[0]["metadata"]["class_name"], "fixture-motorcycle")
        self.assertFalse(items[0]["accepted_count_event"])
        self.assertFalse(result["report"]["accepted_count_events_emitted"])
        self.assertFalse(result["report"]["detector_tracker_encoder_rerun"])
        self.assertEqual(result["report"]["frames_processed"], 2)

    def test_bbox_overlap_alone_does_not_substitute_for_anchor_crossing(self):
        records = self._records()
        for record, box in zip(records, ([1, 1, 6, 5], [2, 1, 7, 5])):
            record["raw_detections"][1]["bbox_xyxy_pixels"] = box
            record["emitted_tracks"][0]["raw_bbox"] = box
        self.assertEqual(transitions(self._replay(records)["diagnostics"]), [])

    def test_nonemitted_unconfirmed_and_lifecycle_predictions_are_ignored(self):
        records = self._records()
        predicted = copy.deepcopy(records[1]["emitted_tracks"][0])
        predicted["emitted"] = False
        records[1]["emitted_tracks"] = []
        records[1]["assigned_observations_including_unconfirmed"] = [predicted]
        records[1]["lifecycle_snapshots"] = [{"track_id": 17, "bbox": [7.5, 1, 8.5, 5], "is_prediction": True}]
        self.assertEqual(transitions(self._replay(records)["diagnostics"]), [])

    def test_missing_measured_provenance_and_broken_source_link_are_rejected(self):
        for change in ("provenance", "bbox", "class", "index"):
            records = self._records()
            observation = records[1]["emitted_tracks"][0]
            if change == "provenance":
                observation["measurement_provenance"] = "synthetic_prediction"
            elif change == "bbox":
                observation["raw_bbox"] = [7, 1, 9, 5]
            elif change == "class":
                observation["class_id"] = 777
            else:
                observation["original_detection_index"] = 4
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self._replay(records)

    def test_native_dimensions_video_identity_and_frame_alignment_are_rejected(self):
        for change in ("dimensions", "video", "frame", "order", "duplicate_id"):
            records = self._records()
            if change == "dimensions":
                records[1]["width"] = 20
            elif change == "video":
                records[1]["video_sha256"] = "b" * 64
            elif change == "frame":
                records[1]["emitted_tracks"][0]["frame_index"] = 7
            elif change == "order":
                records.reverse()
            else:
                records[1]["emitted_tracks"].append(copy.deepcopy(records[1]["emitted_tracks"][0]))
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    self._replay(records)

    def test_cache_variant_and_parent_run_identity_cannot_change_between_frames(self):
        for key, value in (("variant", "reid_off"), ("parent_run_id", "different-synthetic-run")):
            records = self._records()
            records[1][key] = value
            with self.subTest(key=key):
                with self.assertRaises(ValueError):
                    self._replay(records)

    def test_nonfinite_measured_confidence_is_rejected(self):
        for confidence in (math.nan, math.inf, -math.inf):
            records = self._records()
            records[1]["raw_detections"][1]["confidence"] = confidence
            records[1]["emitted_tracks"][0]["confidence"] = confidence
            with self.subTest(confidence=confidence):
                with self.assertRaises(ValueError):
                    self._replay(records)

    def test_one_source_detection_cannot_emit_two_tracks_but_distinct_sources_may_overlap(self):
        records = self._records()
        second = copy.deepcopy(records[1]["emitted_tracks"][0])
        second["track_id"] = 18
        records[1]["emitted_tracks"].append(second)
        with self.assertRaises(ValueError):
            self._replay(records)

        # A separate detection with identical pixels/class is still separate
        # retained evidence. Rejecting duplicate source links is not a policy
        # for deciding whether overlapping IDs represent one physical object.
        records[1]["raw_detections"].append(copy.deepcopy(records[1]["raw_detections"][1]))
        second["original_detection_index"] = 2
        result = self._replay(records)
        self.assertEqual(result["report"]["software_track_ids"], 2)
        self.assertTrue(any(item["track_id"] == 18 for item in result["diagnostics"]))
        self.assertTrue(all(item["accepted_count_event"] is False for item in result["diagnostics"]))


class _RecordingResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records = []

    def startTest(self, test):
        super().startTest(test)
        self.records.append({"id": test.id(), "status": "running"})

    def _set_status(self, test, status, **details):
        record = next(record for record in reversed(self.records) if record["id"] == test.id())
        record.update(status=status, **details)

    def addSuccess(self, test):
        super().addSuccess(test)
        self._set_status(test, "passed")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._set_status(test, "failed")

    def addError(self, test, err):
        super().addError(test, err)
        self._set_status(test, "error")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._set_status(test, "skipped", reason=reason)

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self._set_status(test, "failed" if issubclass(err[0], test.failureException) else "error")


def run_tests():
    """Execute the suite and return actual evidence, without inventing results."""
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    for test_case in (GeometryPrimitivesTests, CrossingStateMachineTests, RetainedTrackBoundaryTests):
        suite.addTests(loader.loadTestsFromTestCase(test_case))
    output = io.StringIO()
    result = unittest.TextTestRunner(stream=output, verbosity=2, resultclass=_RecordingResult).run(suite)
    return {
        "claim_type": "ACTUALLY_EXECUTED_SYNTHETIC_SOFTWARE_CONTRACT_TESTS",
        "scope": "Phase5 geometry and retained-measurement boundary; not physical identity, category counting or model accuracy",
        "fixture_controls_are_product_defaults": False,
        "successful": result.wasSuccessful(),
        "tests_run": result.testsRun,
        "tests_passed": sum(record["status"] == "passed" for record in result.records),
        "failures": [{"id": test.id(), "traceback": trace} for test, trace in result.failures],
        "errors": [{"id": test.id(), "traceback": trace} for test, trace in result.errors],
        "skipped": [{"id": test.id(), "reason": reason} for test, reason in result.skipped],
        "tests": result.records,
        "output": output.getvalue(),
    }


if __name__ == "__main__":
    summary = run_tests()
    print(json.dumps(summary, indent=2))
    sys.exit(0 if summary["successful"] else 1)
