"""P0 positive/negative software fixtures; not real-world accuracy results."""
from copy import deepcopy
import unittest

from phase_8_b_v3_counting_tests import GEOMETRY, SOURCE, observation, frames
from phase_8_b_v4_counting_tests import POLICY as OLD_POLICY
from phase_8_b_v5_counting import experimental_counting_policy, finalize_passages, replay_frames


POLICY = {**deepcopy(OLD_POLICY), "p0_counting": experimental_counting_policy()}


def run(samples, end=None, relations=None, policy=None):
    p = deepcopy(POLICY if policy is None else policy)
    p["episode_relations"] = [] if relations is None else relations
    return replay_frames(frames(samples, end=end), GEOMETRY, source_identity=SOURCE, policy=p)


def parallel(categories=("motorcycle", "motorcycle"), directions=None):
    directions = [False] * len(categories) if directions is None else directions
    samples = {}
    for frame, y in enumerate((30, 47, 70)):
        samples[frame] = [observation(100-y if directions[i] else y,
            track=i+1, detection=i, category=category, physical_episode_id=f"physical:{i+1}")
            for i, category in enumerate(categories)]
    return samples


def relation(a=1, b=2, kind="SAME_UNIT", support=None, verified=True):
    return {"relation_id": f"proof:{a}:{b}:{kind}", "relation_type": kind,
            "first_track_id": a, "second_track_id": b,
            "first_physical_episode_id": f"physical:{a}",
            "second_physical_episode_id": f"physical:{b}",
            "support_frames": [1] if support is None else support,
            "verified": verified}


