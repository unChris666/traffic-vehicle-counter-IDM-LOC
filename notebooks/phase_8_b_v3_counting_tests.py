"""Synthetic software contracts for B v3; these are not video accuracy tests."""

from copy import deepcopy
import math
import unittest

from phase_5_geometry_helpers import Geometry
from phase_8_b_v3_counting import finite_band, passage_display_id, replay_frames


GEOMETRY = Geometry((10, 50), (90, 50),
                    ((0, 0), (100, 0), (100, 40), (0, 40)),
                    ((0, 60), (100, 60), (100, 100), (0, 100)),
                    100, 100, "synthetic-horizontal")
SOURCE = {"video_sha256": "a" * 64, "records_sha256": "b" * 64,
          "geometry_sha256": "c" * 64, "width": 100, "height": 100}
POLICY = {"line_margin_half_width_px": 5, "timeout_frames": 60,
          "timeout_clock": "last_observed_origin", "category_policy": "band_majority_ties_pending"}


def observation(y, *, x=50, track=1, category="motorcycle", detection=0, unit=None, **metadata):
    result = {"track_id": track, "class_name": category, "raw_bbox": [x - 2, y - 4, x + 2, y],
              "original_detection_index": detection, "observed": True, "emitted": True}
    if unit is not None:
        result["unit_id"] = unit
    result.update(metadata)
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


