"""Counterexample tests for B v4 retained-measurement identity/role controls.

All boxes are synthetic contract fixtures, not video observations or accuracy
labels. No model, video decoder or counting pipeline is invoked.
"""

from copy import deepcopy
import unittest

from phase_5_geometry_helpers import Geometry
import phase_8_b_v4_identity as identity


GEOMETRY = Geometry((50, 10), (50, 90), ((0, 0), (49, 0), (49, 100), (0, 100)),
    ((51, 0), (100, 0), (100, 100), (51, 100)), 100, 100)


def observation(frame, track, box, category="motorcycle", **extra):
    return {"frame_index": frame, "track_id": track, "raw_bbox": list(box),
        "class_name": category, "class_id": {"person": 0, "car": 2, "motorcycle": 3, "truck": 7}[category],
        "original_detection_index": track, "confidence": 0.8, "observed": True, "emitted": True,
        "measurement_provenance": "retained_phase_8_detection",
        "unit_id": f"person-track:{track}" if category == "person" else f"track:{track}",
        "episode_id": "unreviewed-person" if category == "person" else "unreviewed-vehicle",
        "role": "unknown_person" if category == "person" else "vehicle",
        "association_verified": False, "identity_conflict": False, **extra}


def frames(values, count=None):
    count = count if count is not None else max([f for f, _ in values] + [0]) + 1
    result = [{"frame_index": f, "observations": []} for f in range(count)]
    for frame, value in values:
        result[frame]["observations"].append(value)
    return result


def run(values, *, count=None, profile="median_temporal_v1"):
    return identity.prepare_identity_frames(frames(values, count), GEOMETRY,
        {"identity": identity.experimental_identity_policy(component_profile=profile)})


def rider_pair(frame, *, person=1, motor=2, x=20, person_dx=0, motor_dx=0):
    return [(frame, observation(frame, person, [x + person_dx + 4, 20, x + person_dx + 12, 38], "person")),
            (frame, observation(frame, motor, [x + motor_dx, 30, x + motor_dx + 20, 45]))]


