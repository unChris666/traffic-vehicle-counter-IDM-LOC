"""P0 identity regressions; synthetic source fixtures, no accuracy claims."""
from copy import deepcopy
import unittest

from phase_8_b_v4_identity_tests import GEOMETRY, observation, frames, rider_pair
import phase_8_b_v5_identity as identity


def run(values, count=None):
    return identity.prepare_identity_frames(frames(values, count), GEOMETRY,
        {"identity": identity.experimental_identity_policy()})


def positive(frame, tracks):
    return {"association_verified": True, "association_id": "positive-local",
        "source_ref": {"retained_same_vehicle_association": {
            "frame_index": frame, "track_ids": tracks, "whole_id_support_implied": False}}}


class HypothesisIsolationTests(unittest.TestCase):
    def test_unverified_clique_does_not_suppress_coexistent_car_and_motorcycle(self):
        shared = "retained-clique:4480,4552"
        result = run([(f, observation(f, track, box, category, unit_id=shared))
            for f in range(3) for track, box, category in
            ((4480, [2, 20, 22, 40], "car"), (4552, [65, 30, 85, 50], "motorcycle"))])
        for row in result["frames"]:
            self.assertEqual(len({o["unit_id"] for o in row["observations"]}), 2)
            self.assertTrue(all(not o["association_verified"] for o in row["observations"]))
        negatives = [r for r in result["unit_relations"] if r["relation_type"] == "DIFFERENT_UNIT"]
        self.assertEqual(len(negatives), 1)
        self.assertFalse(negatives[0]["verified"])
        self.assertEqual(negatives[0]["support_frames"], [0, 1, 2])

    def test_same_box_without_scoped_positive_proof_is_not_identity(self):
        result = run([(0, observation(0, t, [20, 30, 40, 45], unit_id="retained-clique:1,2"))
                      for t in (1, 2)])
        self.assertEqual(len({o["unit_id"] for o in result["frames"][0]["observations"]}), 2)
        self.assertFalse(result["unit_relations"])

    def test_positive_exact_frame_cross_category_alias_is_preserved(self):
        values = [(f, observation(f, t, [20 + f, 30, 40 + f, 45], category,
                    unit_id="retained-clique:1,2", **positive(f, [1, 2])))
                  for f in range(3) for t, category in ((1, "car"), (2, "truck"))]
        result = run(values)
        for row in result["frames"]:
            self.assertEqual(len({o["unit_id"] for o in row["observations"]}), 1)
        relations = [r for r in result["unit_relations"] if r["relation_type"] == "SAME_UNIT"]
        self.assertEqual(len(relations), 1)
        self.assertTrue(relations[0]["verified"])
        self.assertEqual(relations[0]["support_frames"], [0, 1, 2])

    def test_future_relation_does_not_reassign_earlier_independent_motor(self):
        values = []
        for f in range(5):
            proof = positive(f, [1, 2]) if f >= 3 else {}
            values += [(f, observation(f, 1, [20, 30, 40, 45], "car",
                        unit_id="retained-clique:1,2", **proof)),
                       (f, observation(f, 2, [70, 30, 90, 45] if f < 3 else [20, 30, 40, 45],
                        "motorcycle" if f < 3 else "car", unit_id="retained-clique:1,2", **proof))]
        result = run(values)
        early = result["frames"][0]["observations"]
        later = result["frames"][3]["observations"]
        self.assertNotEqual(early[0]["unit_id"], early[1]["unit_id"])
        self.assertEqual(later[0]["unit_id"], later[1]["unit_id"])
        self.assertNotEqual(early[1]["physical_episode_id"], later[1]["physical_episode_id"])
        same = [r for r in result["unit_relations"] if r["relation_type"] == "SAME_UNIT"]
        self.assertTrue(all(min(r["support_frames"]) >= 3 for r in same))
        self.assertTrue(all(early[1]["physical_episode_id"] not in
            (r["first_physical_episode_id"], r["second_physical_episode_id"]) for r in same))

    def test_incomplete_source_clique_is_not_positive(self):
        result = run([(0, observation(0, 1, [20, 30, 40, 45], unit_id="retained-clique:1,2",
                                   **positive(0, [1, 2]))),
                      (0, observation(0, 2, [20, 30, 40, 45], unit_id="retained-clique:1,2"))])
        self.assertEqual(len({o["unit_id"] for o in result["frames"][0]["observations"]}), 2)
        self.assertFalse([r for r in result["unit_relations"] if r["relation_type"] == "SAME_UNIT"])

    def test_disjoint_boxes_reject_retained_geometric_positive_claim(self):
        result = run([(0, observation(0, t, box, unit_id="retained-clique:1,2", **positive(0, [1, 2])))
                      for t, box in ((1, [1, 30, 20, 45]), (2, [70, 30, 90, 45]))])
        self.assertEqual(len({o["unit_id"] for o in result["frames"][0]["observations"]}), 2)
        self.assertTrue(all(not o["association_verified"] for o in result["frames"][0]["observations"]))

    def test_source_bound_reviewed_handoff_produces_bounded_episode_relation(self):
        kwargs = {"unit_id": "reviewed-physical", "episode_id": "reviewed-passage",
            "association_verified": True, "association_id": "reviewed-link",
            "review_refs": [{"review_id": "reviewed-link"}]}
        result = run([(0, observation(0, 73, [20, 30, 40, 45], "car", **kwargs)),
                      (2, observation(2, 93, [22, 30, 42, 45], "car", **kwargs))], count=3)
        relation = next(r for r in result["unit_relations"] if r["relation_type"] == "SAME_UNIT")
        self.assertEqual(relation["support_frames"], [0, 2])
        self.assertNotIn(1, relation["support_frames"])
        self.assertTrue(relation["verified"])
        self.assertEqual(result["frames"][1]["observations"], [])

    def test_class_jitter_without_other_evidence_does_not_mean_new_object(self):
        result = run([(f, observation(f, 1, [20, 30, 40, 45], c))
                      for f, c in enumerate(("car", "person", "truck", "car"))])
        self.assertEqual(len(result["episode_audit"]), 1)

    def test_same_class_disjoint_context_jump_has_no_old_timer_namespace(self):
        result = run([(0, observation(0, 2445, [1, 1, 10, 10])),
                      (1, observation(1, 2445, [80, 80, 90, 90]))])
        first, last = [r["observations"][0] for r in result["frames"]]
        self.assertNotEqual(first["episode_id"], last["episode_id"])
        self.assertEqual(last["previous_physical_episode_id"], first["physical_episode_id"])
        self.assertFalse(last["association_verified"])