class Bv3SyntheticContracts(unittest.TestCase):
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
        result = replay({frame: [observation(y, track=1, unit="physical-1", association_verified=True, association_id="support-1"),
                                observation(y + 1, track=2, unit="physical-1", detection=1, association_verified=True, association_id="support-1")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertTrue(all(ref["track_id"] == 1 for ref in result["events"][0]["evidence"]["source_refs"]))

    def test_person_component_does_not_count(self):
        result = replay({frame: [observation(y, track=1, unit="motorcycle-1"),
                                observation(y, track=2, category="person", detection=1, unit="motorcycle-1", role="rider")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["report"]["counters"]["rider_observations_excluded_plus_zero"], 4)

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


class Bv3ReviewedIdentityContracts(unittest.TestCase):
    def linked(self, y, track, *, category="motorcycle", unit="reviewed-unit", association="review-1", **metadata):
        return observation(y, track=track, category=category, unit=unit,
                           association_verified=True, association_id=association, **metadata)

    def test_reviewed_73_93_reconciles_one_passage_and_preserves_raw_category(self):
        result = replay({
            0: [self.linked(20, 73, category="car", resolved_class_name="car", review_ref="user-73-93")],
            1: [self.linked(47, 73, category="car", resolved_class_name="car", review_ref="user-73-93"),
                self.linked(48, 93, category="truck", resolved_class_name="car", detection=1, review_ref="user-73-93")],
            3: [self.linked(70, 93, category="truck", resolved_class_name="car", review_ref="user-73-93")]})
        self.assertEqual(result["aggregate"]["total"], 1)
        event = result["events"][0]
        self.assertEqual(event["category"], "car")
        self.assertFalse(event["evidence"]["measured_crossing"])
        self.assertEqual(sum(row["count_delta"] for row in result["passage_log"]), 1)
        last_ref = event["evidence"]["source_refs"][-1]
        self.assertEqual((last_ref["track_id"], last_ref["class_name"], last_ref["resolved_class_name"]),
                         (93, "truck", "car"))
        self.assertEqual(last_ref["review_ref"], "user-73-93")
        self.assertTrue(event["evidence"]["reviewed_category_attribution"])

    def test_reviewed_identity_alone_does_not_resolve_category_conflict(self):
        result = replay({0: [self.linked(20, 73, category="car")],
                         1: [self.linked(47, 73, category="car")],
                         2: [self.linked(52, 93, category="truck")],
                         3: [self.linked(70, 93, category="truck")]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["CATEGORY_TIE_IN_BAND"])

    def test_verified_band_handoff_does_not_invent_measured_crossing(self):
        event = replay({0: [self.linked(20, 73)], 1: [self.linked(47, 73)],
                        2: [self.linked(70, 93)]})["events"][0]
        self.assertEqual(event["route"], "LINE_MARGIN")
        self.assertFalse(event["evidence"]["measured_crossing"])
        self.assertTrue(event["evidence"]["raw_track_changes"][0]["association_verified"])

    def test_handoff_before_later_contiguous_crossing_allows_actual_measured_pair(self):
        event = replay({0: [self.linked(20, 73)], 1: [self.linked(35, 93)],
                        2: [self.linked(47, 93)], 3: [self.linked(52, 93)],
                        4: [self.linked(70, 93)]})["events"][0]
        self.assertTrue(event["evidence"]["measured_crossing"])
        pair = event["evidence"]["crossing_pairs"][-1]
        self.assertEqual({pair["first"]["track_id"], pair["second"]["track_id"]}, {93})

    def test_verified_occlusion_handoff_is_one_inferred_passage(self):
        event = replay({0: [self.linked(20, 73)], 1: [self.linked(35, 73)],
                        5: [self.linked(70, 93)]})["events"][0]
        self.assertEqual(event["route"], "OCCLUSION_DIFF_POLYGON")
        self.assertFalse(event["evidence"]["measured_crossing"])

    def test_verified_timeout_handoff_upgrades_without_second_increment(self):
        result = replay({0: [self.linked(20, 73)], 1: [self.linked(35, 73)],
                         70: [self.linked(70, 93)]})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual([row["count_delta"] for row in result["passage_log"]], [1, 0])
        self.assertEqual(len({row["event_id"] for row in result["passage_log"]}), 1)

    def test_different_verified_associations_do_not_prove_same_identity(self):
        result = replay({0: [self.linked(20, 73)], 1: [self.linked(47, 73)],
                         3: [self.linked(70, 93, association="different-review")]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertIn("RAW_TRACK_CHANGED_DURING_PASSAGE", result["decisions"][0]["reasons"])

    def test_unverified_handoff_earlier_in_passage_not_repaired_by_later_crossing(self):
        result = replay({0: [observation(20, track=73, unit="u")],
                         1: [observation(35, track=93, unit="u")],
                         2: [observation(47, track=93, unit="u")],
                         3: [observation(52, track=93, unit="u")],
                         4: [observation(70, track=93, unit="u")]})
        self.assertEqual(result["aggregate"]["total"], 0)

    def test_unverified_matching_unit_name_is_not_duplicate_support(self):
        result = replay({frame: [observation(y, track=73, unit="u"),
                                observation(y, track=93, detection=1, unit="u")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertIn("UNRESOLVED_DUPLICATE_IDENTITY_IN_PASSAGE", result["decisions"][0]["reasons"])

    def test_4149_truck_motorcycle_split_has_independent_geometry_and_timer(self):
        samples = {0: [observation(20, track=4149, category="truck", unit="raw4149", episode_id="reviewed-truck")],
                   1: [observation(47, track=4149, category="truck", unit="raw4149", episode_id="reviewed-truck")],
                   2: [observation(52, track=4149, category="truck", unit="raw4149", episode_id="reviewed-truck")],
                   3: [observation(70, track=4149, category="truck", unit="raw4149", episode_id="reviewed-truck")],
                   10: [observation(20, track=4149, category="motorcycle", unit="raw4149", episode_id="reviewed-motorcycle")]}
        result = replay(samples, end=100)
        self.assertEqual(result["aggregate"]["by_category"], {"truck": 1})
        self.assertEqual(result["report"]["observed_units"], 2)
        self.assertEqual(result["events"][0]["episode_id"], "reviewed-truck")
        self.assertEqual(result["events"][0]["display_id"], "T2000")
        self.assertTrue(all(ref["class_name"] == "truck" for ref in result["events"][0]["evidence"]["source_refs"]))

    def test_2473_to_2507_after_crossing_with_2471_rider_is_one_motorcycle(self):
        samples = {}
        for frame, y in enumerate((80, 52, 47, 30, 20)):
            track = 2473 if frame < 4 else 2507
            samples[frame] = [self.linked(y, track, unit="reviewed-motorcycle", episode_id="motor-episode"),
                              observation(y, track=2471, category="person", detection=1, role="rider",
                                          unit="reviewed-motorcycle", episode_id="rider-episode")]
        result = replay(samples, end=70)
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["events"][0]["direction"], "B_TO_A")
        self.assertEqual(result["events"][0]["display_id"], "M1000")
        self.assertEqual(result["report"]["counters"]["rider_observations_excluded_plus_zero"], 5)
        self.assertTrue(all(ref["track_id"] != 2471 for ref in result["events"][0]["evidence"]["source_refs"]))

    def test_positive_pedestrian_counts_separately_with_own_person_anchor(self):
        result = replay({frame: [observation(y, category="person", role="pedestrian", review_ref="ped-review")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        event = result["events"][0]
        self.assertEqual(event["category"], "pedestrian")
        self.assertEqual(event["display_id"], "P2000")
        self.assertEqual(event["evidence"]["anchor"], "raw_person_bbox_bottom_center")
        self.assertTrue(all(ref["class_name"] == "person" for ref in event["evidence"]["source_refs"]))

    def test_unknown_person_is_not_automatically_pedestrian(self):
        result = replay({frame: [observation(y, category="person")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["PERSON_ROLE_UNRESOLVED"])

    def test_unassociated_person_does_not_gain_pedestrian_from_resolved_label_only(self):
        result = replay({0: [observation(20, category="person", resolved_class_name="pedestrian")],
                         1: [observation(70, category="person", resolved_class_name="pedestrian")]})
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["PERSON_ROLE_UNRESOLVED"])

    def test_unknown_person_without_passage_stays_open_diagnostic(self):
        result = replay({0: [observation(20, category="person")]}, end=100)
        self.assertEqual(result["aggregate"]["pending"], 0)
        self.assertEqual(result["open_passage_diagnostics"][0]["disposition"], "NO_NEW_PASSAGE_EVIDENCE")

    def test_vehicle_anchor_cannot_silently_use_raw_person(self):
        with self.assertRaisesRegex(ValueError, "raw vehicle-class"):
            replay({0: [observation(20, category="person", role="vehicle", resolved_class_name="motorcycle")]})

    def test_roles_need_separate_nonrider_episodes(self):
        with self.assertRaisesRegex(ValueError, "role-specific"):
            replay({0: [observation(20, track=1, unit="u"),
                        observation(20, track=2, detection=1, unit="u", category="person")]})

    def test_pending_decision_key_survives_attempt_state_reset(self):
        samples = {0: 20, 1: [observation(47, identity_conflict=True)], 2: 52, 3: 70,
                   4: 52, 5: 35, 6: [observation(47, identity_conflict=True)], 7: 52, 8: 70}
        result = replay(samples)
        pending = [decision for decision in result["decisions"] if decision["status"] == "pending"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(len({(row["physical_unit_id"], row["passage_id"]) for row in pending}), 1)

    def test_repeated_attempt_can_resolve_same_pending_decision(self):
        result = replay({0: 20, 1: [observation(47, identity_conflict=True)], 2: 52, 3: 70,
                         4: 52, 5: 35, 6: 47, 7: 52, 8: 70})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["aggregate"]["pending"], 0)
        self.assertEqual(result["decisions"][0]["status"], "superseded_by_accepted")
        self.assertEqual(result["decisions"][0]["display_id"], result["events"][0]["display_id"])

    def test_display_ids_reference_same_final_event_after_timeout_upgrade(self):
        result = replay({0: 20, 1: 35, 70: 70})
        self.assertEqual({row["display_id"] for row in result["passage_log"]}, {"M2000"})
        self.assertEqual(result["display_assignments"][0]["display_id"], "M2000")

    def test_cancelled_event_has_no_authoritative_final_display_id(self):
        result = replay({0: 20, 1: 35, 70: 25})
        self.assertIsNone(result["cancelled_events"][0]["display_id"])
        self.assertTrue(all(row["display_id"] is None for row in result["passage_log"]))

    def test_display_id_category_is_final_after_offline_upgrade(self):
        result = replay({0: [observation(20, category="car")], 1: [observation(35, category="car")],
                         70: [observation(47, category="truck")], 71: [observation(52, category="truck")],
                         72: [observation(70, category="truck")]})
        self.assertEqual(result["events"][0]["display_id"], "T2000")
        self.assertTrue(all(row["display_id"] in (None, "T2000") for row in result["passage_log"]))

    def test_real_return_has_new_directional_display_passage_id(self):
        result = replay({0: 20, 1: 47, 2: 52, 3: 70, 4: 52, 5: 47, 6: 30})
        self.assertEqual([event["display_id"] for event in result["events"]], ["M2000", "M1000"])
        self.assertEqual(len({event["physical_unit_id"] for event in result["events"]}), 1)

    def test_display_ids_are_unique_per_category_and_direction(self):
        result = replay({frame: [observation(y, track=1), observation(y, track=2, detection=1),
                                observation(y, track=3, category="car", detection=2)]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual({event["display_id"] for event in result["events"]}, {"M2000", "M2001", "C2000"})

    def test_display_id_capacity_rolls_first_digit_then_fails_explicitly(self):
        self.assertEqual(passage_display_id("car", "A_TO_B", 1000), "C2999")
        self.assertEqual(passage_display_id("car", "A_TO_B", 1001), "C4000")
        self.assertEqual(passage_display_id("car", "A_TO_B", 4000), "C8999")
        self.assertEqual(passage_display_id("pedestrian", "B_TO_A", 5000), "P9999")
        for category, direction, ordinal in (("car", "A_TO_B", 4001), ("car", "B_TO_A", 5001),
                                             ("bus", "A_TO_B", 1), ("car", "UNKNOWN", 1),
                                             ("car", "A_TO_B", 0), ("car", "A_TO_B", True)):
            with self.subTest(category=category, direction=direction, ordinal=ordinal), self.assertRaises(ValueError):
                passage_display_id(category, direction, ordinal)

    def test_verified_association_requires_explicit_nonempty_id(self):
        with self.assertRaisesRegex(ValueError, "requires association_id"):
            replay({0: [observation(20, association_verified=True)]})

    def test_cross_frame_role_change_requires_physical_episode_split(self):
        with self.assertRaisesRegex(ValueError, "Cross-frame role"):
            replay({0: [observation(20, category="person", role="pedestrian", unit="u")],
                    1: [observation(47, category="car", role="vehicle", unit="u")],
                    2: [observation(52, category="car", role="vehicle", unit="u")],
                    3: [observation(70, category="car", role="vehicle", unit="u")]})

    def test_vehicle_and_pedestrian_subtotals_are_separate(self):
        result = replay({frame: [observation(y, track=1),
                                observation(y, track=2, detection=1, category="person", role="pedestrian")]
                         for frame, y in enumerate((20, 47, 52, 70))})
        self.assertEqual(result["aggregate"]["total"], 2)
        self.assertEqual(result["aggregate"]["vehicle_total"], 1)
        self.assertEqual(result["aggregate"]["pedestrian_total"], 1)

    def test_raw_source_links_and_review_refs_survive_event_evidence(self):
        result = replay({0: [observation(20, source_ref={"file": "raw-source", "frame": 0},
                                        measurement_provenance="retained_raw", class_id=3, confidence=0.8)],
                         1: [observation(70, source_ref={"file": "raw-source", "frame": 1},
                                        measurement_provenance="retained_raw", class_id=3, confidence=0.8)]})
        ref = result["events"][0]["evidence"]["source_refs"][0]
        self.assertEqual(ref["source_ref"], {"file": "raw-source", "frame": 0})
        self.assertEqual(ref["measurement_provenance"], "retained_raw")
        self.assertEqual(ref["class_id"], 3)

    def test_superseded_pending_reopens_after_same_passage_timeout_cancellation(self):
        result = replay({0: 20, 1: [observation(47, identity_conflict=True)], 2: 70,
                         3: 52, 4: 35, 5: 36, 6: 38,
                         70: [observation(48, category="bus")]}, end=75)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["aggregate"]["pending"], 1)
        self.assertEqual(len(result["decisions"]), 1)
        self.assertEqual(result["decisions"][0]["status"], "pending")
        self.assertNotIn("event_id", result["decisions"][0])
        self.assertIn("UNSUPPORTED_CATEGORY_TAXONOMY_OPEN", result["decisions"][0]["reasons"])
        self.assertEqual(sum(row["count_delta"] for row in result["passage_log"]), 0)

    def test_pedestrian_inferred_routes_require_explicit_policy(self):
        samples = {0: [observation(20, category="person", role="pedestrian")],
                   1: [observation(35, category="person", role="pedestrian")],
                   5: [observation(70, category="person", role="pedestrian")]}
        result = replay(samples)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertEqual(result["decisions"][0]["reasons"], ["PEDESTRIAN_INFERRED_ROUTE_REQUIRES_POLICY_APPROVAL"])
        allowed = replay(samples, policy={**POLICY, "pedestrian_routes": "all_operational"})
        self.assertEqual(allowed["aggregate"]["pedestrian_total"], 1)
        self.assertFalse(allowed["events"][0]["evidence"]["measured_crossing"])

    def test_pedestrian_timeout_requires_explicit_all_operational_policy(self):
        samples = {0: [observation(20, category="person", role="pedestrian")],
                   1: [observation(35, category="person", role="pedestrian")]}
        result = replay(samples, end=61)
        self.assertEqual(result["aggregate"]["total"], 0)
        self.assertIn("PEDESTRIAN_INFERRED_ROUTE_REQUIRES_POLICY_APPROVAL", result["decisions"][0]["reasons"])
        allowed = replay(samples, end=61, policy={**POLICY, "pedestrian_routes": "all_operational"})
        self.assertEqual(allowed["events"][0]["route"], "ESTIMATED_TIMEOUT")
        self.assertEqual(allowed["events"][0]["display_id"], "P2000")

    def test_bus_only_supported_when_category_and_prefix_explicitly_enabled(self):
        samples = {0: [observation(20, category="bus")], 1: [observation(70, category="bus")]}
        categories = ["motorcycle", "car", "truck", "pedestrian", "bus"]
        with self.assertRaisesRegex(ValueError, "explicit agreed display prefix"):
            replay(samples, policy={**POLICY, "supported_categories": categories})
        result = replay(samples, policy={**POLICY, "supported_categories": categories,
                                        "display_category_prefixes": {"motorcycle": "M", "car": "C", "truck": "T", "pedestrian": "P", "bus": "B"}})
        self.assertEqual(result["events"][0]["category"], "bus")
        self.assertEqual(result["events"][0]["display_id"], "B2000")
        self.assertEqual(result["aggregate"]["vehicle_total"], 1)

    def test_policy_rejects_unapproved_unknown_category_and_prefix(self):
        for change in ({"supported_categories": ["car", "car"]},
                       {"supported_categories": ["angkot"]},
                       {"pedestrian_routes": "guess"},
                       {"display_category_prefixes": {"car": "X"}}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                replay({0: 20}, policy={**POLICY, **change})

    def test_return_timeout_control_blocks_jitter_after_completed_first_passage(self):
        samples = {0: 20, 1: 47, 2: 52, 3: 70, 4: 69}
        legacy = replay(samples, end=64)
        self.assertEqual(legacy["aggregate"]["total"], 2)
        controlled = replay(samples, end=64,
                            policy={**POLICY, "return_timeout_policy": "require_new_passage_evidence"})
        self.assertEqual(controlled["aggregate"]["total"], 1)
        self.assertEqual(controlled["aggregate"]["pending"], 1)
        self.assertEqual(controlled["decisions"][0]["reasons"], ["RETURN_TIMEOUT_REQUIRES_NEW_PASSAGE_EVIDENCE"])
        self.assertEqual(controlled["events"][0]["route"], "LINE_MARGIN")
        self.assertEqual(sum(row["count_delta"] for row in controlled["passage_log"]), 1)

    def test_return_timeout_control_preserves_first_passage_sixty_frame_clock(self):
        result = replay({0: 20, 1: 35}, end=61,
                        policy={**POLICY, "return_timeout_policy": "require_new_passage_evidence"})
        self.assertEqual(result["aggregate"]["total"], 1)
        self.assertEqual(result["events"][0]["route"], "ESTIMATED_TIMEOUT")
        self.assertEqual(result["events"][0]["activation_frame"], 61)

    def test_return_timeout_control_still_accepts_actual_measured_reverse(self):
        result = replay({0: 20, 1: 47, 2: 52, 3: 70, 4: 69, 5: 52, 6: 47, 7: 30},
                        policy={**POLICY, "return_timeout_policy": "require_new_passage_evidence"})
        self.assertEqual(result["aggregate"]["total"], 2)
        self.assertEqual(result["aggregate"]["by_direction"], {"A_TO_B": 1, "B_TO_A": 1})
        self.assertTrue(all(event["evidence"]["measured_crossing"] for event in result["events"]))

    def test_observed_reverse_roi_arrival_resolves_held_return_timeout(self):
        result = replay({0: 20, 1: 47, 2: 52, 3: 70, 4: 69, 70: 30},
                        policy={**POLICY, "return_timeout_policy": "require_new_passage_evidence"})
        self.assertEqual(result["aggregate"]["total"], 2)
        self.assertEqual(result["aggregate"]["pending"], 0)
        self.assertEqual(result["decisions"][0]["status"], "superseded_by_accepted")
        self.assertEqual(result["events"][1]["route"], "OCCLUSION_DIFF_POLYGON")
        self.assertFalse(result["events"][1]["evidence"]["measured_crossing"])

    def test_return_timeout_policy_rejects_undefined_control(self):
        with self.assertRaisesRegex(ValueError, "return_timeout_policy"):
            replay({0: 20}, policy={**POLICY, "return_timeout_policy": "always_count"})

    def test_review_overlay_is_bound_when_in_policy(self):
        first = replay({0: 20, 1: 70}, policy={**POLICY, "review_overlay_sha256": "d" * 64})
        second = replay({0: 20, 1: 70}, policy={**POLICY, "review_overlay_sha256": "e" * 64})
        self.assertNotEqual(first["events"][0]["event_id"], second["events"][0]["event_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
