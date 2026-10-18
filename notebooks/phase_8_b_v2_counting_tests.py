"""Synthetic software contracts for B v2; these are not video accuracy tests."""

from copy import deepcopy
import math
import unittest

from phase_5_geometry_helpers import Geometry
from phase_8_b_v2_counting import finite_band, replay_frames


GEOMETRY = Geometry((10, 50), (90, 50),
                    ((0, 0), (100, 0), (100, 40), (0, 40)),
                    ((0, 60), (100, 60), (100, 100), (0, 100)),
                    100, 100, "synthetic-horizontal")
SOURCE = {"video_sha256": "a" * 64, "records_sha256": "b" * 64,
          "geometry_sha256": "c" * 64, "width": 100, "height": 100}
POLICY = {"line_margin_half_width_px": 5, "timeout_frames": 60,
          "timeout_clock": "last_observed_origin", "category_policy": "band_majority_ties_pending"}


def observation(y, *, x=50, track=1, category="motorcycle", detection=0, unit=None):
    result = {"track_id": track, "class_name": category, "raw_bbox": [x - 2, y - 4, x + 2, y],
              "original_detection_index": detection, "observed": True, "emitted": True}
    if unit is not None:
        result["unit_id"] = unit
    return result


def frames(samples, *, end=None):
    """samples maps actual source frame index to observations or a single y."""
    end = max(samples) if end is None else end
    result = []
    for frame in range(end + 1):
        value = samples.get(frame, [])
        if isinstance(value, (int, float)):
            value = [observation(value)]
        result.append({"frame_index": frame, "observations": value})
    return result


def replay(samples, *, end=None, policy=None, geometry=GEOMETRY, source=None):
    return replay_frames(frames(samples, end=end), geometry, source_identity=source or SOURCE,
                         policy=policy or POLICY)