class BoundedRolesAndIntegrityTests(unittest.TestCase):
    def test_car_truck_overlapping_covariation_creates_hold_not_alias(self):
        values = [(f, observation(f, t, [20 + f, 30, 40 + f, 45], category))
            for f in range(4) for t, category in ((2697, "truck"), (2706, "car"))]
        result = run(values)
        relation = next(r for r in result["unit_relations"]
            if r.get("candidate_kind") == "POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT")
        self.assertFalse(relation["verified"])
        self.assertEqual(relation["support_frames"], [0, 1, 2, 3])
        for row in result["frames"]:
            self.assertEqual(len({o["unit_id"] for o in row["observations"]}), 2)
            self.assertTrue(all("CROSS_CATEGORY_UNIT_OR_COMPONENT_UNRESOLVED"
                in o["identity_timeout_hold"] for o in row["observations"]))

    def test_cargo_like_box_is_not_automatically_relabelled_as_motorcycle(self):
        values = []
        for f in range(4):
            values += [(f, observation(f, 3555, [28 + f, 28, 40 + f, 40], "truck")),
                       (f, observation(f, 3563, [20 + f, 30, 45 + f, 50], "motorcycle"))]
        result = run(values)
        self.assertTrue([r for r in result["unit_relations"] if r.get("candidate_kind")])
        self.assertTrue(all(o["role"] == "vehicle" for row in result["frames"] for o in row["observations"]))
        self.assertTrue(all(next(o for o in row["observations"] if o["track_id"] == 3555)["class_name"] == "truck"
            for row in result["frames"]))
        weak = [r for r in result["unit_relations"] if r.get("candidate_kind")]
        self.assertTrue(all(r["candidate_kind"] == "WEAK_CROSS_CATEGORY_AUDIT_ONLY" for r in weak))
        self.assertTrue(all(not o["identity_timeout_hold"] for row in result["frames"] for o in row["observations"]))

    def test_disjoint_adjacent_vehicles_do_not_create_cross_category_hold(self):
        values = [(f, observation(f, t, [x + f, 30, x + f + 15, 45], category))
            for f in range(4) for t, x, category in ((1, 10, "truck"), (2, 50, "car"))]
        result = run(values)
        self.assertFalse([r for r in result["unit_relations"] if r.get("candidate_kind")])
        self.assertTrue(all(not o["identity_timeout_hold"] for row in result["frames"] for o in row["observations"]))

    def test_short_overlap_cannot_use_future_frames_as_past_identity(self):
        values = [(f, observation(f, t, [x + f, 30, x + 20 + f, 45], category))
            for f in range(2) for t, x, category in ((1, 20, "truck"), (2, 29, "car"))]
        result = run(values)
        self.assertFalse([r for r in result["unit_relations"] if r.get("candidate_kind")])
        self.assertTrue(result["cross_category_audit"])
        self.assertFalse(result["cross_category_audit"][0]["candidate_supported"])

    def test_single_high_iou_frame_holds_conflict_without_merging_or_filling_gap(self):
        values = [(2, observation(2, t, [20 + dx, 30, 40 + dx, 45], category))
            for t, dx, category in ((1, 0, "truck"), (2, .1, "car"))]
        result = run(values, count=5)
        relation = next(r for r in result["unit_relations"] if r.get("candidate_kind"))
        self.assertEqual(relation["candidate_kind"], "POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT")
        self.assertEqual(relation["support_frames"], [2])
        self.assertFalse(relation["verified"])
        self.assertEqual(relation["support_mode"], "EXACT_FRAME_HIGH_IOU_CONFLICT_ONLY")
        self.assertEqual(len({o["unit_id"] for o in result["frames"][2]["observations"]}), 2)
        self.assertTrue(all(not row["observations"] for row in result["frames"] if row["frame_index"] != 2))

    def test_opposite_observed_bc_motion_is_audit_only_even_with_high_overlap(self):
        values = []
        for f in range(3):
            values += [(f, observation(f, 1, [20 + f, 30, 40 + f, 45], "car")),
                       (f, observation(f, 2, [22 - f, 30, 42 - f, 45], "motorcycle"))]
        result = run(values)
        relations = [r for r in result["unit_relations"] if r.get("candidate_kind")]
        self.assertTrue(relations)
        self.assertTrue(all(r["candidate_kind"] == "WEAK_CROSS_CATEGORY_AUDIT_ONLY" for r in relations))
        self.assertTrue(all(not o["identity_timeout_hold"] for row in result["frames"] for o in row["observations"]))

    def test_retained_parent_is_remapped_only_on_exact_supported_frame(self):
        values = []
        for f in range(3):
            child = observation(f, 1, [24, 10, 32, 60], "person")
            if f == 1:
                child.update(role="rider", retained_component_relation_id="retained-role",
                    component_of_unit_id="retained-clique:2,3")
            values += [(f, child), (f, observation(f, 2, [20, 30, 40, 45],
                unit_id="retained-clique:2,3"))]
        relationships = {"component_links": [{"relation_id": "retained-role", "component_track_id": 1,
            "vehicle_track_id": 2, "support_frames": [1]}]}
        result = identity.prepare_identity_frames(frames(values), GEOMETRY,
            {"identity": identity.experimental_identity_policy()}, relationships=relationships)
        child1 = next(o for o in result["frames"][1]["observations"] if o["track_id"] == 1)
        self.assertEqual(child1["component_of_track_id"], 2)
        self.assertEqual(child1["component_of_unit_id"], "track:2")
        self.assertEqual([r["frame_index"] for r in result["retained_component_parent_remap_audit"]], [1])
        for f in (0, 2):
            child = next(o for o in result["frames"][f]["observations"] if o["track_id"] == 1)
            self.assertEqual(child["role"], "unknown_person")
            self.assertNotIn("component_of_track_id", child)

    def test_diagnostic_episode_ids_resolve_to_refined_observed_contexts(self):
        result = run([(0, observation(0, 1, [20, 30, 40, 45])),
                      (1, observation(1, 1, [20, 30, 40, 45])),
                      (2, observation(2, 2, [20, 30, 40, 45])),
                      (3, observation(3, 2, [20, 30, 40, 45]))])
        ids = {row["physical_episode_id"] for row in result["episode_audit"]}
        self.assertTrue(result["handoff_audit"])
        for row in result["handoff_audit"]:
            self.assertIn(row["first_episode_id"], ids)
            self.assertIn(row["second_episode_id"], ids)
            self.assertIn("inherited_first_episode_id", row)
        alias = run([(0, observation(0, t, [20, 30, 40, 45], unit_id="retained-clique:1,2",
            **positive(0, [1, 2]))) for t in (1, 2)])
        ids = {row["physical_episode_id"] for row in alias["episode_audit"]}
        self.assertTrue(alias["alias_context_audit"])
        self.assertTrue(all(row["physical_episode_id"] in ids for row in alias["alias_context_audit"]))

    def test_unknown_semantic_policy_cannot_silently_run_another_policy(self):
        for key in ("cross_category_candidate_policy", "cross_category_candidate_profile",
                    "same_unit_scope", "negative_relation_policy"):
            policy = identity.experimental_identity_policy()
            policy[key] = "disabled-or-unrecognized"
            with self.assertRaises(ValueError):
                identity.prepare_identity_frames([], GEOMETRY, {"identity": policy})

    def test_rider_relation_has_only_observed_parent_scope(self):
        values = sum([rider_pair(f) for f in (0, 1, 2, 4, 5, 6)], [])
        values += [(3, observation(3, 1, [24, 20, 32, 38], "person"))]
        result = run(values)
        roles = [next(o for o in row["observations"] if o["track_id"] == 1)["role"]
                 for row in result["frames"]]
        self.assertEqual(roles, ["rider", "rider", "rider", "unknown_person", "rider", "rider", "rider"])
        support = {f for r in result["unit_relations"] if r["relation_type"] == "COMPONENT_OF"
                   for f in r["support_frames"]}
        self.assertEqual(support, {0, 1, 2, 4, 5, 6})

    def test_unknown_person_is_not_auto_pedestrian(self):
        result = run([(f, observation(f, 1, [20, 10, 30, 30], "person")) for f in range(4)])
        self.assertTrue(all(row["observations"][0]["role"] == "unknown_person" for row in result["frames"]))

    def test_source_fields_and_input_are_preserved(self):
        original = frames(sum([rider_pair(f) for f in range(3)], []))
        preserved = deepcopy(original)
        result = identity.prepare_identity_frames(original, GEOMETRY,
            {"identity": identity.experimental_identity_policy()})
        self.assertEqual(original, preserved)
        for before, after in zip(original, result["frames"]):
            for a, b in zip(before["observations"], after["observations"]):
                for key in ("raw_bbox", "class_name", "confidence", "original_detection_index", "measurement_provenance"):
                    self.assertEqual(a[key], b[key])

    def test_predictions_and_missing_policy_are_rejected(self):
        with self.assertRaises(ValueError):
            run([(0, observation(0, 1, [20, 30, 40, 45], observed=False))])
        with self.assertRaises(ValueError):
            identity.prepare_identity_frames([], GEOMETRY, {})


if __name__ == "__main__":
    unittest.main()
