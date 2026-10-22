"""Synthetic source-scope tests for conservative invalid ambiguity candidates."""
from copy import deepcopy
import unittest

from phase_8_b_v4_identity_tests import GEOMETRY, observation, frames
from phase_8_b_v5_identity_tests import positive
import phase_8_b_v6_identity as identity


def run(values, count=None, relationships=None):
    return identity.prepare_identity_frames(frames(values, count), GEOMETRY,
        {"identity": identity.experimental_identity_policy()}, relationships=relationships)


def ambiguity(result):
    return [r for r in result["unit_relations"] if r.get("candidate_kind") == identity.AMBIGUITY_KIND]


def reviewed(frame, track, unit, *, review_type="SPLIT_IDENTITY"):
    return {"unit_id": unit, "episode_id": "reviewed-scope",
        "review_refs": [{"review_id": "review-" + unit, "reviews_sha256": "a" * 64,
            "source_frame": frame, "track_id": track, "review_type": review_type}]}


class SameCategoryAmbiguityContracts(unittest.TestCase):
    def test_same_category_high_overlap_is_ambiguity_not_merged_identity(self):
        result = run([(f, observation(f, track, [20+f+dx, 30, 40+f+dx, 45]))
            for f in range(3) for track, dx in ((1, 0), (2, 1))])
        rel = ambiguity(result)
        self.assertEqual(len(rel), 1)
        self.assertEqual(rel[0]["support_frames"], [0, 1, 2])
        self.assertFalse(rel[0]["verified"])
        for row in result["frames"]:
            self.assertEqual(len({item["unit_id"] for item in row["observations"]}), 2)
            self.assertTrue(all("SCOPED_UNIT_AMBIGUITY" in item["identity_timeout_hold"] for item in row["observations"]))

    def test_single_observed_high_overlap_can_flag_but_not_fill_missing_frames(self):
        result = run([(2, observation(2, track, [20, 30, 40, 45])) for track in (1, 2)], count=5)
        self.assertEqual(ambiguity(result)[0]["support_frames"], [2])
        self.assertTrue(all(not row["observations"] for row in result["frames"] if row["frame_index"] != 2))

    def test_same_category_adjacent_nonoverlapping_vehicles_remain_independent(self):
        result = run([(f, observation(f, track, [x+f, 30, x+f+15, 45]))
            for f in range(4) for track, x in ((1, 10), (2, 50))])
        self.assertFalse(ambiguity(result))
        self.assertTrue(all("SCOPED_UNIT_AMBIGUITY" not in o["identity_timeout_hold"]
            for row in result["frames"] for o in row["observations"]))

    def test_weak_parallel_overlap_is_not_ambiguity_by_proximity_alone(self):
        result = run([(f, observation(f, track, [20+f+dx, 30, 40+f+dx, 45]))
            for f in range(4) for track, dx in ((1, 0), (2, 12))])
        self.assertFalse(ambiguity(result))
        self.assertTrue(result["ambiguity_audit"])
        self.assertFalse(any(row["ambiguity_supported"] for row in result["ambiguity_audit"]))

    def test_opposite_observed_directions_not_duplicate_even_when_boxes_overlap(self):
        values = []
        for f in range(3):
            values += [(f, observation(f, 1, [20+f, 30, 40+f, 45])),
                       (f, observation(f, 2, [22-f, 30, 42-f, 45]))]
        result = run(values)
        self.assertFalse(ambiguity(result))
        self.assertTrue(any(row["opposite_observed_direction"] for row in result["ambiguity_audit"]))

    def test_verified_positive_same_unit_does_not_become_invalid_geometric_candidate(self):
        result = run([(f, observation(f, track, [20+f, 30, 40+f, 45],
            unit_id="retained-clique:1,2", **positive(f, [1, 2])))
            for f in range(3) for track in (1, 2)])
        self.assertFalse(ambiguity(result))
        self.assertTrue(any(row.get("verified") is True and row["type"] == "SAME_UNIT"
                            for row in result["unit_relations"]))

    def test_class_or_id_renaming_does_not_change_ambiguity_rule(self):
        for category in ("motorcycle", "car", "truck"):
            result = run([(0, observation(0, track, [20, 30, 40, 45], category)) for track in (56, 817)])
            self.assertEqual(len(ambiguity(result)), 1)

    def test_bus_uses_same_ambiguity_policy_without_relabeling(self):
        values = []
        for track in (1, 2):
            item = observation(0, track, [20, 30, 40, 45], "car")
            item.update(class_name="bus", class_id=5)
            values.append((0, item))
        result = run(values)
        self.assertEqual(len(ambiguity(result)), 1)
        self.assertTrue(all(o["class_name"] == "bus" for o in result["frames"][0]["observations"]))

    def test_later_raw_id_context_is_not_globally_blacklisted(self):
        values = [(f, observation(f, track, [5+f, 10, 20+f, 25])) for f in range(3) for track in (1, 2)]
        values.append((3, observation(3, 1, [80, 80, 95, 95])))
        result = run(values)
        first = result["frames"][0]["observations"][0]
        later = result["frames"][3]["observations"][0]
        self.assertNotEqual(first["physical_episode_id"], later["physical_episode_id"])
        self.assertNotIn("SCOPED_UNIT_AMBIGUITY", later["identity_timeout_hold"])

    def test_unknown_person_not_relabelled_from_shared_motion(self):
        result = run([(f, observation(f, track, [20+f, 10, 35+f, 28], category))
            for f in range(3) for track, category in ((1, "person"), (2, "car"))])
        self.assertFalse(ambiguity(result))
        self.assertTrue(all(o["role"] == "unknown_person" for row in result["frames"]
                            for o in row["observations"] if o["track_id"] == 1))