class Bv5CountingContracts(unittest.TestCase):
    def test_actual_translated_vehicle_measured_crossing_keeps_raw_bc(self):
        r = run({0: 30, 1: 70})
        self.assertEqual(r["aggregate"]["measured_total"], 1)
        e = r["events"][0]
        self.assertEqual(e["evidence"]["anchor"], "raw_vehicle_bbox_bottom_center")
        self.assertTrue(e["evidence"]["p0_anchor_quality"]["minimum_corner_toward_progress_px"] > 0)
        for ref in e["evidence"]["source_refs"]:
            self.assertEqual(ref["point"], [(ref["raw_bbox"][0]+ref["raw_bbox"][2])/2, ref["raw_bbox"][3]])

    def test_static_box_bottom_edge_expansion_does_not_arm_timeout(self):
        samples = {f: [observation(y, raw_bbox=[48, 0, 52, y])]
                   for f,y in enumerate((20,23,26))}
        r = run(samples, 100)
        self.assertEqual(r["aggregate"]["total"], 0)
        self.assertFalse(any(a["eligible"] for a in r["eligibility_audit"]))

    def test_static_box_bottom_edge_crossing_is_held_not_measured_passage(self):
        r = run({0:[observation(30,raw_bbox=[48,0,52,30])],
                 1:[observation(70,raw_bbox=[48,0,52,70])]})
        self.assertEqual(r["aggregate"]["total"], 0)
        self.assertEqual(r["aggregate"]["pending"], 1)
        self.assertIn("ANCHOR_DEFORMATION_OR_PHYSICAL_MOTION_UNRESOLVED",r["decisions"][0]["reasons"])

    def test_translation_and_shape_growth_with_all_corners_toward_can_pass(self):
        r=run({0:[observation(30,raw_bbox=[46,20,54,30])],
               1:[observation(70,raw_bbox=[42,50,58,70])]})
        self.assertEqual(r["aggregate"]["measured_total"],1)

    def test_perspective_shape_change_without_corner_support_remains_unknown(self):
        r=run({0:[observation(30,raw_bbox=[46,20,54,30])],
               1:[observation(70,raw_bbox=[40,10,60,70])]})
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertEqual(r["aggregate"]["pending"],1)

    def test_moving_contracting_box_with_whole_box_translation_keeps_crossing(self):
        r=run({0:[observation(30,raw_bbox=[40,10,60,30])],
               1:[observation(70,raw_bbox=[44,58,56,70])]})
        self.assertEqual(r["aggregate"]["measured_total"],1)

    def test_parked_then_genuinely_departing_can_arm(self):
        samples={0:[observation(20,raw_bbox=[48,0,52,20])],
                 1:[observation(23,raw_bbox=[48,0,52,23])],
                 2:[observation(26,raw_bbox=[48,0,52,26])],
                 3:[observation(32,raw_bbox=[48,12,52,32])],
                 4:[observation(38,raw_bbox=[48,18,52,38])]}
        r=run(samples,64)
        self.assertEqual(r["aggregate"]["total"],1)
        self.assertEqual(r["events"][0]["activation_frame"],64)

    def test_timeout_clock_remains_last_origin_plus60(self):
        self.assertEqual(run({0:20,1:23,2:26},61)["aggregate"]["total"],0)
        r=run({0:20,1:23,2:26},62)
        self.assertEqual(r["events"][0]["activation_frame"],62)
        self.assertFalse(r["events"][0]["evidence"]["measured_crossing"])

    def test_visible_stationary_origin_resets_clock(self):
        r=run({0:20,1:23,**{f:26 for f in range(2,100)}})
        self.assertEqual(r["aggregate"]["total"],0)

    def test_missing_frames_never_make_measured_crossing(self):
        r=run({0:20,1:23,2:26,4:70})
        self.assertEqual(r["aggregate"]["measured_total"],0)

    def test_new_episode_cannot_inherit_earlier_origin(self):
        r=run({0:[observation(20,episode_id="old")],1:[observation(23,episode_id="old")],
               2:[observation(26,episode_id="old")],
               3:[observation(70,episode_id="new",identity_episode_boundary=True)],
               4:[observation(80,episode_id="new")],5:[observation(90,episode_id="new")]},100)
        self.assertEqual(r["aggregate"]["total"],0)

    def test_unknown_person_namespace_without_boundary_suspends_old_vehicle_timeout(self):
        samples={0:20,1:23,2:26,**{f:[observation(26,category="person",role="unknown_person",
            unit="person-track:1",identity_episode_boundary=False)] for f in range(3,100)}}
        r=run(samples)
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertTrue(any("RAW_CONTEXT_CHANGED_WITHOUT_PHYSICAL_CONTINUITY_PROOF" in d["reasons"]
                            for d in r["decisions"] if d["status"]=="pending"))

    def test_raw_vehicle_return_after_ambiguous_person_cannot_use_old_origin(self):
        r=run({0:20,1:23,2:26,3:[observation(26,category="person",role="unknown_person",
            unit="person-track:1",identity_episode_boundary=False)],4:70})
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertTrue(any("ORIGIN_TIMER_CONTEXT_CONTINUITY_UNRESOLVED" in d["reasons"]
                            for d in r["decisions"]))

    def test_completed_measured_passage_survives_later_ambiguous_role_change(self):
        r=run({0:30,1:70,2:[observation(70,category="person",role="unknown_person",
            unit="person-track:1",identity_episode_boundary=False)]},100)
        self.assertEqual(r["aggregate"]["measured_total"],1)

    def test_current_positive_vehicle_alias_preserves_passage_when_one_raw_id_changes_role(self):
        meta={"unit":"known-unit","episode_id":"known-episode",
              "association_verified":True,"association_id":"source-proof"}
        r=run({0:[observation(20,**meta)],1:[observation(23,**meta)],
            2:[observation(26,**meta),observation(26,track=2,detection=1,**meta)],
            3:[observation(26,category="person",role="unknown_person",unit="person-track:1",
                           identity_episode_boundary=False),
               observation(26,track=2,detection=1,**meta)]},63)
        self.assertEqual(r["aggregate"]["total"],1)
        self.assertFalse(r["events"][0]["evidence"]["measured_crossing"])
        self.assertEqual(r["events"][0]["route"],"ESTIMATED_TIMEOUT")

    def test_measured_return_is_separate_passage(self):
        r=run({0:30,1:70,2:30})
        self.assertEqual(r["aggregate"]["total"],2)
        self.assertEqual({e["direction"] for e in r["events"]},{"A_TO_B","B_TO_A"})

    def test_changed_departing_id_does_not_create_new_count(self):
        r=run({0:30,1:70,2:[observation(75,track=2)],3:[observation(80,track=2)],
               4:[observation(85,track=2)]},100)
        self.assertEqual(r["aggregate"]["total"],1)

    def test_same_category_nearby_vehicles_without_positive_link_stay_separate(self):
        r=run(parallel())
        self.assertEqual(r["aggregate"]["total"],2)

    def test_verified_scoped_duplicate_is_one_event(self):
        r=run(parallel(),relations=[relation()])
        self.assertEqual(r["aggregate"]["total"],1)
        self.assertEqual(r["aggregate"]["cancelled"],1)
        self.assertEqual(sum(log["count_delta"] for log in r["passage_log"]),1)

    def test_unverified_relation_never_merges(self):
        r=run(parallel(),relations=[relation(verified=False)])
        self.assertEqual(r["aggregate"]["total"],2)

    def test_cross_category_geometric_candidate_holds_counts_without_false_merge(self):
        proof=relation(verified=False)
        proof["candidate_kind"]="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"
        r=run(parallel(("car","truck")),relations=[proof])
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertEqual(r["aggregate"]["pending"],2)
        self.assertEqual(r["aggregate"]["cancelled"],2)
        self.assertFalse(r["decisions"][-1]["physical_episodes_merged"])
        pending=[d for d in r["decisions"] if d["status"]=="pending"]
        self.assertEqual({d["track_id"] for d in pending},{1,2})
        self.assertTrue(all(len(d["candidate_event_ids"])==1 for d in pending))

    def test_connected_uncertain_groups_keep_each_original_passage_reviewable(self):
        proofs=[relation(1,2,verified=False),relation(2,3,verified=False)]
        for proof in proofs:proof["candidate_kind"]="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"
        r=run(parallel(("car","truck","motorcycle")),relations=proofs)
        pending=[d for d in r["decisions"] if d["status"]=="pending"]
        self.assertEqual(len(pending),3)
        self.assertEqual({d["track_id"] for d in pending},{1,2,3})
        self.assertEqual(len({d["passage_id"] for d in pending}),3)

    def test_uncertain_opposite_measured_directions_are_not_one_passage(self):
        proof=relation(verified=False)
        proof["candidate_kind"]="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"
        r=run(parallel(("car","truck"),directions=[False,True]),relations=[proof])
        self.assertEqual(r["aggregate"]["total"],2)
        self.assertEqual(r["aggregate"]["pending"],0)

    def test_repeating_finalizer_is_idempotent(self):
        proof=relation(verified=False)
        proof["candidate_kind"]="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"
        r=run(parallel(("car","truck")),relations=[proof])
        again=finalize_passages(r,[proof],controls=POLICY["p0_counting"])
        self.assertEqual(r,again)

    def test_different_evidence_requires_fresh_replay_after_finalization(self):
        r=run(parallel())
        with self.assertRaisesRegex(ValueError,"fresh replay"):
            finalize_passages(r,[relation()],controls=POLICY["p0_counting"])

    def test_cross_category_candidate_after_passage_does_not_hold_earlier_count(self):
        proof=relation(verified=False,support=[20])
        proof["candidate_kind"]="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"
        r=run(parallel(("car","truck")),end=20,relations=[proof])
        self.assertEqual(r["aggregate"]["total"],2)

    def test_cross_category_candidate_only_one_event_still_holds_relevant_count(self):
        proof=relation(verified=False)
        proof["candidate_kind"]="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT"
        r=run({0:[observation(30,physical_episode_id="physical:1")],
               1:[observation(70,physical_episode_id="physical:1")]},relations=[proof])
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertEqual(r["aggregate"]["pending"],1)

    def test_future_only_relation_never_backpropagates(self):
        r=run(parallel(),end=20,relations=[relation(support=[20])])
        self.assertEqual(r["aggregate"]["total"],2)

    def test_wrong_episode_relation_never_merges(self):
        proof=relation();proof["first_physical_episode_id"]="other"
        self.assertEqual(run(parallel(),relations=[proof])["aggregate"]["total"],2)

    def test_scoped_component_not_independent_and_parent_bc_is_preserved(self):
        r=run(parallel(("truck","motorcycle")),relations=[relation(kind="COMPONENT_OF")])
        self.assertEqual(r["aggregate"]["total"],1)
        self.assertEqual(r["events"][0]["category"],"motorcycle")
        self.assertEqual(r["events"][0]["track_id"],2)
        self.assertEqual(r["events"][0]["evidence"]["anchor"],"raw_vehicle_bbox_bottom_center")

    def test_component_relation_does_not_create_parent_crossing(self):
        r=run({0:[observation(30,physical_episode_id="physical:1")],
               1:[observation(70,physical_episode_id="physical:1")]},
              relations=[relation(kind="COMPONENT_OF")])
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertEqual(r["report"]["offline_finalization"]["newly_created_accepted_events"],0)

    def test_cross_category_positive_duplicate_becomes_one_category_conflict(self):
        r=run(parallel(("car","truck")),relations=[relation()])
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertEqual(r["aggregate"]["pending"],1)
        self.assertEqual(r["aggregate"]["cancelled"],2)

    def test_negative_constraint_vetoes_positive_merge(self):
        r=run(parallel(),relations=[relation(),relation(kind="DIFFERENT_UNIT",verified=False)])
        self.assertEqual(r["aggregate"]["total"],2)
        self.assertTrue(any(a["status"]=="MERGE_BLOCKED" for a in r["finalization_audit"]))

    def test_transitive_negative_constraint_prevents_global_union(self):
        r=run(parallel(("car","car","car")),relations=[relation(1,2),relation(2,3),
                     relation(1,3,kind="DIFFERENT_UNIT",verified=False)])
        self.assertEqual(r["aggregate"]["total"],2)

    def test_opposite_direction_same_unit_is_not_same_passage(self):
        r=run(parallel(directions=[False,True]),relations=[relation()])
        self.assertEqual(r["aggregate"]["total"],2)

    def test_person_role_not_invented_by_counting(self):
        r=run({0:[observation(30,category="person",role="rider")],
               1:[observation(70,category="person",role="rider")]})
        self.assertEqual(r["aggregate"]["total"],0)
        r=run({0:[observation(30,category="person",role="pedestrian")],
               1:[observation(70,category="person",role="pedestrian")]})
        self.assertEqual(r["aggregate"]["pedestrian_total"],1)

    def test_no_synthetic_post_eof_timeout(self):
        r=run({0:20,1:23,2:26})
        self.assertEqual(r["aggregate"]["total"],0)
        self.assertEqual(r["report"]["post_eof_frames_generated"],0)

    def test_configuration_required_and_inputs_immutable(self):
        p=deepcopy(POLICY);sample=frames({0:30,1:70});before=deepcopy(sample)
        r=replay_frames(sample,GEOMETRY,source_identity=SOURCE,policy=p)
        self.assertEqual(sample,before);self.assertEqual(p,POLICY)
        self.assertEqual(r["report"]["version"],"b_v5_p0_eligibility_finalization_v1")
        p.pop("p0_counting")
        with self.assertRaises(ValueError):
            replay_frames(sample,GEOMETRY,source_identity=SOURCE,policy=p)


if __name__=="__main__":
    unittest.main()