class EpisodeTests(unittest.TestCase):
    def test_class_jitter_alone_preserves_vehicle_context(self):
        values = [(f, observation(f, 1, [20, 30, 40, 45], category))
                  for f, category in enumerate(("motorcycle", "person", "motorcycle", "car", "truck"))]
        result = run(values)
        self.assertEqual(len(result["episode_audit"]), 1)
        vehicles = [o for r in result["frames"] for o in r["observations"] if o["role"] == "vehicle"]
        self.assertEqual(len({o["episode_id"] for o in vehicles}), 1)

    def test_raw_id_jump_splits_and_does_not_inherit_old_association(self):
        values = [(0, observation(0, 1, [5, 10, 15, 20], association_verified=True, association_id="old")),
                  (1, observation(1, 1, [80, 70, 90, 80], association_verified=True, association_id="old"))]
        result = run(values)
        a, b = [r["observations"][0] for r in result["frames"]]
        self.assertNotEqual(a["episode_id"], b["episode_id"])
        self.assertFalse(b["association_verified"])
        self.assertNotIn("association_id", b)
        self.assertEqual(b["previous_physical_episode_id"], a["physical_episode_id"])

    def test_contextual_parent_split_protects_parked_vehicle_origin(self):
        values = [(0, observation(0, 1, [55, 25, 80, 45]))]
        for f in range(1, 5):
            values += rider_pair(f, person=1, motor=2, x=55 - 8 * f)
        values.append((5, observation(5, 1, [15, 30, 35, 45])))
        result = run(values)
        reasons = [a["boundary_reason"] for a in result["episode_audit"] if a["track_id"] == 1]
        self.assertEqual(reasons, ["INITIAL_OBSERVATION",
            "VEHICLE_TO_PERSON_WITH_DIFFERENT_POSITIVE_PARENT_CONTEXT",
            "RAW_VEHICLE_AFTER_BOUNDED_COMPONENT_CONTEXT_NO_ORIGIN_INHERITANCE"])
        first = result["frames"][0]["observations"][0]
        last = result["frames"][5]["observations"][0]
        self.assertNotEqual(first["episode_id"], last["episode_id"])

    def test_long_gap_separates_unknown_continuity(self):
        result = run([(0, observation(0, 1, [20, 30, 40, 45])),
                      (61, observation(61, 1, [20, 30, 40, 45]))], count=62)
        self.assertEqual(len(result["episode_audit"]), 2)
        self.assertIn("LONG_MEASUREMENT_GAP", result["episode_audit"][1]["boundary_reason"])

    def test_context_jitter_without_large_jump_does_not_split(self):
        result = run([(f, observation(f, 1, [20 + f % 2, 30, 40 + f % 2, 45])) for f in range(8)])
        self.assertEqual(len(result["episode_audit"]), 1)

    def test_reviewed_identity_scope_is_not_silently_overwritten(self):
        proof = [{"review_id": "bounded-positive", "source_frame": 1}]
        values = [(0, observation(0, 1, [1, 1, 10, 10])),
                  (1, observation(1, 1, [80, 80, 90, 90], unit_id="reviewed", episode_id="scope-1",
                      review_refs=proof, association_verified=True, association_id="verified")),
                  (2, observation(2, 1, [80, 80, 90, 90]))]
        result = run(values)
        middle = result["frames"][1]["observations"][0]
        self.assertEqual((middle["unit_id"], middle["episode_id"]), ("reviewed", "scope-1"))
        self.assertTrue(middle["association_verified"])
        self.assertNotEqual(result["frames"][2]["observations"][0]["unit_id"], "reviewed")

    def test_category_review_does_not_authorize_origin_inheritance_across_gap(self):
        proof = [{"review_id": "only-category", "claim_type": "USER_REVIEW"}]
        values = [(0, observation(0, 1, [5, 5, 15, 15], review_refs=proof, resolved_class_name="car")),
                  (61, observation(61, 1, [80, 80, 90, 90], review_refs=proof, resolved_class_name="car"))]
        result = run(values, count=62)
        first, last = result["frames"][0]["observations"][0], result["frames"][61]["observations"][0]
        self.assertNotEqual(first["episode_id"], last["episode_id"])
        self.assertEqual(last["resolved_class_name"], "car")
        self.assertEqual(last["review_refs"], proof)

    def test_role_review_does_not_authorize_continuity_across_spatial_jump(self):
        proof = [{"review_id": "only-role", "claim_type": "USER_REVIEW"}]
        values = [(0, observation(0, 1, [5, 5, 15, 15], "person", role="pedestrian", review_refs=proof)),
                  (1, observation(1, 1, [80, 80, 90, 90], "person", role="pedestrian", review_refs=proof))]
        result = run(values)
        first, last = [r["observations"][0] for r in result["frames"]]
        self.assertNotEqual(first["episode_id"], last["episode_id"])
        self.assertEqual(last["role"], "pedestrian")

    def test_verified_source_bound_identity_review_can_cover_declared_gap(self):
        kwargs = {"unit_id": "same-physical", "episode_id": "reviewed-episode", "association_verified": True,
            "association_id": "positive-identity", "review_refs": [{"review_id": "positive-identity"}]}
        result = run([(0, observation(0, 1, [5, 5, 15, 15], **kwargs)),
                      (61, observation(61, 1, [80, 80, 90, 90], **kwargs))], count=62)
        self.assertEqual(len(result["episode_audit"]), 1)
        self.assertEqual(result["frames"][61]["observations"][0]["episode_id"], "reviewed-episode")

    def test_return_from_reviewed_role_scope_never_revives_initial_counting_key(self):
        values = [(0, observation(0, 1, [20, 30, 40, 45])),
                  (1, observation(1, 1, [24, 20, 32, 38], "person", role="rider",
                    component_of_unit_id="track:2", review_refs=[{"review_id": "bounded-role"}])),
                  (2, observation(2, 1, [20, 30, 40, 45]))]
        result = run(values)
        first, last = result["frames"][0]["observations"][0], result["frames"][2]["observations"][0]
        self.assertNotEqual(first["physical_episode_id"], last["physical_episode_id"])
        self.assertNotEqual((first["unit_id"], first["episode_id"]), (last["unit_id"], last["episode_id"]))