class HandoffAndSourceContracts(unittest.TestCase):
    def test_unverified_handoff_keeps_exact_endpoint_scope_not_gap_observations(self):
        result = run([(0, observation(0, 1, [20, 30, 40, 45])),
                      (1, observation(1, 1, [21, 30, 41, 45])),
                      (3, observation(3, 2, [22, 30, 42, 45])),
                      (4, observation(4, 2, [23, 30, 43, 45]))], count=5)
        rel = next(row for row in result["unit_relations"] if row.get("candidate_kind") == identity.HANDOFF_KIND)
        self.assertEqual(rel["support_frames"], [1, 3])
        self.assertFalse(rel["verified"])
        self.assertFalse(rel["gap_observations_created"])
        self.assertEqual(result["frames"][2]["observations"], [])
        self.assertNotEqual(rel["first_unit_id"], rel["second_unit_id"])

    def test_positive_reviewed_handoff_not_turned_into_ambiguous_handoff(self):
        extra = {"unit_id":"physical-known", "episode_id":"reviewed-passage",
                 "association_verified":True, "association_id":"review-link",
                 "review_refs":[{"review_id":"review-link"}]}
        result = run([(0, observation(0, 1, [20, 30, 40, 45], **extra)),
                      (2, observation(2, 2, [21, 30, 41, 45], **extra))], count=3)
        self.assertFalse([r for r in result["unit_relations"] if r.get("candidate_kind") == identity.HANDOFF_KIND])

    def test_source_boxes_and_roles_are_not_rewritten(self):
        source = frames([(0, observation(0, t, [20, 30, 40, 45])) for t in (1, 2)])
        before = deepcopy(source)
        result = identity.prepare_identity_frames(source, GEOMETRY, {"identity":identity.experimental_identity_policy()})
        self.assertEqual(source, before)
        for actual, original in zip(result["frames"][0]["observations"], before[0]["observations"]):
            self.assertEqual(actual["raw_bbox"], original["raw_bbox"])
            self.assertEqual(actual["class_name"], original["class_name"])
            self.assertEqual(actual["role"], original["role"])

    def test_semantic_policy_must_be_explicit(self):
        for key in ("ambiguity_policy", "ambiguity_disposition", "direction_policy", "unverified_handoff_policy"):
            controls = identity.experimental_identity_policy()
            controls[key] = "unknown"
            with self.subTest(key=key), self.assertRaises(ValueError):
                identity.prepare_identity_frames([], GEOMETRY, {"identity":controls})


