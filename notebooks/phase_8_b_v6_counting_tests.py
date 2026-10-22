"""Synthetic contracts for the new user policy, not measured video accuracy."""
from copy import deepcopy
import unittest

from phase_8_b_v3_counting_tests import GEOMETRY, SOURCE, observation, frames
from phase_8_b_v5_counting_tests import POLICY as BASE, parallel, relation
from phase_8_b_v6_counting import (BUSINESS_TAXONOMY, DISPLAY_PREFIXES, business_category,
    experimental_counting_policy, passage_display_id, replay_frames, _supported_candidate)


POLICY = {**deepcopy(BASE), "v6_counting": experimental_counting_policy(),
          "supported_categories": ["motorcycle", "car", "truck", "bus", "pedestrian"],
          "display_category_prefixes": DISPLAY_PREFIXES}


def run(samples, end=None, relations=None, policy=None):
    controls = deepcopy(POLICY if policy is None else policy)
    controls["episode_relations"] = [] if relations is None else relations
    return replay_frames(frames(samples, end=end), GEOMETRY, source_identity=SOURCE, policy=controls)


def ambiguous(a=1, b=2, support=None, kind="POSSIBLE_SCOPED_UNIT_OR_COMPONENT_AMBIGUITY"):
    proof=relation(a,b,verified=False,support=support)
    proof["candidate_kind"]=kind
    return proof


def evidence(track,frame):
    return {"verified":True,"claim_type":"USER_REVIEW","evidence_ref":"review:subtype:1",
            "video_sha256":SOURCE["video_sha256"],"track_id":track,"frame_index":frame}