class RoleTests(unittest.TestCase):
    def test_observed_consecutive_rider_scope_no_gap_fill(self):
        values = sum([rider_pair(f) for f in (0, 1, 2, 4, 5, 6)], [])
        values += [(3, observation(3, 1, [24, 20, 32, 38], "person"))]
        result = run(values)
        roles = [next(o for o in r["observations"] if o["track_id"] == 1)["role"] for r in result["frames"]]
        self.assertEqual(roles, ["rider", "rider", "rider", "unknown_person", "rider", "rider", "rider"])
        self.assertEqual([r["support_frames"] for r in result["component_links"]], [[0, 1, 2], [4, 5, 6]])

    def test_stationary_rider_with_parent_not_inferred_pedestrian(self):
        result = run(sum([rider_pair(f) for f in range(5)], []))
        self.assertTrue(all(next(o for o in r["observations"] if o["track_id"] == 1)["role"] == "rider"
                            for r in result["frames"]))

    def test_person_near_motor_outside_vehicle_bc_stays_unknown(self):
        values = []
        for f in range(5):
            values += [(f, observation(f, 1, [24, 20, 32, 49], "person")),
                       (f, observation(f, 2, [20, 30, 40, 45]))]
        result = run(values)
        self.assertTrue(all(r["observations"][0]["role"] == "unknown_person" for r in result["frames"]))

    def test_walking_person_relative_motion_contradiction_stays_unknown(self):
        values = sum([rider_pair(f, x=20, person_dx=f * 5) for f in range(4)], [])
        result = run(values)
        self.assertFalse(result["component_links"])
        self.assertTrue(all(r["observations"][0]["role"] == "unknown_person" for r in result["frames"]))

    def test_two_adjacent_motorcycles_remain_distinct(self):
        values = []
        for f in range(4):
            values += rider_pair(f)
            values.append((f, observation(f, 3, [45, 30, 65, 45])))
        result = run(values)
        first = result["frames"][0]["observations"]
        self.assertEqual(first[0]["component_of_track_id"], 2)
        self.assertNotEqual(first[1]["unit_id"], first[2]["unit_id"])

    def test_competing_parent_motorcycles_do_not_get_automatic_merge(self):
        values = []
        for f in range(4):
            values += rider_pair(f)
            values.append((f, observation(f, 3, [19, 29, 41, 46])))
        result = run(values)
        self.assertFalse(result["component_links"])
        self.assertTrue(all(r["observations"][0]["role"] == "unknown_person" for r in result["frames"]))
        self.assertIn("COMPETING_COMPONENT_PARENTS", result["frames"][0]["observations"][0]["identity_timeout_hold"])
        self.assertTrue(all(not r["applied_support_frames"] for r in result["role_audit"]))

    def test_parent_change_starts_new_role_scope_and_physical_context(self):
        values = sum([rider_pair(f, motor=2 if f < 3 else 3) for f in range(6)], [])
        result = run(values)
        people = [r["observations"][0] for r in result["frames"]]
        self.assertNotEqual(people[2]["role_scope_id"], people[3]["role_scope_id"])
        self.assertNotEqual(people[2]["physical_episode_id"], people[3]["physical_episode_id"])

    def test_same_parent_raw_id_new_source_identity_breaks_child_role_scope(self):
        values = []
        for f in range(6):
            pair = rider_pair(f)
            pair[1][1].update(unit_id="physical-A" if f < 3 else "physical-B",
                episode_id="reviewed-A" if f < 3 else "reviewed-B",
                review_refs=[{"review_id": "split-parent-A" if f < 3 else "split-parent-B"}])
            values += pair
        result = run(values)
        people = [r["observations"][0] for r in result["frames"]]
        self.assertNotEqual(people[2]["role_scope_id"], people[3]["role_scope_id"])
        self.assertNotEqual(people[2]["physical_episode_id"], people[3]["physical_episode_id"])
        self.assertEqual(people[2]["component_of_unit_id"], "physical-A")
        self.assertEqual(people[3]["component_of_unit_id"], "physical-B")

    def test_parent_disjoint_jump_breaks_role_evidence_even_when_person_same_id(self):
        values = sum([rider_pair(f, x=5 if f < 3 else 75) for f in range(6)], [])
        result = run(values)
        roles = [r for r in result["role_audit"] if r["status"] == "SUPPORTED"]
        self.assertEqual([r["support_frames"] for r in roles], [[0, 1, 2], [3, 4, 5]])
        self.assertNotEqual(result["frames"][2]["observations"][0]["physical_episode_id"],
                            result["frames"][3]["observations"][0]["physical_episode_id"])

    def test_explicit_pedestrian_wins_only_within_its_reviewed_scope(self):
        values = []
        for f in range(5):
            values += rider_pair(f)
            if f == 2:
                values[-2][1].update(role="pedestrian", resolved_class_name="pedestrian",
                    review_refs=[{"review_id": "user-ped", "source_frame": 2}])
        result = run(values)
        people = [r["observations"][0] for r in result["frames"]]
        self.assertEqual(people[2]["role"], "pedestrian")
        self.assertTrue(all(o["role"] == "unknown_person" for o in people[:2] + people[3:]))

    def test_median_ablation_keeps_numeric_limit_and_records_max_failure(self):
        # One bbox-size/position outlier among an otherwise co-moving run.
        offsets = [0, 0, 0, 0, 5, 0, 0, 0, 0]
        values = sum([rider_pair(f, person_dx=dx) for f, dx in enumerate(offsets)], [])
        median_result = run(values)
        max_result = run(values, profile="retained_max_v1")
        self.assertEqual(median_result["policy"]["component_motion_limit"], .15)
        self.assertTrue(median_result["component_links"])
        self.assertFalse(max_result["component_links"])
        candidate = median_result["role_audit"][0]
        self.assertGreater(candidate["features"]["relative_motion_max"], .15)
        self.assertEqual(candidate["features"]["relative_motion_median"], 0)

    def test_unknown_people_are_never_auto_pedestrians(self):
        result = run([(f, observation(f, 1, [10, 10, 20, 30], "person")) for f in range(5)])
        self.assertTrue(all(r["observations"][0]["role"] == "unknown_person" for r in result["frames"]))