class ScopedDistinctProofContracts(unittest.TestCase):
    def test_positively_reviewed_distinct_vehicles_not_invalidated_by_overlap(self):
        result = run([(f, observation(f, track, [20+f, 30, 40+f, 45],
            **reviewed(f, track, "physical-" + str(track))))
            for f in range(3) for track in (1, 2)])
        self.assertFalse(ambiguity(result))
        self.assertEqual(len(result["known_distinct_constraint_audit"]), 3)
        self.assertTrue(all("SCOPED_UNIT_AMBIGUITY" not in o["identity_timeout_hold"]
            for row in result["frames"] for o in row["observations"]))

    def test_role_or_category_review_does_not_prove_distinct_vehicle_identity(self):
        for kind in ("PEDESTRIAN_ROLE", "CATEGORY_CORRECTION", None):
            values = [(0, observation(0, track, [20, 30, 40, 45],
                **reviewed(0, track, "custom-" + str(track), review_type=kind))) for track in (1, 2)]
            with self.subTest(kind=kind):
                self.assertEqual(len(ambiguity(run(values))), 1)

    def test_distinct_review_requires_exact_frame_and_track_source_binding(self):
        for field, value in (("source_frame", 99), ("track_id", 99), ("reviews_sha256", "")):
            values = []
            for track in (1, 2):
                extra = reviewed(0, track, "physical-" + str(track))
                extra["review_refs"][0][field] = value
                values.append((0, observation(0, track, [20, 30, 40, 45], **extra)))
            with self.subTest(field=field):
                self.assertEqual(len(ambiguity(run(values))), 1)

    def test_distinct_review_removes_only_supported_cross_category_hold(self):
        values = []
        for f in range(2):
            for track, category in ((1, "car"), (2, "truck")):
                extra = reviewed(f, track, "physical-" + str(track)) if f == 0 else {}
                values.append((f, observation(f, track, [20, 30, 40, 45], category, **extra)))
        result = run(values)
        relations = [r for r in result["unit_relations"]
            if r.get("candidate_kind") == "POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"]
        self.assertEqual([f for r in relations for f in r["support_frames"]], [1])
        self.assertTrue(all("CROSS_CATEGORY_UNIT_OR_COMPONENT_UNRESOLVED" not in o["identity_timeout_hold"]
            for o in result["frames"][0]["observations"]))
        self.assertTrue(all("CROSS_CATEGORY_UNIT_OR_COMPONENT_UNRESOLVED" in o["identity_timeout_hold"]
            for o in result["frames"][1]["observations"]))

    def test_distinct_handoff_clears_only_linked_hold_and_retains_unrelated_reason(self):
        values = [(0, observation(0, 1, [20, 30, 40, 45],
                    identity_timeout_hold=["UNRELATED_EXISTING_REASON"], **reviewed(0, 1, "first"))),
                  (2, observation(2, 2, [21, 30, 41, 45], **reviewed(2, 2, "second")))]
        result = run(values)
        self.assertFalse([r for r in result["unit_relations"] if r.get("candidate_kind") == identity.HANDOFF_KIND])
        first = result["frames"][0]["observations"][0]
        self.assertEqual(first["identity_timeout_hold"], ["UNRELATED_EXISTING_REASON"])
        self.assertEqual(result["handoff_audit"][0]["v6_disposition"], "PROVEN_DISTINCT_NOT_A_HANDOFF")

    def test_distinct_pair_does_not_clear_hold_from_another_unresolved_handoff(self):
        values = [(0, observation(0, 1, [20, 30, 40, 45], **reviewed(0, 1, "first"))),
                  (2, observation(2, 2, [21, 30, 41, 45], **reviewed(2, 2, "second"))),
                  (4, observation(4, 3, [22, 30, 42, 45]))]
        result = run(values)
        self.assertEqual(len([r for r in result["unit_relations"] if r.get("candidate_kind") == identity.HANDOFF_KIND]), 2)
        for row in result["frames"]:
            for item in row["observations"]:
                self.assertIn("POSSIBLE_UNVERIFIED_RAW_ID_HANDOFF_TIMEOUT_HELD", item["identity_timeout_hold"])

    def test_verified_negative_relation_requires_explicit_endpoint_scope(self):
        values = [(0, observation(0, track, [20, 30, 40, 45])) for track in (1, 2)]
        constraint = {"relation_type": "DIFFERENT_UNIT", "relation_id": "review-negative",
            "verified": True, "first_track_id": 1, "second_track_id": 2,
            "first_unit_id": "track:1", "second_unit_id": "track:2",
            "first_episode_id": "unreviewed-vehicle", "second_episode_id": "unreviewed-vehicle",
            "support_frames": [0]}
        self.assertFalse(ambiguity(run(values, relationships={"unit_relations": [constraint]})))
        for key, bad in (("verified", False), ("support_frames", [1]), ("first_episode_id", "other")):
            invalid = {**constraint, key: bad}
            with self.subTest(key=key):
                self.assertEqual(len(ambiguity(run(values, relationships={"unit_relations": [invalid]}))), 1)

    def test_legacy_verified_same_vehicle_review_can_prove_distinct_assignments(self):
        values = []
        for track in (1, 2):
            extra = reviewed(0, track, "physical-" + str(track))
            del extra["review_refs"][0]["review_type"]
            extra.update(association_verified=True, association_id=extra["review_refs"][0]["review_id"])
            values.append((0, observation(0, track, [20, 30, 40, 45], **extra)))
        self.assertFalse(ambiguity(run(values)))


if __name__ == "__main__":
    unittest.main()