class Bv2SyntheticContracts(unittest.TestCase):
    def test_measured_line_margin_and_vehicle_anchor(self):
        result = replay({0: 20, 1: 35, 2: 47, 3: 52, 4: 65})
        self.assertEqual(result["aggregate"]["total"], 1)
        event = result["events"][0]
        self.assertEqual(event["route"], "LINE_MARGIN")
        self.assertEqual(event["direction"], "A_TO_B")
        self.assertTrue(event["evidence"]["measured_crossing"])
        self.assertTrue(event["evidence"]["band_observed"])
        self.assertEqual(event["evidence"]["anchor"], "raw_vehicle_bbox_bottom_center")
        for ref in event["evidence"]["source_refs"]:
            self.assertEqual(ref["point"], [(ref["raw_bbox"][0] + ref["raw_bbox"][2]) / 2,
                                           ref["raw_bbox"][3]])

    def test_reverse_direction(self):
        result = replay({0: 80, 1: 65, 2: 52, 3: 47, 4: 35})
        self.assertEqual(result["events"][0]["direction"], "B_TO_A")

    def test_no_sample_in_band_consecutive_measured_jump(self):
        event = replay({0: 30, 1: 70})["events"][0]
        self.assertTrue(event["evidence"]["measured_crossing"])
        self.assertFalse(event["evidence"]["band_observed"])
        self.assertEqual(event["evidence"]["category_basis"]["policy"], "matching_observed_endpoints")

    def test_touch_then_return_does_not_count(self):
        result = replay({0: 20, 1: 48, 2: 50, 3: 48, 4: 30}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_exact_zero_contact_bracketed_by_opposite_sides_is_measured(self):
        event = replay({0: 20, 1: 50, 2: 50, 3: 70})["events"][0]
        self.assertTrue(event["evidence"]["measured_crossing"])
        self.assertEqual(event["evidence"]["crossing_pairs"][0]["proof"],
                         "opposite_sides_bracket_contiguous_zero_contact")

    def test_stale_touch_cannot_validate_crossing_of_line_extension(self):
        result = replay({0: [observation(30)], 1: [observation(50)],
                         2: [observation(44)], 3: [observation(44, x=5)],
                         4: [observation(70, x=5)]}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_stale_crossing_cannot_validate_later_endpoint_bypass(self):
        result = replay({0: [observation(30)], 1: [observation(52)],
                         2: [observation(44)], 3: [observation(44, x=5)],
                         4: [observation(70, x=5)]}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_reverse_crossing_inside_band_invalidates_earlier_forward_pair(self):
        result = replay({0: [observation(30)], 1: [observation(48)],
                         2: [observation(52)], 3: [observation(48)],
                         4: [observation(48, x=5)], 5: [observation(70, x=5)]}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_start_in_band_is_not_initial_presence_count(self):
        result = replay({0: 48, 1: 52, 2: 70})
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_line_endpoint_crossing_is_not_measured_crossing(self):
        result = replay({0: [observation(30, x=10)], 1: [observation(70, x=10)]}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertIn("NO_VALID_FINITE_LINE_OR_OCCLUSION_EVIDENCE", result["decisions"][0]["reasons"])

    def test_line_extension_crossing_is_not_finite_crossing(self):
        result = replay({0: [observation(30, x=5)], 1: [observation(70, x=5)]}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_finite_band_flat_caps_and_half_width(self):
        self.assertTrue(finite_band((50, 55), GEOMETRY, 5)["inside"])
        self.assertFalse(finite_band((50, 55.01), GEOMETRY, 5)["inside"])
        self.assertFalse(finite_band((9.9, 50), GEOMETRY, 5)["inside"])
        self.assertFalse(finite_band((90.1, 50), GEOMETRY, 5)["inside"])

    def test_gap_without_band_goes_to_polygon_route(self):
        result = replay({0: 20, 1: 35, 5: 70})
        event = result["events"][0]
        self.assertEqual(event["route"], "OCCLUSION_DIFF_POLYGON")
        self.assertFalse(event["evidence"]["measured_crossing"])
        self.assertFalse(event["evidence"]["band_observed"])
        self.assertEqual(event["evidence"]["gaps"][0]["missing_source_frames"], 3)

    def test_gap_after_band_has_line_route_priority_but_is_inferred(self):
        event = replay({0: 20, 1: 35, 2: 47, 8: 70})["events"][0]
        self.assertEqual(event["route"], "LINE_MARGIN")
        self.assertFalse(event["evidence"]["measured_crossing"])
        self.assertTrue(event["evidence"]["band_observed"])

    def test_gap_after_line_contact_before_confirmation_is_explicitly_inferred(self):
        event = replay({0: 20, 1: 47, 2: 52, 8: 70})["events"][0]
        self.assertEqual(event["route"], "LINE_MARGIN")
        self.assertFalse(event["evidence"]["measured_crossing"])

    def test_gap_far_before_complete_line_observations_does_not_block_measured_crossing(self):
        event = replay({0: 20, 5: 35, 6: 47, 7: 52, 8: 70})["events"][0]
        self.assertTrue(event["evidence"]["measured_crossing"])

    def test_different_raw_id_not_guessed_same_vehicle(self):
        result = replay({0: [observation(20, track=1)], 1: [observation(35, track=1)],
                         5: [observation(70, track=2)]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["report"]["observed_units"], 2)

    def test_occlusion_category_must_match(self):
        result = replay({0: 20, 1: 35, 5: [observation(70, category="car")]}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_destination_seen_inside_band_still_prevents_no_destination_timeout(self):
        # Deliberately legal polygons can reach into the margin: entering B is
        # an observation even though that alone does not complete the crossing.
        geometry = Geometry((10, 50), (90, 50), GEOMETRY.side_a,
                            ((0, 51), (100, 51), (100, 100), (0, 100)), 100, 100)
        result = replay({0: 20, 1: 35, 2: 52}, end=100, geometry=geometry)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_category_priority_is_in_band_not_episode(self):
        event = replay({0: [observation(20, category="truck")],
                        1: [observation(35, category="truck")],
                        2: [observation(47, category="car")],
                        3: [observation(52, category="car")],
                        4: [observation(70, category="truck")]})["events"][0]
        self.assertEqual(event["category"], "car")
        self.assertEqual(event["evidence"]["category_basis"]["votes"], {"car": 2})

    def test_band_category_tie_stays_pending(self):
        result = replay({0: 20, 1: [observation(47, category="car")],
                         2: [observation(52, category="truck")], 3: 70})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["CATEGORY_TIE_IN_BAND"])

    def test_unsupported_bus_taxonomy_stays_pending(self):
        result = replay({0: [observation(20, category="bus")], 1: [observation(70, category="bus")]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["UNSUPPORTED_CATEGORY_TAXONOMY_OPEN"])

    def test_timeout_is_exactly_sixty_frames_from_last_origin(self):
        result = replay({0: 20, 10: 35}, end=70)
        event = result["events"][0]
        self.assertEqual(event["activation_frame"], 70)
        self.assertEqual(event["route"], "ESTIMATED_TIMEOUT")
        self.assertFalse(event["evidence"]["measured_crossing"])
        self.assertFalse(event["evidence"]["id_change_proven"])
        self.assertTrue(event["evidence"]["direction_assumed"])
        self.assertEqual(result["passage_log"][-1]["requested_label"], "CHANGE_ID")

    def test_visible_stationary_origin_resets_clock(self):
        result = replay({**{frame: 35 for frame in range(1, 101)}, 0: 20}, end=159)
        self.assertEqual(result["aggregate"]["total"], 0)
        result = replay({**{frame: 35 for frame in range(1, 101)}, 0: 20}, end=160)
        self.assertEqual(result["events"][0]["activation_frame"], 160)

    def test_no_approach_direction_no_timeout_count(self):
        self.assertEqual(replay({0: 20}, end=100)["aggregate"]["total"], 0)
        self.assertEqual(replay({0: 35, 1: 20}, end=100)["aggregate"]["total"], 0)

    def test_u_turn_before_band_cancels_timeout_eligibility(self):
        result = replay({0: 20, 1: 35, 2: 25}, end=100)
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_eof_not_padded_to_fire_timeout(self):
        result = replay({0: 20, 10: 35}, end=69)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["report"]["frame_count"], 70)
        self.assertEqual(result["report"]["post_eof_frames_generated"], 0)

    def test_timeout_then_destination_upgrades_same_event(self):
        result = replay({0: 20, 1: 35, 70: 70}, end=70)
        self.assertEqual(result["aggregate"]["total"], 1)
        event = result["events"][0]
        self.assertEqual(event["activation_frame"], 61)
        self.assertEqual(event["decision_frame"], 70)
        self.assertEqual(event["route"], "OCCLUSION_DIFF_POLYGON")
        self.assertEqual([row["count_delta"] for row in result["passage_log"]], [1, 0])
        self.assertEqual(len({row["event_id"] for row in result["passage_log"]}), 1)

    def test_timeout_then_measured_u_turn_voids_count_with_audit(self):
        result = replay({0: 20, 1: 35, 70: 25}, end=70)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(len(result["cancelled_events"]), 1)
        self.assertEqual([row["count_delta"] for row in result["passage_log"]], [1, -1])

    def test_timeout_later_band_category_replaces_origin_category_without_plus_one(self):
        result = replay({0: [observation(20, category="truck")],
                         1: [observation(35, category="truck")],
                         70: [observation(47, category="car")],
                         71: [observation(52, category="car")],
                         72: [observation(70, category="truck")]})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["events"][0]["category"], "car")
        self.assertEqual(sum(row["count_delta"] for row in result["passage_log"]), 1)

    def test_timeout_new_identity_conflict_cancels_estimate(self):
        later = observation(47)
        later["identity_conflict"] = True
        result = replay({0: 20, 1: 35, 70: [later]}, end=70)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(len(result["cancelled_events"]), 1)

    def test_timeout_new_band_tie_cancels_estimate_until_resolved(self):
        result = replay({0: 20, 1: 35, 70: [observation(47, category="car")],
                         71: [observation(52, category="truck")]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertTrue(any(row["status"] == "cancelled" for row in result["passage_log"]))

    def test_real_return_counts_two_distinct_passages(self):
        result = replay({0: 20, 1: 47, 2: 52, 3: 70, 4: 52, 5: 47, 6: 30})
        self.assertEqual(result["aggregate"]["total"], 2)
        self.assertEqual(result["aggregate"]["by_direction"], {"A_TO_B": 1, "B_TO_A": 1})
        self.assertEqual(len({event["passage_id"] for event in result["events"]}), 2)

    def test_overlapping_distinct_units_still_two_vehicles(self):
        result = replay({frame: [observation(y, track=1), observation(y, track=2, detection=1)]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 2)

    def test_actual_unresolved_duplicate_evidence_blocks_local_passage(self):
        records = frames({0: 20, 1: 47, 2: 52, 3: 70})
        records[1]["observations"][0]["identity_conflict"] = True
        result = replay_frames(records, GEOMETRY, source_identity=SOURCE, policy=POLICY)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE"])

    def test_unresolved_duplicate_evidence_does_not_override_timeout_reliability(self):
        records = frames({0: 20, 1: 35}, end=70)
        records[1]["observations"][0]["identity_conflict"] = True
        result = replay_frames(records, GEOMETRY, source_identity=SOURCE, policy=POLICY)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE"])

    def test_supported_known_unit_duplicates_share_one_raw_anchor(self):
        result = replay({frame: [observation(y, track=1, unit="physical-1"),
                                observation(y + 1, track=2, unit="physical-1", detection=1)]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertTrue(all(ref["track_id"] == 1 for ref in result["events"][0]["evidence"]["source_refs"]))

    def test_person_component_does_not_count(self):
        result = replay({frame: [observation(y, track=1, unit="motorcycle-1"),
                                observation(y, track=2, category="person", detection=1, unit="motorcycle-1")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["report"]["counters"]["ignored_nonvehicle_observations"], 4)

    def test_raw_track_handoff_never_splices_measured_trajectory(self):
        result = replay({0: [observation(20, track=1, unit="known-unit")],
                         1: [observation(47, track=1, unit="known-unit")],
                         2: [observation(70, track=2, unit="known-unit")]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["RAW_TRACK_CHANGED_DURING_PASSAGE"])

    def test_deterministic_without_mutating_input(self):
        records = frames({0: 20, 1: 47, 2: 52, 3: 70})
        before = deepcopy((records, SOURCE, POLICY))
        first = replay_frames(records, GEOMETRY, source_identity=SOURCE, policy=POLICY)
        second = replay_frames(records, GEOMETRY, source_identity=SOURCE, policy=POLICY)
        self.assertEqual(first, second)
        self.assertEqual(before, (records, SOURCE, POLICY))

    def test_namespace_binds_effective_geometry(self):
        changed = Geometry((9, 50), (91, 50), GEOMETRY.side_a, GEOMETRY.side_b, 100, 100)
        first = replay({0: 20, 1: 70})
        second = replay({0: 20, 1: 70}, geometry=changed)
        self.assertNotEqual(first["events"][0]["event_id"], second["events"][0]["event_id"])

    def test_validation_rejects_predictions_and_broken_measurements(self):
        for modification in ({"observed": False}, {"emitted": False},
                             {"original_detection_index": -1}, {"raw_bbox": [0, 0, 0, 2]},
                             {"raw_bbox": [0, 0, math.nan, 2]}):
            with self.subTest(modification=modification):
                bad = observation(20)
                bad.update(modification)
                with self.assertRaises(ValueError):
                    replay({0: [bad]})

    def test_validation_rejects_noncontiguous_frames_and_duplicate_links(self):
        with self.assertRaisesRegex(ValueError, "contiguous"):
            replay_frames([{"frame_index": 0, "observations": []},
                           {"frame_index": 2, "observations": []}], GEOMETRY,
                          source_identity=SOURCE, policy=POLICY)
        with self.assertRaisesRegex(ValueError, "detection link"):
            replay({0: [observation(20), observation(30, track=2)]})

    def test_validation_rejects_invalid_policy_source_and_dimensions(self):
        for change in ({"line_margin_half_width_px": -1}, {"timeout_frames": 0},
                       {"timeout_clock": "entry"}, {"category_policy": "last_frame"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replay({0: 20}, policy={**POLICY, **change})
        for change in ({"video_sha256": None}, {"records_sha256": "FAKE"}, {"width": 640}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replay({0: 20}, source={**SOURCE, **change})

    def test_empty_input_is_zero_not_a_video_result_claim(self):
        result = replay_frames([], GEOMETRY, source_identity=SOURCE, policy=POLICY)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertIsNone(result["report"]["last_frame_index"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