class HandoffAndSourceTests(unittest.TestCase):
    def test_exact_frame_clique_alias_joins_current_context_not_closed_initial_object(self):
        shared = "retained-clique:1,3"
        values = [(0, observation(0, 1, [55, 25, 80, 45], unit_id=shared))]
        for f in range(1, 4):
            values += rider_pair(f, person=1, motor=2, x=55 - 8 * f)
        for f in range(4, 9):
            positive = f in (5, 6)
            proof = {"retained_same_vehicle_association": {"frame_index": f,
                "track_ids": [1, 3], "whole_id_support_implied": False}}
            kwargs = {"unit_id": shared}
            if positive:
                kwargs.update(association_verified=True, association_id="exact-clique", source_ref=proof)
            values.append((f, observation(f, 1, [15, 30, 35, 45], "car", **kwargs)))
            if f >= 5:
                values.append((f, observation(f, 3, [15, 30, 35, 45], "car", **kwargs)))
        result = run(values)
        old = result["frames"][0]["observations"][0]
        current = result["frames"][4]["observations"][0]
        alias5 = next(o for o in result["frames"][5]["observations"] if o["track_id"] == 3)
        alias7 = next(o for o in result["frames"][7]["observations"] if o["track_id"] == 3)
        self.assertNotEqual(old["episode_id"], current["episode_id"])
        self.assertEqual(alias5["episode_id"], current["episode_id"])
        self.assertTrue(alias5["association_verified"])
        self.assertFalse(alias7["association_verified"])
        self.assertEqual(alias7["episode_id"], current["episode_id"])
        self.assertTrue(result["alias_context_audit"])
        self.assertTrue(all(a["earlier_frames_reassigned"] is False for a in result["alias_context_audit"]))

    def test_single_positive_alias_flag_does_not_align_without_complete_source_clique(self):
        proof = {"retained_same_vehicle_association": {"frame_index": 0,
            "track_ids": [1, 2], "whole_id_support_implied": False}}
        result = run([(0, observation(0, 1, [20, 30, 40, 45], unit_id="one",
                        association_verified=True, association_id="incomplete", source_ref=proof)),
                      (0, observation(0, 2, [20, 30, 40, 45], unit_id="two"))])
        self.assertFalse(result["alias_context_audit"])
        self.assertNotEqual(result["frames"][0]["observations"][0]["unit_id"],
                            result["frames"][0]["observations"][1]["unit_id"])

    def test_vehicle_alias_never_reassigns_raw_person_interval(self):
        proof = {"retained_same_vehicle_association": {"frame_index": 0,
            "track_ids": [1, 2], "whole_id_support_implied": False}}
        values = [(0, observation(0, t, [20, 30, 40, 45], unit_id="clique",
                    association_verified=True, association_id="positive", source_ref=proof)) for t in (1, 2)]
        values += [(1, observation(1, 1, [20, 30, 40, 45], "person")),
                   (2, observation(2, 1, [20, 30, 40, 45], unit_id="clique"))]
        result = run(values)
        person = result["frames"][1]["observations"][0]
        resumed = result["frames"][2]["observations"][0]
        self.assertEqual(person["unit_id"], "person-track:1")
        self.assertEqual(person["episode_id"], "unreviewed-person")
        self.assertFalse(person["identity_episode_boundary"])
        self.assertFalse(resumed["identity_episode_boundary"])

    def test_stationary_id_switch_holds_estimates_without_claiming_alias(self):
        values = [(0, observation(0, 1, [20, 30, 40, 45])),
                  (1, observation(1, 1, [20, 30, 40, 45])),
                  (2, observation(2, 2, [20, 30, 40, 45])),
                  (3, observation(3, 2, [20, 30, 40, 45]))]
        result = run(values)
        self.assertEqual(len(result["handoff_audit"]), 1)
        self.assertFalse(result["handoff_audit"][0]["automatic_alias_created"])
        self.assertTrue(all(r["observations"][0]["identity_timeout_hold"] for r in result["frames"]))
        self.assertEqual(len({r["observations"][0]["unit_id"] for r in result["frames"]}), 2)

    def test_reviewed_unique_handoff_keeps_existing_verified_counting_identity(self):
        kwargs = {"unit_id": "verified-unit", "episode_id": "verified-episode", "association_verified": True,
                  "association_id": "source-bound", "review_refs": [{"review_id": "bounded"}]}
        result = run([(0, observation(0, 1, [20, 30, 40, 45], **kwargs)),
                      (1, observation(1, 2, [20, 30, 40, 45], **kwargs))])
        self.assertFalse(result["handoff_audit"])
        self.assertEqual(len({r["observations"][0]["episode_id"] for r in result["frames"]}), 1)

    def test_coexistent_nearby_vehicles_never_handoff_or_merge(self):
        values = [(f, observation(f, t, [20, 30, 40, 45])) for f in range(3) for t in (1, 2)]
        result = run(values)
        self.assertFalse(result["handoff_audit"])
        self.assertEqual(len({o["unit_id"] for o in result["frames"][0]["observations"]}), 2)

    def test_no_mutation_and_raw_vehicle_bc_not_replaced_by_person_union(self):
        original = frames(sum([rider_pair(f) for f in range(4)], []))
        preserved = deepcopy(original)
        result = identity.prepare_identity_frames(original, GEOMETRY,
            {"identity": identity.experimental_identity_policy()})
        self.assertEqual(original, preserved)
        for before, after in zip(original, result["frames"]):
            for source, decorated in zip(before["observations"], after["observations"]):
                for field in ("raw_bbox", "class_name", "confidence", "original_detection_index", "measurement_provenance"):
                    self.assertEqual(source[field], decorated[field])
        self.assertEqual(result["frames"][0]["observations"][1]["raw_bbox"], [20, 30, 40, 45])

    def test_predictions_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Prediction"):
            run([(0, observation(0, 1, [20, 30, 40, 45], observed=False))])

    def test_missing_policy_cannot_silently_use_defaults(self):
        with self.assertRaisesRegex(ValueError, "Explicit"):
            identity.prepare_identity_frames([], GEOMETRY, {})

    def test_unknown_profile_and_appearance_claim_are_rejected(self):
        for change in ({"component_motion_profile": "secret-fallback"}, {"appearance_features_used": True}):
            policy = identity.experimental_identity_policy(); policy.update(change)
            with self.assertRaises(ValueError):
                identity.prepare_identity_frames([], GEOMETRY, {"identity": policy})

    def test_assignments_expose_parent_and_counting_episode_without_source_boxes(self):
        result = run(sum([rider_pair(f) for f in range(3)], []))
        rider = result["assignments"][0]
        self.assertEqual(rider["component_of_track_id"], 2)
        self.assertEqual(rider["physical_unit_id"], "person-track:1")
        self.assertIn("physical_episode_id", rider)
        self.assertNotIn("raw_bbox", rider)


if __name__ == "__main__":
    unittest.main()