class Bv6CountingContracts(unittest.TestCase):
    def test_same_category_ambiguous_pair_invalid_both_without_merge(self):
        result=run(parallel(),relations=[ambiguous()])
        self.assertEqual(result["aggregate"]["total"],0)
        self.assertEqual(result["aggregate"]["pending"],0)
        self.assertEqual(result["aggregate"]["invalid"],2)
        self.assertEqual({row["track_id"] for row in result["invalid_decisions"]},{1,2})
        self.assertTrue(all(row["count_delta"]==0 and not row["physical_episodes_merged"]
                            for row in result["invalid_decisions"]))
        self.assertTrue(all(row["source_ref"]["raw_bbox"] for row in result["invalid_decisions"]))
        self.assertEqual(sum(log["count_delta"]for log in result["passage_log"]),0)

    def test_cross_category_ambiguity_invalid_both(self):
        result=run(parallel(("car","truck")),relations=[ambiguous(kind="POSSIBLE_CROSS_CATEGORY_UNIT_OR_COMPONENT")])
        self.assertEqual(result["aggregate"]["invalid"],2)
        self.assertEqual(result["aggregate"]["pending"],0)

    def test_opposite_valid_passages_are_not_duplicates(self):
        result=run(parallel(directions=[False,True]),relations=[ambiguous()])
        self.assertEqual(result["aggregate"]["total"],2)
        self.assertEqual(result["aggregate"]["invalid"],0)
        self.assertEqual({row["direction"]for row in result["events"]},{"A_TO_B","B_TO_A"})

    def test_genuine_return_same_id_has_two_passages(self):
        result=run({0:30,1:70,2:30})
        self.assertEqual(result["aggregate"]["total"],2)
        self.assertEqual(result["aggregate"]["invalid"],0)

    def test_turn_before_crossing_does_not_create_count(self):
        result=run({0:20,1:23,2:26,3:20,4:10},100)
        self.assertEqual(result["aggregate"]["total"],0)

    def test_nearby_without_scoped_conflict_remain_independent(self):
        result=run(parallel())
        self.assertEqual(result["aggregate"]["total"],2)
        self.assertEqual(result["aggregate"]["invalid"],0)

    def test_verified_duplicate_is_one_passage_plus_zero_not_two_invalid(self):
        result=run(parallel(),relations=[relation()])
        self.assertEqual(result["aggregate"]["total"],1)
        self.assertEqual(result["aggregate"]["invalid"],0)

    def test_future_only_ambiguity_never_invalidates_old_passage(self):
        result=run(parallel(),end=20,relations=[ambiguous(support=[20])])
        self.assertEqual(result["aggregate"]["total"],2)
        self.assertEqual(result["aggregate"]["invalid"],0)

    def test_unrelated_source_reference_does_not_extend_ambiguity_scope(self):
        candidate={"evidence":{"source_refs":[
            {"track_id":1,"physical_episode_id":"physical:1","frame_index":0},
            {"track_id":1,"physical_episode_id":"physical:1","frame_index":1}],
            "competitor_context":{"track_id":88,"physical_episode_id":"foreign","frame_index":50}}}
        self.assertFalse(_supported_candidate(candidate,ambiguous(support=[20]),"first"))

    def test_foreign_episode_does_not_invalidate(self):
        proof=ambiguous();proof["first_physical_episode_id"]="foreign";proof["second_physical_episode_id"]="foreign2"
        self.assertEqual(run(parallel(),relations=[proof])["aggregate"]["total"],2)

    def test_invalid_does_not_blacklist_a_later_passage_same_raw_id(self):
        samples={0:[observation(30,physical_episode_id="physical:1")],
            1:[observation(70,physical_episode_id="physical:1")],
            2:[observation(70,physical_episode_id="physical:new",episode_id="new",identity_episode_boundary=True)],
            3:[observation(30,physical_episode_id="physical:new",episode_id="new")]}
        result=run(samples,relations=[ambiguous(support=[1])])
        self.assertEqual(result["aggregate"]["invalid"],1)
        self.assertEqual(result["aggregate"]["total"],1)
        self.assertEqual(result["events"][0]["direction"],"B_TO_A")

    def test_role_unknown_remains_pending_not_invalid_or_pedestrian(self):
        result=run({0:[observation(30,category="person",role="unknown_person")],
                    1:[observation(70,category="person",role="unknown_person")]})
        self.assertEqual(result["aggregate"]["invalid"],0)
        self.assertEqual(result["aggregate"]["pending"],1)
        self.assertEqual(result["aggregate"]["pedestrian_total"],0)

    def test_category_conflict_without_unit_ambiguity_stays_pending(self):
        result=run({0:[observation(30,category="car")],1:[observation(47,category="car")],
                    2:[observation(52,category="truck")],3:[observation(70,category="truck")]})
        self.assertEqual(result["aggregate"]["invalid"],0)
        self.assertEqual(result["aggregate"]["pending"],1)

    def test_raw_id_change_in_origin_does_not_make_two_timeouts(self):
        samples={0:[observation(20,track=1,physical_episode_id="physical:1")],
            1:[observation(23,track=1,physical_episode_id="physical:1")],
            2:[observation(26,track=1,physical_episode_id="physical:1")],
            3:[observation(26,track=2,physical_episode_id="physical:2")],
            4:[observation(29,track=2,physical_episode_id="physical:2")],
            5:[observation(32,track=2,physical_episode_id="physical:2")]}
        proof=ambiguous(support=[2,3],kind="UNVERIFIED_ORIGIN_HANDOFF")
        result=run(samples,100,relations=[proof])
        self.assertEqual(result["aggregate"]["total"],0)
        self.assertEqual(result["aggregate"]["invalid"],2)
        diagnostics=result["open_passage_diagnostics"]
        self.assertTrue(all(row["disposition"]=="INVALID_AMBIGUOUS_UNIT"
                            and not row["timeout_eligible"] for row in diagnostics))
        self.assertEqual(result["report"]["open_passage_diagnostic_counts"],
                         {"INVALID_AMBIGUOUS_UNIT":2})

    def test_unknown_person_context_suspends_and_invalidates_old_vehicle_timeout(self):
        samples={0:20,1:23,2:26,**{f:[observation(26,category="person",role="unknown_person",
            unit="person-track:1",identity_episode_boundary=False)]for f in range(3,100)}}
        result=run(samples)
        self.assertEqual(result["aggregate"]["total"],0)
        self.assertTrue(any("RAW_CONTEXT_CHANGED_WITHOUT_PHYSICAL_CONTINUITY_PROOF"in row["reasons"]
                            for row in result["invalid_decisions"]))

    def test_appearing_away_from_line_never_arms_timeout(self):
        result=run({0:75,1:80,2:85},100)
        self.assertEqual(result["aggregate"]["total"],0)

    def test_completed_passage_new_departing_id_stays_one(self):
        result=run({0:30,1:70,2:[observation(75,track=2)],3:[observation(80,track=2)],
                    4:[observation(85,track=2)]},100)
        self.assertEqual(result["aggregate"]["total"],1)

    def test_timeout_still_exactly_sixty_source_frames(self):
        self.assertEqual(run({0:20,1:23,2:26},61)["aggregate"]["total"],0)
        result=run({0:20,1:23,2:26},62)
        self.assertEqual(result["events"][0]["activation_frame"],62)
        self.assertFalse(result["events"][0]["evidence"]["measured_crossing"])

    def test_bus_raw_label_runs_end_to_end_with_B_prefix(self):
        result=run({0:[observation(30,category="bus")],1:[observation(70,category="bus")]})
        self.assertEqual(result["aggregate"]["by_category"],{"bus":1})
        self.assertEqual(result["events"][0]["display_id"],"B2000")
        self.assertTrue(result["events"][0]["event_id"].startswith("b_v6_"))

    def test_bus_positive_duplicate_finalizer_preserves_B_prefix(self):
        result=run(parallel(("bus","bus")),relations=[relation()])
        self.assertEqual(result["aggregate"]["total"],1)
        self.assertEqual(result["events"][0]["display_id"],"B2000")

    def test_prefix_direction_parity_and_no_leading_zero(self):
        self.assertEqual(passage_display_id("bus","B_TO_A",1),"B1000")
        self.assertEqual(passage_display_id("bus","A_TO_B",1001),"B4000")

    def test_business_mapping_only_when_source_subtype_positive(self):
        for subtype,wanted in BUSINESS_TAXONOMY.items():
            samples={f:[observation(y,category="truck",vehicle_subtype=subtype,
                vehicle_subtype_evidence=evidence(1,f))]for f,y in enumerate((30,70))}
            with self.subTest(subtype=subtype):
                result=run(samples)
                self.assertEqual(result["events"][0]["category"],wanted)
                self.assertEqual(result["events"][0]["evidence"]["source_refs"][0]["class_name"],"truck")
                self.assertEqual(len(result["business_taxonomy_audit"]),2)

    def test_subtype_unknown_not_inferred_from_raw_vehicle_label(self):
        self.assertEqual(business_category("truck"),"truck")
        self.assertEqual(business_category("car"),"car")
        with self.assertRaises(ValueError):business_category("truck",vehicle_subtype="minivan")

    def test_foreign_subtype_review_rejected(self):
        proof=evidence(1,0);proof["video_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"another source"):
            run({0:[observation(30,category="truck",vehicle_subtype="cargo_van",vehicle_subtype_evidence=proof)]})

    def test_person_cannot_be_relabelled_from_vehicle_subtype(self):
        with self.assertRaises(ValueError):
            business_category("person",vehicle_subtype="bus",subtype_evidence=evidence(1,0))

    def test_policy_and_source_inputs_remain_unchanged(self):
        samples=frames(parallel());p=deepcopy(POLICY);p["episode_relations"]=[ambiguous()]
        before,pbefore=deepcopy(samples),deepcopy(p)
        replay_frames(samples,GEOMETRY,source_identity=SOURCE,policy=p)
        self.assertEqual(samples,before);self.assertEqual(p,pbefore)

    def test_bus_configuration_cannot_be_implicit(self):
        p=deepcopy(POLICY);p["display_category_prefixes"].pop("bus")
        with self.assertRaises(ValueError):run({0:30,1:70},policy=p)


if __name__=="__main__":unittest.main()
